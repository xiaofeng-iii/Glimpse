"""
API Integration Tests - 测试 FastAPI 后端接口
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient


class TestAPIServer:
    """Test the FastAPI server endpoints"""

    @pytest.fixture(scope="class")
    def client(self):
        """Create test client"""
        from api.server import app
        with TestClient(app) as client:
            yield client

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Glimpse API"
        assert "version" in data

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_list_memories(self, client):
        """Test list memories endpoint"""
        response = client.get("/api/memories")
        assert response.status_code == 200
        data = response.json()
        assert "memories" in data
        assert "total" in data
        assert isinstance(data["memories"], list)

    def test_search_memories(self, client):
        """Test search endpoint"""
        response = client.get("/api/search?q=test&source=all")
        assert response.status_code == 200
        data = response.json()
        assert "memories" in data
        assert "query" in data
        assert data["query"] == "test"

    def test_get_settings(self, client):
        """Test get settings endpoint"""
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert "hotkeys" in data
        assert "ai" in data
        assert "screenshot" in data

    def test_update_settings(self, client):
        """Test update settings endpoint"""
        new_settings = {
            "ui": {
                "theme": "dark"
            }
        }
        response = client.put("/api/settings", json=new_settings)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True

    def test_cluster_status(self, client):
        """Test cluster status endpoint"""
        response = client.get("/api/cluster/status")
        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert "count" in data
        assert "max_count" in data

    def test_stats_endpoint(self, client):
        """Test stats endpoint"""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "sqlite_count" in data
        assert "chroma_count" in data


class TestMemoryNotFound:
    """Test error cases"""

    @pytest.fixture(scope="class")
    def client(self):
        from api.server import app
        with TestClient(app) as client:
            yield client

    def test_get_nonexistent_memory(self, client):
        """Test getting a non-existent memory"""
        response = client.get("/api/memories/non-existent-id-12345")
        assert response.status_code == 404

    def test_delete_nonexistent_memory(self, client):
        """Test deleting a non-existent memory"""
        response = client.delete("/api/memories/non-existent-id-12345")
        assert response.status_code == 404


class TestWebSocketConnection:
    """Test WebSocket endpoint"""

    @pytest.fixture(scope="class")
    def client(self):
        from api.server import app
        with TestClient(app) as client:
            yield client

    def test_websocket_connect(self, client):
        """Test WebSocket can connect"""
        with client.websocket_connect("/ws/events") as websocket:
            # Send ping
            websocket.send_text("ping")
            # Receive pong
            data = websocket.receive_text()
            assert data == "pong"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
