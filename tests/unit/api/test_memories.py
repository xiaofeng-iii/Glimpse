import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.schemas import MemoryUpdateRequest
from db.sqlite_manager import MemoryRecord


def make_memory(summary="updated", status="PENDING"):
    return MemoryRecord(
        id="memory-1",
        created_at="2026-01-01 12:00:00",
        image_path="image.png",
        ai_summary=summary,
        app_name="unknown",
        text_content="recognized",
        sync_status=status,
    )


def test_patch_memory_returns_canonical_record_without_duplicate_broadcast():
    from api.routes.memories import update_memory

    memory_service = MagicMock()
    memory_service.update_memory_summary.return_value = make_memory()

    with patch(
        "api.routes.memories.get_memory_service",
        return_value=memory_service,
    ):
        response = asyncio.run(
            update_memory(
                "memory-1",
                MemoryUpdateRequest(ai_summary="  updated  "),
            )
        )

    assert response.ai_summary == "updated"
    assert response.sync_status == "PENDING"
    memory_service.update_memory_summary.assert_called_once_with(
        "memory-1",
        "updated",
    )


def test_patch_memory_missing_returns_404():
    from api.routes.memories import update_memory

    memory_service = MagicMock()
    memory_service.update_memory_summary.return_value = None

    with patch(
        "api.routes.memories.get_memory_service",
        return_value=memory_service,
    ):
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                update_memory(
                    "missing",
                    MemoryUpdateRequest(ai_summary="updated"),
                )
            )

    assert error.value.status_code == 404


@pytest.mark.parametrize("summary", ["", "   ", "x" * 4001])
def test_memory_update_schema_rejects_invalid_summary(summary):
    with pytest.raises(ValidationError):
        MemoryUpdateRequest(ai_summary=summary)
