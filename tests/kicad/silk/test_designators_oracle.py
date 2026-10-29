# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite silk --designators`` judged by the running ``kicad-cli`` (change c0212; capability
silkscreen-layout, "Placed designators checked"; hypotheses ``H-K-SILK-DRC`` and ``H-K-SILK-INK``), on the
authored benches of ``tests/_silkbench.py`` written for the tool's major with their projects.

Before the command, every designator lies over its pads, and KiCad reports ``silk_over_copper`` and
``silk_overlap`` (the control). After it, KiCad's DRC reports no silkscreen or text finding, and each
designator's ink, as KiCad draws the written board, is the rectangle that Fenolite's check computed."""

from __future__ import annotations

import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _probes import major, runner
from _silkbench import mixed, row

from fenolite.backends.kicad.fields import field_anchor, field_angle
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.backends.kicad.textink import board_texts
from fenolite.cli import main as cli_main
from fenolite.model.design import Design
from fenolite.silk.board import field_rect
from fenolite.silk.extents import InkCache, TextKey, cache_folder

pytestmark = pytest.mark.needs_kicad
SILK_TYPES = frozenset(
    {"silk_over_copper", "silk_overlap", "silk_edge_clearance", "text_height", "text_thickness"}
)
CLOSE = 1_000
"""1 µm: the plot's rounding of a point and of half the stroke."""


def _write(folder: Path, name: str, design: Design) -> Path:
    board = folder / f"{name}.kicad_pcb"
    board.write_text(write_board(design, target=major()).text, encoding="utf-8", newline="\n")
    project = synthesize_project(design, target=major(), board_name=name)
    board.with_suffix(".kicad_pro").write_text(project, encoding="utf-8", newline="\n")
    return board


def _drc(board: Path) -> Counter[str]:
    report = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert report.report is not None
    found = (*report.report.violations, *report.report.unconnected_items)
    return Counter(item.type for item in found if not item.excluded)


def _silk(
    monkeypatch: pytest.MonkeyPatch, folder: Path, board: Path, *args: str
) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(folder)
    monkeypatch.setenv("FENOLITE_CACHE_DIR", str(folder / "cache"))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    cli = str(runner().path)
    code = cli_main.main(["silk", board.name, "--designators", "--kicad-cli", cli, *args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


@pytest.mark.parametrize("bench", ["row", "mixed"])
def test_placed_designators_pass_drc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bench: str) -> None:
    design = row() if bench == "row" else mixed()
    board = _write(tmp_path, bench, design)
    before = _drc(board)
    assert before["silk_over_copper"] > 0 and before["silk_overlap"] > 0  # the control
    code, env = _silk(monkeypatch, tmp_path, board, "--drc", "--confirm")
    assert code == 0, env
    result = env["result"]
    assert result["unplaced"] == 0 and result["changed"] is True
    assert result["measure"]["source"] == f"kicad-cli {runner().version()}"
    assert result["drc"]["new"] == [] and env["evidence"]["level"] == "KICAD-VERIFIED"
    after = _drc(board)
    assert not SILK_TYPES & set(after), after
    # each designator is drawn where Fenolite's check put it
    placed = read_board(board.read_text(encoding="utf-8"), file=board.name)
    assert placed.board is not None
    names = {c.id: c.ref for c in placed.circuit.components}
    drawn = {item.text: item.ink for item in board_texts(runner(), board, ["F.SilkS", "B.SilkS"])}
    cache = InkCache(cache_folder({"FENOLITE_CACHE_DIR": str(tmp_path / "cache")}))
    tool = f"kicad-cli {runner().version()}"
    for fp in placed.board.footprints:
        ref = names[fp.component_id]
        field = next(f for f in fp.fields if f.name == "Reference")
        assert field.thickness is not None
        key = TextKey(ref, field.size.w, field.size.h, field.thickness)
        hit, ink = cache.get(tool, key)
        assert hit and ink is not None, ref
        anchor = field_anchor(fp, field)
        rect = field_rect(ink, field_angle(fp, field), field.mirrored).moved(anchor.x, anchor.y)
        seen = drawn[ref]
        assert all(
            abs(a - b) <= CLOSE for a, b in zip((rect.x0, rect.y0, rect.x1, rect.y1), seen, strict=True)
        ), ref
