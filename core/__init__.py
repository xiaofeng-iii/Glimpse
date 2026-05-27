"""
Core module
"""
# Lazy imports to avoid circular dependencies and enable isolated unit testing.
# Use container.get("capture_manager") / container.get("task_queue") for runtime access.

__all__ = ["capture_manager", "task_queue"]


def __getattr__(name):
    if name == "capture_manager":
        from core.capture import capture_manager
        return capture_manager
    if name == "task_queue":
        from core.task_queue import task_queue
        return task_queue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
