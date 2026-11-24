import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from app.execution.audit import ExecutionAuditLogger
from app.execution.policy import (
    SecurityPolicyError,
    validate_command_and_arguments,
    validate_workspace_path,
)


class SandboxExecutionResult(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class DockerSandboxManager:
    def __init__(
        self,
        image_name: str = "devpilot-sandbox:latest",
        cpu_limit: str = "1.0",
        memory_limit: str = "512m",
        pids_limit: int = 64,
        max_output_bytes: int = 50000,
        default_timeout: int = 30,
    ) -> None:
        self._image_name = image_name
        self._cpu_limit = cpu_limit
        self._memory_limit = memory_limit
        self._pids_limit = pids_limit
        self._max_output_bytes = max_output_bytes
        self._default_timeout = default_timeout
        self._audit_logger = ExecutionAuditLogger.get_logger()
        self._runtime_binary: Optional[str] = self._detect_runtime()

    def _detect_runtime(self) -> Optional[str]:
        for candidate in ["podman", "docker"]:
            found = shutil.which(candidate)
            if found:
                return found
        return None

    def is_available(self) -> bool:
        if not self._runtime_binary:
            return False
        try:
            import subprocess

            env = dict(os.environ)
            if "podman" in self._runtime_binary and "DOCKER_HOST" not in env:
                sock_path = f"/run/user/{os.getuid()}/podman/podman.sock"
                if os.path.exists(sock_path):
                    env["DOCKER_HOST"] = f"unix://{sock_path}"

            proc = subprocess.run(
                [self._runtime_binary, "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3.0,
                check=False,
                env=env,
            )
            return proc.returncode == 0
        except Exception:
            return False

    def _truncate_output(self, text: str) -> str:
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) > self._max_output_bytes:
            truncated = encoded[: self._max_output_bytes].decode("utf-8", errors="replace")
            return truncated + f"\n[Output truncated: exceeded limit of {self._max_output_bytes} bytes]"
        return text

    async def execute(
        self,
        session_id: str,
        workspace_dir: Path,
        command: str,
        args: List[str],
        timeout: Optional[int] = None,
        allow_network: bool = False,
    ) -> SandboxExecutionResult:
        start_time = time.time()
        effective_timeout = timeout or self._default_timeout

        try:
            validate_command_and_arguments(command, args)
        except SecurityPolicyError as error:
            duration = time.time() - start_time
            self._audit_logger.log(
                session_id=session_id,
                operation="container_execute",
                target=f"{command} {' '.join(args)}",
                status="rejected",
                exit_code=-1,
                error_type=error.error_type,
                error_message=error.message,
                duration_seconds=duration,
            )
            return SandboxExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=error.message,
                duration_seconds=duration,
                error_type=error.error_type,
                error_message=error.message,
            )

        if not self.is_available():
            duration = time.time() - start_time
            error_message = "Container execution engine (Docker/Podman) is unavailable. Host execution is strictly forbidden."
            self._audit_logger.log(
                session_id=session_id,
                operation="container_execute",
                target=f"{command} {' '.join(args)}",
                status="failed",
                exit_code=-1,
                error_type="CONTAINER_UNAVAILABLE",
                error_message=error_message,
                duration_seconds=duration,
            )
            return SandboxExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=error_message,
                duration_seconds=duration,
                error_type="CONTAINER_UNAVAILABLE",
                error_message=error_message,
            )

        resolved_workspace = workspace_dir.resolve()
        resolved_workspace.mkdir(parents=True, exist_ok=True)

        network_flag = "bridge" if allow_network else "none"
        docker_cmd = [
            self._runtime_binary,  # type: ignore[list-item]
            "run",
            "--rm",
            "--network",
            network_flag,
            f"--cpus={self._cpu_limit}",
            f"--memory={self._memory_limit}",
            f"--pids-limit={self._pids_limit}",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop=ALL",
            "-u",
            "1000:1000",
        ]
        if "podman" in str(self._runtime_binary):
            docker_cmd.append("--userns=keep-id")

        docker_cmd.extend([
            "-v",
            f"{str(resolved_workspace)}:/workspace:rw,Z",
            "-w",
            "/workspace",
            self._image_name,
            command,
            *args,
        ])

        env = dict(os.environ)
        if "podman" in str(self._runtime_binary) and "DOCKER_HOST" not in env:
            sock_path = f"/run/user/{os.getuid()}/podman/podman.sock"
            if os.path.exists(sock_path):
                env["DOCKER_HOST"] = f"unix://{sock_path}"

        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=float(effective_timeout),
            )
            duration = time.time() - start_time
            exit_code = process.returncode if process.returncode is not None else -1

            stdout_text = self._truncate_output(stdout_bytes.decode("utf-8", errors="replace"))
            stderr_text = self._truncate_output(stderr_bytes.decode("utf-8", errors="replace"))

            is_success = exit_code == 0
            error_type = None if is_success else "NON_ZERO_EXIT"
            error_message = None if is_success else f"Command failed with exit code {exit_code}"

            if exit_code == 137:
                error_type = "RESOURCE_LIMIT_EXCEEDED"
                error_message = "Container was terminated (likely OOM killed or process limit exceeded)"

            self._audit_logger.log(
                session_id=session_id,
                operation="container_execute",
                target=f"{command} {' '.join(args)}",
                status="success" if is_success else "failed",
                exit_code=exit_code,
                error_type=error_type,
                error_message=error_message,
                duration_seconds=duration,
            )

            return SandboxExecutionResult(
                success=is_success,
                exit_code=exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
                duration_seconds=duration,
                error_type=error_type,
                error_message=error_message,
            )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            try:
                process.kill()
            except Exception:
                pass

            error_type = "TIMEOUT"
            error_message = f"Command execution timed out after {effective_timeout} seconds"
            self._audit_logger.log(
                session_id=session_id,
                operation="container_execute",
                target=f"{command} {' '.join(args)}",
                status="timeout",
                exit_code=-1,
                error_type=error_type,
                error_message=error_message,
                duration_seconds=duration,
            )

            return SandboxExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=error_message,
                duration_seconds=duration,
                error_type=error_type,
                error_message=error_message,
            )

        except Exception as exception:
            duration = time.time() - start_time
            error_type = "EXECUTION_FAILURE"
            error_message = f"Sandbox execution process error: {str(exception)}"
            self._audit_logger.log(
                session_id=session_id,
                operation="container_execute",
                target=f"{command} {' '.join(args)}",
                status="failed",
                exit_code=-1,
                error_type=error_type,
                error_message=error_message,
                duration_seconds=duration,
            )

            return SandboxExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=error_message,
                duration_seconds=duration,
                error_type=error_type,
                error_message=error_message,
            )
