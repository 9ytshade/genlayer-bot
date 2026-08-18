from collections import defaultdict, deque
from contextvars import ContextVar, Token
from datetime import datetime, timezone
import asyncio
import hashlib
import json
import os
import re
from typing import Any, Deque

from redis.asyncio import Redis


DEFAULT_MAX_ITEMS = 300
MIN_MAX_ITEMS = 50
MAX_MAX_ITEMS = 1000
SAFE_META_KEYS = {
    "action",
    "appealable",
    "capabilitycode",
    "contractname",
    "contractnames",
    "contracttype",
    "errorcount",
    "executionstatus",
    "final",
    "gaslimit",
    "leaderonly",
    "method",
    "network",
    "numrounds",
    "sourcecount",
    "status",
    "terminal",
    "validatorcount",
    "verdict",
    "votecount",
    "warningcount",
    "workflowtype",
    "zeroroundnomajority",
}
_log_wallet_address: ContextVar[str | None] = ContextVar(
    "log_wallet_address",
    default=None,
)
URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
ADDRESS_PATTERN = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
HASH_PATTERN = re.compile(r"\b0x[a-fA-F0-9]{64}\b")


def _max_items_from_environment() -> int:
    try:
        configured = int(os.getenv("ACTIVITY_LOG_MAX_ITEMS", str(DEFAULT_MAX_ITEMS)))
    except ValueError:
        configured = DEFAULT_MAX_ITEMS
    return min(max(configured, MIN_MAX_ITEMS), MAX_MAX_ITEMS)


def set_log_wallet_address(wallet_address: str | None) -> Token:
    return _log_wallet_address.set(wallet_address)


def reset_log_wallet_address(token: Token) -> None:
    _log_wallet_address.reset(token)


def _wallet_scope(wallet_address: str | None) -> str:
    normalized = str(wallet_address or "system").strip().lower()
    if not normalized:
        normalized = "system"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _safe_string(value: Any, max_length: int = 160) -> str:
    sanitized = " ".join(str(value).split())
    sanitized = URL_PATTERN.sub("[redacted]", sanitized)
    sanitized = HASH_PATTERN.sub("[redacted]", sanitized)
    sanitized = ADDRESS_PATTERN.sub("[redacted]", sanitized)
    return sanitized[:max_length]


def _enqueue(queue: asyncio.Queue, item: dict[str, Any]) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(item)


def sanitize_log_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for raw_key, value in (meta or {}).items():
        key = str(raw_key)
        normalized_key = "".join(character for character in key.lower() if character.isalnum())
        if normalized_key in {"errors", "warnings"} and isinstance(value, (list, tuple, set)):
            sanitized[f"{normalized_key[:-1]}Count"] = len(value)
            continue
        if normalized_key not in SAFE_META_KEYS:
            continue
        if isinstance(value, bool) or value is None:
            sanitized[key] = value
        elif isinstance(value, (int, float)):
            sanitized[key] = value
        elif isinstance(value, str):
            sanitized[key] = _safe_string(value)
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [_safe_string(item, 80) for item in value[:10]]
    return sanitized


def make_log_item(
    level: str,
    event: str,
    message: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": _safe_string(level, 16).upper(),
        "event": _safe_string(event, 80),
        "message": _safe_string(message, 240),
        "meta": sanitize_log_meta(meta),
    }


class MemoryLogsStore:
    def __init__(self, max_items: int = DEFAULT_MAX_ITEMS):
        self._max_items = max_items
        self._items: dict[str, Deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self._max_items)
        )
        self._subscribers: dict[asyncio.Queue, str] = {}
        self._lock = asyncio.Lock()

    async def append(
        self,
        level: str,
        event: str,
        message: str,
        meta: dict[str, Any] | None = None,
        *,
        wallet_address: str | None = None,
    ) -> None:
        scope = _wallet_scope(wallet_address or _log_wallet_address.get())
        log_item = make_log_item(level, event, message, meta)

        async with self._lock:
            self._items[scope].append(log_item)
            subscribers = [
                queue
                for queue, subscriber_scope in self._subscribers.items()
                if subscriber_scope == scope
            ]

        for queue in subscribers:
            _enqueue(queue, log_item)

    async def recent(self, wallet_address: str, limit: int = 80) -> list[dict[str, Any]]:
        scope = _wallet_scope(wallet_address)
        async with self._lock:
            return list(self._items.get(scope, ()))[-limit:]

    async def subscribe(self, wallet_address: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[queue] = _wallet_scope(wallet_address)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.pop(queue, None)


class RedisLogsStore:
    def __init__(self, redis_url: str, max_items: int = DEFAULT_MAX_ITEMS):
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._max_items = max_items
        self._prefix = "genlayer:logs:v2"
        self._tasks: dict[asyncio.Queue, asyncio.Task] = {}

    def _key(self, scope: str) -> str:
        return f"{self._prefix}:{scope}:items"

    def _channel(self, scope: str) -> str:
        return f"{self._prefix}:{scope}:stream"

    async def append(
        self,
        level: str,
        event: str,
        message: str,
        meta: dict[str, Any] | None = None,
        *,
        wallet_address: str | None = None,
    ) -> None:
        scope = _wallet_scope(wallet_address or _log_wallet_address.get())
        log_item = make_log_item(level, event, message, meta)
        payload = json.dumps(log_item, separators=(",", ":"))
        key = self._key(scope)
        await self._redis.lpush(key, payload)
        await self._redis.ltrim(key, 0, self._max_items - 1)
        await self._redis.publish(self._channel(scope), payload)

    async def recent(self, wallet_address: str, limit: int = 80) -> list[dict[str, Any]]:
        scope = _wallet_scope(wallet_address)
        payloads = await self._redis.lrange(self._key(scope), 0, max(limit - 1, 0))
        return [json.loads(payload) for payload in reversed(payloads)]

    async def subscribe(self, wallet_address: str) -> asyncio.Queue:
        scope = _wallet_scope(wallet_address)
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._channel(scope))

        async def listen() -> None:
            try:
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        _enqueue(queue, json.loads(message["data"]))
            finally:
                await pubsub.unsubscribe(self._channel(scope))
                await pubsub.close()

        self._tasks[queue] = asyncio.create_task(listen())
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        task = self._tasks.pop(queue, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


max_items = _max_items_from_environment()
redis_url = os.getenv("REDIS_URL")
logs_store = RedisLogsStore(redis_url, max_items) if redis_url else MemoryLogsStore(max_items)
