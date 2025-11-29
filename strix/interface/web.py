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
from strix.interface.web_server import app, setup_static_files
from strix.interface.utils import (
    assign_workspace_subdirs,
    clone_repository,
    collect_local_sources,
    generate_run_name,
    infer_target_type,
)
from strix.llm.config import LLMConfig

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

    # Load existing scans from disk
    scan_manager = ScanManager.get_instance()
    scan_manager.load_scans_from_disk()

    # Process targets
    targets_info = []
    for target in args.targets_info:
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
            logger.error(f"Invalid target '{target}': {e}")
            raise

    assign_workspace_subdirs(targets_info)

    # Generate run name if not provided
    run_name = args.run_name or generate_run_name(targets_info)

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
        user_instructions=args.instruction or "",
        run_name=run_name,
        max_iterations=300,
        local_sources=local_sources,
    )

    # Setup cleanup handlers
    def cleanup_on_exit() -> None:
        scan_info = scan_manager.get_scan(scan_id)
        if scan_info and scan_info.tracer:
            scan_info.tracer.cleanup()

    def signal_handler(_signum: int, _frame: Any) -> None:
        cleanup_on_exit()
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
    logger.info(f"Starting scan {scan_id}...")

    # Start scan and await the task
    scan_task = None
    try:
        scan_task = await scan_manager.start_scan(scan_id)
        await scan_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Scan interrupted by user")
        if scan_task:
            scan_task.cancel()
            try:
                await scan_task
            except asyncio.CancelledError:
                pass
        scan_manager.stop_scan(scan_id)
    except Exception as e:
        logger.exception(f"Error during scan: {e}")
        raise
    finally:
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

