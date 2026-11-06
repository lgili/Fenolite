# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rounded-rectangle pads through Altium → KiCad → Altium, and a pad that one side lacks at level 5 of
``equivalent`` (capability kicad-file-backend, "A created pad keeps its corner ratio"; capability
design-equivalence, "Copper that reaches a pad the other side lacks"; change c0444).

The source is the authored board ``tests/data/kicad/convert/roundrect_roundtrip.kicad_pcb``: ``R1`` has
two rounded-rectangle pads (ratio 0.2) routed to ``J1``, net ``A`` on F.Cu and net ``B`` through two vias
and B.Cu. Its conversion to Altium is the Altium source of the round trip."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.checks.equivalence.levels import compare_designs
from fenolite.checks.equivalence.model import Tolerances
from fenolite.model.board import Board, FootprintInstance
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "convert" / "roundrect_roundtrip.kicad_pcb"
TOLERANCES = Tolerances(length_nm=3)
RATIO = 200_000


def _write(result: ConversionResult, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def _pcbdoc(folder: Path) -> Path:
    (path,) = folder.glob("*.PcbDoc")
    return path


def _round_trip(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The Altium source, the KiCad project converted from it, and the Altium project converted back."""
    source = _pcbdoc(_write(convert(FIXTURE, to="altium"), tmp_path / "source"))
    kicad = _write(convert(source, to="kicad", allow_lossy=True), tmp_path / "kicad")
    altium = _write(convert(kicad, to="altium", allow_lossy=True), tmp_path / "altium")
    return source, kicad, altium


def _board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def _footprint(design: Design, ref: str) -> FootprintInstance:
    ident = next(c.id for c in design.circuit.components if c.ref == ref)
    return next(fp for fp in _board(design).footprints if fp.component_id == ident)


def test_kicad_board_keeps_the_corner_ratio(tmp_path: Path) -> None:
    """Scenario "A created pad keeps its corner ratio": each rounded-rectangle pad of the KiCad board
    converted from Altium holds ``roundrect_rratio 0.2``; the reading gives ``corner_ratio`` 200 000."""
    _, kicad, _ = _round_trip(tmp_path)
    (board,) = kicad.glob("*.kicad_pcb")
    text = board.read_text(encoding="utf-8")
    assert text.count(" smd roundrect") == 2
    assert re.findall(r"\(roundrect_rratio ([0-9.]+)\)", text) == ["0.2", "0.2"]
    design = convert(kicad, to="altium", allow_lossy=True, verify=False).conversion.design
    pads = _footprint(design, "R1").pads
    assert sorted((pad.shape, pad.corner_ratio) for pad in pads) == [("roundrect", RATIO)] * 2


def test_round_trip_keeps_every_pad_and_its_routing(tmp_path: Path) -> None:
    """The Altium project converted back holds every pad of the source, loses no pad, and is equivalent to
    the source at level 5 in the relative frame."""
    source, kicad, altium = _round_trip(tmp_path)
    back = convert(kicad, to="altium", allow_lossy=True, verify=False)
    assert not [row for row in back.conversion.report.rows if row.kind == "pad" and row.ids("lost")]
    a = AltiumBackend().read(source).design
    b = AltiumBackend().read(_pcbdoc(altium)).design
    assert [len(_footprint(b, ref).pads) for ref in ("R1", "J1")] == [2, 2]
    report = compare_designs(a, b, level=5, tolerances=TOLERANCES, frame="relative")
    assert [(d.level, d.kind, d.where) for d in report.differences] == []


def test_level_five_sees_copper_that_reaches_a_lost_pad(tmp_path: Path) -> None:
    """Scenario "Copper that reaches a pad the other side lacks": with ``R1``'s pad 2 dropped on side b,
    level 5 reports ``route-connectivity`` on net ``B``: side a joins ``J1-2`` and ``R1-2``, side b
    ``J1-2`` alone. Without the pad's track the dropped pad is a level-3 difference only."""
    source, _, altium = _round_trip(tmp_path)
    a = AltiumBackend().read(source).design
    b = AltiumBackend().read(_pcbdoc(altium)).design
    r1 = _footprint(b, "R1")
    dropped = dataclasses.replace(r1, pads=tuple(p for p in r1.pads if p.number != "2"))
    board = _board(b)
    lost = dataclasses.replace(
        b,
        board=dataclasses.replace(
            board, footprints=tuple(dropped if fp.id == r1.id else fp for fp in board.footprints)
        ),
    )
    report = compare_designs(a, lost, level=5, tolerances=TOLERANCES, frame="relative")
    found = [(d.level, d.kind, d.where, d.a, d.b) for d in report.differences if d.level == 5]
    assert found == [(5, "route-connectivity", "B:J1-2", "J1-2,R1-2", "J1-2")]
    assert (3, "pad-missing", "R1-2") in [(d.level, d.kind, d.where) for d in report.differences]
