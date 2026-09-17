import os
import subprocess
from pathlib import Path


ROOT = Path.cwd()


def safe_path(path: str) -> Path:
    """Prevent the agent from accessing files outside the repository."""
    requested = (ROOT / path).resolve()

    if requested != ROOT and ROOT not in requested.parents:
        raise ValueError("Path is outside the repository.")

    return requested


def read_file(path: str) -> str:
    file_path = safe_path(path)

    if not file_path.exists():
        return f"ERROR: File does not exist: {path}"

    if not file_path.is_file():
        return f"ERROR: Not a file: {path}"

    return file_path.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    file_path = safe_path(path)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return f"Successfully wrote {path}"


def list_files(path: str = ".") -> str:
    directory = safe_path(path)

    if not directory.exists():
        return f"ERROR: Directory does not exist: {path}"

    files = []

    for item in directory.rglob("*"):
        if item.is_file():
            relative = item.relative_to(ROOT)

            # Don't expose git internals or secrets.
            if ".git" in relative.parts:
                continue

            files.append(str(relative))

    return "\n".join(files[:500])


def run_command(command: str) -> str:
    """
    Run a shell command in the repository.

    The command comes from the AI, so this is intentionally restricted
    to commands useful for development.
    """

    dangerous = [
        "rm -rf",
        "sudo",
        "shutdown",
        "reboot",
        "mkfs",
        "dd if=",
        ":(){",
    ]

    lowered = command.lower()

    for blocked in dangerous:
        if blocked in lowered:
            return f"ERROR: Blocked dangerous command: {blocked}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
        )

        output = result.stdout

        if result.returncode != 0:
            return (
                f"COMMAND FAILED\n"
                f"Exit code: {result.returncode}\n\n"
                f"{output}"
            )

        return f"COMMAND SUCCEEDED\n\n{output}"

    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 5 minutes."


def git_diff() -> str:
    return run_command("git diff")


def git_status() -> str:
    return run_command("git status --short")

