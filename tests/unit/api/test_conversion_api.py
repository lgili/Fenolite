# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.convert``: the verification of a conversion (capability design-conversion, "Conversion
verified by equivalence", "Differences matched to the report" and "Conversion without verification";
change c0159)."""

from __future__ import annotations

import dataclasses

import pytest
from _convert import TWO_LAYER, read_as, two_layer, with_pads

import fenolite.convert as convert_package
from fenolite.api import ConversionResult, convert
from fenolite.api.conversion import profiles
from fenolite.convert import to_altium
from fenolite.convert.direction import Options, Written
from fenolite.convert.sources import SourceProject
from fenolite.core.coords import Point
from fenolite.core.evidence import Level


def test_profiles_load() -> None:
    found = profiles()
    assert sorted(found) == ["kicad-to-altium", "kicad-to-kicad"]
    altium = found["kicad-to-altium"]
    assert (altium.frame, altium.tolerance_nm, altium.tolerance_ppm) == ("relative", 3, 20)
    assert (found["kicad-to-kicad"].frame, found["kicad-to-kicad"].tolerance_nm) == ("absolute", 0)


def test_sample_verified() -> None:
    """Scenario "Sample verified": the two-layer sample reads back equal at level 5."""
    result = convert(TWO_LAYER, to="altium")
    reply = result.equivalence_json()
    assert reply is not None and reply["level"] == 5 and reply["equivalent"] is True
    assert reply["profile"]["name"] == "kicad-to-altium" and reply["frame"] == "relative"
    assert reply["explained"] == [] and reply["unexplained"] == 0
    assert not [i for i in result.issues if i.severity == "error"]
    assert result.evidence.level == Level.INFERRED


def test_lost_pad_explains_its_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Lost pad explains its pin": the custom pad is lost, and the ``pad-missing`` and
    ``pin-missing`` differences at its ``REF-PIN`` are explained by the kind ``pad``."""
    design, (pad_id,), ref = with_pads(two_layer(), {"shape": "custom"})
    number = next(p.number for fp in design.board.footprints for p in fp.pads if p.id == pad_id)  # type: ignore[union-attr]
    read_as(monkeypatch, design)
    result = convert("two_layer.kicad_pcb", to="altium", allow_lossy=True)
    found = {(e.difference.kind, e.difference.where, e.kind) for e in result.explained}
    where = f"{ref}-{number}"
    assert {("pad-missing", where, "pad"), ("pin-missing", where, "pad")} <= found
    assert result.unexplained == ()
    assert not [i for i in result.issues if i.code == "convert.unexplained"]
    reply = result.equivalence_json()
    assert reply is not None and {row["by"] for row in reply["explained"]} <= {"pad"}


def _moving(source: SourceProject, options: Options) -> Written:
    """The Altium direction with the first footprint moved by 1 mm, and nothing reported."""
    board = source.design.board
    assert board is not None
    first = board.footprints[0]
    moved = dataclasses.replace(first, position=Point(first.position.x + 1_000_000, first.position.y))
    board = dataclasses.replace(board, footprints=(moved, *board.footprints[1:]))
    written = to_altium.write(
        dataclasses.replace(source, design=dataclasses.replace(source.design, board=board)), options
    )
    return dataclasses.replace(written, design=source.design)


def test_undeclared_change_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Undeclared change is caught": a writer that moves a footprint by 1 mm and reports nothing
    gives one ``convert.unexplained`` error at the footprint's reference."""
    direction = dataclasses.replace(to_altium.DIRECTION, write=_moving)
    monkeypatch.setitem(convert_package.DIRECTIONS, ("kicad", "altium"), direction)
    result = convert(TWO_LAYER, to="altium")
    design = two_layer()
    assert design.board is not None
    ref = next(c.ref for c in design.circuit.components if c.id == design.board.footprints[0].component_id)
    errors = [i for i in result.issues if i.severity == "error"]
    assert [(i.code, i.where) for i in errors] == [("convert.unexplained", ref)]
    assert [(d.kind, d.where) for d in result.unexplained] == [("position", ref)]


def test_verification_skipped() -> None:
    """Scenario "Verification skipped": no comparison, one ``convert.no-verify`` warning, and the evidence
    ``UNVERIFIED``."""
    result = convert(TWO_LAYER, to="altium", verify=False)
    assert isinstance(result, ConversionResult) and result.equivalence is None
    assert result.equivalence_json() is None
    assert [i.code for i in result.issues if i.severity == "warning"] == ["convert.no-verify"]
    assert result.evidence.level == Level.UNVERIFIED


def test_kicad_retarget_verified() -> None:
    result = convert(TWO_LAYER, to="kicad", kicad_version=10)
    reply = result.equivalence_json()
    assert reply is not None and reply["equivalent"] is True and reply["frame"] == "absolute"
    assert reply["profile"]["name"] == "kicad-to-kicad"
