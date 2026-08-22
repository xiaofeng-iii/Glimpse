"""DI container lifecycle tests."""

from unittest.mock import Mock

from container import DIContainer


def _fresh_container() -> DIContainer:
    container = object.__new__(DIContainer)
    container._initialized = False
    DIContainer.__init__(container)
    return container


def _initialize_with_inert_runtime_handlers(
    container: DIContainer,
    events: list[str],
) -> None:
    container._shutdown_keyboard_manager = Mock()
    container._shutdown_task_queue = lambda: events.append("task_queue")
    container._shutdown_capture_manager = Mock()
    container._shutdown_cluster_buffer = Mock()
    container.initialize_defaults()


def test_shutdown_closes_initialized_databases_after_task_queue() -> None:
    events: list[str] = []
    container = _fresh_container()
    _initialize_with_inert_runtime_handlers(container, events)

    sqlite_manager = Mock()
    sqlite_manager.close.side_effect = lambda: events.append("sqlite_manager")
    chroma_manager = Mock()
    chroma_manager.close.side_effect = lambda: events.append("chroma_manager")

    container.register_singleton_factory("sqlite_manager", lambda: sqlite_manager)
    container.register_singleton_factory("chroma_manager", lambda: chroma_manager)
    assert container.get("sqlite_manager") is sqlite_manager
    assert container.get("chroma_manager") is chroma_manager

    container.shutdown()

    sqlite_manager.close.assert_called_once_with()
    chroma_manager.close.assert_called_once_with()
    assert events == ["task_queue", "chroma_manager", "sqlite_manager"]


def test_shutdown_does_not_create_unused_database_managers() -> None:
    events: list[str] = []
    container = _fresh_container()
    _initialize_with_inert_runtime_handlers(container, events)

    sqlite_factory = Mock()
    chroma_factory = Mock()
    container.register_singleton_factory("sqlite_manager", sqlite_factory)
    container.register_singleton_factory("chroma_manager", chroma_factory)

    container.shutdown()

    sqlite_factory.assert_not_called()
    chroma_factory.assert_not_called()
