# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of a net-tie footprint in ``convert --to altium`` and in ``equivalent`` (capability
altium-pcb-writer, "Copper of a net-tie footprint"; capability design-equivalence, "Copper of a net-tie
footprint"; change c0431).

The source is the authored board ``tests/data/kicad/convert/net_tie_copper.kicad_pcb``: one two-pad net tie
``NT1`` whose F.Cu line joins pad 1 (net ``A``) and pad 2 (net ``B``). The written PcbDoc is read by
Fenolite only: Altium's own reading of it is a kit request (evidence ``INFERRED``)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TrackRecord
from fenolite.checks.equivalence.levels import compare_designs
from fenolite.checks.equivalence.model import Tolerances
from fenolite.convert import LossyConversionError
from fenolite.core.coords import Point
from fenolite.model.board import Board, FootprintInstance
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "convert" / "net_tie_copper.kicad_pcb"
NO_INDEX = 0xFFFF
TOP_LAYER = 1
MM = 1_000_000
TOLERANCES = Tolerances(length_nm=3)


def _written(
    tmp_path: Path, source: Path = FIXTURE, *, allow_lossy: bool = False
) -> tuple[Path, ConversionResult]:
    result = convert(source, to="altium", allow_lossy=allow_lossy)
    (name,) = [key for key in result.conversion.files if key.endswith(".PcbDoc")]
    path = tmp_path / name
    path.write_bytes(result.conversion.files[name])
    return path, result


def _board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def _tie(design: Design) -> FootprintInstance:
    ident = next(c.id for c in design.circuit.components if c.ref == "NT1")
    return next(fp for fp in _board(design).footprints if fp.component_id == ident)


def _with_tie(design: Design, new: FootprintInstance) -> Design:
    board = _board(design)
    footprints = tuple(new if fp.id == new.id else fp for fp in board.footprints)
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=footprints))


def test_tie_line_is_component_copper_without_a_loss(tmp_path: Path) -> None:
    """Scenario "A net tie keeps its copper": no ``footprint-copper`` row, nothing unexplained, and the
    PcbDoc holds one track on the top layer that belongs to the component, with no net."""
    path, result = _written(tmp_path)
    report = result.conversion.report
    assert not [row for row in report.rows if row.kind == "footprint-copper" and row.ids("lost")]
    assert result.unexplained == ()
    doc = read_pcbdoc(path.read_bytes())
    (track,) = [t for t in doc.tracks if isinstance(t, TrackRecord)]
    assert track.prefix.layer == TOP_LAYER
    assert track.prefix.component == 0
    assert track.prefix.net is None or track.prefix.net == NO_INDEX
    assert doc.components[0].record.get("COMPONENTKIND") == "4"


def test_tie_line_reads_back_on_its_layer(tmp_path: Path) -> None:
    """The reading of the PcbDoc holds the line in ``NT1``'s frame within 3 nm, on F.Cu, with no net, and
    the pads keep their own nets."""
    path, _ = _written(tmp_path)
    tie = _tie(AltiumBackend().read(path).design)
    (line,) = [g for g in tie.graphics if g.layer == "F.Cu"]
    assert line.kind == "line" and line.net_id is None
    assert abs(line.width - 300_000) <= 3
    ends = sorted(line.points, key=lambda p: p.x)
    assert abs(ends[0].x + MM // 2) <= 3 and abs(ends[1].x - MM // 2) <= 3
    assert all(abs(p.y) <= 3 for p in ends)
    assert tie.net_ties == (("1", "2"),)
    assert len({pad.net_id for pad in tie.pads}) == 2


def test_equivalent_sees_a_missing_tie_line(tmp_path: Path) -> None:
    """Scenario "An open net tie is a difference": without the line, level 3 reports one
    ``net-tie-copper`` difference at ``NT1``; levels 1 and 2 report none."""
    path, result = _written(tmp_path)
    source = result.conversion.design
    read = AltiumBackend().read(path).design
    tie = _tie(read)
    opened = _with_tie(
        read, dataclasses.replace(tie, graphics=tuple(g for g in tie.graphics if g.layer != "F.Cu"))
    )
    same = compare_designs(source, read, level=3, tolerances=TOLERANCES, frame="relative")
    assert same.differences == ()
    report = compare_designs(source, opened, level=3, tolerances=TOLERANCES, frame="relative")
    found = [(d.level, d.kind, d.where, d.b) for d in report.differences]
    assert found == [(3, "net-tie-copper", "NT1", "")]
    assert report.differences[0].a.startswith("top segment width 300000 at ")


def test_equivalent_sees_a_moved_tie_line(tmp_path: Path) -> None:
    """A line moved by 0.1 mm is a difference on both sides; a footprint that is a net tie on neither side
    compares no copper."""
    path, result = _written(tmp_path)
    source = result.conversion.design
    read = AltiumBackend().read(path).design
    tie = _tie(read)
    moved = tuple(
        dataclasses.replace(g, points=tuple(Point(p.x, p.y + 100_000) for p in g.points))
        if g.layer == "F.Cu"
        else g
        for g in tie.graphics
    )
    shifted = _with_tie(read, dataclasses.replace(tie, graphics=moved))
    report = compare_designs(source, shifted, level=3, tolerances=TOLERANCES, frame="relative")
    assert sorted((d.kind, bool(d.a), bool(d.b)) for d in report.differences) == [
        ("net-tie-copper", False, True),
        ("net-tie-copper", True, False),
    ]
    plain_source = _with_tie(source, dataclasses.replace(_tie(source), net_ties=()))
    plain = _with_tie(shifted, dataclasses.replace(_tie(shifted), net_ties=()))
    assert (
        compare_designs(plain_source, plain, level=3, tolerances=TOLERANCES, frame="relative").differences
        == ()
    )


def test_unwritten_tie_copper_is_refused_then_explained(tmp_path: Path) -> None:
    """A filled circle on F.Cu has no record (``pcbdoc.graphic_problem``): it stays a refused
    ``footprint-copper`` loss, and with ``allow_lossy`` the ``net-tie-copper`` difference it causes is
    explained by that row."""
    text = FIXTURE.read_text(encoding="utf-8").replace(
        "(fp_line\n\t\t\t(start -0.5 0)\n\t\t\t(end 0.5 0)",
        "(fp_circle\n\t\t\t(center 0 0)\n\t\t\t(end 0.3 0)",
    )
    text = text.replace(
        '(type solid)\n\t\t\t)\n\t\t\t(layer "F.Cu")',
        '(type solid)\n\t\t\t)\n\t\t\t(fill yes)\n\t\t\t(layer "F.Cu")',
    )
    assert "(fp_circle" in text and "(fill yes)" in text
    source = tmp_path / "net_tie_circle.kicad_pcb"
    source.write_text(text, encoding="utf-8")
    with pytest.raises(LossyConversionError):
        convert(source, to="altium")
    _, result = _written(tmp_path, source, allow_lossy=True)
    assert result.unexplained == ()
    explained = [(e.difference.kind, e.difference.where, e.kind) for e in result.explained]
    assert ("net-tie-copper", "NT1", "footprint-copper") in explained
