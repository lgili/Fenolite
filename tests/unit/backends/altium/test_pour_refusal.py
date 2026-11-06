# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Refusal of a pour (change c0215; capability altium-pour, "Refusal of a pour"): a polygon whose input the
engine cannot evaluate keeps its outline, and so does every later polygon of its layer that depends on it.
The forms the writer does not write (a hatched or shelved polygon, unshaped copper, a polygon query in a
rule) are made by changing the reading or the rule records."""

from __future__ import annotations

import dataclasses
import importlib.util

import pytest
from _altium_pour import Board, clearance, pad, rect, via, zone

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.pour import EXACT, REASONS, PourReading, PourResult, pour_reading
from fenolite.backends.altium.read.pcb import PolygonRecord
from fenolite.backends.altium.read.pcbprops import PropertyRecord
from fenolite.core.coords import Point
from fenolite.model.board import Graphic

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")


def _board() -> Board:
    """``GND_L01_P000`` (the first poured, around a ``VIN`` via) and a later ``VIN`` polygon overlapping it on
    the top layer, a ``VIN`` polygon far from both on the top layer, and a ``GND`` polygon on the bottom
    layer."""
    return Board(
        zones=(
            zone("z1", "GND", rect(1, 1, 20, 29), priority=3),
            zone("z2", "VIN", rect(15, 1, 30, 29), priority=2),
            zone("z3", "VIN", rect(33, 1, 39, 29), priority=1),
            zone("z4", "GND", layer="B.Cu"),
        ),
        pads=(pad("p1", "VIN", 25, 15, kind="thru_hole", shape="circle", size=(1.6, 1.6), drill=0.8),),
        vias=(via("v1", "GND", 5, 5), via("v2", "VIN", 36, 15), via("v3", "VIN", 10, 15)),
        rules=(clearance(0.2),),
    )


def _reasons(result: PourResult) -> dict[tuple[str | None, str], str]:
    return {(p.net, p.layer): p.reason for p in result.polygons if p.net != "VIN" or p.layer != "F.Cu"} | {
        ("VIN", f"F.Cu#{p.index}"): p.reason for p in result.polygons if p.net == "VIN" and p.layer == "F.Cu"
    }


def test_every_polygon_pours_without_a_refusal() -> None:
    _, result = _board().pour()
    assert [p.reason for p in result.polygons] == ["", "", "", ""]


def test_a_rule_scope_the_reader_does_not_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A rule scope the reader does not parse": a Clearance rule scoped
    ``InPolygon('GND_L01_P000')`` at priority 1 refuses that polygon (``rule-scope``) and the later VIN
    polygon that overlaps it (``depends-on-refused``); the far VIN polygon and the bottom polygon pour."""
    original = pcbdoc.rule_records

    def records(spec: pcbdoc.PcbDocSpec, filename: str) -> list[bytes]:
        keys = [
            ("GAP", "20mil"),
            ("GENERICCLEARANCE", "20mil"),
            ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
            ("OBJECTCLEARANCES", ""),
        ]
        extra = pcbdoc._rule(  # pyright: ignore[reportPrivateUsage]
            0, "Clearance", "polygon", "InPolygon('GND_L01_P000')", 1, keys, filename
        )
        return [extra, *original(spec, filename)]

    monkeypatch.setattr(pcbdoc, "rule_records", records)
    result = _board().write()
    assert result.pour is not None
    assert result.pour.unpoured == {"depends-on-refused": 1, "rule-scope": 1}
    assert {(reason, zone_id) for reason, zone_id, _ in result.pour.refused} == {
        ("rule-scope", "z1"),
        ("depends-on-refused", "z2"),
    }
    assert result.pour.poured == 2
    codes = [(i.code, i.severity, i.where) for i in result.pour.issues("pour.PcbDoc")]
    assert ("altium.zone-unpoured", "warning", "zone/z1") in codes
    assert ("altium.zone-unpoured", "warning", "zone/z2") in codes
    assert ("altium.zones-poured", "info", "pour.PcbDoc") in codes


def _with_record(reading: PourReading, index: int, **values: str) -> PourReading:
    polygons: list[PolygonRecord] = []
    for at, polygon in enumerate(reading.document.polygons):
        if at == index:
            fields = tuple((key, values.get(key, value)) for key, value in polygon.record.fields)
            polygon = dataclasses.replace(polygon, record=PropertyRecord(polygon.record.raw, fields))
        polygons.append(polygon)
    return dataclasses.replace(
        reading, document=dataclasses.replace(reading.document, polygons=tuple(polygons))
    )


def test_hatched_and_shelved_polygons() -> None:
    """Input I1: a hatched polygon and a shelved one are refused, and the later polygon that overlaps the
    first one depends on it."""
    reading = _board().base()
    hatched = pour_reading(_with_record(reading, 0, HATCHSTYLE="45Degree"))
    assert [p.reason for p in hatched.polygons] == ["hatched", "depends-on-refused", "", ""]
    shelved = pour_reading(_with_record(reading, 3, SHELVED="TRUE"))
    assert [p.reason for p in shelved.polygons] == ["", "", "", "shelved"]


def test_shelved_and_plane_layer_are_exact_outcomes() -> None:
    """Change c0463, D4: a shelved polygon and one on an internal plane pour no copper, as in Altium; they
    are exact outcomes (``exact``), and the later polygon that overlaps them is not held back."""
    reading = _board().base()
    for values in ({"SHELVED": "TRUE"}, {"LAYER": "PLANE1"}):
        result = pour_reading(_with_record(reading, 0, **values))
        first, second, *_ = result.polygons
        assert first.reason in EXACT and first.exact and not first.poured and first.pieces == ()
        assert [p.reason for p in result.polygons[1:]] == ["", "", ""]
        assert second.pieces
    hatched = pour_reading(_with_record(reading, 0, HATCHSTYLE="45Degree")).polygons[0]
    assert not hatched.exact


@pytest.mark.parametrize(
    "values",
    [
        {"POUROVERSTYLE": "0"},
        {"POUROVERSTYLE": "1"},
        {"POUROVERSTYLE": "2"},
        {"ARCRESOLUTION": "0.5mil"},
        {"ARCRESOLUTION": "0.0394mil"},
        {"ARCRESOLUTION": "0.5118mil"},
        {"ARCRESOLUTION": "0.3937mil"},
        {"ARCRESOLUTION": "0.01mm"},
        {"REMOVEISLANDSBYAREA": "TRUE", "AREATHRESHOLD": "250000000000.000000"},
        {"REMOVEISLANDSBYAREA": "TRUE", "AREATHRESHOLD": "232500465000.930304"},
        {"REMOVEISLANDSBYAREA": "TRUE", "AREATHRESHOLD": "15500031000.062008"},
        {"REMOVENECKS": "TRUE", "NECKWIDTHTHRESHOLD": "5mil"},
        {"REMOVENECKS": "TRUE", "NECKWIDTHTHRESHOLD": "0.127mm"},
    ],
    ids=lambda values: ",".join(f"{k}={v}" for k, v in values.items()),
)
def test_threshold_and_pour_over_read_every_documented_value(values: dict[str, str]) -> None:
    """Change c0463, task 3.3: every value of ``POUROVERSTYLE``, ``ARCRESOLUTION``, ``AREATHRESHOLD`` and
    ``NECKWIDTHTHRESHOLD`` that ``pcb-pour.md`` (I8, I10, I12, I14) records reads, so none refuses
    ``threshold`` or ``pour-over``; a value no source defines still does."""
    reading = _board().base()
    assert set(values) <= {key for key, _ in reading.document.polygons[0].record.fields}  # the keys are set
    assert pour_reading(_with_record(reading, 0, **values)).polygons[0].reason == ""


@pytest.mark.parametrize(
    ("values", "reason"),
    [
        ({"POUROVERSTYLE": "3"}, "pour-over"),
        ({"ARCRESOLUTION": "0mil"}, "threshold"),
        ({"REMOVEISLANDSBYAREA": "TRUE", "AREATHRESHOLD": "much"}, "threshold"),
    ],
)
def test_undefined_threshold_and_pour_over_refuse(values: dict[str, str], reason: str) -> None:
    reading = _board().base()
    assert pour_reading(_with_record(reading, 0, **values)).polygons[0].reason == reason


def test_unshaped_copper_within_reach() -> None:
    """Input I20: a graphic on the top layer within a polygon's reach refuses that polygon; one beyond every
    reach refuses none."""
    reading = _board().base()
    board = reading.design.board
    assert board is not None

    def with_graphic(x: int, y: int) -> PourReading:
        line = Graphic(
            id="g1", kind="line", layer="F.Cu", points=(Point(x, y), Point(x + 1_000_000, y)), width=200_000
        )
        return dataclasses.replace(
            reading,
            design=dataclasses.replace(reading.design, board=dataclasses.replace(board, graphics=(line,))),
        )

    zone_one = next(
        z for z in board.zones if z.provenance is not None and z.provenance.locator.endswith("#0")
    )
    inside = zone_one.outline[0]
    near = pour_reading(with_graphic(inside.x + 2_000_000, inside.y + 2_000_000))  # Y grows inward here
    assert near.polygons[0].reason == "unshaped-copper"
    far = pour_reading(with_graphic(inside.x - 900_000_000, inside.y))
    assert [p.reason for p in far.polygons] == ["", "", "", ""]


def test_no_board_outline() -> None:
    reading = dataclasses.replace(_board().base(), edges=None)
    assert {p.reason for p in pour_reading(reading).polygons} == {"no-board"}


def test_every_reason_is_listed() -> None:
    """Each reason the engine gives is a key of ``REASONS``."""
    assert {"rule-scope", "depends-on-refused", "copper-check", "hatched", "shelved", "unshaped-copper",
            "no-board", "connect-none", "connect-scope"} <= set(REASONS)  # fmt: skip
