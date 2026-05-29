"""
Cluster Buffer - asyncio-backed screenshot collection buffer.
"""
import asyncio
import threading
from concurrent.futures import Future
from typing import List, Optional

from async_runtime import get_async_runtime
from event_bus import EventSignal


class ClusterBuffer:
    """Collects related screenshots and flushes them after a timeout."""

    def __init__(self, settings_manager):
        self._settings_manager = settings_manager
        self._images: List[str] = []
        self._lock = threading.RLock()
        self._remaining_seconds = 0
        self._generation = 0
        self._timer_future: Optional[Future] = None

        self.flushed = EventSignal("cluster_flushed")
        self.discarded = EventSignal("cluster_discarded")
        self.state_changed = EventSignal("cluster_state_changed")
        self.countdown_changed = EventSignal("cluster_countdown_changed")

    def is_collecting(self) -> bool:
        with self._lock:
            return bool(self._images)

    def add_image(self, image_path: str) -> bool:
        """Add an image and reset the collection timer."""
        with self._lock:
            max_images = self._get_max_images()
            timeout = self._get_timeout_seconds()
            first_image = not self._images

            self._images.append(image_path)
            self._generation += 1
            generation = self._generation
            self._remaining_seconds = timeout
            count = len(self._images)
            should_flush = count >= max_images

            self._restart_timer_locked(generation, timeout)

        self.state_changed.emit("COLLECTING", count, max_images)
        self.countdown_changed.emit(timeout)

        if should_flush:
            self.flush()

        return first_image

    def flush(self):
        """Submit the current cluster."""
        with self._lock:
            if not self._images:
                return
            images = self._images.copy()
            max_images = self._clear_locked()

        self.state_changed.emit("IDLE", 0, max_images)
        self.flushed.emit(images)

    def discard(self):
        """Discard the current cluster."""
        with self._lock:
            if not self._images:
                return
            max_images = self._clear_locked()

        self.state_changed.emit("IDLE", 0, max_images)
        self.discarded.emit()

    def get_images(self) -> List[str]:
        with self._lock:
            return self._images.copy()

    def get_count(self) -> int:
        with self._lock:
            return len(self._images)

    def get_remaining_seconds(self) -> int:
        with self._lock:
            return self._remaining_seconds

    def has_active_timer(self) -> bool:
        with self._lock:
            return self._timer_future is not None and not self._timer_future.done()

    def close(self) -> None:
        with self._lock:
            self._cancel_timer_locked()
            self._images.clear()
            self._remaining_seconds = 0
            self._generation += 1

    def _restart_timer_locked(self, generation: int, timeout: int) -> None:
        self._cancel_timer_locked()
        self._timer_future = get_async_runtime().create_task(
            self._run_timer(generation, timeout)
        )

    def _cancel_timer_locked(self) -> None:
        if self._timer_future is not None:
            self._timer_future.cancel()
            self._timer_future = None

    async def _run_timer(self, generation: int, timeout: int):
        remaining = max(timeout, 0)
        try:
            if remaining == 0:
                self.countdown_changed.emit(0)
                self._handle_timeout(generation)
                return

            while remaining > 0:
                await asyncio.sleep(1)
                remaining -= 1

                with self._lock:
                    if generation != self._generation or not self._images:
                        return
                    self._remaining_seconds = remaining

                self.countdown_changed.emit(remaining)

            self._handle_timeout(generation)
        except asyncio.CancelledError:
            return
        finally:
            with self._lock:
                if generation == self._generation and (
                    self._timer_future is None or self._timer_future.done()
                ):
                    self._timer_future = None

    def _handle_timeout(self, generation: int) -> None:
        with self._lock:
            if generation != self._generation or not self._images:
                return
            auto_submit = self._settings_manager.get("cluster.cluster_auto_submit", True)

        if auto_submit:
            self.flush()

    def _clear_locked(self) -> int:
        self._cancel_timer_locked()
        self._images.clear()
        self._remaining_seconds = 0
        self._generation += 1
        return self._get_max_images()

    def _get_max_images(self) -> int:
        return int(self._settings_manager.get("cluster.cluster_max_images", 5))

    def _get_timeout_seconds(self) -> int:
        return max(int(self._settings_manager.get("cluster.cluster_timeout", 5)), 0)
