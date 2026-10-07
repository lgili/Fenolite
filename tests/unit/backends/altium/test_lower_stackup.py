# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A stack-up with masks, sheets and stated kinds in the write of a model as an Altium project (capability
altium-build, "Stack-ups with masks, sheets and kinds in an Altium build"; change c0101):
``backends.altium.lower.stack_from_stackup`` and the account of the write."""

from __future__ import annotations

import dataclasses

from _boards import STACKUP_FIXTURE, bare_board, four_layer_stackup, stack_entry, stack_of

from fenolite.backends.altium import lower
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.docboard import StackSpec
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.errors import Issue
from fenolite.lens.altium import write_model
from fenolite.model.board import Stackup
from fenolite.model.design import Design

TWO = ("F.Cu", "B.Cu")
FOUR = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def two_layers(kind: str | None, **more: object) -> Stackup:
    return stack_of(
        stack_entry("F.Mask", "soldermask", 0),
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", 1_500_000, dielectric_kind=kind),
        stack_entry("B.Cu", "copper", 35_000),
        **more,  # type: ignore[arg-type]
    )


def stack_issues(issues: tuple[Issue, ...]) -> list[Issue]:
    return [i for i in issues if i.code == "altium.not-lowered" and i.where == "stackup"]


def document_stack(design: Design) -> tuple[list[tuple[str | None, str | None]], tuple[Issue, ...]]:
    """The dielectrics of the written PCB document as (``DIELTYPE``, height), and the issues of the write."""
    written = write_model(design, allow_lossy=True)
    (name,) = [n for n in written.files if n.endswith(".PcbDoc")]
    document = read_pcbdoc(written.files[name], file=name)
    found = [(e.diel_type, e.diel_height) for e in document.board.stack if e.kind == "dielectric"]
    return found, written.issues


def test_a_stated_kind_is_written() -> None:
    ids = rec.copper_stack(TWO, ())
    by_count = lower.stack_from_stackup(two_layers(None), TWO, ids)
    stated = lower.stack_from_stackup(two_layers("prepreg"), TWO, ids)
    assert by_count is not None and [d.kind for d in by_count.dielectrics] == ["core"]
    assert stated is not None and [d.kind for d in stated.dielectrics] == ["prepreg"]
    assert stated.thicknesses == by_count.thicknesses == (35_000, 35_000)


def test_a_core_where_the_table_says_prepreg_in_the_document() -> None:
    plain, issues = document_stack(bare_board(2, two_layers(None)))
    stated, stated_issues = document_stack(bare_board(2, two_layers("prepreg")))
    assert [kind for kind, _ in plain] == ["1"] and [kind for kind, _ in stated] == ["2"]
    assert plain[0][1] == stated[0][1]
    assert stack_issues(issues) == [] and stack_issues(stated_issues) == []


def test_gap_and_values_without_a_key_are_named() -> None:
    assert lower.stack_gap(two_layers("core")) is None
    assert lower.stack_gap(four_layer_stackup()) == "between In1.Cu and In2.Cu (2 dielectric entries)"
    assert lower.stack_unheld(two_layers("core")) == ()
    held = dataclasses.replace(two_layers("core", finish="ENIG"), impedance_controlled=True)
    assert lower.stack_unheld(held) == ("the finish", "the impedance-control flag")
    assert lower.stack_unheld(four_layer_stackup()) == (
        "the solder mask thickness",
        "the colours",
        "the finish",
        "the impedance-control flag",
    )


def test_two_sheets_in_one_gap() -> None:
    """The four-layer KiCad board whose core holds two sheets, written as an Altium PCB document."""
    design = read_board(STACKUP_FIXTURE)
    assert design.board is not None and design.board.stackup is not None
    assert lower.stack_from_stackup(design.board.stackup, FOUR, rec.copper_stack(FOUR, ())) is None
    found, issues = document_stack(design)
    default = StackSpec.default(rec.copper_stack(FOUR, ()), ())
    assert len(found) == len(default.dielectrics) == 3
    assert found == document_stack(bare_board(4))[0]  # the default values of a board without a stack-up
    (issue,) = stack_issues(issues)
    assert issue.severity == "info" and "between In1.Cu and In2.Cu" in issue.message
    assert "default stack values" in issue.message


def test_values_without_a_key_give_one_info_and_the_values_are_written() -> None:
    stackup = stack_of(
        stack_entry("F.Mask", "soldermask", 10_000, color="Green"),
        stack_entry("F.Cu", "copper", 70_000),
        stack_entry("dielectric 1", "dielectric", 1_000_000, dielectric_kind="core"),
        stack_entry("B.Cu", "copper", 70_000),
        stack_entry("B.Mask", "soldermask", 10_000),
        finish="ENIG",
    )
    found, issues = document_stack(bare_board(2, stackup))
    assert [kind for kind, _ in found] == ["1"] and found[0][1] == "39.3701mil"
    (issue,) = stack_issues(issues)
    assert issue.severity == "info"
    for what in ("the solder mask thickness", "the colours", "the finish"):
        assert what in issue.message
    assert "impedance" not in issue.message
