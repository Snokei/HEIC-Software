"""
viewer/preloader.py
Background image preloader.
Loads surrounding images around current_index into the cache
so navigation feels instant.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional

from .cache import ImageCache
from .image_loader import LoadResult, load_image

logger = logging.getLogger(__name__)

_STOP = object()

ReadyCallback = Callable[[str, LoadResult], None]


class Preloader:
    """
    Preloads images surrounding the current position into *cache*.

    Priority order: current → next → prev → next+1 → prev-1 → ...

    Usage::
        pl = Preloader(cache)
        pl.start(on_ready=my_callback)  # callback(path, LoadResult)
        pl.update(files, current_index)
        pl.stop()
    """

    def __init__(self, cache: ImageCache) -> None:
        self._cache = cache
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._on_ready: Optional[ReadyCallback] = None
        self._running = False

    def start(self, on_ready: Optional[ReadyCallback] = None) -> None:
        if self._running:
            return
        self._on_ready = on_ready
        self._running = True
        self._thread = threading.Thread(
            target=self._worker,
            name="preload-worker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._queue.put(_STOP)

    def update(
        self,
        files: list[str],
        current_index: int,
        clear_cache: bool = False,
    ) -> None:
        """
        Rebuild the preload queue around *current_index*.
        Call this whenever the displayed image changes.
        """
        # Drain the existing queue
        with self._queue.mutex:
            self._queue.queue.clear()

        if clear_cache:
            self._cache.clear()

        if not files:
            return

        # Build priority-ordered list: curr, +1, -1, +2, -2, ...
        ordered: list[str] = []
        seen: set[str] = set()
        n = len(files)
        left = current_index - 1
        right = current_index + 1

        # Current first
        path = files[current_index]
        ordered.append(path)
        seen.add(path)

        while left >= 0 or right < n:
            if right < n:
                p = files[right]
                if p not in seen:
                    ordered.append(p)
                    seen.add(p)
                right += 1
            if left >= 0:
                p = files[left]
                if p not in seen:
                    ordered.append(p)
                    seen.add(p)
                left -= 1

        for path in ordered:
            if path not in self._cache:
                self._queue.put(path)

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                break
            path: str = item
            if path not in self._cache:
                try:
                    result = load_image(path)
                    if result.ok and result.image is not None:
                        self._cache.put(path, result.image)
                        if self._on_ready:
                            self._on_ready(path, result)
                except Exception as exc:
                    logger.debug("Preload error (%s): %s", path, exc)
            self._queue.task_done()
