"""
Shared desktop actions for API routes and background hotkeys.
"""
import asyncio
from typing import Any, Dict

from api.dependencies import (
    get_capture_manager,
    get_cluster_buffer,
    get_memory_service,
    get_settings_manager,
)
from api.websocket import broadcast_event
from utils.logger import get_logger

logger = get_logger(__name__)

_cluster_processing_initialized = False


async def _capture_fullscreen(force: bool = False):
    capture_manager = get_capture_manager()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: capture_manager.capture_fullscreen(force_bypass_debounce=force),
    )


def _report_background_future(future) -> None:
    try:
        future.result()
    except Exception as exc:
        logger.error("Background broadcast error: %s", exc)


def _emit_from_thread(
    loop: asyncio.AbstractEventLoop,
    event_type: str,
    data: Dict[str, Any],
) -> None:
    if loop.is_closed():
        return

    future = asyncio.run_coroutine_threadsafe(
        broadcast_event(event_type, data),
        loop,
    )
    future.add_done_callback(_report_background_future)


async def _create_memory_in_background(
    image_path: str,
    source: str,
) -> None:
    memory_service = get_memory_service()

    try:
        memory_id = await asyncio.to_thread(
            memory_service.create_memory,
            image_path,
            "unknown",
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
                "image_path": image_path,
                "source": source,
            },
        )
    except Exception as exc:
        await broadcast_event(
            "error_occurred",
            {
                "message": str(exc),
                "image_path": image_path,
                "source": source,
            },
        )


def setup_cluster_processing(loop: asyncio.AbstractEventLoop) -> None:
    """Create one memory from all images when the cluster buffer is flushed."""
    global _cluster_processing_initialized
    if _cluster_processing_initialized:
        return
    _cluster_processing_initialized = True

    cluster_buffer = get_cluster_buffer()

    def on_cluster_flushed(image_paths):
        if not image_paths:
            return

        memory_service = get_memory_service()
        primary_image = image_paths[0]

        def on_complete(memory_id):
            if not memory_id:
                _emit_from_thread(
                    loop,
                    "error_occurred",
                    {
                        "message": "Cluster memory creation failed",
                        "image_path": primary_image,
                        "source": "cluster",
                    },
                )
                return

            _emit_from_thread(
                loop,
                "memory_saved",
                {
                    "memory_id": memory_id,
                    "image_path": primary_image,
                    "images": image_paths,
                    "source": "cluster",
                },
            )

        def on_error(message: str):
            _emit_from_thread(
                loop,
                "error_occurred",
                {
                    "message": message,
                    "image_path": primary_image,
                    "images": image_paths,
                    "source": "cluster",
                },
            )

        try:
            memory_service.create_cluster_memory_async(
                image_paths,
                app_name="unknown",
                on_complete=on_complete,
                on_error=on_error,
            )
        except Exception as exc:
            async def create_cluster_in_background():
                try:
                    memory_id = await asyncio.to_thread(
                        memory_service.create_cluster_memory,
                        image_paths,
                        "unknown",
                    )
                    on_complete(memory_id)
                except Exception as background_exc:
                    on_error(str(background_exc))

            logger.warning("Cluster async queue unavailable, falling back to thread: %s", exc)
            asyncio.run_coroutine_threadsafe(create_cluster_in_background(), loop)

    cluster_buffer.flushed.connect(on_cluster_flushed)


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
    """Capture a screenshot, start async analysis, and return immediately."""
    try:
        capture_result = await capture_only(force=force, source=source)
        if not capture_result.get("success"):
            return capture_result

        image_path = capture_result["image_path"]

        settings_manager = get_settings_manager()
        if settings_manager.get("cluster.cluster_mode", False):
            cluster_buffer = get_cluster_buffer()
            cluster_buffer.add_image(image_path)
            return {
                "success": True,
                "accepted": True,
                "message": "Screenshot added to cluster",
                "image_path": image_path,
                "source": source,
                "clustered": True,
                "cluster_count": cluster_buffer.get_count(),
            }

        memory_service = get_memory_service()
        loop = asyncio.get_running_loop()

        def on_complete(memory_id):
            if not memory_id:
                _emit_from_thread(
                    loop,
                    "error_occurred",
                    {
                        "message": "Memory creation failed",
                        "image_path": image_path,
                        "source": source,
                    },
                )
                return

            _emit_from_thread(
                loop,
                "memory_saved",
                {
                    "memory_id": memory_id,
                    "image_path": image_path,
                    "source": source,
                },
            )

        def on_error(message: str):
            _emit_from_thread(
                loop,
                "error_occurred",
                {
                    "message": message,
                    "image_path": image_path,
                    "source": source,
                },
            )

        try:
            memory_service.create_memory_async(
                image_path,
                app_name="unknown",
                on_complete=on_complete,
                on_error=on_error,
            )
        except Exception:
            asyncio.create_task(_create_memory_in_background(image_path, source))

        return {
            "success": True,
            "accepted": True,
            "message": "Screenshot captured and analysis started",
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
