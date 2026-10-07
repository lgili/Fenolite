# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A stack-up with masks, sheets and stated kinds in an Altium build (capability altium-build, "Stack-ups
with masks, sheets and kinds in an Altium build"; change c0101)."""

from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path

from _altium_copper import routed_build, routed_model
from _boards import four_layer_stackup, stack_entry, stack_of

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.errors import Issue
from fenolite.lens import altium_copper
from fenolite.model.board import Stackup
from fenolite.model.design import Design

FOUR = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
TWO = ("F.Cu", "B.Cu")


def script_stackup(*, masks: int = 10_000, finish: str = "", color: str = "") -> Stackup:
    """What a four-layer ``design.stackup()`` gives: masks, 35 and 17.5 µm copper, prepreg, core, prepreg."""
    return stack_of(
        stack_entry("F.Mask", "soldermask", masks, color=color),
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", 200_000, dielectric_kind="prepreg"),
        stack_entry("In1.Cu", "copper", 17_500),
        stack_entry("dielectric 2", "dielectric", 1_200_000, dielectric_kind="core"),
        stack_entry("In2.Cu", "copper", 17_500),
        stack_entry("dielectric 3", "dielectric", 200_000, dielectric_kind="prepreg"),
        stack_entry("B.Cu", "copper", 35_000),
        stack_entry("B.Mask", "soldermask", masks),
        finish=finish,
    )


def two_layers(kind: str | None) -> Stackup:
    return stack_of(
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", 1_500_000, dielectric_kind=kind),
        stack_entry("B.Cu", "copper", 35_000),
    )


def with_stackup(model: Design, stackup: Stackup) -> Design:
    assert model.board is not None
    return dataclasses.replace(model, board=dataclasses.replace(model.board, stackup=stackup))


def values(stackup: Stackup, layers: tuple[str, ...]) -> tuple[altium_copper.StackSpec, list[Issue]]:
    return altium_copper.stack_values(with_stackup(routed_model(), stackup), layers)


def stack_issues(issues: object) -> list[Issue]:
    return [i for i in issues if i.code == "altium.not-lowered" and i.where == "stackup"]  # type: ignore[attr-defined]


def test_masks_are_passed_over_and_stated_kinds_written() -> None:
    spec, issues = values(script_stackup(), FOUR)
    assert spec.thicknesses == (35_000, 17_500, 17_500, 35_000)
    assert [(d.kind, d.thickness) for d in spec.dielectrics] == [
        ("prepreg", 200_000),
        ("core", 1_200_000),
        ("prepreg", 200_000),
    ]
    (issue,) = issues
    assert (issue.code, issue.severity, issue.where) == ("altium.not-lowered", "info", "stackup")
    assert "the solder mask thickness" in issue.message
    for other in ("colour", "finish", "impedance"):
        assert other not in issue.message


def test_a_stated_kind_wins_over_the_table_by_count() -> None:
    by_count, none = values(two_layers(None), TWO)
    stated, issues = values(two_layers("prepreg"), TWO)
    assert [d.kind for d in by_count.dielectrics] == ["core"] and none == []
    assert [d.kind for d in stated.dielectrics] == ["prepreg"] and issues == []
    assert altium_copper.dielectric_kinds(1) == ("core",)


def test_values_without_a_key_are_named_once() -> None:
    stackup = dataclasses.replace(script_stackup(finish="ENIG", color="Green"), impedance_controlled=True)
    spec, issues = values(stackup, FOUR)
    (issue,) = issues
    for what in ("the solder mask thickness", "the colours", "the finish", "the impedance-control flag"):
        assert what in issue.message
    assert "the copper and dielectric values are written" in issue.message
    assert spec.thicknesses == (35_000, 17_500, 17_500, 35_000)
    quiet, none = values(script_stackup(masks=0), FOUR)
    assert none == [] and quiet.dielectrics == spec.dielectrics


def test_two_sheets_in_one_gap_fall_back_to_the_defaults() -> None:
    spec, issues = values(four_layer_stackup(), FOUR)
    copper = pcbrecords.copper_stack(FOUR, ())
    assert spec == altium_copper.StackSpec.default(copper, ())
    (issue,) = issues
    assert (issue.severity, issue.where) == ("info", "stackup")
    assert "between In1.Cu and In2.Cu" in issue.message and "default stack values" in issue.message


def test_a_stackup_without_the_new_fields_gives_what_it_gave() -> None:
    """Copper and dielectric entries alone, as the Altium import gives them: the table by count, no issue."""
    plain = stack_of(
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("d1", "dielectric", 200_000, material="FR-4", epsilon_r="4.800"),
        stack_entry("In1.Cu", "copper", 17_500),
        stack_entry("d2", "dielectric", 1_200_000),
        stack_entry("In2.Cu", "copper", 17_500),
        stack_entry("d3", "dielectric", 200_000),
        stack_entry("B.Cu", "copper", 35_000),
    )
    spec, issues = values(plain, FOUR)
    assert issues == [] and [d.kind for d in spec.dielectrics] == list(altium_copper.dielectric_kinds(3))


def test_script_stackup_reaches_the_document() -> None:
    """The four-layer sample built with ``--target altium`` and its PCB document read back."""
    model = with_stackup(routed_model(), script_stackup())
    with tempfile.TemporaryDirectory() as folder:
        output = routed_build(Path(folder), model)
    (issue,) = stack_issues(output.issues)
    assert "the solder mask thickness" in issue.message and "finish" not in issue.message
    document = read_pcbdoc(output.files["routed.PcbDoc"], file="routed.PcbDoc")
    dielectrics = [entry for entry in document.board.stack if entry.kind == "dielectric"]
    assert [entry.diel_type for entry in dielectrics] == ["2", "1", "2"]  # prepreg, core, prepreg
    assert [entry.diel_height for entry in dielectrics] == ["7.874mil", "47.2441mil", "7.874mil"]
    copper = [entry.copper_thickness for entry in document.board.stack if entry.kind == "signal"]
    assert copper == ["1.378mil", "0.689mil", "0.689mil", "1.378mil"]
