# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` run as a subprocess against the running ``kicad-cli`` (change c0013, task group 7)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ELAPSED = re.compile(r'"elapsed_ms": \d+')


def cli_path() -> str:
    from _probes import runner

    return str(runner().path)


def check(root: Path, *args: str) -> tuple[int, dict[str, Any], str, str]:
    """``(exit code, envelope, stdout, stderr)`` of ``fenolite check <root> … --json`` run in ``root``."""
    command = [
        sys.executable,
        "-m",
        "fenolite",
        "check",
        str(root),
        "--kicad-cli",
        cli_path(),
        *args,
        "--json",
    ]
    run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=900, check=False)
    envelope: dict[str, Any] = json.loads(run.stdout) if run.stdout.strip() else {}
    return run.returncode, envelope, run.stdout, run.stderr


def stage(envelope: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in envelope["result"]["stages"] if s["name"] == name)


def without_elapsed(stdout: str) -> str:
    return ELAPSED.sub('"elapsed_ms": 0', stdout)


__all__ = ["check", "cli_path", "stage", "without_elapsed"]
