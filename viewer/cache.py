"""
viewer/cache.py
Memory-aware LRU image cache for HEIC Photo Viewer.
Evicts oldest entries when total estimated RAM exceeds the configured limit.
Thread-safe via threading.Lock.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

# Rough bytes-per-pixel estimate per mode
_BPP = {
    "1": 0.125, "L": 1, "P": 1, "RGB": 3, "RGBA": 4,
    "CMYK": 4, "YCbCr": 3, "I": 4, "F": 4, "LA": 2,
}


def _image_bytes(img: Image.Image) -> int:
    """Estimate uncompressed RAM usage of a PIL image."""
    w, h = img.size
    bpp = _BPP.get(img.mode, 3)
    return int(w * h * bpp)


class ImageCache:
    """
    LRU cache that evicts entries when total RAM exceeds *max_bytes*.

    Usage::
        cache = ImageCache(max_mb=400)
        cache.put("/path/img.heic", pil_image)
        img = cache.get("/path/img.heic")   # None if not cached
    """

    def __init__(self, max_mb: int = 400) -> None:
        self._max_bytes: int = max_mb * 1024 * 1024
        self._store: OrderedDict[str, tuple[Image.Image, int]] = OrderedDict()
        self._used_bytes: int = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, path: str) -> Optional[Image.Image]:
        """Return cached image or None. Moves entry to MRU position."""
        with self._lock:
            entry = self._store.get(path)
            if entry is None:
                return None
            self._store.move_to_end(path)
            return entry[0]

    def put(self, path: str, img: Image.Image) -> None:
        """Insert or refresh an entry, evicting LRU items if over budget."""
        size = _image_bytes(img)
        with self._lock:
            # If path already cached, remove old size first
            if path in self._store:
                _, old_size = self._store.pop(path)
                self._used_bytes -= old_size

            # Evict LRU entries until there's room
            while self._used_bytes + size > self._max_bytes and self._store:
                _key, (_img, _sz) = self._store.popitem(last=False)
                self._used_bytes -= _sz
                logger.debug("Cache evicted: %s (freed %d KB)", _key, _sz // 1024)

            self._store[path] = (img, size)
            self._used_bytes += size

    def __contains__(self, path: str) -> bool:
        with self._lock:
            return path in self._store

    def remove(self, path: str) -> None:
        """Explicitly remove an entry (e.g., after file deleted)."""
        with self._lock:
            entry = self._store.pop(path, None)
            if entry:
                self._used_bytes -= entry[1]

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._store.clear()
            self._used_bytes = 0

    @property
    def used_mb(self) -> float:
        with self._lock:
            return self._used_bytes / (1024 * 1024)

    @property
    def max_mb(self) -> int:
        return self._max_bytes // (1024 * 1024)

    def resize(self, max_mb: int) -> None:
        """Update the budget and evict if necessary."""
        with self._lock:
            self._max_bytes = max_mb * 1024 * 1024
            while self._used_bytes > self._max_bytes and self._store:
                _key, (_img, _sz) = self._store.popitem(last=False)
                self._used_bytes -= _sz
