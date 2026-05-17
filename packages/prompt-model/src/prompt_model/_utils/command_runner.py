from __future__ import annotations

import asyncio
import subprocess


def run_command(cmd: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a shell command and raise if it fails."""
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=capture_output,
    )


async def run_command_async(cmd: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a shell command asynchronously and raise if it fails."""
    stdout = asyncio.subprocess.PIPE if capture_output else None
    stderr = asyncio.subprocess.PIPE if capture_output else None

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=stdout,
        stderr=stderr,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    assert process.returncode is not None

    stdout_text = stdout_bytes.decode() if stdout_bytes is not None else None
    stderr_text = stderr_bytes.decode() if stderr_bytes is not None else None
    result: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(
        cmd,
        process.returncode,
        stdout_text,
        stderr_text,
    )

    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            cmd,
            output=stdout_text,
            stderr=stderr_text,
        )

    return result
