# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The direction from KiCad to Altium (capability design-conversion, "KiCad to Altium direction",
"Changes of the Altium direction" and "Lossy conversions need consent"; change c0159)."""

from __future__ import annotations

import dataclasses

import pytest
from _convert import TWO_LAYER, read_as, two_layer, with_pads

from fenolite.backends.altium import lower
from fenolite.backends.altium.cfb import CompoundTooLarge
from fenolite.convert import LossyConversionError, TargetLimitError, convert_project, to_altium
from fenolite.core.evidence import Level
from fenolite.model.design import Design


def _lossy() -> Design:
    """The two-layer board with one custom pad and one component not fitted."""
    design, _, _ = with_pads(two_layer(), {"shape": "custom"})
    first = design.circuit.components[0]
    circuit = dataclasses.replace(
        design.circuit, components=(dataclasses.replace(first, dnp=True), *design.circuit.components[1:])
    )
    return dataclasses.replace(design, circuit=circuit)


def test_exit_7_without_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Exit 7 without consent", without the CLI: a lost pad and a lost fitted flag are refused
    with one issue per kind; with consent the conversion completes with one ``convert.lossy`` per kind."""
    read_as(monkeypatch, _lossy())
    with pytest.raises(LossyConversionError) as refused:
        convert_project("two_layer.kicad_pcb", to="altium")
    assert refused.value.cli_code == "FEN-7001"
    assert [(i.code, i.severity, i.where) for i in refused.value.issues] == [
        ("convert.lossy", "warning", "dnp"),
        ("convert.lossy", "warning", "pad"),
    ]
    assert refused.value.issues[0].message.startswith("1 of 1 dnp item(s)")
    assert (
        refused.value.issues[1].message.startswith("1 of 4 pad item(s)")
        and "custom" in refused.value.issues[1].message
    )
    conversion = convert_project("two_layer.kicad_pcb", to="altium", allow_lossy=True)
    lossy = [i.where for i in conversion.issues if i.code == "convert.lossy"]
    assert lossy == ["dnp", "pad"] and conversion.report.refused == ("dnp", "pad")
    dnp = conversion.report.row("dnp")
    assert dnp is not None and (dnp.source, dnp.lost) == (1, 1)
    assert dnp.reasons[0].reason == lower.DNP_REASON


def test_unpoured_polygon_is_a_change() -> None:
    """Scenario "Unpoured polygon is a change": the filled zone of the sample and the generated schematic
    are changes, with one ``convert.changed`` info each, and nothing is lost."""
    conversion = convert_project(TWO_LAYER, to="altium")
    fill = conversion.report.row("zone-fill")
    schematic = conversion.report.row("schematic")
    assert fill is not None and fill.changed > 0 and fill.lost == 0
    assert schematic is not None and (schematic.changed, schematic.lost) == (1, 0)
    assert not conversion.report.lossy
    assert [i.where for i in conversion.issues if i.code == "convert.changed"] == ["zone-fill", "schematic"]
    assert not [i for i in conversion.issues if i.code == lower.NOT_LOWERED]


def test_experimental_and_inferred() -> None:
    conversion = convert_project(TWO_LAYER, to="altium")
    assert conversion.direction.experimental and conversion.direction is to_altium.DIRECTION
    assert conversion.evidence.level == Level.INFERRED
    assert {"H-A-VER-RTA2-3", "H-G-CONV-LEDGER"} <= set(conversion.evidence.hypotheses)


def test_bodies_reach_the_writer() -> None:
    """``bodies="off"`` writes no component body: each one the board holds is a reported loss."""
    off = convert_project(TWO_LAYER, to="altium", bodies="off")
    body = off.report.row("body")
    held = sum(len(fp.bodies) for fp in two_layer().board.footprints)  # type: ignore[union-attr]
    assert (body.lost if body is not None else 0) == held


def test_document_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    """A document the writer cannot hold is refused as a whole, with or without consent."""

    def too_large(*_args: object, **_kwargs: object) -> None:
        raise CompoundTooLarge("the compound file needs 119 FAT sectors")

    monkeypatch.setattr(lower, "write_design", too_large)
    with pytest.raises(TargetLimitError, match="119 FAT sectors") as refused:
        convert_project(TWO_LAYER, to="altium", allow_lossy=True)
    assert "DIFAT" in refused.value.hint
