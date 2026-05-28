"""
Shared desktop actions for API routes and background hotkeys.
"""
import asyncio
from typing import Any, Dict

from api.dependencies import get_capture_manager, get_memory_service
from api.websocket import broadcast_event

_background_tasks: set[asyncio.Task] = set()


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


async def _create_memory_background(image_path: str, source: str) -> None:
    try:
        await broadcast_event(
            "status_updated",
            {
                "message": "Screenshot captured. Analyzing in background...",
                "source": source,
            },
        )

        memory_service = get_memory_service()
        loop = asyncio.get_running_loop()
        memory_id = await loop.run_in_executor(
            None,
            lambda: memory_service.create_memory(
                image_path,
                app_name="unknown",
            ),
        )

        if not memory_id:
            await broadcast_event(
                "error_occurred",
                {
                    "message": "Memory creation failed",
                    "image_path": image_path,
                    "source": source,
                },
            )
            return

        await broadcast_event(
            "memory_saved",
            {
                "memory_id": memory_id,
                "source": source,
            },
        )
    except Exception as exc:
        await broadcast_event(
            "error_occurred",
            {
                "message": f"Memory creation error: {exc}",
                "image_path": image_path,
                "source": source,
            },
        )


def _schedule_background_analysis(image_path: str, source: str) -> None:
    task = asyncio.create_task(_create_memory_background(image_path, source))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def capture_and_analyze(*, force: bool = False, source: str = "api") -> Dict[str, Any]:
    """Capture a screenshot and synchronously create memory — returns full result.

    Mirrors main-branch Qt flow: capture → analyze → save → return memory data.
    For fire-and-forget (global hotkeys), use capture_and_analyze_background() instead.
    """
    try:
        capture_result = await capture_only(force=force, source=source)
        if not capture_result.get("success"):
            return capture_result

        image_path = capture_result["image_path"]

        await broadcast_event("status_updated", {
            "message": "Screenshot captured. Analyzing...",
            "source": source,
        })

        memory_service = get_memory_service()
        loop = asyncio.get_running_loop()
        memory_id = await loop.run_in_executor(
            None,
            lambda: memory_service.create_memory(image_path, app_name="unknown"),
        )

        if not memory_id:
            return {
                "success": False,
                "message": "Memory creation failed",
                "source": source,
            }

        # Fetch the created memory to return its data directly
        search_service = None
        try:
            from api.dependencies import get_search_service
            search_service = get_search_service()
            memory = search_service.get_memory_by_id(memory_id)
        except Exception:
            memory = None

        memory_data = None
        if memory:
            from api.routes.memories import memory_to_response
            memory_data = memory_to_response(memory)

        await broadcast_event("memory_saved", {
            "memory_id": memory_id,
            "source": source,
        })

        return {
            "success": True,
            "message": "Screenshot captured and analyzed.",
            "memory_id": memory_id,
            "memory": memory_data,
            "image_path": image_path,
            "source": source,
        }
    except Exception as exc:
        await broadcast_event("error_occurred", {
            "message": str(exc),
            "source": source,
        })
        raise


async def capture_and_analyze_background(*, force: bool = False, source: str = "api") -> Dict[str, Any]:
    """Capture a screenshot and schedule memory creation in the background (fire-and-forget).

    Used by global hotkeys where we can't block for 40+ seconds.
    """
    try:
        capture_result = await capture_only(force=force, source=source)
        if not capture_result.get("success"):
            return capture_result

        image_path = capture_result["image_path"]
        _schedule_background_analysis(image_path, source)

        return {
            "success": True,
            "message": "Screenshot captured. Analysis started.",
            "image_path": image_path,
            "source": source,
        }
    except Exception as exc:
        await broadcast_event("error_occurred", {
            "message": str(exc),
            "source": source,
        })
        raise
