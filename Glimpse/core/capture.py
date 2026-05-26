"""
Capture - pynput 与 mss 的封装，包含集群防抖算法
注入PathManager
"""
import time
from typing import Optional, Callable, Tuple, TYPE_CHECKING
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
    """截图管理器 - 注入PathManager，包含集群防抖"""

    def __init__(self, path_manager: "PathManager"):
        self._path_manager = path_manager
        self._sct = mss.mss()
        self._last_capture_time = 0
        self._debounce_interval = 5.0
        self._cluster_threshold = 2.0
        self._last_region: Optional[Tuple[int, int, int, int]] = None
        self._capture_window_start = 0
        self._max_captures_per_window = 10
        self._fullscreen_debounce_time = 0
        self._region_debounce_time = 0
        self._fullscreen_count = 0
        self._region_count = 0
        self._settings_lock = Lock()

    def capture_fullscreen(self, delay: float = 0, force_bypass_debounce: bool = False) -> Optional[CaptureResult]:
        if delay > 0:
            time.sleep(delay)

        if not force_bypass_debounce and not self._check_debounce(is_fullscreen=True):
            return None

        if self._check_force_split():
            return None

        try:
            screenshot = self._sct.grab(self._sct.monitors[1])
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

            filename = f"screenshot_{int(time.time() * 1000)}.png"
            image_path = self._path_manager.get_screenshot_path(filename)

            img.save(str(image_path), "PNG")

            self._update_capture_count(is_fullscreen=True)

            return CaptureResult(
                image_path=str(image_path),
                width=screenshot.width,
                height=screenshot.height,
                timestamp=time.time(),
            )
        except Exception as e:
            print(f"Capture error: {e}")
            return None

    def capture_region(self, region: Tuple[int, int, int, int]) -> Optional[CaptureResult]:
        x, y, w, h = region
        if w <= 0 or h <= 0:
            return None

        if not self._check_debounce(is_fullscreen=False):
            return None

        if self._check_force_split():
            return None

        if self._is_clustered_region(region):
            return None

        try:
            monitor = {"top": y, "left": x, "width": w, "height": h}
            screenshot = self._sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

            filename = f"screenshot_{int(time.time() * 1000)}.png"
            image_path = self._path_manager.get_screenshot_path(filename)

            img.save(str(image_path), "PNG")

            self._update_capture_count(is_fullscreen=False)

            self._last_region = region

            return CaptureResult(
                image_path=str(image_path),
                width=w,
                height=h,
                timestamp=time.time(),
            )
        except Exception as e:
            print(f"Capture error: {e}")
            return None

    def _check_debounce(self, is_fullscreen: bool = True) -> bool:
        current_time = time.time()
        last_time = self._fullscreen_debounce_time if is_fullscreen else self._region_debounce_time
        if current_time - last_time < self._debounce_interval:
            return False
        return True

    def _check_force_split(self) -> bool:
        with self._settings_lock:
            current_time = time.time()
            if current_time - self._capture_window_start >= self._debounce_interval:
                self._capture_window_start = current_time
                self._fullscreen_count = 0
                self._region_count = 0

            count = self._fullscreen_count + self._region_count
            if count >= self._max_captures_per_window:
                return True
            return False

    def _update_capture_count(self, is_fullscreen: bool = True):
        with self._settings_lock:
            self._last_capture_time = time.time()
            if is_fullscreen:
                self._fullscreen_debounce_time = self._last_capture_time
                self._fullscreen_count += 1
            else:
                self._region_debounce_time = self._last_capture_time
                self._region_count += 1

    def _is_clustered_region(self, region: Tuple[int, int, int, int]) -> bool:
        if self._last_region is None:
            return False

        x1, y1, w1, h1 = region
        x2, y2, w2, h2 = self._last_region

        x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
        y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
        overlap_area = x_overlap * y_overlap

        area1 = w1 * h1
        area2 = w2 * h2
        iou = overlap_area / (area1 + area2 - overlap_area + 1e-6)

        time_diff = time.time() - self._last_capture_time

        return iou > 0.5 and time_diff < self._cluster_threshold

    def set_debounce_interval(self, interval: float) -> bool:
        try:
            self._debounce_interval = float(interval)
            return True
        except (ValueError, TypeError):
            return False

    def set_cluster_threshold(self, threshold: float) -> bool:
        try:
            self._cluster_threshold = float(threshold)
            return True
        except (ValueError, TypeError):
            return False

    def set_max_captures_per_window(self, max_captures: int) -> bool:
        try:
            self._max_captures_per_window = int(max_captures)
            return True
        except (ValueError, TypeError):
            return False

    def update_settings(self, settings: dict) -> bool:
        with self._settings_lock:
            old_debounce = self._debounce_interval
            old_cluster = self._cluster_threshold
            old_max = self._max_captures_per_window

            new_debounce = old_debounce
            new_cluster = old_cluster
            new_max = old_max

            try:
                if "debounce_interval" in settings:
                    value = float(settings["debounce_interval"])
                    if value <= 0:
                        raise ValueError(f"Invalid debounce_interval: {value}")
                    new_debounce = value

                if "cluster_threshold" in settings:
                    value = float(settings["cluster_threshold"])
                    if value <= 0:
                        raise ValueError(f"Invalid cluster_threshold: {value}")
                    new_cluster = value

                if "max_captures_per_window" in settings:
                    value = int(settings["max_captures_per_window"])
                    if value <= 0:
                        raise ValueError(f"Invalid max_captures_per_window: {value}")
                    new_max = value

                self._debounce_interval = new_debounce
                self._cluster_threshold = new_cluster
                self._max_captures_per_window = new_max
                return True
            except (ValueError, TypeError):
                self._debounce_interval = old_debounce
                self._cluster_threshold = old_cluster
                self._max_captures_per_window = old_max
                return False

    def get_settings(self) -> dict:
        return {
            "debounce_interval": self._debounce_interval,
            "cluster_threshold": self._cluster_threshold,
            "max_captures_per_window": self._max_captures_per_window
        }

    def close(self):
        self._sct.close()


# 全局实例占位 — 实际实例由 DIContainer 通过初始化路径管理器后注入
# 参见 container.py:initialize_defaults()
capture_manager = None
