# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A derived courtyard is not written back to Altium (change c0489; capability design-conversion). The
source is the committed sample ``tests/data/altium/blink``, written by Fenolite's own writer, whose three
footprints get a derived courtyard on import."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from fenolite.api.board import read_board
from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.lower import from_design
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import derivedcourtyards
from fenolite.core.coords import Point
from fenolite.core.errors import Issue

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")

SOURCE = Path(__file__).resolve().parents[2] / "data" / "altium" / "blink" / "blink.PcbDoc"


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (found,) = [*folder.glob("*.kicad_pcb"), *folder.glob("*.PcbDoc")]
    return found


def _primitives(path: Path) -> dict[str, int]:
    doc = read_pcbdoc(path.read_bytes())
    kinds = ("pads", "vias", "tracks", "arcs", "texts", "fills", "regions", "components")
    return {kind: len(getattr(doc, kind)) for kind in kinds}


def _courtyards(path: Path) -> int:
    board = read_board(path).design.board
    assert board is not None
    return sum(1 for fp in board.footprints for g in fp.graphics if g.layer.endswith("CrtYd"))


def test_the_altium_writer_skips_a_derived_courtyard(tmp_path: Path) -> None:
    design = read_board(SOURCE).design
    assert len(derivedcourtyards.found(design)) == 3
    issues: list[Issue] = []
    inputs = from_design(design, issues=issues)
    assert inputs.pcb is not None
    path = tmp_path / "blink.PcbDoc"
    path.write_bytes(pcbdoc.write_pcbdoc_result(inputs.pcb, filename=path.name, pour="outline").data)
    assert _primitives(path) == _primitives(SOURCE)


def test_carrier_round_trip() -> None:
    rows = [("R1", "F.CrtYd", (Point(0, 0), Point(1, 0), Point(1, 1))), ("U1", "B.CrtYd", (Point(-1, 2),))]
    assert sorted(derivedcourtyards.read_carrier(derivedcourtyards.carrier_text(rows).encode())) == sorted(
        rows
    )
    assert derivedcourtyards.read_carrier(b'{"schema":"other","courtyards":[]}') == []
    assert derivedcourtyards.read_carrier(b"not json") == []


def test_altium_to_altium_through_kicad(tmp_path: Path) -> None:
    """Scenario "Altium to Altium through KiCad"."""
    board = _write(convert(SOURCE, to="kicad", allow_lossy=True, verify=False), tmp_path / "k")
    text = board.read_text(encoding="utf-8")
    assert text.count('(layer "F.CrtYd")') + text.count('(layer "B.CrtYd")') == 3
    carried = boardcarrier.carried(text)
    assert len(derivedcourtyards.read_carrier(carried.get(derivedcourtyards.PROPERTY))) == 3
    back = _write(convert(board, to="altium", allow_lossy=True, verify=False), tmp_path / "b")
    assert _courtyards(back) == 3  # derived again on import, none read from the document
    assert _primitives(back) == _primitives(SOURCE)


def test_an_edited_courtyard_is_kept(tmp_path: Path) -> None:
    """Scenario "An edited courtyard is kept": one point of one courtyard moved by 0.1 mm."""
    board = _write(convert(SOURCE, to="kicad", allow_lossy=True, verify=False), tmp_path / "k")
    text = board.read_text(encoding="utf-8")
    poly = re.search(r"\(fp_poly\n\s*\(pts\n\s*\(xy ([-\d.]+) ([-\d.]+)\)", text)
    assert poly is not None
    moved = f"{float(poly.group(1)) + 0.1:.6f}".rstrip("0").rstrip(".")
    board.write_text(text.replace(poly.group(0), poly.group(0).replace(poly.group(1), moved, 1), 1), "utf-8")
    back = _write(convert(board, to="altium", allow_lossy=True, verify=False), tmp_path / "b")
    before, after = _primitives(SOURCE), _primitives(back)
    drawn = sum(after[k] - before[k] for k in ("tracks", "arcs", "fills", "regions"))
    assert drawn >= 1  # the edited courtyard is a drawing of its footprint
