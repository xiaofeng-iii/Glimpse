"""
Capture - pynput 与 mss 的封装，包含滑动窗口截图限流
注入PathManager
"""
from collections import deque
import time
import traceback
from typing import Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from threading import Lock

import mss
from PIL import Image

if TYPE_CHECKING:
    from config.path_manager import PathManager


@dataclass
class CaptureResult:
    image_path: str
    width: int
    height: int
    timestamp: float
    app_name: Optional[str] = None


class CaptureManager:
    """截图管理器 - 注入PathManager，负责截图本身，防重复逻辑由上层 ClusterBuffer 处理"""

    def __init__(self, path_manager: "PathManager"):
        self._path_manager = path_manager
        self._last_capture_time = 0
        self._capture_limit_window_seconds = 5.0
        self._max_captures_per_window = 10
        self._capture_timestamps = deque()
        self._next_capture_reservation_id = 0
        self._settings_lock = Lock()

    def _save_screenshot(self, screenshot) -> CaptureResult:
        img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

        filename = f"screenshot_{int(time.time() * 1000)}.png"
        image_path = self._path_manager.get_screenshot_path(filename)

        img.save(str(image_path), "PNG")

        return CaptureResult(
            image_path=str(image_path),
            width=screenshot.width,
            height=screenshot.height,
            timestamp=time.time(),
        )

    def capture_fullscreen(self, delay: float = 0, force_bypass_debounce: bool = False) -> Optional[CaptureResult]:
        if delay > 0:
            time.sleep(delay)

        reservation = self._try_reserve_capture_slot()
        if reservation is None:
            return None

        try:
            with mss.mss() as sct:
                screenshot = sct.grab(sct.monitors[1])
                result = self._save_screenshot(screenshot)
            return result
        except Exception as e:
            self._release_capture_slot(reservation)
            print(f"Capture fullscreen error: {e}")
            traceback.print_exc()
            return None

    def capture_region(self, region: Tuple[int, int, int, int]) -> Optional[CaptureResult]:
        x, y, w, h = region
        if w <= 0 or h <= 0:
            return None

        reservation = self._try_reserve_capture_slot()
        if reservation is None:
            return None

        try:
            monitor = {"top": y, "left": x, "width": w, "height": h}
            with mss.mss() as sct:
                screenshot = sct.grab(monitor)
                result = self._save_screenshot(screenshot)
            return result
        except Exception as e:
            self._release_capture_slot(reservation)
            print(f"Capture region error: {e}")
            traceback.print_exc()
            return None

    def _prune_capture_timestamps_locked(self, now: float):
        cutoff = now - self._capture_limit_window_seconds
        while self._capture_timestamps and self._capture_timestamps[0][0] <= cutoff:
            self._capture_timestamps.popleft()

    def _try_reserve_capture_slot(self) -> Optional[Tuple[float, int]]:
        with self._settings_lock:
            now = time.time()
            self._prune_capture_timestamps_locked(now)
            if len(self._capture_timestamps) >= self._max_captures_per_window:
                return None

            reservation = (now, self._next_capture_reservation_id)
            self._next_capture_reservation_id += 1
            self._capture_timestamps.append(reservation)
            self._last_capture_time = now
            return reservation

    def _release_capture_slot(self, reservation: Tuple[float, int]):
        with self._settings_lock:
            try:
                self._capture_timestamps.remove(reservation)
            except ValueError:
                pass

    def set_capture_limit_window_seconds(self, seconds: float) -> bool:
        try:
            value = float(seconds)
            if value <= 0:
                return False
            with self._settings_lock:
                self._capture_limit_window_seconds = value
                self._prune_capture_timestamps_locked(time.time())
            return True
        except (ValueError, TypeError):
            return False

    def set_debounce_interval(self, interval: float) -> bool:
        return self.set_capture_limit_window_seconds(interval)

    def set_max_captures_per_window(self, max_captures: int) -> bool:
        try:
            value = int(max_captures)
            if value <= 0:
                return False
            with self._settings_lock:
                self._max_captures_per_window = value
            return True
        except (ValueError, TypeError):
            return False

    def update_settings(self, settings: dict) -> bool:
        with self._settings_lock:
            old_window = self._capture_limit_window_seconds
            old_max = self._max_captures_per_window

            new_window = old_window
            new_max = old_max

            try:
                if "capture_limit_window_seconds" in settings:
                    value = float(settings["capture_limit_window_seconds"])
                    if value <= 0:
                        raise ValueError(f"Invalid capture_limit_window_seconds: {value}")
                    new_window = value
                elif "debounce_interval" in settings:
                    value = float(settings["debounce_interval"])
                    if value <= 0:
                        raise ValueError(f"Invalid debounce_interval: {value}")
                    new_window = value

                if "max_captures_per_window" in settings:
                    value = int(settings["max_captures_per_window"])
                    if value <= 0:
                        raise ValueError(f"Invalid max_captures_per_window: {value}")
                    new_max = value

                self._capture_limit_window_seconds = new_window
                self._max_captures_per_window = new_max
                self._prune_capture_timestamps_locked(time.time())
                return True
            except (ValueError, TypeError):
                self._capture_limit_window_seconds = old_window
                self._max_captures_per_window = old_max
                return False

    def get_settings(self) -> dict:
        with self._settings_lock:
            return {
                "capture_limit_window_seconds": self._capture_limit_window_seconds,
                "max_captures_per_window": self._max_captures_per_window
            }

    def close(self):
        return None


# 全局实例占位 — 实际实例由 DIContainer 通过初始化路径管理器后注入
# 参见 container.py:initialize_defaults()
capture_manager = None
