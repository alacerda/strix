"""Basic tests for web interface."""

import pytest
from fastapi.testclient import TestClient

from strix.interface.web_server import app
from strix.telemetry.tracer import Tracer, set_global_tracer


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def tracer() -> Tracer:
    """Create a test tracer."""
    test_tracer = Tracer("test-run")
    set_global_tracer(test_tracer)
    return test_tracer


def test_index_endpoint(client: TestClient) -> None:
    """Test that index endpoint returns 404 when assets not configured."""
    response = client.get("/")
    # Should return 500 if assets not configured, or 404 if index.html not found
    assert response.status_code in (404, 500)


def test_get_agents_empty(client: TestClient) -> None:
    """Test getting agents when none exist."""
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert data["agents"] == {}


def test_get_agents_with_data(client: TestClient, tracer: Tracer) -> None:
    """Test getting agents when they exist."""
    tracer.log_agent_creation("agent-1", "Test Agent", "Test task")
    
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "agent-1" in data["agents"]


def test_get_agent_not_found(client: TestClient) -> None:
    """Test getting a non-existent agent."""
    response = client.get("/api/agents/non-existent")
    assert response.status_code == 404


def test_get_agent_found(client: TestClient, tracer: Tracer) -> None:
    """Test getting an existing agent."""
    tracer.log_agent_creation("agent-1", "Test Agent", "Test task")
    
    response = client.get("/api/agents/agent-1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "agent-1"
    assert data["name"] == "Test Agent"


def test_get_agent_messages(client: TestClient, tracer: Tracer) -> None:
    """Test getting agent messages."""
    tracer.log_agent_creation("agent-1", "Test Agent", "Test task")
    tracer.log_chat_message("Hello", "user", "agent-1")
    
    response = client.get("/api/agents/agent-1/messages")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello"


def test_get_agent_tools(client: TestClient, tracer: Tracer) -> None:
    """Test getting agent tools."""
    tracer.log_agent_creation("agent-1", "Test Agent", "Test task")
    tracer.log_tool_execution_start("agent-1", "test_tool", {"arg": "value"})
    
    response = client.get("/api/agents/agent-1/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) == 1
    assert data["tools"][0]["tool_name"] == "test_tool"


def test_get_vulnerabilities_empty(client: TestClient) -> None:
    """Test getting vulnerabilities when none exist."""
    response = client.get("/api/vulnerabilities")
    assert response.status_code == 200
    data = response.json()
    assert "vulnerabilities" in data
    assert data["vulnerabilities"] == []


def test_get_vulnerabilities_with_data(client: TestClient, tracer: Tracer) -> None:
    """Test getting vulnerabilities when they exist."""
    tracer.add_vulnerability_report("Test Vuln", "Test content", "high")
    
    response = client.get("/api/vulnerabilities")
    assert response.status_code == 200
    data = response.json()
    assert "vulnerabilities" in data
    assert len(data["vulnerabilities"]) == 1
    assert data["vulnerabilities"][0]["title"] == "Test Vuln"


def test_get_stats(client: TestClient, tracer: Tracer) -> None:
    """Test getting stats."""
    tracer.log_agent_creation("agent-1", "Test Agent", "Test task")
    tracer.log_tool_execution_start("agent-1", "test_tool", {})
    
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "tools" in data
    assert "vulnerabilities" in data
    assert "llm_stats" in data
    assert data["agents"] == 1
    assert data["tools"] == 1


def test_send_message_agent_not_found(client: TestClient) -> None:
    """Test sending message to non-existent agent."""
    response = client.post(
        "/api/agents/non-existent/message",
        json={"content": "Hello"}
    )
    assert response.status_code == 404


def test_stop_agent_not_found(client: TestClient) -> None:
    """Test stopping non-existent agent."""
    response = client.post("/api/agents/non-existent/stop")
    assert response.status_code == 404


def test_websocket_connection(client: TestClient) -> None:
    """Test WebSocket connection."""
    with client.websocket_connect("/ws") as websocket:
        # Should receive initial state or ping
        data = websocket.receive_json()
        assert "type" in data

