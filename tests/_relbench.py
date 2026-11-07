# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A design script in a folder of its own, built in-process through ``fenolite build``, for the tests of
placement in code (change c0255)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.design import Design


class Bench:
    """A design script in a folder of its own, built into ``out`` in-process."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, name: str) -> None:
        self.monkeypatch = monkeypatch
        self.folder = tmp_path / "src"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.script = self.folder / "design.py"
        self.script.write_text(text, encoding="utf-8")
        self.out = tmp_path / "out"
        self.name = name

    def build(self, *flags: str, out: Path | None = None) -> tuple[int, dict[str, Any], str]:
        stdout, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", stdout)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["build", str(self.script), "--out", str(out or self.out), *flags, "--json"]
        code = cli_main.main(args)
        return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, err.getvalue()

    @property
    def board(self) -> Path:
        return self.out / f"{self.name}.kicad_pcb"

    def read(self) -> Design:
        return read_board(self.board.read_text(encoding="utf-8"))

    def positions(self) -> dict[str, tuple[Point, int, str]]:
        design = self.read()
        assert design.board is not None
        refs = {c.id: c.ref for c in design.circuit.components}
        return {refs[fp.component_id]: (fp.position, fp.rotation, fp.side) for fp in design.board.footprints}

    def edit_script(self, old: str, new: str) -> None:
        text = self.script.read_text(encoding="utf-8")
        assert old in text, old
        self.script.write_text(text.replace(old, new), encoding="utf-8")

    def files(self) -> dict[str, bytes]:
        return {
            str(p.relative_to(self.out)): p.read_bytes()
            for p in sorted(self.out.rglob("*"))
            if p.is_file() and not p.name.endswith(".bak")
        }

    def paths(self) -> dict[str, str]:
        """Component path → reference on the written board."""
        return {c.properties.get("fenolite.path", c.ref): c.ref for c in self.read().circuit.components}


__all__ = ["Bench"]
