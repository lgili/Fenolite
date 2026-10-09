# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Unnumbered hole pads in authored footprints (capability dsl-footprint-authoring, "Unnumbered hole pads in
authored footprints"; change c0102)."""

from __future__ import annotations

import pytest
from _buildhelp import blink, build
from _outlinehelp import definitions

from fenolite.backends.kicad.mod import prepare_authored_definition, write_footprint
from fenolite.core.ids import derived_id
from fenolite.dsl import DslError, Footprint, Part, connect, mm


def two_holes() -> Footprint:
    fp = Footprint("Proj", "Two_Holes")
    fp.pad("", at=(mm(0), mm(0)), size=(mm(3.2), mm(3.2)), shape="circle", kind="np_thru_hole", drill=mm(3.2))
    fp.pad("", at=(mm(10), mm(0)), size=(mm(2), mm(2)), shape="circle", kind="np_thru_hole", drill=mm(2))
    return fp


def test_two_unnumbered_holes() -> None:
    fp = two_holes()
    pads = fp.definition.pads
    assert [pad.id for pad in pads] == [
        derived_id("pad", "fenolite.dsl", "Proj:Two_Holes:pad::1"),
        derived_id("pad", "fenolite.dsl", "Proj:Two_Holes:pad::2"),
    ]
    assert [(pad.number, pad.kind, pad.layers) for pad in pads] == [
        ("", "np_thru_hole", ("*.Cu", "*.Mask"))
    ] * 2
    for target in (9, 10):
        text = write_footprint(prepare_authored_definition(fp.definition), target=target)
        assert text.count('(pad "" np_thru_hole circle') == 2


def test_numbered_pads_keep_their_ids() -> None:
    fp = Footprint("Proj", "Mixed")
    fp.pad("1", at=(mm(-2), mm(0)), size=(mm(1), mm(1)))
    fp.pad("", at=(mm(0), mm(0)), size=(mm(2), mm(2)), shape="circle", kind="np_thru_hole", drill=mm(2))
    fp.pad("2", at=(mm(2), mm(0)), size=(mm(1), mm(1)))
    ids = [pad.id for pad in fp.definition.pads]
    assert ids[0] == derived_id("pad", "fenolite.dsl", "Proj:Mixed:pad:1")
    assert ids[1] == derived_id("pad", "fenolite.dsl", "Proj:Mixed:pad::1")
    assert ids[2] == derived_id("pad", "fenolite.dsl", "Proj:Mixed:pad:2")


def test_empty_number_refused_for_other_kinds() -> None:
    fp = Footprint("Proj", "Refused")
    with pytest.raises(DslError, match="pad number ''"):
        fp.pad("", at=(mm(0), mm(0)), size=(mm(2), mm(2)), shape="circle", kind="thru_hole", drill=mm(1))
    with pytest.raises(DslError, match="pad number ''"):
        fp.pad("", at=(mm(0), mm(0)), size=(mm(1), mm(1)))
    with pytest.raises(DslError, match="never shared"):
        fp.pad("", at=(mm(0), mm(0)), size=(mm(2), mm(2)), kind="np_thru_hole", drill=mm(2), shared=True)
    with pytest.raises(DslError, match="drill"):
        fp.pad("", at=(mm(0), mm(0)), size=(mm(2), mm(2)), kind="np_thru_hole")
    assert fp.definition.pads == ()


def test_a_pad_map_cannot_name_the_empty_number() -> None:
    with pytest.raises(DslError, match="non-empty"):
        Part("R1", "Mini:Mini_R", footprint="Proj:Mixed", pad_map={"1": ""})


def test_no_pin_for_an_unnumbered_hole() -> None:
    design = blink()
    fp = Footprint("Proj", "R_With_Hole", kind="smd")
    fp.pad("1", at=(mm(-1), mm(0)), size=(mm(0.9), mm(0.95)))
    fp.pad("2", at=(mm(1), mm(0)), size=(mm(0.9), mm(0.95)))
    fp.pad("", at=(mm(0), mm(2)), size=(mm(1), mm(1)), shape="circle", kind="np_thru_hole", drill=mm(1))
    fp.rect((mm(-2), mm(-1)), (mm(2), mm(3)), layer="F.CrtYd", width=mm(0.05))
    design.add_footprint(fp)
    r9 = Part("R9", "Mini:Mini_R", footprint="Proj:R_With_Hole", value="1k")
    design.add(r9)
    connect(design.nets["GND"], r9[1])
    connect(design.nets["LED_A"], r9[2])
    r9.place(mm(40), mm(22))
    output = build(design, 10, **definitions(design))
    assert output.files and not [i for i in output.issues if i.severity == "error"]
    assert "build.pad-without-pin" not in [i.code for i in output.issues]
    assert '(pad "" np_thru_hole circle' in output.files["blink.kicad_pcb"].decode("utf-8")
