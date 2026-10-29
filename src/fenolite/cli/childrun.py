# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One ``fenolite`` command run as a child process: the runner core that ``fenolite mcp`` (change c0195) and
the viewer's run and action routes (changes c0270 and c0271) share.

``run_child`` runs ``python -m fenolite <command> --json [--progress] ...`` in a folder, in its own process
group, with standard input closed. It stops the group (a terminate, then a kill) when the caller's
``cancelled`` event is set or the time limit passes; the command line's own signal handling leaves no partial
write. Progress records of ``--progress`` are handed to the caller as they arrive. The result is the
envelope (exit 0 or 5), the command's error object (any other exit), or a ``FEN-1003`` error when the child
was stopped, ``FEN-1001`` when it said nothing usable.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Literal, cast

from fenolite.cli.errors import CliError
from fenolite.cli.output import to_jsonable

GRACE = 5.0
"""Seconds between the terminate and the kill of a stopped child."""
Json = dict[str, Any]
Progress = Callable[[Json], None]
"""Receives each ``--progress`` record (the object under ``progress``) of the child."""


@dataclass(frozen=True, slots=True)
class ChildResult:
    """How a child ended: its exit code, its envelope or error object, and why it was stopped, if it was."""

    exit: int
    value: Json
    stopped: Literal["cancelled", "timeout"] | None = None


def error_object(code: str, message: str, *, where: str, hint: str = "") -> tuple[int, Json]:
    """``(exit code, error object)`` of a refusal the runner itself gives."""
    error = CliError(code, message, where=where, hint=hint or None)
    return int(error.exit_code), cast("Json", to_jsonable(error.info()))


def default_executable() -> list[str]:
    return [sys.executable, "-m", "fenolite"]


def run_child(
    words: Sequence[str],
    *,
    root: Path,
    timeout: float,
    cancelled: threading.Event | None = None,
    progress: Progress | None = None,
    executable: Sequence[str] | None = None,
    where: str = "",
) -> ChildResult:
    """Run ``[command, words...]`` as described in the module docstring; ``where`` names the call in a
    refusal."""
    stop = cancelled if cancelled is not None else threading.Event()
    argv = [
        *(executable if executable is not None else default_executable()),
        *words[:1],
        "--json",
        *(["--progress"] if progress is not None else []),
        *words[1:],
    ]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    child = subprocess.Popen(
        argv, cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, creationflags=group, start_new_session=os.name != "nt",
    )  # fmt: skip
    out: list[bytes] = []
    errors: list[str] = []
    readers = [
        threading.Thread(target=lambda: out.append(cast("IO[bytes]", child.stdout).read()), daemon=True),
        threading.Thread(target=_stderr, args=(child, errors, progress), daemon=True),
    ]
    for reader in readers:
        reader.start()
    stopped = _wait(child, stop, timeout)
    for reader in readers:
        reader.join(GRACE)
    name = where or (words[0] if words else "fenolite")
    if stopped is not None:
        message = (
            "the call was cancelled"
            if stopped == "cancelled"
            else f"the call ran longer than {timeout:g} s and was stopped"
        )
        code, value = error_object("FEN-1003", message, where=name, hint="the call can be run again")
        return ChildResult(code, value, stopped)
    code = int(child.returncode)
    if code in (0, 5):
        try:
            return ChildResult(code, cast("Json", json.loads(b"".join(out).decode("utf-8"))))
        except ValueError as exc:
            failed, value = error_object(
                "FEN-1001", f"the command's output is not its envelope: {exc}", where=name
            )
            return ChildResult(failed, value)
    for line in reversed(errors):
        try:
            found = json.loads(line)
        except ValueError:
            continue
        if isinstance(found, dict) and "code" in found:
            return ChildResult(code, cast("Json", found))
    failed, value = error_object(
        "FEN-1001", f"the command exited {code} without its error object", where=name
    )
    return ChildResult(failed, value)


Stopped = Literal["cancelled", "timeout"]


def _wait(child: subprocess.Popen[bytes], cancelled: threading.Event, timeout: float) -> Stopped | None:
    """Wait for ``child``; stop it on cancellation or after the timeout and say which, else ``None``."""
    deadline = time.monotonic() + timeout
    while child.poll() is None:
        if cancelled.wait(0.05):
            stop(child)
            return "cancelled"
        if time.monotonic() > deadline:
            stop(child)
            return "timeout"
    return None


def stop(child: subprocess.Popen[bytes]) -> None:
    """Terminate the process group of ``child``, then kill it after :data:`GRACE` seconds."""
    if os.name == "nt":
        child.terminate()
    else:
        os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(GRACE)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            child.kill()
        else:
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()


def _stderr(child: subprocess.Popen[bytes], errors: list[str], progress: Progress | None) -> None:
    """Read the child's stderr: progress records go to ``progress``, other lines are kept."""
    for raw in cast("IO[bytes]", child.stderr):
        line = raw.decode("utf-8", "replace").strip()
        try:
            value = json.loads(line)
        except ValueError:
            errors.append(line)
            continue
        record = cast("Json", value).get("progress") if isinstance(value, dict) else None
        if isinstance(record, dict):
            if progress is not None:
                progress(cast("Json", record))
        else:
            errors.append(line)


__all__ = ["GRACE", "ChildResult", "default_executable", "error_object", "run_child", "stop"]
