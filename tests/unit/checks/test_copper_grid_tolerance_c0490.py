# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The grid tolerance of an Altium document and the tolerance stated in a finding (capability
copper-check, "Grid tolerance of an Altium document" and "The tolerance is stated in the finding"; change
c0490). Every document here is authored for Fenolite."""

from __future__ import annotations

import dataclasses

import _altium_records as rec
import pytest
from _coppercheck import Copper, mm

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.backend import CLEARANCE_TOLERANCE_NM, AltiumBackend
from fenolite.backends.altium.read import pcb
from fenolite.backends.altium.read.proptext import parse_length
from fenolite.backends.kicad.triad import write_triad
from fenolite.checks.copper import check_copper
from fenolite.cli.cmd_build import copper_guard
from fenolite.core.coords import Point


def _altium(gap: int, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN202
    """An authored document with a 0.25 mm Clearance rule and two 10 mil tracks of two nets, the second
    moved in the model so that the edges are ``gap`` nm apart; the copper report of its rules view."""
    rule = rec.rule("Clearance", "Clearance", GAP="0.25mm", GENERICCLEARANCE="0.25mm", OBJECTCLEARANCES="")
    tracks = [
        rec.track((0, 0), (10_000_000, 0), 100_000, net=0),
        rec.track((0, 300_000), (10_000_000, 300_000), 100_000, net=1),
    ]
    document = rec.document(nets=("A", "B"), rules=[rule], tracks=tracks)
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    first, second = design.board.tracks
    sign = 1 if second.start.y > first.start.y else -1
    y = first.start.y + sign * (first.width + gap)
    moved = dataclasses.replace(second, start=Point(second.start.x, y), end=Point(second.end.x, y))
    board = dataclasses.replace(design.board, tracks=(first, moved))
    monkeypatch.setattr(pcb, "read_rule_fields", lambda data, file: [r.fields for r in document.rules])
    rules = AltiumBackend().rules_from_bytes(
        dataclasses.replace(design, board=board), b"document", file="a.PcbDoc"
    )
    return check_copper(
        rules.design,
        pads=(),
        tolerance=rules.clearance_tolerance,
        tolerance_source=rules.tolerance_source,
    )


def test_a_rule_saved_in_mil_reads_within_half_a_unit() -> None:
    """Case 2 of design D2: a metric rule saved in mil with four decimals reads within half a file unit
    (1.27 nm) of the metric value; with Altium's 3.5 units it makes the four units of the tolerance."""
    assert parse_length("9.8425mil") == 250_000  # 249 999.5 nm, half to even
    assert abs(parse_length("3.937mil") - 100_000) <= 1  # type: ignore[operator]


def test_a_gap_a_few_units_short(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A gap a few units short": two file units (5.08 nm, read 6 nm) below the rule."""
    report = _altium(250_000 - 6, monkeypatch)
    assert [f.code for f in report.findings] == []
    assert report.summary["tolerated"] == 1
    assert report.summary["tolerance"] == CLEARANCE_TOLERANCE_NM == 11


def test_a_gap_beyond_the_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A gap beyond the tolerance": 1 nm below the rule less the tolerance."""
    report = _altium(250_000 - CLEARANCE_TOLERANCE_NM - 1, monkeypatch)
    (found,) = report.findings
    assert found.code == "copper.clearance" and found.clearance == 250_000
    assert found.message.endswith(
        "; the clearance is 0.25 mm (rule:Clearance), less a tolerance of 0.000011 mm "
        "(4 units of the Altium grid)"
    )
    assert "tolerated" not in report.summary


def _kicad(edge_gap: int) -> Copper:
    made = Copper()
    made.netclass("Signal", mm(0.2))
    made.net("A", "Signal")
    made.net("B", "Signal")
    made.track("A", Point(0, 0), Point(mm(10), 0), width=250_000)
    made.track("B", Point(0, 250_000 + edge_gap), Point(mm(10), 250_000 + edge_gap), width=250_000)
    return made


def test_the_message_of_a_kicad_finding() -> None:
    """Scenario "The message of a KiCad finding": the KiCad rules view of the build's guard."""
    texts = write_triad(_kicad(mm(0.2) - 600).build(), name="bench", target=10)
    files = {name: text.encode("utf-8") for name, text in texts.items()}
    issues, _ = copper_guard(files, name="bench", mode="refuse", target=10)
    (found,) = [issue for issue in issues if issue.code == "copper.clearance"]
    assert "the clearance is 0.2 mm (" in found.message
    assert found.message.endswith(", less a tolerance of 0.0005 mm (KiCad's DRC epsilon)")


def test_a_strict_check_keeps_its_message() -> None:
    """A check with a tolerance of 0 gives the message it gave before, byte for byte."""
    report = check_copper(_kicad(mm(0.2) - 600).build(), pads=None)
    (found,) = report.findings
    assert found.message == (
        "copper of A and B is 0.1994 mm apart on F.Cu at (0, 0.2247) mm; the clearance is 0.2 mm "
        "(class:Signal)"
    )
    assert "tolerated" not in report.summary and "tolerance" not in report.summary
