import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from db.sqlite_manager import MemoryRecord


def test_capture_and_analyze_broadcasts_readable_processing_memory():
    from api.desktop_actions import capture_and_analyze

    pending = MemoryRecord(
        id="memory-pending",
        created_at="2026-08-27 12:00:00",
        image_path="capture.png",
        ai_summary="",
        app_name="unknown",
        text_content="",
        sync_status="PENDING",
        analysis_status="PROCESSING",
    )
    memory_service = MagicMock()
    memory_service.prepare_screenshot_memory.return_value = pending
    settings_manager = MagicMock()
    settings_manager.get.return_value = False
    broadcast = AsyncMock()

    with (
        patch(
            "api.desktop_actions.capture_only",
            AsyncMock(
                return_value={
                    "success": True,
                    "image_path": "capture.png",
                    "source": "api",
                }
            ),
        ),
        patch("api.desktop_actions.get_settings_manager", return_value=settings_manager),
        patch("api.desktop_actions.get_memory_service", return_value=memory_service),
        patch("api.desktop_actions.broadcast_event", broadcast),
    ):
        result = asyncio.run(capture_and_analyze())

    assert result["memory_id"] == "memory-pending"
    assert result["memory"]["analysis_status"] == "PROCESSING"
    memory_service.create_memory_async.assert_called_once()
    broadcast.assert_awaited_once_with(
        "memory_processing_started",
        {"memory": pending.to_dict(), "source": "api"},
    )


def test_cluster_flush_broadcasts_readable_processing_memory_before_scheduling():
    import api.desktop_actions as desktop_actions

    pending = MemoryRecord(
        id="cluster-pending",
        created_at="2026-08-27 12:00:00",
        image_path="first.png",
        ai_summary="",
        app_name="unknown",
        text_content="",
        extra_images='["second.png"]',
        sync_status="PENDING",
        analysis_status="PROCESSING",
    )
    callbacks = []
    cluster_buffer = MagicMock()
    cluster_buffer.flushed.connect.side_effect = callbacks.append
    memory_service = MagicMock()
    memory_service.prepare_cluster_memory.return_value = pending
    broadcast = AsyncMock()
    original_initialized = desktop_actions._cluster_processing_initialized

    async def scenario():
        desktop_actions._cluster_processing_initialized = False
        with (
            patch("api.desktop_actions.get_cluster_buffer", return_value=cluster_buffer),
            patch("api.desktop_actions.get_memory_service", return_value=memory_service),
            patch("api.desktop_actions.broadcast_event", broadcast),
        ):
            desktop_actions.setup_cluster_processing(asyncio.get_running_loop())
            callbacks[0](["first.png", "second.png"])
            await asyncio.sleep(0)

    try:
        asyncio.run(scenario())
    finally:
        desktop_actions._cluster_processing_initialized = original_initialized

    memory_service.prepare_cluster_memory.assert_called_once_with(
        ["first.png", "second.png"],
        app_name="unknown",
    )
    memory_service.create_cluster_memory_async.assert_called_once_with(
        ["first.png", "second.png"],
        app_name="unknown",
        on_complete=memory_service.create_cluster_memory_async.call_args.kwargs["on_complete"],
        on_error=memory_service.create_cluster_memory_async.call_args.kwargs["on_error"],
        memory_id="cluster-pending",
    )
    broadcast.assert_awaited_once_with(
        "memory_processing_started",
        {"memory": pending.to_dict(), "source": "cluster"},
    )
