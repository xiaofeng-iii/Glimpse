import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.routes.settings import (
    INDEX_REPAIR_TASK_ID,
    OCR_BACKFILL_TASK_ID,
    get_ocr_backfill_status,
    start_index_repair,
    start_ocr_backfill,
)
from core.task_queue import TaskStatus


def task(task_id, status, result=None):
    return SimpleNamespace(
        id=task_id,
        status=status,
        result=result,
        error=None,
    )


def test_start_ocr_backfill_returns_live_progress():
    queue = MagicMock()
    submitted = task(OCR_BACKFILL_TASK_ID, TaskStatus.PENDING)
    queue.get_task.return_value = None
    queue.submit.return_value = submitted
    memory_service = MagicMock()
    memory_service.get_ocr_backfill_progress.return_value = {
        "status": "running",
        "total": 4,
        "processed": 1,
        "updated": 1,
        "succeeded": 1,
        "skipped": 0,
        "failed": 0,
        "index_failed": 0,
    }

    with (
        patch("api.routes.settings.get_task_queue", return_value=queue),
        patch(
            "api.routes.settings.get_memory_service",
            return_value=memory_service,
        ),
    ):
        response = asyncio.run(start_ocr_backfill())

    assert response["task_id"] == OCR_BACKFILL_TASK_ID
    assert response["running"] is True
    assert response["result"]["processed"] == 1
    queue.submit.assert_called_once_with(
        OCR_BACKFILL_TASK_ID,
        memory_service.backfill_ocr,
    )


def test_ocr_backfill_conflicts_with_index_repair():
    queue = MagicMock()

    def get_task(task_id):
        if task_id == INDEX_REPAIR_TASK_ID:
            return task(task_id, TaskStatus.RUNNING)
        return None

    queue.get_task.side_effect = get_task
    with patch("api.routes.settings.get_task_queue", return_value=queue):
        with pytest.raises(HTTPException) as error:
            asyncio.run(start_ocr_backfill())
    assert error.value.status_code == 409


def test_index_repair_conflicts_with_ocr_backfill():
    queue = MagicMock()

    def get_task(task_id):
        if task_id == OCR_BACKFILL_TASK_ID:
            return task(task_id, TaskStatus.RUNNING)
        return None

    queue.get_task.side_effect = get_task
    with patch("api.routes.settings.get_task_queue", return_value=queue):
        with pytest.raises(HTTPException) as error:
            asyncio.run(start_index_repair())
    assert error.value.status_code == 409


def test_get_ocr_backfill_status_uses_completed_result():
    queue = MagicMock()
    queue.get_task.return_value = task(
        OCR_BACKFILL_TASK_ID,
        TaskStatus.COMPLETED,
        result={"status": "completed", "processed": 2, "updated": 2},
    )

    with patch("api.routes.settings.get_task_queue", return_value=queue):
        response = asyncio.run(get_ocr_backfill_status())

    assert response["running"] is False
    assert response["status"] == "completed"
    assert response["result"]["updated"] == 2
