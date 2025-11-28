"""Web server for Strix web interface."""

import asyncio
import json
import logging
import queue
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from strix.telemetry.tracer import get_global_tracer

logger = logging.getLogger(__name__)

# Thread-safe event queue for broadcasting
_event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
_event_processor_task: asyncio.Task[Any] | None = None


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event to all connected clients."""
        if not self.active_connections:
            return

        message = {
            "type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time(),
        }

        message_json = json.dumps(message)
        disconnected: list[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


# Global WebSocket manager
websocket_manager = WebSocketManager()


async def process_event_queue() -> None:
    """Process events from the thread-safe queue and broadcast via WebSocket."""
    while True:
        try:
            # Get event from queue (with timeout to allow checking for shutdown)
            try:
                event = _event_queue.get(timeout=0.5)
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue

            event_type = event.get("type")
            data = event.get("data", {})

            # Broadcast based on event type
            if event_type == "agent_created":
                await websocket_manager.broadcast("agent_created", data)
            elif event_type == "agent_updated":
                await websocket_manager.broadcast("agent_updated", data)
            elif event_type == "message":
                await websocket_manager.broadcast("message", data)
            elif event_type == "tool_execution":
                await websocket_manager.broadcast("tool_execution", data)
            elif event_type == "vulnerability_found":
                await websocket_manager.broadcast("vulnerability_found", data)
            elif event_type == "stats_updated":
                await websocket_manager.broadcast("stats_updated", data)

            _event_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Error processing event queue: {e}")
            await asyncio.sleep(0.1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Lifespan context manager for FastAPI app."""
    # Startup
    global _event_processor_task
    _event_processor_task = asyncio.create_task(process_event_queue())
    yield
    # Shutdown
    if _event_processor_task:
        _event_processor_task.cancel()
        try:
            await _event_processor_task
        except asyncio.CancelledError:
            pass


# FastAPI app with lifespan
app = FastAPI(title="Strix Web Interface", version="0.4.0", lifespan=lifespan)

# Static files will be mounted after app creation
_web_assets_path: Path | None = None


def setup_static_files(web_assets_path: Path) -> None:
    """Setup static files serving."""
    global _web_assets_path
    _web_assets_path = web_assets_path

    static_dir = web_assets_path / "static"
    if web_assets_path.exists() and static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve the main HTML file."""
    if _web_assets_path is None:
        raise HTTPException(status_code=500, detail="Web assets not configured")

    index_path = _web_assets_path / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")

    return FileResponse(str(index_path))


# REST API Endpoints


@app.get("/api/agents")
async def get_agents() -> dict[str, Any]:
    """Get all agents."""
    tracer = get_global_tracer()
    if not tracer:
        return {"agents": {}}

    return {"agents": tracer.agents}


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    """Get details of a specific agent."""
    tracer = get_global_tracer()
    if not tracer:
        raise HTTPException(status_code=404, detail="Tracer not available")

    if agent_id not in tracer.agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return tracer.agents[agent_id]


@app.get("/api/agents/{agent_id}/messages")
async def get_agent_messages(agent_id: str) -> dict[str, Any]:
    """Get messages for a specific agent."""
    tracer = get_global_tracer()
    if not tracer:
        return {"messages": []}

    messages = [msg for msg in tracer.chat_messages if msg.get("agent_id") == agent_id]
    return {"messages": messages}


@app.get("/api/agents/{agent_id}/tools")
async def get_agent_tools(agent_id: str) -> dict[str, Any]:
    """Get tool executions for a specific agent."""
    tracer = get_global_tracer()
    if not tracer:
        return {"tools": []}

    tools = tracer.get_agent_tools(agent_id)
    return {"tools": tools}


@app.get("/api/vulnerabilities")
async def get_vulnerabilities() -> dict[str, Any]:
    """Get all vulnerabilities."""
    tracer = get_global_tracer()
    if not tracer:
        return {"vulnerabilities": []}

    return {"vulnerabilities": tracer.vulnerability_reports}


@app.get("/api/stats")
async def get_stats() -> dict[str, Any]:
    """Get general statistics."""
    tracer = get_global_tracer()
    if not tracer:
        return {
            "agents": 0,
            "tools": 0,
            "vulnerabilities": 0,
            "llm_stats": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "cost": 0.0,
            },
        }

    llm_stats = tracer.get_total_llm_stats()
    total_stats = llm_stats.get("total", {})

    return {
        "agents": len(tracer.agents),
        "tools": tracer.get_real_tool_count(),
        "vulnerabilities": len(tracer.vulnerability_reports),
        "llm_stats": {
            "input_tokens": total_stats.get("input_tokens", 0),
            "output_tokens": total_stats.get("output_tokens", 0),
            "cached_tokens": total_stats.get("cached_tokens", 0),
            "cost": total_stats.get("cost", 0.0),
        },
    }


class MessageRequest(BaseModel):
    """Request model for sending a message."""

    content: str


@app.post("/api/agents/{agent_id}/message")
async def send_agent_message(agent_id: str, request: MessageRequest) -> dict[str, Any]:
    """Send a message to an agent."""
    tracer = get_global_tracer()
    if not tracer:
        raise HTTPException(status_code=500, detail="Tracer not available")

    if agent_id not in tracer.agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # Log the message
    message_id = tracer.log_chat_message(
        content=request.content,
        role="user",
        agent_id=agent_id,
    )

    # Send message to agent via agents_graph
    try:
        from strix.tools.agents_graph.agents_graph_actions import send_user_message_to_agent

        send_user_message_to_agent(agent_id, request.content)
    except (ImportError, AttributeError) as e:
        logger.warning(f"Failed to send message to agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {e}") from e

    # Broadcast via WebSocket
    await websocket_manager.broadcast(
        "message",
        {
            "agent_id": agent_id,
            "message_id": message_id,
            "role": "user",
            "content": request.content,
        },
    )

    return {"success": True, "message_id": message_id}


@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str) -> dict[str, Any]:
    """Stop an agent."""
    tracer = get_global_tracer()
    if not tracer:
        raise HTTPException(status_code=500, detail="Tracer not available")

    if agent_id not in tracer.agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    try:
        from strix.tools.agents_graph.agents_graph_actions import stop_agent

        result = stop_agent(agent_id)
        if result.get("success"):
            tracer.update_agent_status(agent_id, "stopped")
            await websocket_manager.broadcast(
                "agent_updated",
                {"agent_id": agent_id, "status": "stopped"},
            )
            return {"success": True, "message": result.get("message", "Agent stopped")}
        else:
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to stop agent")
            )
    except (ImportError, AttributeError) as e:
        logger.warning(f"Failed to stop agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop agent: {e}") from e


# WebSocket endpoint


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time updates."""
    await websocket_manager.connect(websocket)
    try:
        # Send initial state
        tracer = get_global_tracer()
        if tracer:
            await websocket.send_json(
                {
                    "type": "initial_state",
                    "data": {
                        "agents": tracer.agents,
                        "vulnerabilities": tracer.vulnerability_reports,
                        "stats": {
                            "agents": len(tracer.agents),
                            "tools": tracer.get_real_tool_count(),
                            "vulnerabilities": len(tracer.vulnerability_reports),
                        },
                    },
                }
            )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle ping/pong or other client messages if needed
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        websocket_manager.disconnect(websocket)


# Event broadcasting functions (called from Tracer)
# These functions are thread-safe and can be called from any thread


def broadcast_agent_created(agent_id: str, agent_data: dict[str, Any]) -> None:
    """Broadcast agent creation event (thread-safe)."""
    _event_queue.put({"type": "agent_created", "data": {"agent_id": agent_id, **agent_data}})


def broadcast_agent_updated(agent_id: str, updates: dict[str, Any]) -> None:
    """Broadcast agent update event (thread-safe)."""
    _event_queue.put({"type": "agent_updated", "data": {"agent_id": agent_id, **updates}})


def broadcast_message(agent_id: str, message_data: dict[str, Any]) -> None:
    """Broadcast new message event (thread-safe)."""
    _event_queue.put({"type": "message", "data": {"agent_id": agent_id, **message_data}})


def broadcast_tool_execution(agent_id: str, tool_data: dict[str, Any]) -> None:
    """Broadcast tool execution event (thread-safe)."""
    _event_queue.put({"type": "tool_execution", "data": {"agent_id": agent_id, **tool_data}})


def broadcast_vulnerability(report_id: str, vuln_data: dict[str, Any]) -> None:
    """Broadcast vulnerability found event (thread-safe)."""
    _event_queue.put({"type": "vulnerability_found", "data": {"report_id": report_id, **vuln_data}})


def broadcast_stats(stats: dict[str, Any]) -> None:
    """Broadcast stats update event (thread-safe)."""
    _event_queue.put({"type": "stats_updated", "data": stats})

