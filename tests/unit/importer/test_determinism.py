# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic imports (capability board-to-code, "Deterministic imports"; change c0275): two runs in
other processes, with other ``PYTHONHASHSEED`` values and working folders, write the same bytes, which
``ruff format`` leaves unchanged."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _importcode import PROJECT, STAMP


def _run(folder: Path, seed: str) -> dict[str, str]:
    folder.mkdir()
    env = {**os.environ, "PYTHONHASHSEED": seed}
    args = [sys.executable, "-m", "fenolite", "import", str(PROJECT), "--to", "python", "--out", "out",
            "--confirm", "--json", "--timestamp", STAMP, "--seed", seed]  # fmt: skip
    done = subprocess.run(args, cwd=folder, env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    out = folder / "out"
    return {
        p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }


def test_same_bytes_twice(tmp_path: Path) -> None:
    first = _run(tmp_path / "a", "1")
    second = _run(tmp_path / "b", "4242")
    assert first == second
    for folder in (tmp_path / "a" / "out",):
        for script in folder.glob("*.py"):
            text = script.read_text(encoding="utf-8")
            assert str(tmp_path) not in text and str(PROJECT.parent) not in text
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff is not installed")
    scripts = [str(p) for p in sorted((tmp_path / "a" / "out").glob("*.py"))]
    done = subprocess.run(
        [ruff, "format", "--check", "--no-cache", "--line-length", "110", *scripts],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
