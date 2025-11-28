"""Web interface for Strix."""

import argparse
import asyncio
import atexit
import logging
import signal
import sys
import threading
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import uvicorn
from strix.agents.StrixAgent import StrixAgent
from strix.interface.scan_manager import ScanManager
from strix.interface.web_server import (
    app,
    broadcast_agent_created_legacy,
    broadcast_agent_updated_legacy,
    broadcast_message_legacy,
    broadcast_stats_legacy,
    broadcast_tool_execution_legacy,
    broadcast_vulnerability_legacy,
    setup_static_files,
)
from strix.llm.config import LLMConfig
from strix.telemetry.tracer import Tracer, get_global_tracer, set_global_tracer

logger = logging.getLogger(__name__)


def _build_scan_config(args: argparse.Namespace) -> dict[str, Any]:
    """Build scan configuration from arguments."""
    return {
        "scan_id": args.run_name,
        "targets": args.targets_info,
        "user_instructions": args.instruction or "",
        "run_name": args.run_name,
    }


def _build_agent_config(args: argparse.Namespace) -> dict[str, Any]:
    """Build agent configuration from arguments."""
    llm_config = LLMConfig()

    config = {
        "llm_config": llm_config,
        "max_iterations": 300,
    }

    if getattr(args, "local_sources", None):
        config["local_sources"] = args.local_sources

    return config


async def run_web(args: argparse.Namespace) -> None:
    """Run Strix in web mode."""
    # Setup web assets path
    # Try to find web_assets directory relative to this file first (development mode)
    web_assets_path = Path(__file__).parent / "web_assets"
    
    # If not found, try to find it in the installed package location
    if not web_assets_path.exists():
        # Try to find the strix.interface module location
        spec = find_spec("strix.interface")
        if spec and spec.origin:
            # Get the directory containing the interface module
            interface_dir = Path(spec.origin).parent
            candidate = interface_dir / "web_assets"
            if candidate.exists():
                web_assets_path = candidate
    
    setup_static_files(web_assets_path)

    # Create tracer
    scan_config = _build_scan_config(args)
    agent_config = _build_agent_config(args)

    tracer = Tracer(scan_config["run_name"])
    tracer.set_scan_config(scan_config)
    set_global_tracer(tracer)

    # Setup event callbacks for WebSocket broadcasting
    _setup_tracer_callbacks(tracer)

    # Setup cleanup handlers
    def cleanup_on_exit() -> None:
        tracer.cleanup()

    def signal_handler(_signum: int, _frame: Any) -> None:
        tracer.cleanup()
        sys.exit(0)

    atexit.register(cleanup_on_exit)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal_handler)

    # Get web server configuration
    web_host = getattr(args, "web_host", "127.0.0.1")
    web_port = getattr(args, "web_port", 8080)

    # Start web server in a thread
    server_thread = threading.Thread(
        target=_run_server,
        args=(web_host, web_port),
        daemon=False,  # Not a daemon so it keeps the process alive
    )
    server_thread.start()

    logger.info(f"Web interface available at http://{web_host}:{web_port}")
    logger.info("Starting scan...")

    # Run scan in async context
    try:
        agent = StrixAgent(agent_config)
        await agent.execute_scan(scan_config)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Scan interrupted by user")
    except Exception as e:
        logger.exception(f"Error during scan: {e}")
        raise
    finally:
        tracer.cleanup()
        # Keep the process alive by waiting for the server thread
        # This allows the web interface to remain accessible after scan completion
        logger.info("Scan completed. Web interface remains available.")
        logger.info("Press Ctrl+C to stop the server.")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            logger.info("Shutting down web server...")


def _run_server(host: str, port: int) -> None:
    """Run the uvicorn server."""
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except Exception as e:
        logger.exception(f"Error running web server: {e}")


def _setup_tracer_callbacks(tracer: Tracer) -> None:
    """Setup callbacks on tracer to broadcast events via WebSocket."""

    # Store original methods
    original_log_agent_creation = tracer.log_agent_creation
    original_update_agent_status = tracer.update_agent_status
    original_log_chat_message = tracer.log_chat_message
    original_log_tool_execution_start = tracer.log_tool_execution_start
    original_update_tool_execution = tracer.update_tool_execution
    original_add_vulnerability_report = tracer.add_vulnerability_report

    # Broadcasting functions are now thread-safe (use queue), so we can call them directly
    # Wrap log_agent_creation
    def wrapped_log_agent_creation(
        agent_id: str, name: str, task: str, parent_id: str | None = None
    ) -> None:
        original_log_agent_creation(agent_id, name, task, parent_id)
        agent_data = tracer.agents.get(agent_id, {})
        try:
            broadcast_agent_created_legacy(agent_id, agent_data)
        except Exception:
            pass  # Ignore errors in broadcasting

    # Wrap update_agent_status
    def wrapped_update_agent_status(
        agent_id: str, status: str, error_message: str | None = None
    ) -> None:
        original_update_agent_status(agent_id, status, error_message)
        updates = {"status": status}
        if error_message:
            updates["error_message"] = error_message
        try:
            broadcast_agent_updated_legacy(agent_id, updates)
        except Exception:
            pass  # Ignore errors in broadcasting

    # Wrap log_chat_message
    def wrapped_log_chat_message(
        content: str,
        role: str,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        message_id = original_log_chat_message(content, role, agent_id, metadata)
        if agent_id:
            message_data = {
                "message_id": message_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
            }
            try:
                broadcast_message_legacy(agent_id, message_data)
            except Exception:
                pass  # Ignore errors in broadcasting
        return message_id

    # Wrap log_tool_execution_start
    def wrapped_log_tool_execution_start(
        agent_id: str, tool_name: str, args: dict[str, Any]
    ) -> int:
        execution_id = original_log_tool_execution_start(agent_id, tool_name, args)
        tool_data = {
            "execution_id": execution_id,
            "tool_name": tool_name,
            "args": args,
            "status": "running",
        }
        try:
            broadcast_tool_execution_legacy(agent_id, tool_data)
        except Exception:
            pass  # Ignore errors in broadcasting
        return execution_id

    # Wrap update_tool_execution
    def wrapped_update_tool_execution(
        execution_id: int, status: str, result: Any | None = None
    ) -> None:
        original_update_tool_execution(execution_id, status, result)
        tool_data = tracer.tool_executions.get(execution_id)
        if tool_data:
            agent_id = tool_data.get("agent_id")
            if agent_id:
                tool_data = {
                    "execution_id": execution_id,
                    "tool_name": tool_data.get("tool_name"),
                    "status": status,
                    "result": result,
                }
                try:
                    broadcast_tool_execution_legacy(agent_id, tool_data)
                except Exception:
                    pass  # Ignore errors in broadcasting

    # Wrap add_vulnerability_report
    def wrapped_add_vulnerability_report(
        title: str, content: str, severity: str
    ) -> str:
        report_id = original_add_vulnerability_report(title, content, severity)
        vuln_data = {
            "id": report_id,
            "title": title,
            "content": content,
            "severity": severity,
        }
        try:
            broadcast_vulnerability_legacy(report_id, vuln_data)
        except Exception:
            pass  # Ignore errors in broadcasting
        return report_id

    # Replace methods
    tracer.log_agent_creation = wrapped_log_agent_creation
    tracer.update_agent_status = wrapped_update_agent_status
    tracer.log_chat_message = wrapped_log_chat_message
    tracer.log_tool_execution_start = wrapped_log_tool_execution_start
    tracer.update_tool_execution = wrapped_update_tool_execution
    tracer.add_vulnerability_report = wrapped_add_vulnerability_report

    # Setup periodic stats updates
    def update_stats_periodically() -> None:
        while True:
            try:
                import time

                time.sleep(2)  # Update every 2 seconds
                current_tracer = get_global_tracer()
                if current_tracer:
                    llm_stats = current_tracer.get_total_llm_stats()
                    stats = {
                        "agents": len(current_tracer.agents),
                        "tools": current_tracer.get_real_tool_count(),
                        "vulnerabilities": len(current_tracer.vulnerability_reports),
                        "llm_stats": llm_stats.get("total", {}),
                    }
                    try:
                        broadcast_stats_legacy(stats)
                    except Exception:
                        pass  # Ignore errors in broadcasting
            except Exception as e:
                logger.warning(f"Error in stats update thread: {e}")

    stats_thread = threading.Thread(target=update_stats_periodically, daemon=True)
    stats_thread.start()


def run_server_only(web_host: str = "127.0.0.1", web_port: int = 8080) -> None:
    """Run web server only without starting a scan."""
    # Setup web assets path
    web_assets_path = Path(__file__).parent / "web_assets"
    
    # If not found, try to find it in the installed package location
    if not web_assets_path.exists():
        spec = find_spec("strix.interface")
        if spec and spec.origin:
            interface_dir = Path(spec.origin).parent
            candidate = interface_dir / "web_assets"
            if candidate.exists():
                web_assets_path = candidate
    
    setup_static_files(web_assets_path)

    # Load existing scans from disk
    scan_manager = ScanManager.get_instance()
    scan_manager.load_scans_from_disk()
    logger.info(f"Loaded {len(scan_manager.list_scans())} existing scan(s) from disk")

    # Get web server configuration
    logger.info(f"Web interface available at http://{web_host}:{web_port}")
    logger.info("Server running. Use the web interface to create new scans.")

    # Run server (this will block)
    try:
        uvicorn.run(app, host=web_host, port=web_port, log_level="info")
    except KeyboardInterrupt:
        logger.info("Shutting down web server...")
    except Exception as e:
        logger.exception(f"Error running web server: {e}")
        raise

