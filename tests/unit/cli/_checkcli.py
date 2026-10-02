# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Running ``fenolite`` in-process for the tests of ``check``, ``inspect`` and ``doctor`` (change c0013), with
the machine's own ``kicad-cli`` hidden: no ``PATH`` entry, no ``FENOLITE_KICAD_CLI`` and a missing macOS
bundle, so only a fake passed explicitly ever runs."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad import cli as kicad_cli

ELAPSED = re.compile(r'"elapsed_ms": \d+')


def hide_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    empty = tmp_path / "empty-path"
    empty.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv("FENOLITE_KICAD_CLI", raising=False)
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", tmp_path / "missing" / "kicad-cli")


def run(
    monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any], str]:
    """``(exit code, envelope, stderr error object, raw stdout)``."""
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}"), out.getvalue()


def without_elapsed(stdout: str) -> str:
    return ELAPSED.sub('"elapsed_ms": 0', stdout)


__all__ = ["hide_kicad", "run", "without_elapsed"]
