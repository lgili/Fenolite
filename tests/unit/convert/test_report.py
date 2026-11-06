# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The conversion report: kinds, rows and reasons (capability design-conversion, "Conversion report" and
"Conversion kinds"; change c0159)."""

from __future__ import annotations

import dataclasses

import pytest
from _convert import read_as, two_layer, with_pads
from _gensheets import BLINK

from fenolite.backends.altium import lower
from fenolite.convert import DIRECTIONS, convert_project
from fenolite.convert.report import (
    BY_NAME,
    EXPLAINS,
    KINDS,
    REFUSE,
    SOURCE,
    ConversionReport,
    Explainer,
    Reason,
    ReportRow,
    merge,
)
from fenolite.convert.sources import read_source


def test_kinds_are_closed() -> None:
    """Scenario "Vocabulary is closed": every kind that ``lower`` can report and every kind a registered
    direction names is a row of ``KINDS``; the table has no repeat."""
    names = [row.name for row in KINDS]
    assert len(names) == len(set(names))
    named = {*lower.KINDS, *lower.MORE_KINDS, lower.PLACEMENT_RULE_KIND, lower.KEEPOUT_FOOTPRINTS_KIND}
    for direction in DIRECTIONS.values():
        named |= set(direction.kinds)
    assert named <= set(BY_NAME)


def test_loss_classes_closed() -> None:
    """Every kind of ``lower.LOSS_KINDS`` and ``dnp`` are ``refuse``, and no other kind is."""
    assert REFUSE == lower.LOSS_KINDS | {"dnp"}


def test_explains_closed() -> None:
    """Every lost kind of ``EXPLAINS`` is a row of ``KINDS`` (``SOURCE`` aside), and every difference kind
    it names is one of the comparison's."""
    from fenolite.checks.equivalence.model import KINDS as DIFFERENCES

    kinds = {kind for _, kind, _ in DIFFERENCES}
    for row in EXPLAINS:
        assert row.kind in BY_NAME or row.kind == SOURCE
        assert set(row.differences) <= kinds


def test_rows_in_table_order_and_counts() -> None:
    report = ConversionReport.of(
        source={"pad": 10, "footprint": 2},
        written={"pad": 7},
        lost={"pad": {"b": ("1", "2"), "a": ("3",)}},
        changed={"zone-fill": {"unpoured": ("z",)}},
    )
    assert [row.kind for row in report.rows] == ["footprint", "pad", "zone-fill"]
    pad = report.row("pad")
    assert pad is not None and (pad.source, pad.written, pad.changed, pad.lost) == (10, 7, 0, 3)
    assert [(r.reason, r.count) for r in pad.reasons] == [("b", 2), ("a", 1)]
    fill = report.row("zone-fill")
    assert fill is not None and (fill.source, fill.written, fill.changed, fill.lost) == (1, 0, 1, 0)
    assert report.lossy and report.refused == ("pad",)
    data = report.to_json()
    assert data["refused"] == ["pad"] and "ids" not in data["rows"][1]["reasons"][0]
    assert report.to_json(ids=True)["rows"][1]["reasons"][0]["ids"] == ["1", "2"]


def test_merge_adds_counts_and_joins_reasons() -> None:
    one = ConversionReport.of(source={"pad": 2}, lost={"pad": {"r": ("1",)}})
    two = ConversionReport.of(source={"pad": 3}, lost={"pad": {"r": ("2",), "s": ("3",)}})
    pad = merge(one, two).row("pad")
    assert pad is not None and (pad.source, pad.lost) == (5, 3)
    assert [(r.reason, r.ids) for r in pad.reasons] == [("r", ("1", "2")), ("s", ("3",))]


def test_reasons_are_counted_apart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Reasons are counted apart" (amended by changes c0160 and c0433): one custom pad and two
    connector pads give the row ``pad`` with ``lost`` 1 (the custom shape) and ``changed`` 2 (the two pads
    written as surface pads without openings), each under its own reason."""
    design, _, _ = with_pads(two_layer(), {"shape": "custom"}, {"kind": "connect"}, {"kind": "connect"})
    read_as(monkeypatch, design)
    conversion = convert_project("two_layer.kicad_pcb", to="altium", allow_lossy=True)
    pad = conversion.report.row("pad")
    assert pad is not None and pad.lost == 1 and pad.changed == 2
    by_outcome = {reason.outcome: reason for reason in pad.reasons}
    assert by_outcome["lost"].count == 1 and "custom" in by_outcome["lost"].reason
    assert by_outcome["changed"].count == 2 and "connector" in by_outcome["changed"].reason


def test_explainer_locates_lost_pads(monkeypatch: pytest.MonkeyPatch) -> None:
    design, (pad_id,), ref = with_pads(two_layer(), {"shape": "custom"})
    read_as(monkeypatch, design)
    conversion = convert_project("two_layer.kicad_pcb", to="altium", allow_lossy=True)
    explainer = Explainer(conversion.design, conversion.report)
    number = next(p.number for fp in design.board.footprints for p in fp.pads if p.id == pad_id)  # type: ignore[union-attr]
    assert explainer.explain("pad-missing", f"{ref}-{number}", "1", "0") == "pad"
    assert explainer.explain("pad-size", f"{ref}-{number}", "1", "2") is None
    assert explainer.explain("position", ref, "0,0", "1,1") is None
    assert explainer.explain("ref-ambiguous", "X", "2", "2") == SOURCE
    assert explainer.explain("ref-ambiguous", "X", "1", "2") is None


def test_lost_schematic_explains_a_designator_used_twice() -> None:
    """Change c0425: when the schematic is lost for duplicate designators, a reference that the source
    circuit holds twice (the public Altium blink with a second ``R1``, made in memory) explains its
    ``ref-ambiguous``; a reference held once does not, and without the lost row nothing is explained."""
    design = read_source(BLINK).design
    first = next(c for c in design.circuit.components if c.ref == "R1")
    twin = dataclasses.replace(first, id=f"{first.id}-twin")
    circuit = dataclasses.replace(design.circuit, components=(*design.circuit.components, twin))
    design = dataclasses.replace(design, circuit=circuit)
    lost = ConversionReport.of(
        source={"schematic": 1},
        lost={"schematic": {"the imported circuit has duplicate designators": ("s",)}},
    )
    explainer = Explainer(design, lost)
    assert explainer.explain("ref-ambiguous", "R1", "2", "1") == "schematic"
    assert explainer.explain("ref-ambiguous", "R1", "2", "0") == "schematic"
    assert explainer.explain("ref-ambiguous", "D1", "1", "2") is None
    kept = Explainer(design, ConversionReport.of(source={"schematic": 1}))
    assert kept.explain("ref-ambiguous", "R1", "2", "1") is None


def test_kept_items_are_not_losses() -> None:
    """Scenario "Kept items are not losses" (capability design-conversion, "Conversion report"; change
    c0424)."""
    report = ConversionReport.of(
        source={"rule": 2}, kept={"rule": {"KiCad has no routing topology rule": ["rul-1"]}}
    )
    row = report.row("rule")
    assert row is not None
    assert (row.source, row.written, row.changed, row.lost, row.kept) == (2, 1, 0, 0, 1)
    assert [r.outcome for r in row.reasons] == ["kept"]
    assert not report.lossy and report.refused == ()
    assert row.to_json()["kept"] == 1
    plain = ConversionReport.of(source={"rule": 1}).row("rule")
    assert plain is not None and "kept" not in plain.to_json()
    twice = (Reason(row.reasons[0].reason, "kept", ("rul-1", "rul-1")),)
    assert merge(report, report).row("rule") == ReportRow("rule", 4, 2, 0, 0, twice, 2)
