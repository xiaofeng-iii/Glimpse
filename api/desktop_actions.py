"""
Shared desktop actions for API routes and background hotkeys.
"""
import asyncio
from typing import Any, Dict

from api.dependencies import get_capture_manager, get_memory_service
from api.websocket import broadcast_event


async def _capture_fullscreen(force: bool = False):
    capture_manager = get_capture_manager()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: capture_manager.capture_fullscreen(force_bypass_debounce=force),
    )


async def capture_only(*, force: bool = False, source: str = "api") -> Dict[str, Any]:
    """Capture a screenshot and broadcast the completion event."""
    result = await _capture_fullscreen(force=force)
    if result is None:
        return {
            "success": False,
            "message": "Screenshot rate limited or capture failed",
            "source": source,
        }

    await broadcast_event(
        "screenshot_completed",
        {
            "image_path": result.image_path,
            "source": source,
        },
    )

    return {
        "success": True,
        "message": "Screenshot captured successfully",
        "image_path": result.image_path,
        "source": source,
    }


async def capture_and_analyze(*, force: bool = False, source: str = "api") -> Dict[str, Any]:
    """Capture a screenshot, create a memory, and broadcast lifecycle events."""
    try:
        capture_result = await capture_only(force=force, source=source)
        if not capture_result.get("success"):
            return capture_result

        memory_service = get_memory_service()
        image_path = capture_result["image_path"]
        loop = asyncio.get_running_loop()
        memory_id = await loop.run_in_executor(
            None,
            lambda: memory_service.create_memory(
                image_path,
                app_name="unknown",
            ),
        )

        if not memory_id:
            return {
                "success": False,
                "message": "Memory creation failed",
                "image_path": image_path,
                "source": source,
            }

        await broadcast_event(
            "memory_saved",
            {
                "memory_id": memory_id,
                "source": source,
            },
        )

        return {
            "success": True,
            "memory_id": memory_id,
            "image_path": image_path,
            "source": source,
        }
    except Exception as exc:
        await broadcast_event(
            "error_occurred",
            {
                "message": str(exc),
                "source": source,
            },
        )
        raise
