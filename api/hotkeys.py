"""
Global hotkey lifecycle for API mode.
"""
import asyncio
import os
from typing import Callable, Dict, Optional

from api.dependencies import get_keyboard_manager, get_settings_manager
from api.desktop_actions import capture_and_analyze
from api.websocket import broadcast_event, has_active_connections
from utils.logger import get_logger

logger = get_logger(__name__)

_hotkey_loop: Optional[asyncio.AbstractEventLoop] = None


def _hotkeys_enabled() -> bool:
    if os.getenv("GLIMPSE_DISABLE_API_HOTKEYS") == "1":
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def _report_future(future) -> None:
    try:
        future.result()
    except Exception as exc:
        logger.error("Global hotkey handler failed: %s", exc)


def _schedule(coro) -> None:
    loop = _hotkey_loop
    if loop is None or loop.is_closed():
        return

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    future.add_done_callback(_report_future)


async def _handle_screenshot_hotkey() -> None:
    if has_active_connections():
        await broadcast_event(
            "desktop_action",
            {
                "action": "trigger_screenshot",
                "source": "global_hotkey",
            },
        )
        return

    result = await capture_and_analyze(source="global_hotkey")
    if not result.get("success"):
        await broadcast_event(
            "error_occurred",
            {
                "message": result.get("message", "Screenshot hotkey failed"),
                "source": "global_hotkey",
            },
        )


def _build_hotkey_handlers() -> Dict[str, Callable[[], None]]:
    settings_manager = get_settings_manager()
    configured_hotkeys = settings_manager.get("hotkeys", {})
    handlers: Dict[str, Callable[[], None]] = {}

    screenshot_hotkey = (configured_hotkeys.get("screenshot") or "").strip()
    if screenshot_hotkey:
        handlers[screenshot_hotkey] = lambda: _schedule(_handle_screenshot_hotkey())

    return handlers


def setup_global_hotkeys(loop: asyncio.AbstractEventLoop) -> None:
    global _hotkey_loop
    _hotkey_loop = loop
    if not _hotkeys_enabled():
        return
    reload_global_hotkeys()


def reload_global_hotkeys() -> bool:
    if not _hotkeys_enabled():
        return True

    keyboard_manager = get_keyboard_manager()
    success = keyboard_manager.reload_hotkeys(_build_hotkey_handlers())
    if not success:
        logger.warning("Failed to reload API global hotkeys")
    return success


def shutdown_global_hotkeys() -> None:
    global _hotkey_loop
    _hotkey_loop = None
