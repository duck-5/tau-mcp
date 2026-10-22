"""
In-memory caching and session state management for tau_mcp.
Provides an in-memory TTL CacheManager to eliminate duplicate API calls
during LLM reasoning turns without polluting the local filesystem.
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tau_mcp.storage")

class CacheManager:
    """
    In-memory TTL cache for TAU API and catalog responses.
    Keeps responses cached in RAM during conversations without disk pollution.
    """
    _storage: Dict[str, Dict[str, Any]] = {}

    def __init__(self, profile: Optional[str] = None):
        self.profile = profile or "default"
        if self.profile not in CacheManager._storage:
            CacheManager._storage[self.profile] = {}
        self._cache = CacheManager._storage[self.profile]

    def get(self, key: str, max_age: Optional[int] = None) -> Optional[Any]:
        """
        Retrieves cached value if key exists and age does not exceed max_age (in seconds).
        Returns None if expired or not found.
        """
        entry = self._cache.get(key)
        if not entry:
            return None

        entry_time = entry.get("timestamp", 0)
        age = time.time() - entry_time

        if max_age is not None and age >= max_age:
            logger.debug(f"Cache expired for '{key}' (age: {age:.0f}s, max: {max_age}s)")
            return None

        logger.debug(f"Cache hit for '{key}' (age: {age:.0f}s)")
        return entry.get("data")

    def set(self, key: str, data: Any) -> None:
        """Stores data in the in-memory cache with the current timestamp."""
        self._cache[key] = {
            "timestamp": time.time(),
            "data": data
        }

    def delete(self, key: str) -> bool:
        """Deletes a specific key from the cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self, prefix: Optional[str] = None) -> int:
        """Clears all cached entries or entries matching prefix."""
        if not prefix:
            count = len(self._cache)
            self._cache.clear()
            return count

        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._cache[k]
        return len(keys_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics on currently cached entries."""
        now = time.time()
        entries_info = {}
        for k, v in self._cache.items():
            age = now - v.get("timestamp", 0)
            data = v.get("data")
            count = len(data) if isinstance(data, (list, dict)) else 1
            entries_info[k] = {
                "age_seconds": round(age),
                "items_count": count
            }

        return {
            "profile": self.profile,
            "storage_type": "in-memory",
            "total_entries": len(self._cache),
            "entries": entries_info
        }

class DataStore:
    """Lightweight in-memory data store for temporary session state."""
    _store: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, val: Any) -> None:
        self._store[key] = val

    def list_keys(self) -> List[str]:
        return list(self._store.keys())
