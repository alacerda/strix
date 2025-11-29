"""Scan Manager for managing multiple scans simultaneously."""

import asyncio
import json
import logging
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from strix.agents.StrixAgent import StrixAgent
from strix.llm.config import LLMConfig
from strix.telemetry.tracer import (
    Tracer,
    get_context_tracer,
    get_global_tracer,
    set_context_tracer,
    set_global_tracer,
)

logger = logging.getLogger(__name__)


class ScanInfo:
    """Information about a scan."""

    def __init__(
        self,
        scan_id: str,
        tracer: Tracer,
        agent: Optional[StrixAgent],
        scan_config: dict[str, Any],
        agent_config: dict[str, Any],
        task: Optional[asyncio.Task] = None,
    ):
        self.scan_id = scan_id
        self.tracer = tracer
        self.agent = agent
        self.scan_config = scan_config
        self.agent_config = agent_config
        self.task = task
        self.status = "created"
        self.start_time = datetime.now(UTC).isoformat()
        self.end_time: Optional[str] = None
        self.error: Optional[str] = None

    def _get_docker_info(self) -> dict[str, Any]:
        """Get Docker container information for this scan."""
        try:
            from strix.runtime.docker_runtime import DockerRuntime
            
            docker_runtime = DockerRuntime()
            return docker_runtime.get_scan_container_info(self.scan_id)
        except Exception as e:
            logger.debug(f"Failed to get Docker info for scan {self.scan_id}: {e}")
            return {
                "container_id": None,
                "container_name": None,
                "container_status": None,
            }

    def to_dict(self) -> dict[str, Any]:
        """Convert scan info to dictionary."""
        docker_info = self._get_docker_info()
        
        total_agents = len(self.tracer.agents) if self.tracer else 0
        running_agents = sum(
            1 for agent in (self.tracer.agents.values() if self.tracer else [])
            if agent.get("status") == "running"
        )
        
        result = {
            "scan_id": self.scan_id,
            "run_name": self.scan_config.get("run_name", self.scan_id),
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "targets": self.scan_config.get("targets", []),
            "user_instructions": self.scan_config.get("user_instructions", ""),
            "error": self.error,
            "container_id": docker_info["container_id"],
            "container_name": docker_info["container_name"],
            "container_status": docker_info["container_status"],
            "total_agents_count": total_agents,
            "running_agents_count": running_agents,
        }
        
        return result

    def save_metadata(self) -> None:
        """Save scan metadata to disk."""
        try:
            run_dir = self.tracer.get_run_dir()
            metadata_file = run_dir / "metadata.json"
            metadata = self.to_dict()
            metadata["config"] = {
                "max_iterations": self.agent_config.get("max_iterations", 300),
            }
            with metadata_file.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save metadata for scan {self.scan_id}: {e}")


class ScanManager:
    """Manages multiple scans simultaneously."""

    _instance: Optional["ScanManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._scans: dict[str, ScanInfo] = {}
        self._lock = threading.Lock()
        self._runs_dir = Path.cwd() / "strix_runs"

    @classmethod
    def get_instance(cls) -> "ScanManager":
        """Get singleton instance of ScanManager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_scan(
        self,
        targets: list[dict[str, Any]],
        user_instructions: str = "",
        run_name: Optional[str] = None,
        max_iterations: int = 300,
        local_sources: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """Create a new scan and return scan_id."""
        scan_id = run_name or f"scan-{uuid4().hex[:8]}"

        # Create tracer
        tracer = Tracer(scan_id)
        scan_config = {
            "scan_id": scan_id,
            "targets": targets,
            "user_instructions": user_instructions,
            "run_name": scan_id,
        }
        tracer.set_scan_config(scan_config)

        # Create agent config
        llm_config = LLMConfig()
        agent_config = {
            "llm_config": llm_config,
            "max_iterations": max_iterations,
            "tracer": tracer,
        }
        if local_sources:
            agent_config["local_sources"] = local_sources

        from strix.telemetry.tracer import set_context_tracer

        previous_context_tracer = None
        try:
            from strix.telemetry.tracer import get_context_tracer

            previous_context_tracer = get_context_tracer()
        except Exception:
            pass

        set_context_tracer(tracer)

        try:
            agent = StrixAgent(agent_config)
        finally:
            if previous_context_tracer is not None:
                set_context_tracer(previous_context_tracer)
            else:
                set_context_tracer(None)

        # Create scan info
        scan_info = ScanInfo(scan_id, tracer, agent, scan_config, agent_config)
        scan_info.status = "created"
        scan_info.save_metadata()

        with self._lock:
            self._scans[scan_id] = scan_info

        logger.info(f"Created scan {scan_id}")
        return scan_id

    async def start_scan(self, scan_id: str) -> None:
        """Start a scan execution."""
        with self._lock:
            scan_info = self._scans.get(scan_id)
            if not scan_info:
                raise ValueError(f"Scan {scan_id} not found")
            if scan_info.status not in ("created", "stopped"):
                raise ValueError(f"Scan {scan_id} cannot be started (status: {scan_info.status})")

        scan_info.status = "running"
        scan_info.start_time = datetime.now(UTC).isoformat()
        scan_info.save_metadata()

        # Setup periodic stats updates for this scan
        def update_stats_periodically() -> None:
            import time
            iteration_count = 0
            while scan_info.status == "running":
                try:
                    time.sleep(2)  # Update every 2 seconds
                    if scan_info.status != "running":
                        break
                    llm_stats = scan_info.tracer.get_total_llm_stats()
                    stats = {
                        "agents": len(scan_info.tracer.agents),
                        "tools": scan_info.tracer.get_real_tool_count(),
                        "vulnerabilities": len(scan_info.tracer.vulnerability_reports),
                        "llm_stats": llm_stats.get("total", {}),
                    }
                    try:
                        from strix.interface.web_server import broadcast_stats

                        broadcast_stats(scan_id, stats)
                    except Exception:
                        pass
                    
                    iteration_count += 1
                    if iteration_count >= 5:
                        try:
                            scan_info.tracer.save_trace_data()
                        except Exception:
                            pass
                        iteration_count = 0
                except Exception as e:
                    logger.warning(f"Error in stats update thread for scan {scan_id}: {e}")

        stats_thread = threading.Thread(target=update_stats_periodically, daemon=True)
        stats_thread.start()

        # Setup tracer callbacks for broadcasting
        from strix.interface.web_server import (
            broadcast_agent_created,
            broadcast_agent_updated,
            broadcast_message,
            broadcast_stats,
            broadcast_tool_execution,
            broadcast_vulnerability,
        )

        # Store original methods
        original_log_agent_creation = scan_info.tracer.log_agent_creation
        original_update_agent_status = scan_info.tracer.update_agent_status
        original_log_chat_message = scan_info.tracer.log_chat_message
        original_log_tool_execution_start = scan_info.tracer.log_tool_execution_start
        original_update_tool_execution = scan_info.tracer.update_tool_execution
        original_add_vulnerability_report = scan_info.tracer.add_vulnerability_report

        # Wrap methods to broadcast with scan_id
        def wrapped_log_agent_creation(
            agent_id: str, name: str, task: str, parent_id: str | None = None
        ) -> None:
            original_log_agent_creation(agent_id, name, task, parent_id)
            agent_data = scan_info.tracer.agents.get(agent_id, {})
            try:
                broadcast_agent_created(scan_id, agent_id, agent_data)
            except Exception:
                pass

        def wrapped_update_agent_status(
            agent_id: str, status: str, error_message: str | None = None
        ) -> None:
            original_update_agent_status(agent_id, status, error_message)
            updates = {"status": status}
            if error_message:
                updates["error_message"] = error_message
            try:
                broadcast_agent_updated(scan_id, agent_id, updates)
            except Exception:
                pass

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
                    broadcast_message(scan_id, agent_id, message_data)
                except Exception:
                    pass
            return message_id

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
                broadcast_tool_execution(scan_id, agent_id, tool_data)
            except Exception:
                pass
            return execution_id

        def wrapped_update_tool_execution(
            execution_id: int, status: str, result: Any | None = None
        ) -> None:
            original_update_tool_execution(execution_id, status, result)
            tool_data = scan_info.tracer.tool_executions.get(execution_id)
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
                        broadcast_tool_execution(scan_id, agent_id, tool_data)
                    except Exception:
                        pass

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
                broadcast_vulnerability(scan_id, report_id, vuln_data)
            except Exception:
                pass
            return report_id

        # Replace methods
        scan_info.tracer.log_agent_creation = wrapped_log_agent_creation
        scan_info.tracer.update_agent_status = wrapped_update_agent_status
        scan_info.tracer.log_chat_message = wrapped_log_chat_message
        scan_info.tracer.log_tool_execution_start = wrapped_log_tool_execution_start
        scan_info.tracer.update_tool_execution = wrapped_update_tool_execution
        scan_info.tracer.add_vulnerability_report = wrapped_add_vulnerability_report

        # Start scan in background task
        async def run_scan():
            from strix.telemetry.tracer import get_context_tracer, set_context_tracer

            previous_context_tracer = get_context_tracer()
            set_context_tracer(scan_info.tracer)
            try:
                await scan_info.agent.execute_scan(scan_info.scan_config)
                scan_info.status = "completed"
                scan_info.end_time = datetime.now(UTC).isoformat()
            except asyncio.CancelledError:
                scan_info.status = "stopped"
                scan_info.end_time = datetime.now(UTC).isoformat()
                logger.info(f"Scan {scan_id} stopped")
            except Exception as e:
                scan_info.status = "failed"
                scan_info.error = str(e)
                scan_info.end_time = datetime.now(UTC).isoformat()
                logger.exception(f"Scan {scan_id} failed: {e}")
            finally:
                if previous_context_tracer is not None:
                    set_context_tracer(previous_context_tracer)
                else:
                    set_context_tracer(None)
                scan_info.tracer.cleanup()
                scan_info.save_metadata()
                # Broadcast scan updated event (thread-safe via queue)
                try:
                    from strix.interface.web_server import _event_queue

                    _event_queue.put(
                        {
                            "type": "scan_updated",
                            "scan_id": scan_id,
                            "data": scan_info.to_dict(),
                        }
                    )
                except Exception:
                    pass
                # Broadcast final stats
                try:
                    from strix.interface.web_server import broadcast_stats

                    llm_stats = scan_info.tracer.get_total_llm_stats()
                    stats = {
                        "agents": len(scan_info.tracer.agents),
                        "tools": scan_info.tracer.get_real_tool_count(),
                        "vulnerabilities": len(scan_info.tracer.vulnerability_reports),
                        "llm_stats": llm_stats.get("total", {}),
                    }
                    broadcast_stats(scan_id, stats)
                except Exception:
                    pass

        task = asyncio.create_task(run_scan())
        scan_info.task = task

        logger.info(f"Started scan {scan_id}")

    def stop_scan(self, scan_id: str) -> bool:
        """Stop a running scan."""
        with self._lock:
            scan_info = self._scans.get(scan_id)
            if not scan_info:
                return False
            if scan_info.status != "running":
                return False

        if scan_info.task:
            scan_info.task.cancel()
        scan_info.status = "stopping"
        scan_info.save_metadata()
        logger.info(f"Stopping scan {scan_id}")
        return True

    def get_scan(self, scan_id: str) -> Optional[ScanInfo]:
        """Get scan info by scan_id."""
        with self._lock:
            return self._scans.get(scan_id)

    def list_scans(self) -> list[dict[str, Any]]:
        """List all scans."""
        with self._lock:
            return [scan_info.to_dict() for scan_info in self._scans.values()]

    def load_scans_from_disk(self) -> None:
        """Load scans from disk on startup."""
        if not self._runs_dir.exists():
            return

        for run_dir in self._runs_dir.iterdir():
            if not run_dir.is_dir():
                continue

            metadata_file = run_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            try:
                with metadata_file.open("r", encoding="utf-8") as f:
                    metadata = json.load(f)

                scan_id = metadata.get("scan_id") or metadata.get("run_name")
                if not scan_id:
                    continue

                # Create tracer from existing run
                tracer = Tracer(scan_id)
                scan_config = {
                    "scan_id": scan_id,
                    "targets": metadata.get("targets", []),
                    "user_instructions": metadata.get("user_instructions", ""),
                    "run_name": scan_id,
                }
                tracer.set_scan_config(scan_config)

                # Create agent config
                llm_config = LLMConfig()
                config_data = metadata.get("config", {})
                agent_config = {
                    "llm_config": llm_config,
                    "max_iterations": config_data.get("max_iterations", 300),
                }

                # Create scan info (without agent since scan is already done)
                scan_info = ScanInfo(scan_id, tracer, None, scan_config, agent_config)
                scan_info.status = metadata.get("status", "completed")
                scan_info.start_time = metadata.get("start_time", datetime.now(UTC).isoformat())
                scan_info.end_time = metadata.get("end_time")
                scan_info.error = metadata.get("error")

                with self._lock:
                    self._scans[scan_id] = scan_info

                logger.info(f"Loaded scan {scan_id} from disk (status: {scan_info.status})")
            except Exception as e:
                logger.warning(f"Failed to load scan from {run_dir}: {e}")

    def delete_scan(self, scan_id: str) -> bool:
        """Delete a scan and all its associated data.
        
        This method:
        - Stops the scan if it's running
        - Removes the scan from memory
        - Deletes all files in strix_runs/{scan_id}/
        - Removes associated Docker containers
        
        Args:
            scan_id: The ID of the scan to delete
            
        Returns:
            True if the scan was successfully deleted, False if scan not found
        """
        # Validate scan_id to prevent path traversal
        if not scan_id or "/" in scan_id or ".." in scan_id:
            logger.warning(f"Invalid scan_id for deletion: {scan_id}")
            return False
        
        # Stop scan if running
        with self._lock:
            scan_info = self._scans.get(scan_id)
            if not scan_info:
                logger.warning(f"Scan {scan_id} not found for deletion")
                return False
            
            # Stop scan if it's running
            if scan_info.status == "running":
                logger.info(f"Stopping scan {scan_id} before deletion")
                if scan_info.task:
                    scan_info.task.cancel()
                scan_info.status = "stopping"
        
        # Remove from memory
        with self._lock:
            if scan_id in self._scans:
                del self._scans[scan_id]
                logger.info(f"Removed scan {scan_id} from memory")
        
        # Delete Docker containers
        try:
            from strix.runtime.docker_runtime import DockerRuntime
            
            docker_runtime = DockerRuntime()
            docker_runtime.delete_scan_containers(scan_id)
            logger.info(f"Deleted Docker containers for scan {scan_id}")
        except Exception as e:
            logger.warning(f"Failed to delete Docker containers for scan {scan_id}: {e}")
            # Continue with file deletion even if Docker cleanup fails
        
        # Delete files from disk
        run_dir = self._runs_dir / scan_id
        if run_dir.exists() and run_dir.is_dir():
            try:
                shutil.rmtree(run_dir)
                logger.info(f"Deleted directory {run_dir} for scan {scan_id}")
            except OSError as e:
                logger.error(f"Failed to delete directory {run_dir} for scan {scan_id}: {e}")
                return False
        else:
            logger.debug(f"Directory {run_dir} does not exist for scan {scan_id}")
        
        logger.info(f"Successfully deleted scan {scan_id}")
        return True

