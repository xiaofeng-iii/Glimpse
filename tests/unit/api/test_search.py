import asyncio
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
