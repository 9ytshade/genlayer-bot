from collections import deque
from datetime import datetime, timezone
import asyncio
from typing import Deque, Dict, Any, List


class LogsStore:
    def __init__(self, max_items: int = 300):
        self._items: Deque[Dict[str, Any]] = deque(maxlen=max_items)
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def append(self, level: str, event: str, message: str, meta: Dict[str, Any] | None = None):
        log_item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "event": event,
            "message": message,
            "meta": meta or {},
        }

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


logs_store = LogsStore()
