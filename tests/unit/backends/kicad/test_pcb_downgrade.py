# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Boards and footprints of KiCad 10 written for KiCad 9 on request (change c0162; capability
kicad-version-gating, "Targets and downgrade refusal", "Downgrade edits" and "Downgrade consent")."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad import resolver
from fenolite.backends.kicad.mod import read_footprint, write_footprint, write_pretty
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import DowngradeRefusedError, FileKind, LossyWriteError, check_emittable

TOKENS = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "tokens"
SKELETON = (TOKENS / "skeleton.kicad_pcb").read_text(encoding="utf-8")
VIA = '(drill 0.3)\n\t\t(layers "F.Cu" "B.Cu")'


def ten_board(via_child: str = "", *, setup: str = "") -> str:
    """The fuzz skeleton at a header of 10 (20250513, nets still by number), with ``via_child`` on its via
    and ``setup`` appended to its setup."""
    text = SKELETON.replace("(version 20241229)", "(version 20250513)")
    if via_child:
        text = text.replace(VIA, f"{VIA}\n\t\t{via_child}")
    if setup:
        text = text.replace("(pad_to_mask_clearance 0)", f"(pad_to_mask_clearance 0)\n\t\t{setup}")
    return text


def test_refused_without_downgrade() -> None:
    with pytest.raises(DowngradeRefusedError) as refused:
        write_board(read_board(ten_board()), target=9)
    assert "fenolite convert" in refused.value.hint


def test_unchanged_without_downgrade() -> None:
    """Every write without ``downgrade`` keeps its bytes: a downgrade flag on a write that is none changes
    nothing either."""
    design = read_board(SKELETON)
    assert write_board(design, target=9).text == write_board(design, target=9, downgrade=True).text
    ten = read_board(ten_board())
    assert write_board(ten, target=10).text == write_board(ten, target=10, downgrade=True).text


def test_downgrade_on_request() -> None:
    edits: list[resolver.Edit] = []
    written = write_board(read_board(ten_board(setup="(capping no)")), target=9, downgrade=True, edits=edits)
    assert "(version 20241229)" in written.text.splitlines()[1]
    assert not [i for i in check_emittable(parse(written.text), FileKind.BOARD, 9) if i.severity == "error"]
    assert [(e.row, e.action) for e in edits] == [("capping", "same")]
    assert [i.code for i in written.issues if i.code.startswith("kicad.downgrade")] == [resolver.CHANGED_CODE]


def test_design_loss_needs_consent() -> None:
    """Scenario "Design loss needs consent": a via whose ``capping`` is set."""
    design = read_board(ten_board("(capping yes)"))
    with pytest.raises(LossyWriteError) as refused:
        write_board(design, target=9, downgrade=True)
    assert refused.value.droppable and "--allow-lossy" in refused.value.hint
    assert [resolver.row_id(i) for i in refused.value.issues] == ["capping"]
    edits: list[resolver.Edit] = []
    written = write_board(design, target=9, downgrade=True, allow_lossy=True, edits=edits)
    assert "capping" not in written.text
    assert [(e.row, e.action) for e in edits] == [("capping", "design")]
    lost = [i for i in written.issues if i.code == resolver.LOST_CODE]
    assert len(lost) == 1 and lost[0].hint == "row capping (design)"


def test_setup_protection_at_the_node() -> None:
    """The setup's 10 children are resolved in place; ``setup`` itself stays (scenario "Setup kept")."""
    setup = "(tenting (front yes) (back no))\n\t\t(covering (front no) (back no))\n\t\t(filling yes)"
    design = read_board(ten_board(setup=setup))
    with pytest.raises(LossyWriteError):
        write_board(design, target=9, downgrade=True)
    edits: list[resolver.Edit] = []
    written = write_board(design, target=9, downgrade=True, allow_lossy=True, edits=edits)
    tree = parse(written.text)
    node = tree.find("setup")
    assert node is not None
    tenting = node.find("tenting")
    assert tenting is not None and [a.text for a in tenting.atoms()] == ["front"]
    assert node.find("covering") is None and node.find("filling") is None
    assert node.find("pcbplotparams") is not None
    assert {(e.row, e.action) for e in edits} == {
        ("tenting-front", "rewrite"),
        ("tenting-back", "rewrite"),
        ("covering", "same"),
        ("filling", "design"),
    }


FOOTPRINT_10 = """(footprint "Jumper"
	(version 20250513)
	(generator "pcbnew")
	(generator_version "10.0")
	(layer "F.Cu")
	(duplicate_pad_numbers_are_jumpers yes)
	(attr smd)
	(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask") (tenting (front none) (back none)))
	(pad "1" smd rect (at 2 0) (size 1 1) (layers "F.Cu" "F.Mask"))
)
"""


def test_footprint_downgrade() -> None:
    defn = read_footprint(FOOTPRINT_10, library="L")
    with pytest.raises(LossyWriteError) as refused:
        write_footprint(defn, target=9, downgrade=True)
    assert [resolver.row_id(i) for i in refused.value.issues] == [
        "footprint-duplicate-pad-numbers-are-jumpers"
    ]
    edits: list[resolver.Edit] = []
    texts = write_pretty([defn], target=9, downgrade=True, allow_lossy=True, edits=edits)
    text = texts["Jumper.kicad_mod"]
    assert "(version 20241229)" in text and "duplicate_pad_numbers_are_jumpers" not in text
    assert "tenting" not in text
    assert {(e.row, e.action, e.file) for e in edits} == {
        ("footprint-duplicate-pad-numbers-are-jumpers", "design", "Jumper.kicad_mod"),
        ("tenting-front", "same", "Jumper.kicad_mod"),
        ("tenting-back", "same", "Jumper.kicad_mod"),
    }


def test_footprint_unchanged_without_downgrade() -> None:
    defn = read_footprint(FOOTPRINT_10, library="L")
    assert write_footprint(defn, target=10) == write_footprint(defn, target=10, downgrade=True)
    plain = write_footprint(defn, target=9, allow_lossy=True)
    assert "duplicate_pad_numbers_are_jumpers" not in plain
