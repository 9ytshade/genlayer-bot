from collections import deque
from datetime import datetime, timezone
import asyncio
import json
import os
from typing import Any, Deque

from redis.asyncio import Redis


def make_log_item(level: str, event: str, message: str, meta: dict[str, Any] | None = None):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "event": event,
        "message": message,
        "meta": meta or {},
    }


class MemoryLogsStore:
    def __init__(self, max_items: int = 300):
        self._items: Deque[dict[str, Any]] = deque(maxlen=max_items)
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def append(self, level: str, event: str, message: str, meta: dict[str, Any] | None = None):
        log_item = make_log_item(level, event, message, meta)

        async with self._lock:
            self._items.append(log_item)
            subscribers = list(self._subscribers)

        for queue in subscribers:
            queue.put_nowait(log_item)

    async def recent(self, limit: int = 80):
        async with self._lock:
            return list(self._items)[-limit:]

    async def subscribe(self):
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)


class RedisLogsStore:
    def __init__(self, redis_url: str, max_items: int = 300):
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._max_items = max_items
        self._key = "genlayer:logs"
        self._channel = "genlayer:logs"
        self._tasks: dict[asyncio.Queue, asyncio.Task] = {}

    async def append(self, level: str, event: str, message: str, meta: dict[str, Any] | None = None):
        log_item = make_log_item(level, event, message, meta)
        payload = json.dumps(log_item)
        await self._redis.lpush(self._key, payload)
        await self._redis.ltrim(self._key, 0, self._max_items - 1)
        await self._redis.publish(self._channel, payload)

    async def recent(self, limit: int = 80):
        payloads = await self._redis.lrange(self._key, 0, max(limit - 1, 0))
        return [json.loads(payload) for payload in reversed(payloads)]

    async def subscribe(self):
        queue: asyncio.Queue = asyncio.Queue()
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._channel)

        async def listen():
            try:
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        queue.put_nowait(json.loads(message["data"]))
            finally:
                await pubsub.unsubscribe(self._channel)
                await pubsub.close()

        self._tasks[queue] = asyncio.create_task(listen())
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        task = self._tasks.pop(queue, None)
        if task:
            task.cancel()


redis_url = os.getenv("REDIS_URL")
logs_store = RedisLogsStore(redis_url) if redis_url else MemoryLogsStore()
