"""
Capture - pynput 与 mss 的封装，包含防抖与窗口限流
注入PathManager
"""
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
        self._debounce_interval = 5.0
        self._capture_window_start = 0
        self._max_captures_per_window = 10
        self._fullscreen_debounce_time = 0
        self._region_debounce_time = 0
        self._fullscreen_count = 0
        self._region_count = 0
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

        if not force_bypass_debounce and not self._check_debounce(is_fullscreen=True):
            return None

        if self._check_force_split():
            return None

        try:
            with mss.mss() as sct:
                screenshot = sct.grab(sct.monitors[1])
                result = self._save_screenshot(screenshot)
            self._update_capture_count(is_fullscreen=True)
            return result
        except Exception as e:
            print(f"Capture fullscreen error: {e}")
            traceback.print_exc()
            return None

    def capture_region(self, region: Tuple[int, int, int, int]) -> Optional[CaptureResult]:
        x, y, w, h = region
        if w <= 0 or h <= 0:
            return None

        if not self._check_debounce(is_fullscreen=False):
            return None

        if self._check_force_split():
            return None

        try:
            monitor = {"top": y, "left": x, "width": w, "height": h}
            with mss.mss() as sct:
                screenshot = sct.grab(monitor)
                result = self._save_screenshot(screenshot)
            self._update_capture_count(is_fullscreen=False)
            return result
        except Exception as e:
            print(f"Capture region error: {e}")
            traceback.print_exc()
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

    def set_debounce_interval(self, interval: float) -> bool:
        try:
            self._debounce_interval = float(interval)
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
            old_max = self._max_captures_per_window

            new_debounce = old_debounce
            new_max = old_max

            try:
                if "debounce_interval" in settings:
                    value = float(settings["debounce_interval"])
                    if value <= 0:
                        raise ValueError(f"Invalid debounce_interval: {value}")
                    new_debounce = value

                if "max_captures_per_window" in settings:
                    value = int(settings["max_captures_per_window"])
                    if value <= 0:
                        raise ValueError(f"Invalid max_captures_per_window: {value}")
                    new_max = value

                self._debounce_interval = new_debounce
                self._max_captures_per_window = new_max
                return True
            except (ValueError, TypeError):
                self._debounce_interval = old_debounce
                self._max_captures_per_window = old_max
                return False

    def get_settings(self) -> dict:
        return {
            "debounce_interval": self._debounce_interval,
            "max_captures_per_window": self._max_captures_per_window
        }

    def close(self):
        return None


# 全局实例占位 — 实际实例由 DIContainer 通过初始化路径管理器后注入
# 参见 container.py:initialize_defaults()
capture_manager = None
