"""Basic tests for web interface."""

import pytest
from fastapi.testclient import TestClient

from strix.interface.scan_manager import ScanManager
from strix.interface.web_server import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def scan_id() -> str:
    """Create a test scan."""
    scan_manager = ScanManager.get_instance()
    scan_id = scan_manager.create_scan(
        targets=[{"type": "url", "details": {"target_url": "http://example.com"}, "original": "http://example.com"}],
        user_instructions="Test scan",
        run_name="test-scan",
    )
    return scan_id


def test_index_endpoint(client: TestClient) -> None:
    """Test that index endpoint returns 404 when assets not configured."""
    response = client.get("/")
    # Should return 500 if assets not configured, or 404 if index.html not found
    assert response.status_code in (404, 500)


def test_list_scans(client: TestClient) -> None:
    """Test listing scans."""
    response = client.get("/api/scans")
    assert response.status_code == 200
    data = response.json()
    assert "scans" in data
    assert isinstance(data["scans"], list)


def test_get_scan_agents_empty(client: TestClient, scan_id: str) -> None:
    """Test getting agents when none exist."""
    response = client.get(f"/api/scans/{scan_id}/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert data["agents"] == {}


def test_get_scan_vulnerabilities_empty(client: TestClient, scan_id: str) -> None:
    """Test getting vulnerabilities when none exist."""
    response = client.get(f"/api/scans/{scan_id}/vulnerabilities")
    assert response.status_code == 200
    data = response.json()
    assert "vulnerabilities" in data
    assert data["vulnerabilities"] == []


def test_get_scan_stats(client: TestClient, scan_id: str) -> None:
    """Test getting stats."""
    response = client.get(f"/api/scans/{scan_id}/stats")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "tools" in data
    assert "vulnerabilities" in data
    assert "llm_stats" in data


def test_get_scan_not_found(client: TestClient) -> None:
    """Test getting a non-existent scan."""
    response = client.get("/api/scans/non-existent")
    assert response.status_code == 404


def test_websocket_connection(client: TestClient) -> None:
    """Test WebSocket connection."""
    with client.websocket_connect("/ws") as websocket:
        # Should receive initial state or ping
        data = websocket.receive_json()
        assert "type" in data

