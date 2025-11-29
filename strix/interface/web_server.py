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

from strix.interface.scan_manager import ScanManager
from strix.interface.utils import (
    assign_workspace_subdirs,
    clone_repository,
    collect_local_sources,
    generate_run_name,
    infer_target_type,
)

logger = logging.getLogger(__name__)

# Thread-safe event queue for broadcasting
_event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
_event_processor_task: asyncio.Task[Any] | None = None


class WebSocketConnection:
    """Represents a WebSocket connection with subscribed scans."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.subscribed_scans: set[str] = set()  # Empty set means all scans


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocketConnection] = []

    async def connect(self, websocket: WebSocket) -> WebSocketConnection:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        conn = WebSocketConnection(websocket)
        self.active_connections.append(conn)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
        return conn

    def disconnect(self, conn: WebSocketConnection) -> None:
        """Remove a WebSocket connection."""
        if conn in self.active_connections:
            self.active_connections.remove(conn)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(
        self, event_type: str, data: dict[str, Any], scan_id: str | None = None
    ) -> None:
        """Broadcast an event to connected clients.
        
        If scan_id is provided, only send to clients subscribed to that scan.
        If scan_id is None, send to all clients.
        """
        if not self.active_connections:
            return

        message = {
            "type": event_type,
            "data": data,
            "scan_id": scan_id,
            "timestamp": asyncio.get_event_loop().time(),
        }

        message_json = json.dumps(message)
        disconnected: list[WebSocketConnection] = []

        for conn in self.active_connections:
            # If connection has no subscribed scans, send all events
            # Otherwise, only send if scan_id matches or is None
            if not conn.subscribed_scans or scan_id is None or scan_id in conn.subscribed_scans:
                try:
                    await conn.websocket.send_text(message_json)
                except Exception as e:
                    logger.warning(f"Failed to send message to WebSocket: {e}")
                    disconnected.append(conn)

        for conn in disconnected:
            self.disconnect(conn)


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
            scan_id = event.get("scan_id")

            # Broadcast based on event type
            if event_type == "agent_created":
                await websocket_manager.broadcast("agent_created", data, scan_id)
            elif event_type == "agent_updated":
                await websocket_manager.broadcast("agent_updated", data, scan_id)
            elif event_type == "message":
                await websocket_manager.broadcast("message", data, scan_id)
            elif event_type == "tool_execution":
                await websocket_manager.broadcast("tool_execution", data, scan_id)
            elif event_type == "vulnerability_found":
                await websocket_manager.broadcast("vulnerability_found", data, scan_id)
            elif event_type == "stats_updated":
                await websocket_manager.broadcast("stats_updated", data, scan_id)
            elif event_type == "scan_created":
                await websocket_manager.broadcast("scan_created", data, scan_id)
            elif event_type == "scan_updated":
                await websocket_manager.broadcast("scan_updated", data, scan_id)
            elif event_type == "scan_deleted":
                await websocket_manager.broadcast("scan_deleted", data, scan_id)
            elif event_type == "status_message":
                await websocket_manager.broadcast("status_message", data, scan_id)

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
_nextjs_build_path: Path | None = None


def setup_static_files(web_assets_path: Path) -> None:
    """Setup static files serving."""
    global _web_assets_path, _nextjs_build_path
    _web_assets_path = web_assets_path

    # Check for Next.js build
    project_root = Path(__file__).parent.parent.parent.parent
    nextjs_build = project_root / "frontend" / ".next"
    nextjs_standalone = nextjs_build / "standalone"
    
    if nextjs_standalone.exists():
        _nextjs_build_path = nextjs_standalone
        # Serve Next.js static files
        nextjs_static = nextjs_build / "static"
        if nextjs_static.exists():
            app.mount("/_next/static", StaticFiles(directory=str(nextjs_static)), name="nextjs-static")
        # Serve other Next.js assets from standalone
        standalone_next = nextjs_standalone / "_next"
        if standalone_next.exists():
            app.mount("/_next", StaticFiles(directory=str(standalone_next)), name="nextjs")
    else:
        # Fallback to legacy static files
        static_dir = web_assets_path / "static"
        if web_assets_path.exists() and static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve the main HTML file (Next.js or legacy)."""
    # Try Next.js build first
    if _nextjs_build_path:
        nextjs_html = _nextjs_build_path / "index.html"
        if nextjs_html.exists():
            return FileResponse(str(nextjs_html))
    
    # Fallback to legacy HTML
    if _web_assets_path is None:
        raise HTTPException(status_code=500, detail="Web assets not configured")

    index_path = _web_assets_path / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")

    return FileResponse(str(index_path))


# REST API Endpoints

# Scan Management Endpoints


class CreateScanRequest(BaseModel):
    """Request model for creating a scan."""

    targets: list[str]
    user_instructions: str = ""
    run_name: str | None = None
    max_iterations: int = 300


class MessageRequest(BaseModel):
    """Request model for sending a message."""

    content: str


@app.get("/api/scans")
async def list_scans() -> dict[str, Any]:
    """List all scans."""
    scan_manager = ScanManager.get_instance()
    scans = scan_manager.list_scans()
    return {"scans": scans}


@app.post("/api/scans")
async def create_scan(request: CreateScanRequest) -> dict[str, Any]:
    """Create a new scan."""
    scan_manager = ScanManager.get_instance()

    # Process targets
    targets_info = []
    for target in request.targets:
        try:
            target_type, target_dict = infer_target_type(target)
            display_target = (
                target_dict.get("target_path", target)
                if target_type == "local_code"
                else target
            )
            targets_info.append(
                {"type": target_type, "details": target_dict, "original": display_target}
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid target '{target}': {e}") from e

    assign_workspace_subdirs(targets_info)

    # Generate run name if not provided
    run_name = request.run_name or generate_run_name(targets_info)

    # Clone repositories if needed
    for target_info in targets_info:
        if target_info["type"] == "repository":
            repo_url = target_info["details"]["target_repo"]
            dest_name = target_info["details"].get("workspace_subdir")
            cloned_path = clone_repository(repo_url, run_name, dest_name)
            target_info["details"]["cloned_repo_path"] = cloned_path

    # Collect local sources
    local_sources = collect_local_sources(targets_info)

    # Create scan
    scan_id = scan_manager.create_scan(
        targets=targets_info,
        user_instructions=request.user_instructions,
        run_name=run_name,
        max_iterations=request.max_iterations,
        local_sources=local_sources,
    )

    scan_info = scan_manager.get_scan(scan_id)
    if scan_info:
        await websocket_manager.broadcast(
            "scan_created",
            scan_info.to_dict(),
            scan_id,
        )

    asyncio.create_task(scan_manager.start_scan(scan_id))

    scan_info = scan_manager.get_scan(scan_id)
    if scan_info:
        return scan_info.to_dict()
    return {"scan_id": scan_id, "status": "created"}


@app.get("/api/scans/{scan_id}")
async def get_scan(scan_id: str) -> dict[str, Any]:
    """Get details of a specific scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    return scan_info.to_dict()


@app.post("/api/scans/{scan_id}/stop")
async def stop_scan(scan_id: str) -> dict[str, Any]:
    """Stop a running scan."""
    scan_manager = ScanManager.get_instance()
    success = scan_manager.stop_scan(scan_id)
    if not success:
        raise HTTPException(
            status_code=400, detail=f"Scan {scan_id} cannot be stopped (not running)"
        )

    # Broadcast scan updated event
    scan_info = scan_manager.get_scan(scan_id)
    if scan_info:
        await websocket_manager.broadcast(
            "scan_updated",
            scan_info.to_dict(),
            scan_id,
        )

    return {"success": True, "message": f"Scan {scan_id} stopped"}


@app.delete("/api/scans/{scan_id}")
async def delete_scan(scan_id: str) -> dict[str, Any]:
    """Delete a scan and all its associated data."""
    scan_manager = ScanManager.get_instance()
    
    # Check if scan exists
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    
    # Delete the scan
    success = scan_manager.delete_scan(scan_id)
    if not success:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete scan {scan_id}"
        )
    
    # Broadcast scan deleted event
    await websocket_manager.broadcast(
        "scan_deleted",
        {"scan_id": scan_id},
        scan_id,
    )
    
    return {"success": True, "message": f"Scan {scan_id} deleted successfully"}


def _transform_agents(agents_dict: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Transform agents dict to ensure agent_id field exists."""
    transformed = {}
    for agent_id, agent_data in agents_dict.items():
        transformed_agent = dict(agent_data)
        if "id" in transformed_agent and "agent_id" not in transformed_agent:
            transformed_agent["agent_id"] = transformed_agent["id"]
        transformed[agent_id] = transformed_agent
    return transformed


@app.get("/api/scans/{scan_id}/agents")
async def get_scan_agents(scan_id: str) -> dict[str, Any]:
    """Get all agents for a specific scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    return {"agents": _transform_agents(scan_info.tracer.agents)}


@app.get("/api/scans/{scan_id}/agents/{agent_id}")
async def get_scan_agent(scan_id: str, agent_id: str) -> dict[str, Any]:
    """Get details of a specific agent in a scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    if agent_id not in scan_info.tracer.agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    agent_data = dict(scan_info.tracer.agents[agent_id])
    if "id" in agent_data and "agent_id" not in agent_data:
        agent_data["agent_id"] = agent_data["id"]

    return agent_data


@app.get("/api/scans/{scan_id}/agents/{agent_id}/messages")
async def get_scan_agent_messages(scan_id: str, agent_id: str) -> dict[str, Any]:
    """Get messages for a specific agent in a scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    messages = [
        msg for msg in scan_info.tracer.chat_messages if msg.get("agent_id") == agent_id
    ]
    return {"messages": messages}


@app.get("/api/scans/{scan_id}/agents/{agent_id}/tools")
async def get_scan_agent_tools(scan_id: str, agent_id: str) -> dict[str, Any]:
    """Get tool executions for a specific agent in a scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    tools = scan_info.tracer.get_agent_tools(agent_id)
    return {"tools": tools}


@app.get("/api/scans/{scan_id}/vulnerabilities")
async def get_scan_vulnerabilities(scan_id: str) -> dict[str, Any]:
    """Get all vulnerabilities for a specific scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    return {"vulnerabilities": scan_info.tracer.vulnerability_reports}


@app.get("/api/scans/{scan_id}/stats")
async def get_scan_stats(scan_id: str) -> dict[str, Any]:
    """Get statistics for a specific scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    llm_stats = scan_info.tracer.get_total_llm_stats()
    total_stats = llm_stats.get("total", {})

    return {
        "agents": len(scan_info.tracer.agents),
        "tools": scan_info.tracer.get_real_tool_count(),
        "vulnerabilities": len(scan_info.tracer.vulnerability_reports),
        "llm_stats": {
            "input_tokens": total_stats.get("input_tokens", 0),
            "output_tokens": total_stats.get("output_tokens", 0),
            "cached_tokens": total_stats.get("cached_tokens", 0),
            "cost": total_stats.get("cost", 0.0),
        },
    }


@app.post("/api/scans/{scan_id}/agents/{agent_id}/message")
async def send_scan_agent_message(
    scan_id: str, agent_id: str, request: MessageRequest
) -> dict[str, Any]:
    """Send a message to an agent in a specific scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    if agent_id not in scan_info.tracer.agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # Log the message
    # Note: The broadcast is handled automatically by the tracer callback
    # (wrapped_log_chat_message in scan_manager.py), so we don't need to broadcast here
    message_id = scan_info.tracer.log_chat_message(
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

    return {"success": True, "message_id": message_id}


@app.post("/api/scans/{scan_id}/agents/{agent_id}/stop")
async def stop_scan_agent(scan_id: str, agent_id: str) -> dict[str, Any]:
    """Stop an agent in a specific scan."""
    scan_manager = ScanManager.get_instance()
    scan_info = scan_manager.get_scan(scan_id)
    if not scan_info:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    if agent_id not in scan_info.tracer.agents:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    try:
        from strix.tools.agents_graph.agents_graph_actions import stop_agent

        result = stop_agent(agent_id)
        if result.get("success"):
            scan_info.tracer.update_agent_status(agent_id, "stopped")
            await websocket_manager.broadcast(
                "agent_updated",
                {"agent_id": agent_id, "status": "stopped"},
                scan_id,
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
    """WebSocket endpoint for real-time updates.
    
    Clients can subscribe to specific scans by sending a subscribe message.
    """
    conn = await websocket_manager.connect(websocket)
    
    # Check if scan_id is provided in query string (for backward compatibility)
    scan_id = None
    try:
        query_string = websocket.url.query
        if query_string:
            from urllib.parse import parse_qs
            params = parse_qs(query_string)
            if "scan_id" in params:
                scan_id = params["scan_id"][0]
                conn.subscribed_scans.add(scan_id)
    except Exception:
        pass  # Ignore errors parsing query string
    
    # Subscribe to specific scan if provided
    if scan_id:
        conn.subscribed_scans.add(scan_id)
        scan_manager = ScanManager.get_instance()
        scan_info = scan_manager.get_scan(scan_id)
        if scan_info:
            # Send initial state for this scan
            await websocket.send_json(
                {
                    "type": "initial_state",
                    "scan_id": scan_id,
                    "data": {
                        "agents": _transform_agents(scan_info.tracer.agents),
                        "vulnerabilities": scan_info.tracer.vulnerability_reports,
                        "stats": {
                            "agents": len(scan_info.tracer.agents),
                            "tools": scan_info.tracer.get_real_tool_count(),
                            "vulnerabilities": len(scan_info.tracer.vulnerability_reports),
                        },
                    },
                }
            )
    else:
        # Send all scans list
        scan_manager = ScanManager.get_instance()
        scans = scan_manager.list_scans()
        await websocket.send_json(
            {
                "type": "initial_state",
                "data": {
                    "scans": scans,
                },
            }
        )

    # Keep connection alive and handle incoming messages
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                try:
                    message = json.loads(data)
                    # Handle subscription messages
                    if message.get("type") == "subscribe":
                        scan_ids = message.get("scan_ids", [])
                        if scan_ids:
                            conn.subscribed_scans.update(scan_ids)
                        else:
                            conn.subscribed_scans.clear()  # Subscribe to all
                    elif message.get("type") == "unsubscribe":
                        scan_ids = message.get("scan_ids", [])
                        for sid in scan_ids:
                            conn.subscribed_scans.discard(sid)
                except (json.JSONDecodeError, KeyError):
                    # Handle ping/pong
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
        websocket_manager.disconnect(conn)


# Event broadcasting functions (called from Tracer/ScanManager)
# These functions are thread-safe and can be called from any thread


def broadcast_agent_created(
    scan_id: str, agent_id: str, agent_data: dict[str, Any]
) -> None:
    """Broadcast agent creation event (thread-safe)."""
    _event_queue.put(
        {
            "type": "agent_created",
            "scan_id": scan_id,
            "data": {"agent_id": agent_id, **agent_data},
        }
    )


def broadcast_agent_updated(scan_id: str, agent_id: str, updates: dict[str, Any]) -> None:
    """Broadcast agent update event (thread-safe)."""
    _event_queue.put(
        {"type": "agent_updated", "scan_id": scan_id, "data": {"agent_id": agent_id, **updates}}
    )


def broadcast_message(scan_id: str, agent_id: str, message_data: dict[str, Any]) -> None:
    """Broadcast new message event (thread-safe)."""
    _event_queue.put(
        {"type": "message", "scan_id": scan_id, "data": {"agent_id": agent_id, **message_data}}
    )


def broadcast_tool_execution(scan_id: str, agent_id: str, tool_data: dict[str, Any]) -> None:
    """Broadcast tool execution event (thread-safe)."""
    _event_queue.put(
        {"type": "tool_execution", "scan_id": scan_id, "data": {"agent_id": agent_id, **tool_data}}
    )


def broadcast_vulnerability(scan_id: str, report_id: str, vuln_data: dict[str, Any]) -> None:
    """Broadcast vulnerability found event (thread-safe)."""
    _event_queue.put(
        {
            "type": "vulnerability_found",
            "scan_id": scan_id,
            "data": {"report_id": report_id, **vuln_data},
        }
    )


def broadcast_stats(scan_id: str, stats: dict[str, Any]) -> None:
    """Broadcast stats update event (thread-safe)."""
    _event_queue.put({"type": "stats_updated", "scan_id": scan_id, "data": stats})

