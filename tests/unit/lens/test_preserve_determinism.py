# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Preservation is the build's normal form (capability layout-lens, scenarios "Two rebuilds over a routed
board" and "Cache regenerated over a routed board"; change c0019)."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _buildhelp import BLINK
from _layout_edit import edit_blink

import fenolite.cli.main as cli_main


def snapshot(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix != ".bak"
    }


def inprocess(monkeypatch: pytest.MonkeyPatch, out: Path, target: int) -> None:
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    args = ["--kicad-version", str(target), "build", str(BLINK), "--out", str(out), "--confirm", "--json"]
    assert cli_main.main(args) == 0


def by_subprocess(out: Path, target: int, seed: int, tmp: Path) -> None:
    env = {**os.environ, "PYTHONHASHSEED": str(seed), "KICAD_CONFIG_HOME": str(tmp / "kc")}
    flags = ["--seed", str(seed), "--kicad-version", str(target)]
    args = [sys.executable, "-m", "fenolite", "build", str(BLINK), "--out", str(out), "--confirm", "--json"]
    subprocess.run([*args, *flags], check=True, capture_output=True, env=env)


def routed(monkeypatch: pytest.MonkeyPatch, out: Path, target: int) -> None:
    inprocess(monkeypatch, out, target)
    board = out / "blink.kicad_pcb"
    board.write_text(edit_blink(board.read_text(encoding="utf-8")), encoding="utf-8")


@pytest.mark.parametrize("target", [9, 10])
def test_two_rebuilds_over_a_routed_board(
    target: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    a, b = tmp_path / "a", tmp_path / "b"
    routed(monkeypatch, a, target)
    inprocess(monkeypatch, a, target)
    first = snapshot(a)
    inprocess(monkeypatch, a, target)
    assert snapshot(a) == first
    routed(monkeypatch, b, target)
    by_subprocess(b, target, 1, tmp_path)
    assert snapshot(b) == first
    by_subprocess(b, target, 2, tmp_path)
    assert snapshot(b) == first


def test_cache_regenerated_over_a_routed_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    out = tmp_path / "a"
    routed(monkeypatch, out, 10)
    inprocess(monkeypatch, out, 10)
    before = snapshot(out)
    shutil.rmtree(out / ".fenolite")
    inprocess(monkeypatch, out, 10)
    assert snapshot(out) == before and len([k for k in before if k.startswith(".fenolite/")]) == 7
