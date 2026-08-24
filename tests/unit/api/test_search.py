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


def test_search_route_forwards_date_filter_bounds():
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
    )
