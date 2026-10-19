import asyncio
from datetime import date
from unittest.mock import MagicMock, patch

from db.sqlite_manager import MemoryRecord


def test_search_route_forwards_development_tuning_options():
    from api.routes.search import search

    memory = MemoryRecord(
        id="1",
        created_at="now",
        image_path="path",
        ai_summary="summary",
        app_name="app",
    )
    memory.match_sources = ["语义"]
    memory.search_debug = {
        "mode": "vector",
        "text_rank": None,
        "semantic_rank": 1,
        "semantic_distance": 1.2,
        "rrf_score": None,
    }
    search_service = MagicMock()
    search_service.search.return_value = [memory]

    with patch("api.routes.search.get_search_service", return_value=search_service):
        result = asyncio.run(
            search(
                q="自然语言",
                source="semantic",
                limit=30,
                semantic_threshold=1.3,
                candidate_multiplier=4,
                rrf_k=80,
                debug=True,
            )
        )

    search_service.search.assert_called_once_with(
        "自然语言",
        limit=30,
        source_filter="semantic",
        semantic_threshold=1.3,
        candidate_multiplier=4,
        rrf_k=80,
        include_debug=True,
    )
    assert result.memories[0].search_debug.semantic_distance == 1.2


def test_search_route_forwards_date_and_content_type_filters():
    from api.routes.search import search

    search_service = MagicMock()
    search_service.search.return_value = []

    with patch("api.routes.search.get_search_service", return_value=search_service):
        asyncio.run(
            search(
                q="自然语言",
                source="all",
                limit=20,
                semantic_threshold=None,
                candidate_multiplier=2,
                rrf_k=60,
                debug=False,
                date_from=date(2026, 8, 1),
                date_to=date(2026, 8, 24),
                memory_type="text",
            )
        )

    search_service.search.assert_called_once_with(
        "自然语言",
        limit=20,
        source_filter="all",
        semantic_threshold=None,
        candidate_multiplier=2,
        rrf_k=60,
        include_debug=False,
        created_after="2026-08-01 00:00:00",
        created_before="2026-08-25 00:00:00",
        memory_type="text",
    )


def test_search_route_forwards_tag_ids():
    from api.routes.search import search

    search_service = MagicMock()
    search_service.search.return_value = []

    with patch("api.routes.search.get_search_service", return_value=search_service):
        asyncio.run(
            search(
                q="自然语言",
                source="all",
                limit=20,
                semantic_threshold=None,
                candidate_multiplier=2,
                rrf_k=60,
                debug=False,
                tag_ids=[1, 2],
            )
        )

    search_service.search.assert_called_once_with(
        "自然语言",
        limit=20,
        source_filter="all",
        semantic_threshold=None,
        candidate_multiplier=2,
        rrf_k=60,
        include_debug=False,
        tag_ids=[1, 2],
    )


def test_search_route_without_filters_omits_tag_ids():
    from api.routes.search import search

    search_service = MagicMock()
    search_service.search.return_value = []

    with patch("api.routes.search.get_search_service", return_value=search_service):
        asyncio.run(
            search(
                q="自然语言",
                source="all",
                limit=20,
                semantic_threshold=None,
                candidate_multiplier=2,
                rrf_k=60,
                debug=False,
                tag_ids=None,
            )
        )

    assert "tag_ids" not in search_service.search.call_args.kwargs


def test_search_response_preserves_tags_and_user_text():
    from api.routes.search import search
    from db.sqlite_manager import TagRecord

    memory = MemoryRecord(
        id="1",
        created_at="now",
        image_path="path",
        ai_summary="summary",
        app_name="app",
        user_text="搜索页备注",
    )
    memory.tags = [TagRecord(id=1, name="工作")]
    search_service = MagicMock()
    search_service.search.return_value = [memory]

    with patch("api.routes.search.get_search_service", return_value=search_service):
        result = asyncio.run(
            search(
                q="自然语言",
                source="all",
                limit=20,
                semantic_threshold=None,
                candidate_multiplier=2,
                rrf_k=60,
                debug=False,
            )
        )

    # 搜索响应与普通记忆响应同构：tags 为对象列表，user_text 不丢失。
    assert result.memories[0].user_text == "搜索页备注"
    assert [tag.model_dump() for tag in result.memories[0].tags] == [
        {"id": 1, "name": "工作"}
    ]


def test_repeated_tag_ids_query_params_parse_as_list():
    from fastapi.testclient import TestClient
    from api.server import app

    search_service = MagicMock()
    search_service.search.return_value = []
    search_service.get_recent_memories.return_value = []
    search_service.get_recent_memories_count.return_value = 0

    with (
        patch("api.routes.search.get_search_service", return_value=search_service),
        patch("api.routes.memories.get_search_service", return_value=search_service),
    ):
        client = TestClient(app)
        search_response = client.get("/api/search?q=test&tag_ids=1&tag_ids=2")
        list_response = client.get("/api/memories?tag_ids=3&tag_ids=4")

    assert search_response.status_code == 200
    assert list_response.status_code == 200
    assert search_service.search.call_args.kwargs["tag_ids"] == [1, 2]
    assert (
        search_service.get_recent_memories.call_args.kwargs["tag_ids"] == [3, 4]
    )
    assert (
        search_service.get_recent_memories_count.call_args.kwargs["tag_ids"]
        == [3, 4]
    )
