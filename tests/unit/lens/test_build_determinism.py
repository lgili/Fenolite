# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reproducible builds (capability design-dsl, "Reproducible builds"; cli-contract, MODIFIED
"Determinism flags"; change c0011)."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _buildhelp import BLINK, BLINK_DIR

import fenolite.cli.main as cli_main


def snapshot(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix != ".bak"
    }


def inprocess(monkeypatch: pytest.MonkeyPatch, out: Path, *flags: str) -> None:
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    assert cli_main.main(["build", str(BLINK), "--out", str(out), "--confirm", "--json", *flags]) == 0


def subprocess_build(out: Path, target: int, seed: int, tmp: Path) -> None:
    env = {**os.environ, "PYTHONHASHSEED": str(seed), "KICAD_CONFIG_HOME": str(tmp / "kc")}
    flags = ["--seed", str(seed), "--timestamp", f"2026-0{seed}-01T00:00:00Z", "--kicad-version", str(target)]
    args = [
        sys.executable,
        "-m",
        "fenolite",
        "build",
        str(BLINK),
        "--out",
        str(out),
        "--confirm",
        "--json",
        *flags,
    ]
    subprocess.run(args, check=True, capture_output=True, env=env)


@pytest.mark.parametrize("target", [9, 10])
def test_twice_in_process_and_twice_by_subprocess(
    target: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    script_before = snapshot(BLINK_DIR)
    outs = [tmp_path / f"o{i}" for i in range(4)]
    inprocess(monkeypatch, outs[0], "--kicad-version", str(target))
    inprocess(monkeypatch, outs[1], "--kicad-version", str(target), "--seed", "7")
    subprocess_build(outs[2], target, 1, tmp_path)
    subprocess_build(outs[3], target, 2, tmp_path)
    first = snapshot(outs[0])
    assert first and all(snapshot(o) == first for o in outs[1:])
    assert snapshot(BLINK_DIR) == script_before and not (BLINK_DIR / "__pycache__").exists()


def test_cache_regenerated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    out = tmp_path / "B"
    inprocess(monkeypatch, out)
    before = {k: v for k, v in snapshot(out).items() if k.startswith(".fenolite/")}
    shutil.rmtree(out / ".fenolite")
    inprocess(monkeypatch, out)
    assert {k: v for k, v in snapshot(out).items() if k.startswith(".fenolite/")} == before and len(
        before
    ) == 7
