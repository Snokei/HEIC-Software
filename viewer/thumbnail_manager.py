"""
viewer/thumbnail_manager.py
Async thumbnail generation pipeline.
Uses a thread pool of 2 workers so HEIC decodes don't block each other.
Results are delivered via a callback on the calling thread via a polling loop.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional

from PIL import Image

from .image_loader import load_image

logger = logging.getLogger(__name__)

# Sentinel to shut down workers
_STOP = object()

ThumbCallback = Callable[[int, Image.Image], None]


class ThumbnailManager:
    """
    Generates thumbnails in background threads.

    Usage::
        mgr = ThumbnailManager(size=80, num_workers=2)
        mgr.start(callback=my_callback)   # callback(idx, pil_image)
        mgr.enqueue(0, "/path/a.heic")
        # ... poll via mgr.poll() from main thread (called by Tk after)
        mgr.stop()
    """

    def __init__(self, size: int = 80, num_workers: int = 2) -> None:
        self._size = size
        self._num_workers = num_workers
        self._in_queue: queue.Queue = queue.Queue()
        self._out_queue: queue.Queue = queue.Queue()
        self._workers: list[threading.Thread] = []
        self._callback: Optional[ThumbCallback] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, callback: ThumbCallback) -> None:
        if self._running:
            return
        self._callback = callback
        self._running = True
        for i in range(self._num_workers):
            t = threading.Thread(
                target=self._worker,
                name=f"thumb-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for _ in self._workers:
            self._in_queue.put(_STOP)
        self._workers.clear()

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def enqueue(self, idx: int, path: str) -> None:
        self._in_queue.put((idx, path))

    def clear_queue(self) -> None:
        """Drain the input queue (e.g., when a new folder is opened)."""
        with self._in_queue.mutex:
            self._in_queue.queue.clear()

    # ------------------------------------------------------------------
    # Main-thread poll — call this from a Tk .after() loop
    # ------------------------------------------------------------------

    def poll(self, max_per_call: int = 5) -> None:
        """Deliver pending thumb results via callback (call from main thread)."""
        if not self._callback:
            return
        for _ in range(max_per_call):
            try:
                idx, img = self._out_queue.get_nowait()
                self._callback(idx, img)
            except queue.Empty:
                break

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _worker(self) -> None:
        size = (self._size, self._size)
        while True:
            item = self._in_queue.get()
            if item is _STOP:
                break
            idx, path = item
            try:
                result = load_image(path)
                if result.ok:
                    img = result.image
                    # Convert to RGB for reliable thumbnail
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    img.thumbnail(size, Image.Resampling.LANCZOS)
                    self._out_queue.put((idx, img))
                else:
                    logger.debug("Thumb failed for %s: %s", path, result.error)
            except Exception as exc:
                logger.debug("Thumb worker error (%s): %s", path, exc)
            finally:
                self._in_queue.task_done()
