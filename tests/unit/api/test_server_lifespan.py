import asyncio
from unittest.mock import MagicMock, patch


def test_lifespan_schedules_vector_repair_without_running_it_inline():
    from api import server

    ai_client = MagicMock()
    settings_manager = MagicMock()
    memory_service = MagicMock()
    memory_service.maybe_schedule_vector_index_repair.return_value = True

    fake_container = MagicMock()
    fake_container.get.side_effect = {
        "ai_client": ai_client,
        "settings_manager": settings_manager,
        "memory_service": memory_service,
    }.__getitem__

    entered_lifespan = False

    async def run_lifespan():
        nonlocal entered_lifespan
        async with server.lifespan(server.app):
            entered_lifespan = True
            memory_service.maybe_schedule_vector_index_repair.assert_called_once_with()

    with (
        patch.object(server, "container", fake_container),
        patch.object(server, "configure_ai_client") as configure_ai,
        patch.object(server, "setup_signal_forwarding") as setup_websocket,
        patch.object(server, "setup_cluster_processing") as setup_cluster,
        patch.object(server, "setup_global_hotkeys") as setup_hotkeys,
        patch.object(server, "shutdown_global_hotkeys") as shutdown_hotkeys,
    ):
        asyncio.run(run_lifespan())

    assert entered_lifespan is True
    fake_container.initialize_defaults.assert_called_once_with()
    configure_ai.assert_called_once_with(ai_client, settings_manager)
    setup_websocket.assert_called_once()
    setup_cluster.assert_called_once()
    setup_hotkeys.assert_called_once()
    shutdown_hotkeys.assert_called_once_with()
    fake_container.shutdown.assert_called_once_with()
