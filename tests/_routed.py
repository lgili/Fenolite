# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A copy of ``examples/blink_routed`` with its libraries, built in-process through ``fenolite build`` (change
c0028): the harness of the script-copper tests of the build and of the layout merge."""

from __future__ import annotations

import io
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.copper import is_copper_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.model.board import Track, Via
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[1]
ROUTED_DIR = ROOT / "examples" / "blink_routed"
NAME = "blink_routed"


def isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


class Routed:
    """The routed blink copied under ``tmp_path`` and built into ``out``; ``confirm=False`` builds nothing."""

    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int = 10, *, confirm: bool = True
    ) -> None:
        isolate(monkeypatch, tmp_path)
        self.monkeypatch = monkeypatch
        self.target = target
        root = tmp_path / "repo"
        shutil.copytree(ROUTED_DIR, root / "examples" / "blink_routed")
        shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
        self.script = root / "examples" / "blink_routed" / "design.py"
        self.out = tmp_path / "B"
        if confirm:
            code, env, err = self.build("--confirm")
            assert code == 0, (env.get("issues"), err)

    def build(self, *flags: str) -> tuple[int, dict[str, Any], str]:
        out, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", out)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["--kicad-version", str(self.target), "build", str(self.script), "--out", str(self.out)]
        code = cli_main.main([*args, *flags, "--json"])
        return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()

    @property
    def board(self) -> Path:
        return self.out / f"{NAME}.kicad_pcb"

    def edit_board(self, change: Callable[[str], str]) -> None:
        self.board.write_text(change(self.board.read_text(encoding="utf-8")), encoding="utf-8")

    def edit_script(self, old: str, new: str) -> None:
        text = self.script.read_text(encoding="utf-8")
        assert old in text, old
        self.script.write_text(text.replace(old, new), encoding="utf-8")

    def read(self) -> Design:
        return read_board(self.board.read_text(encoding="utf-8"))

    def files(self) -> dict[str, bytes]:
        return {
            p.relative_to(self.out).as_posix(): p.read_bytes()
            for p in sorted(self.out.rglob("*"))
            if p.is_file() and not p.name.endswith(".bak")
        }


def codes(env: dict[str, Any]) -> list[str]:
    return [i["code"] for i in env["issues"]]


def script_copper(design: Design) -> tuple[list[Track], list[Via]]:
    """The tracks and vias of ``design`` whose KiCad uuid is a copper uuid."""
    assert design.board is not None
    tracks = [t for t in design.board.tracks if is_copper_uuid(t.native_ids.get("kicad", ""))]
    vias = [v for v in design.board.vias if is_copper_uuid(v.native_ids.get("kicad", ""))]
    return tracks, vias


__all__ = ["NAME", "ROUTED_DIR", "Routed", "codes", "isolate", "script_copper"]
