# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kit's steps (capability altium-verification, "Kit steps settle hypotheses")."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from fenolite.verify import load_register
from fenolite.verify.kit import steps
from fenolite.verify.kit.manifest import read_kit
from fenolite.verify.kit.steps import GROUPS, SAMPLES, STEPS, Step, steps_markdown

ROOT = Path(__file__).resolve().parents[4]
REGISTER = load_register(ROOT / "docs" / "hypotheses.md")
REQUIRED = (
    "H-A-WRITE-SCHLIB",
    "H-A-WRITE-PCBLIB",
    "H-A-WRITE-SCHDOC",
    "H-A-WRITE-PCBDOC",
    "H-A-PH-CHECKSUM",
    "H-A-PH-ZERO-FIELDS",
    "H-A-PH-NO-CACHE",
    "H-A-PH-LAYOUT",
)
KIT_TEST = re.compile(r"\bK[1-9]\.[0-9]+\b|\bgroups? K[1-9]")
"""A test cell names a kit step or a kit group."""


def _named() -> set[str]:
    return {ident for step in STEPS for ident in step.hypotheses}


def test_the_list_is_well_formed() -> None:
    assert steps.problems() == []
    assert [step.id for step in STEPS] == sorted(
        (step.id for step in STEPS), key=lambda i: tuple(map(int, i[1:].split(".")))
    )
    assert {step.group for step in STEPS} == {group.number for group in GROUPS} == set(range(1, 10))
    assert {step.sample for step in STEPS} == {*SAMPLES, steps.KIT_SAMPLE}


def test_problems_are_named() -> None:
    first = STEPS[0]
    bad = [
        dataclasses.replace(first, id="X1"),
        dataclasses.replace(first, sample="nowhere"),
        dataclasses.replace(first, instruction="One. Two. Three."),
        dataclasses.replace(first, hypotheses=()),
        dataclasses.replace(first, result="../outside"),
        dataclasses.replace(first, kind="form"),
        dataclasses.replace(first, pending={"copper.clearance": "c9999"}),
    ]
    for step in bad:
        assert steps.problems([step]), step
    assert any("twice" in text for text in steps.problems([first, first]))


def test_register_and_steps_agree() -> None:
    """Scenario "Steps and register agree": every id a step names is a register row, and every row whose
    test is a kit step or a kit group is named by a step."""
    rows = {row.id: row for row in REGISTER}
    assert sorted(_named() - set(rows)) == []
    by_test = {row.id for row in REGISTER if KIT_TEST.search(row.test)}
    assert sorted(by_test - _named()) == []
    assert set(REQUIRED) <= _named()
    for ident in REQUIRED:
        named = [step.id for step in STEPS if ident in step.hypotheses]
        assert rows[ident].test.startswith("kit request") and all(i in rows[ident].test for i in named), ident
    for ident in ("H-A-KIT-RESAVE", "H-A-KIT-COMPILE", "H-A-KIT-REPOUR", "H-A-KIT-DRC", "H-A-KIT-SCRIPT"):
        assert ident in by_test and rows[ident].level_text == "INFERRED"


def test_a_step_that_can_end_in_a_file_does() -> None:
    """A step that opens a document and saves or exports something is a ``file`` step with a check; a
    typed step names no document."""
    for step in STEPS:
        if step.kind == "file":
            assert step.document and step.checks and f"results/{step.result}" in step.instruction, step.id
        else:
            assert not step.document and "Type " in step.instruction, step.id
            assert step.result == step.id


def test_instructions_are_fenolite_s_own_words() -> None:
    """At most two sentences each, and a menu path is written with the sign that separates menu names."""
    for step in STEPS:
        assert len(step.instruction) <= 330, step.id
        if step.kind == "file" and "messages" not in step.checks and step.id != "K7.2":
            assert " » " in step.instruction, step.id


def test_pending_checks_are_declared() -> None:
    """No check is pending today; the copper check that waited for c0088 is a check of its two steps."""
    assert not [step.id for step in STEPS if step.pending] and "pending (" not in steps_markdown()
    with_copper = [step.id for step in STEPS if "copper.clearance" in step.checks]
    assert with_copper == ["K4.2", "K6.1"] and "c0088" not in steps.PENDING_REASONS


def test_markdown_is_generated_from_the_steps() -> None:
    text = steps_markdown()
    assert text.endswith("\n") and "\r" not in text
    for step in STEPS:
        assert f"**{step.id}**" in text and step.instruction in text
    assert text.count("*(scripted)*") == sum(1 for step in STEPS if step.scripted)
    one = steps_markdown(STEPS[:1])
    assert "**K1.1**" in one and "**K1.2**" not in one and "## K2" not in one


def test_steps_survive_the_manifest(built_kit: Path) -> None:
    kit = read_kit((built_kit / "kit.json").read_bytes())
    assert [step.to_json() for step in kit.steps] == [step.to_json() for step in STEPS]
    assert all(isinstance(step, Step) for step in kit.steps)
