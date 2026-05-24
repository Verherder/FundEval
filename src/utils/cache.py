# -*- coding: UTF-8 -*-
"""Simple in-memory cache utility with TTL support."""

import time
import threading


class SimpleCache:
    """Thread-safe in-memory key-value store with optional TTL."""

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key, default=None):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return default
            expires, value = entry
            if expires and time.time() > expires:
                del self._data[key]
                return default
            return value

    def set(self, key, value, ttl=None):
        expires = time.time() + ttl if ttl else None
        with self._lock:
            self._data[key] = (expires, value)

    def delete(self, key):
        with self._lock:
            self._data.pop(key, None)

    def clear(self):
        with self._lock:
            self._data.clear()

    def __contains__(self, key):
        return self.get(key) is not None
