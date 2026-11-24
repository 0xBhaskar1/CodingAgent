import os
from pathlib import Path
from typing import List, Set

ALLOWED_BASE_COMMANDS: Set[str] = {
    "python",
    "python3",
    "pytest",
    "pip",
    "pip3",
}

APPROVED_DEPENDENCIES: Set[str] = {
    "pytest",
    "pytest-asyncio",
    "pydantic",
    "pydantic-settings",
    "fastapi",
    "requests",
    "httpx",
    "sqlalchemy",
    "numpy",
    "pandas",
    "typing-extensions",
    "aiosqlite",
    "websockets",
}

DISALLOWED_ARG_CHARS: Set[str] = {
    ";",
    "&",
    "|",
    "`",
    "$",
    "(",
    ")",
    "<",
    ">",
    "\n",
    "\r",
    "\0",
}

PROTECTED_POLICY_FILES: Set[str] = {
    "Dockerfile",
    "Dockerfile.sandbox",
    "docker-compose.yml",
    ".env",
    "policy.py",
    "sandbox.py",
    "executor.py",
}


class SecurityPolicyError(Exception):
    def __init__(self, message: str, error_type: str = "POLICY_VIOLATION") -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


def validate_workspace_path(workspace_dir: Path, target_relative_path: str) -> Path:
    if not target_relative_path:
        return workspace_dir.resolve()

    if "\0" in target_relative_path:
        raise SecurityPolicyError(
            "Null byte detected in file path",
            error_type="INVALID_FILE_PATH",
        )

    if target_relative_path.startswith("/") or target_relative_path.startswith("\\"):
        raise SecurityPolicyError(
            f"Absolute path '{target_relative_path}' is not permitted within workspace sandbox",
            error_type="INVALID_FILE_PATH",
        )

    resolved_workspace = workspace_dir.resolve()
    normalized = os.path.normpath(target_relative_path)
    resolved_target = (resolved_workspace / normalized).resolve()

    try:
        resolved_target.relative_to(resolved_workspace)
    except ValueError:
        raise SecurityPolicyError(
            f"Path traversal detected: '{target_relative_path}' attempts to escape workspace",
            error_type="INVALID_FILE_PATH",
        )

    target_name = resolved_target.name
    if target_name in PROTECTED_POLICY_FILES:
        raise SecurityPolicyError(
            f"Modification of protected policy file '{target_name}' is forbidden",
            error_type="POLICY_VIOLATION",
        )

    return resolved_target


def validate_command_and_arguments(command: str, args: List[str]) -> None:
    base_cmd = command.strip().lower()
    if base_cmd not in ALLOWED_BASE_COMMANDS:
        raise SecurityPolicyError(
            f"Command '{command}' is not in the allowed command policy",
            error_type="UNSUPPORTED_COMMAND",
        )

    for argument in args:
        for forbidden in DISALLOWED_ARG_CHARS:
            if forbidden in argument:
                raise SecurityPolicyError(
                    f"Command injection attempt detected: character '{forbidden}' in argument '{argument}'",
                    error_type="UNSUPPORTED_COMMAND",
                )

        if "--privileged" in argument:
            raise SecurityPolicyError(
                "Privileged execution flag is prohibited",
                error_type="POLICY_VIOLATION",
            )


def validate_dependency_name(package_name: str) -> str:
    cleaned = package_name.strip().lower()
    for forbidden in DISALLOWED_ARG_CHARS:
        if forbidden in cleaned:
            raise SecurityPolicyError(
                f"Invalid characters in package name: {package_name}",
                error_type="DISALLOWED_DEPENDENCY",
            )

    normalized_name = cleaned.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("!=")[0].strip()
    if normalized_name not in APPROVED_DEPENDENCIES:
        raise SecurityPolicyError(
            f"Package '{normalized_name}' is not in the approved dependency allowlist",
            error_type="DISALLOWED_DEPENDENCY",
        )
    return normalized_name
