import asyncio
from unittest.mock import MagicMock, patch

from api.schemas import TagListResponse


def test_list_tags_returns_all_tags_with_counts():
    from api.routes.tags import list_tags

    memory_service = MagicMock()
    memory_service.get_all_tags.return_value = [
        {"id": 1, "name": "工作", "memory_count": 8},
        {"id": 2, "name": "灵感", "memory_count": 0},
    ]

    with patch(
        "api.routes.tags.get_memory_service",
        return_value=memory_service,
    ):
        response = asyncio.run(list_tags())

    assert isinstance(response, TagListResponse)
    assert [tag.model_dump() for tag in response.tags] == [
        {"id": 1, "name": "工作", "memory_count": 8},
        {"id": 2, "name": "灵感", "memory_count": 0},
    ]


def test_tags_route_is_registered_under_api_prefix():
    from api.server import app

    paths = {route.path for route in app.routes}
    assert "/api/tags" in paths
