# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Teardrops and blind vias over the board through ``fenolite import --to python`` (change c0277): the
teardrop settings of a via come back as ``teardrop=`` of its table, a blind via over both copper layers is a
table row, and the teardrop zones KiCad draws again are reported as regenerated, not lost."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, imported, teardropped

from fenolite.api import read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.importer.tables import copper_tables, has_teardrops, via_teardrop
from fenolite.model.board import Teardrop

FULL = Teardrop(
    max_length=1_000_000, max_width=2_000_000, length_ratio=500_000, width_ratio=1_000_000, curved=False,
    filter_ratio=900_000, two_segments=True, prefer_zones=True,
)  # fmt: skip


def _source(tmp_path: Path, **kwargs: str):  # noqa: ANN202
    design = read_board(teardropped(tmp_path, **kwargs)).design
    assert design.board is not None
    return design, design.board


def test_via_settings_are_read_from_the_slot(tmp_path: Path) -> None:
    _, board = _source(tmp_path)
    at = {(via.position.x, via.position.y): via for via in board.vias}
    first, second = at[110_000_000, 133_000_000], at[130_000_000, 133_000_000]
    assert via_teardrop(first) == (FULL, True) and via_teardrop(second) == (None, True)
    assert has_teardrops(first) and not has_teardrops(second)
    assert all(via.teardrop is None for via in board.vias)  # the reader does not project the child


def test_tables_group_by_settings_and_keep_the_blind_via(tmp_path: Path) -> None:
    design, board = _source(tmp_path)
    names = {net.id: net.name for net in design.circuit.nets}
    tables = copper_tables(board, names)
    vias = [table for table in tables.tables if table.kind == "via" and table.net == "GND"]
    assert not tables.left_out and tables.teardrops_lost == 0
    found = [(t.key, t.via_kind, t.layers, t.teardrop == FULL, t.rows) for t in vias]
    assert found == [
        ("GND/via/1", "blind", ("F.Cu", "B.Cu"), False, ((30_000_000, 33_000_000),)),
        ("GND/via/2", "through", None, False, ((50_000_000, 33_000_000),)),
        ("GND/via/3", "through", None, True, ((10_000_000, 33_000_000),)),
    ]


def test_unreadable_settings_are_counted(tmp_path: Path) -> None:
    design, board = _source(tmp_path, settings="(teardrops (enabled maybe))")
    names = {net.id: net.name for net in design.circuit.nets}
    tables = copper_tables(board, names)
    assert tables.left_out == {"teardrop-setting": 1}
    assert sum(len(t.rows) for t in tables.tables if t.kind == "via") == 6


def test_import_writes_the_settings_and_builds_them(tmp_path: Path) -> None:
    reply = imported(tmp_path, teardropped(tmp_path / "src"), "--confirm")
    assert reply.exit_code == 0, reply.error
    codes = [issue["code"] for issue in reply.envelope["issues"]]
    assert "import.teardrops-regenerated" in codes
    assert not [row for row in reply.result["unexpressed"] if row["kind"].startswith("teardrop")]
    text = (tmp_path / "out" / "copper.py").read_text(encoding="utf-8")
    assert "from fenolite.dsl import Design, Net, mm, teardrop" in text
    assert "teardrop=teardrop(\n" in text and 'kind="blind",\n' in text
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "teardropped.kicad_pcb").read_text(encoding="utf-8"))
    vias = {tuple(a.value for a in via.find("at").atoms()): via for via in root.nodes("via")}  # type: ignore[union-attr]
    held = vias["110", "133"].find("teardrops")
    assert held is not None and len(held.nodes()) == 9
    assert vias["130", "133"].atoms()[0].value == "blind" and vias["130", "133"].find("teardrops") is None


def test_zones_lost_with_their_settings(tmp_path: Path) -> None:
    """A teardrop zone whose settings the import cannot read is lost, not regenerated."""
    reply = imported(
        tmp_path, teardropped(tmp_path / "src", settings="(teardrops (enabled maybe))"), "--allow-lossy"
    )
    assert reply.exit_code == 0, reply.error
    kinds = {row["kind"]: row["count"] for row in reply.result["unexpressed"]}
    assert kinds == {"teardrop": 1, "teardrop-setting": 1}
    assert "import.teardrops-regenerated" not in [issue["code"] for issue in reply.envelope["issues"]]


def test_zone_of_another_type_is_unexpressed(tmp_path: Path) -> None:
    reply = imported(tmp_path, teardropped(tmp_path / "src", kind="track_end"), "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    assert {row["kind"]: row["count"] for row in reply.result["unexpressed"]} == {"teardrop": 1}
