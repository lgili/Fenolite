# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DRC violations as located issues (capability verification-loop, "DRC findings as issues"; change c0020)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.base import DrcItem, DrcReport, DrcViolation
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.drc_json import (
    RESERVED_SUFFIXES,
    finding_issues,
    finding_types,
    format_position,
    issue_severity,
    item_locations,
    sanitise,
    type_code,
)
from fenolite.core.coords import Point
from fenolite.core.errors import ISSUE_CODE
from fenolite.model.design import Design

TWO_LAYER = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _design() -> Design:
    return read_board(TWO_LAYER.read_text(encoding="utf-8"), file=TWO_LAYER.name)


def _report(
    *violations: DrcViolation,
    unconnected: tuple[DrcViolation, ...] = (),
    source: str = "b.kicad_pcb",
    parity: tuple[DrcViolation, ...] = (),
) -> DrcReport:
    return DrcReport(
        source,
        "",
        "10.0.6",
        "mm",
        violations=violations,
        unconnected_items=unconnected,
        schematic_parity=parity,
    )


def _item(uuid: str, x: int = 0, y: int = 0) -> DrcItem:
    return DrcItem(uuid, "item", Point(x, y))


def _pad(design: Design, ref: str, number: str) -> str:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    fp = next(f for f in design.board.footprints if refs[f.component_id] == ref)
    return next(p for p in fp.pads if p.number == number).native_ids["kicad"]


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("shorting_items", "kicad.drc.shorting-items"),
        ("lib_footprint_mismatch", "kicad.drc.lib-footprint-mismatch"),
        ("rules_not_loaded", "kicad.drc.type-rules-not-loaded"),
        ("rules-unchecked", "kicad.drc.type-rules-unchecked"),
        ("", "kicad.drc.unknown"),
        ("__", "kicad.drc.unknown"),
        ("Odd  Type!!x", "kicad.drc.odd-type-x"),
        ("-a__b-", "kicad.drc.a-b"),
    ],
)
def test_codes_without_underscores(raw: str, code: str) -> None:
    assert type_code("kicad", raw) == code and ISSUE_CODE.match(code)
    assert code.rsplit(".", 1)[1] not in RESERVED_SUFFIXES


def test_ref_pin_and_locator() -> None:
    design = _design()
    assert design.board is not None
    track = design.board.tracks[0]
    assert track.provenance is not None
    violation = DrcViolation(
        "clearance", "too close", "error", (_item(track.native_ids["kicad"]), _item(_pad(design, "R1", "2")))
    )
    (found,) = finding_issues(_report(violation), oracle="kicad", design=design)
    assert (found.code, found.severity) == ("kicad.drc.clearance", "error")
    assert found.where == f"{track.provenance.locator}, R1-2"
    assert found.message == "clearance: too close"


def test_footprint_and_unnumbered_pad_give_the_reference() -> None:
    design = _design()
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    fp = design.board.footprints[0]
    locations = item_locations(design, "kicad")
    assert locations[fp.native_ids["kicad"]] == refs[fp.component_id]
    pads = tuple(dataclasses.replace(p, number="") for p in fp.pads)
    board = dataclasses.replace(design.board, footprints=(dataclasses.replace(fp, pads=pads),))
    unnumbered = item_locations(dataclasses.replace(design, board=board), "kicad")
    assert {unnumbered[p.native_ids["kicad"]] for p in pads} == {refs[fp.component_id]}


def test_unknown_item_gives_the_position() -> None:
    violation = DrcViolation("clearance", "d", "error", (_item("no-such-uuid", 12_500_000, 3_250_000),))
    (found,) = finding_issues(_report(violation), oracle="kicad", design=_design())
    assert found.where == "@12.5,3.25"


def test_repeated_uuid_and_refused_read_give_positions() -> None:
    design = _design()
    assert design.board is not None
    fp = design.board.footprints[0]
    same = fp.pads[0].native_ids
    pads = tuple(dataclasses.replace(p, native_ids=same) for p in fp.pads)
    board = dataclasses.replace(design.board, footprints=(dataclasses.replace(fp, pads=pads),))
    repeated = dataclasses.replace(design, board=board)
    assert same["kicad"] not in item_locations(repeated, "kicad")
    pad = _pad(design, "R1", "2")
    violation = DrcViolation("clearance", "d", "error", (_item(pad, -1_000_000, 500),))
    (refused,) = finding_issues(_report(violation), oracle="kicad", design=None)
    assert refused.where == "@-1,0.0005"
    assert item_locations(None, "kicad") == {} and item_locations(design, "other") == {}


@pytest.mark.parametrize(
    ("point", "text"),
    [
        (Point(12_500_000, 3_250_000), "@12.5,3.25"),
        (Point(0, 0), "@0,0"),
        (Point(-1, 1_000_000), "@-0.000001,1"),
        (Point(100_000_000, -20_000_001), "@100,-20.000001"),
    ],
)
def test_format_position(point: Point, text: str) -> None:
    assert format_position(point) == text


def test_excluded_and_unknown_severities() -> None:
    excluded = DrcViolation("clearance", "d", "error", excluded=True)
    fatal = DrcViolation("clearance", "d", "fatal")
    warning = DrcViolation("clearance", "d", "warning")
    assert [issue_severity(v) for v in (excluded, fatal, warning)] == ["info", "error", "warning"]
    found = finding_issues(_report(excluded, fatal), oracle="kicad", design=None)
    assert [i.severity for i in found] == ["info", "error"]


def test_paths_removed_from_messages() -> None:
    home = str(Path.home())
    violation = DrcViolation("lib_footprint_issues", f"/tmp/fenolite-kicad-x/lib and {home}/libs", "warning")
    report = _report(violation, source="/tmp/fenolite-kicad-x/b.kicad_pcb")
    (found,) = finding_issues(report, oracle="kicad", design=None)
    assert found.message == "lib_footprint_issues: <tmp>/lib and ~/libs"
    assert "/tmp/" not in found.message and home not in found.message
    assert sanitise("x/y", source="b.kicad_pcb") == "x/y"  # a bare name has no folder to replace


def test_unconnected_mapped_and_parity_only_counted() -> None:
    open_net = DrcViolation("unconnected_items", "missing", "error", (_item("u1"), _item("u2", 1_000_000, 0)))
    parity = DrcViolation("footprint_missing", "p", "error")
    report = _report(unconnected=(open_net,), parity=(parity,))
    (found,) = finding_issues(report, oracle="kicad", design=None)
    assert (found.code, found.where) == ("kicad.drc.unconnected-items", "@0,0, @1,0")
    assert finding_types(report, oracle="kicad") == {"kicad.drc.unconnected-items": "unconnected_items"}


def test_order_follows_the_report() -> None:
    first = DrcViolation("b_type", "1", "error")
    second = DrcViolation("a_type", "2", "warning")
    found = finding_issues(_report(first, second), oracle="fake", design=None)
    assert [i.code for i in found] == ["fake.drc.b-type", "fake.drc.a-type"]
    assert list(finding_types(_report(first, second), oracle="fake")) == [
        "fake.drc.a-type",
        "fake.drc.b-type",
    ]
