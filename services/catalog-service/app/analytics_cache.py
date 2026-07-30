from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from time import monotonic
from typing import Any, Hashable


class BoundedTTLCache:
    """Small process-local cache for bounded admin aggregates.

    It is deliberately simple: application writes explicitly invalidate it,
    entries expire quickly, and callers receive copies so response mutation
    cannot corrupt cached values. Multi-worker production deployments should
    use the same API with a shared Redis-backed implementation.
    """

    def __init__(self, *, ttl_seconds: float = 30.0, max_entries: int = 128) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._values: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = RLock()

    def get(self, key: Hashable) -> Any | None:
        now = monotonic()
        with self._lock:
            item = self._values.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            self._values.move_to_end(key)
            return deepcopy(value)

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._values[key] = (monotonic() + self.ttl_seconds, deepcopy(value))
            self._values.move_to_end(key)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


admin_analytics_cache = BoundedTTLCache()


def invalidate_admin_analytics() -> None:
    admin_analytics_cache.clear()
