# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A blink copy built into a folder through ``fenolite build``, for the command-level tests of the layout
lens (changes c0019 and c0069): the board is edited by token edit, as KiCad would, and built again
in-process."""

from __future__ import annotations

import io
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[1]

COPPER_WARN = ("--copper-check", "warn")
"""For the tests whose edited board, fills or rules give a real copper error that is not their subject: a
footprint swapped under an existing track, authored fills that cover a pad, and a 0.3 mm clearance that the
0.25 mm gaps between the pads of ``U1`` do not meet. The copper guard (change c0029) reports those as
warnings in this mode, and the build writes."""


class Project:
    """A copy of a design folder (the blink by default) with its libraries, built into ``out``.

    ``folder`` is the design's folder relative to the repository root and ``name`` the design name; the
    copy keeps the folder's place in the tree, so its library tables find ``tests/data/libs``."""

    name = "blink"

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        target: int = 10,
        *,
        folder: str = "examples/blink_2layer",
        name: str = "blink",
    ) -> None:
        self.monkeypatch = monkeypatch
        self.target = target
        self.name = name
        root = tmp_path / "repo"
        shutil.copytree(ROOT / folder, root / folder)
        shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
        self.script = root / folder / "design.py"
        self.out = tmp_path / "B"
        code, _, err = self.build("--confirm")
        assert code == 0, err

    def run(self, command: str, *flags: str, out: Path | None = None) -> tuple[int, dict[str, object], str]:
        """``fenolite <command> <script> --out <out> <flags> --json``: exit code, envelope and stderr."""
        stdout, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", stdout)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["--kicad-version", str(self.target), command, str(self.script), "--out", str(out or self.out)]
        code = cli_main.main([*args, *flags, "--json"])
        return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, err.getvalue()

    def build(self, *flags: str) -> tuple[int, dict[str, object], str]:
        return self.run("build", *flags)

    @property
    def board(self) -> Path:
        return self.out / f"{self.name}.kicad_pcb"

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
            str(p.relative_to(self.out)): p.read_bytes()
            for p in sorted(self.out.rglob("*"))
            if p.is_file() and not p.name.endswith(".bak")
        }


def codes(env: dict[str, object]) -> list[str]:
    return [i["code"] for i in env["issues"]]  # type: ignore[union-attr, index]


def footprint(design: Design, ref: str) -> tuple[object, object]:
    assert design.board is not None
    refs = {c.id: c for c in design.circuit.components}
    (fp,) = [f for f in design.board.footprints if refs[f.component_id].ref == ref]
    return fp, refs[fp.component_id]


def node_of(text: str, ref: str) -> Node:
    (fp,) = [
        c
        for c in parse(text).children
        if isinstance(c, Node) and c.name == "footprint" and f'"Reference" "{ref}"' in dumps(c)
    ]
    return fp


def prop_node(text: str, ref: str, name: str) -> Node:
    (prop,) = [p for p in node_of(text, ref).nodes("property") if p.atoms()[0].value == name]
    return prop


__all__ = ["COPPER_WARN", "Project", "codes", "footprint", "node_of", "prop_node"]
