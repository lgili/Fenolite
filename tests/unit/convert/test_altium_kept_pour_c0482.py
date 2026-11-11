# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The source's pour is kept (change c0482; capability design-conversion, "The source's pour is kept").

The source is authored for these tests: the board of ``tests/_altium_pour.py`` with one GND zone of one
outline on F.Cu and on B.Cu and a GND via, poured and written by Fenolite's own writer. Its regions stand
for the regions Altium saved."""

from __future__ import annotations

import dataclasses
import importlib.util
from collections import Counter
from pathlib import Path

import pytest
from _altium_pour import FILENAME, Board, clearance, rect, via, zone

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import zonepours

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")

OUTLINE = rect(2, 2, 38, 28)


def _board(*extra: object) -> Board:
    zones = (zone("z1", "GND", OUTLINE), zone("z2", "GND", OUTLINE, layer="B.Cu"))
    vias = (via("v1", "GND", 20, 15), *extra)
    return Board(zones=zones, vias=vias, rules=(clearance(0.2),))  # type: ignore[arg-type]


def _regions(data: bytes) -> Counter[bytes]:
    """The pour regions of a document, plain and shape-based, each without its polygon index."""
    document = read_pcbdoc(data, file=FILENAME)
    found: Counter[bytes] = Counter()
    for records in (document.regions, document.shape_regions):
        for record in records:
            if isinstance(record, RegionRecord) and record.prefix.polygon is not None:
                found[record.raw[:10] + record.raw[12:]] += 1
    return found


def _kept(data: bytes, *, failed: bool = False) -> dict[str, pcbdoc.KeptPour]:
    """The pours of a written document, as a conversion to KiCad carries them."""
    document = read_pcbdoc(data, file=FILENAME)
    kept: dict[str, pcbdoc.KeptPour] = {}
    for index, polygon in enumerate(document.polygons):
        plain = document.regions_of(index)
        shapes = [
            r for r in document.shape_regions if isinstance(r, RegionRecord) and r.prefix.polygon == index
        ]
        kept[str(index)] = pcbdoc.KeptPour(
            tuple((v.x, v.y) for v in polygon.vertices),
            "GND",
            tuple((a.raw, b.raw) for a, b in zip(plain, shapes, strict=True)),
            polygon.record.get("LAYER") or "",
            failed,
        )
    return kept


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def test_writer_keeps_the_carried_regions() -> None:
    """The writer writes the carried regions of both polygons, which share one outline and net."""
    source = _board().write().data
    spec = dataclasses.replace(_board().spec(), kept_pours=_kept(source))
    written = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="computed")
    assert written.pour is not None and written.pour.kept and written.pour.poured == 2
    assert _regions(written.data) == _regions(source) and sum(_regions(source).values()) >= 4


def test_a_new_fault_computes_the_pour() -> None:
    """A via of another net inside the pour is a fault the source's pour does not have: the pour is
    computed. With the source failing the check itself, the carried regions stand."""
    source = _board().write().data
    other = via("v2", "VCC", 30, 20)
    spec = dataclasses.replace(_board(other).spec(), kept_pours=_kept(source))
    computed = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="computed")
    assert computed.pour is not None and not computed.pour.kept
    spec = dataclasses.replace(_board(other).spec(), kept_pours=_kept(source, failed=True))
    kept = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="computed")
    assert kept.pour is not None and kept.pour.kept


def test_an_edited_outline_computes_the_pour() -> None:
    source = _board().write().data
    moved = Board(zones=(zone("z1", "GND", rect(2, 2, 37, 28)), zone("z2", "GND", OUTLINE, layer="B.Cu")),
                  vias=(via("v1", "GND", 20, 15),), rules=(clearance(0.2),))  # fmt: skip
    spec = dataclasses.replace(moved.spec(), kept_pours=_kept(source))
    written = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="computed")
    assert written.pour is not None and not written.pour.kept


def test_carrier_round_trip() -> None:
    kept = _kept(_board().write().data, failed=True)
    text = zonepours.carrier_text(kept.items())
    assert zonepours.read_carrier(text.encode("utf-8")) == kept
    assert zonepours.read_carrier(b'{"schema":"other"}') == {}


def test_conversion_through_kicad_keeps_the_pour(tmp_path: Path) -> None:
    """Scenario "The source's pour comes back": Altium to KiCad carries both pours; the way back writes the
    source's regions and reports no zone fill changed."""
    (tmp_path / "altium").mkdir()
    source = tmp_path / "altium" / FILENAME
    source.write_bytes(_board().write().data)
    to_kicad = convert(source, to="kicad", allow_lossy=True, verify=False)
    (board,) = _write(to_kicad, tmp_path / "kicad").glob("*.kicad_pcb")
    carried = zonepours.read_carrier(
        boardcarrier.carried(board.read_text(encoding="utf-8")).get(zonepours.PROPERTY)
    )
    assert sorted(p.layer for p in carried.values()) == ["BOTTOM", "TOP"]
    back = convert(board, to="altium", allow_lossy=True, verify=False)
    assert "zone-fill" not in {r.kind for r in back.conversion.report.rows if r.changed}
    (document,) = _write(back, tmp_path / "back").glob("*.PcbDoc")
    assert _regions(document.read_bytes()) == _regions(source.read_bytes())
