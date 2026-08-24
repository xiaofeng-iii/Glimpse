import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.schemas import MemoryCreateRequest, MemoryUpdateRequest
from db.sqlite_manager import MemoryRecord


def make_memory(summary="updated", status="PENDING", memory_type="screenshot"):
    return MemoryRecord(
        id="memory-1",
        created_at="2026-01-01 12:00:00",
        image_path="image.png",
        ai_summary=summary,
        app_name="unknown",
        text_content="recognized",
        sync_status=status,
        memory_type=memory_type,
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


def test_create_text_memory_returns_indexed_text_record_and_broadcasts():
    from api.routes.memories import create_text_memory

    memory_service = MagicMock()
    memory_service.create_text_memory.return_value = "memory-1"
    memory_service.get_memory.return_value = make_memory(
        summary="手动内容",
        status="SYNCED",
    )
    memory_service.get_memory.return_value.image_path = ""
    memory_service.get_memory.return_value.text_content = None
    memory_service.get_memory.return_value.memory_type = "text"

    run_in_threadpool = AsyncMock(return_value="memory-1")
    broadcast = AsyncMock()
    with (
        patch("api.routes.memories.get_memory_service", return_value=memory_service),
        patch("api.routes.memories.run_in_threadpool", run_in_threadpool),
        patch("api.routes.memories.broadcast_event", broadcast),
    ):
        response = asyncio.run(
            create_text_memory(MemoryCreateRequest(content="  手动内容  "))
        )

    assert response.memory_type == "text"
    assert response.image_path == ""
    assert response.ai_summary == "手动内容"
    run_in_threadpool.assert_awaited_once_with(
        memory_service.create_text_memory,
        "手动内容",
    )
    broadcast.assert_awaited_once_with(
        "memory_saved",
        {"memory_id": "memory-1", "source": "text", "notify": False},
    )


def test_list_memories_forwards_inclusive_date_filters_and_filtered_total():
    from api.routes.memories import list_memories

    search_service = MagicMock()
    search_service.get_recent_memories.return_value = [make_memory()]
    search_service.get_recent_memories_count.return_value = 1

    with patch("api.routes.memories.get_search_service", return_value=search_service):
        response = asyncio.run(
            list_memories(
                limit=100,
                offset=0,
                date_from=date(2026, 8, 1),
                date_to=date(2026, 8, 24),
            )
        )

    assert response.total == 1
    search_service.get_recent_memories.assert_called_once_with(
        limit=100,
        offset=0,
        created_after="2026-08-01 00:00:00",
        created_before="2026-08-25 00:00:00",
    )
    search_service.get_recent_memories_count.assert_called_once_with(
        created_after="2026-08-01 00:00:00",
        created_before="2026-08-25 00:00:00",
    )


def test_list_memories_forwards_content_type_filter_and_filtered_total():
    from api.routes.memories import list_memories

    search_service = MagicMock()
    search_service.get_recent_memories.return_value = [make_memory(memory_type="text")]
    search_service.get_recent_memories_count.return_value = 1

    with patch("api.routes.memories.get_search_service", return_value=search_service):
        response = asyncio.run(
            list_memories(
                limit=100,
                offset=0,
                memory_type="text",
            )
        )

    assert response.total == 1
    assert response.memories[0].memory_type == "text"
    search_service.get_recent_memories.assert_called_once_with(
        limit=100,
        offset=0,
        created_after=None,
        created_before=None,
        memory_type="text",
    )
    search_service.get_recent_memories_count.assert_called_once_with(
        created_after=None,
        created_before=None,
        memory_type="text",
    )


def test_list_memories_preserves_a_reversed_range_as_422():
    from api.routes.memories import list_memories

    with patch("api.routes.memories.get_search_service", return_value=MagicMock()):
        with pytest.raises(HTTPException) as error:
            asyncio.run(
                list_memories(
                    limit=100,
                    offset=0,
                    date_from=date(2026, 8, 24),
                    date_to=date(2026, 8, 1),
                )
            )

    assert error.value.status_code == 422


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
