# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots and cut-outs in a script build for Altium (capability altium-build, "PCB document output"; change
c0168): slotted hole parts become free slot pads, and the cut-outs and slots of the outline are reported
while ``pcbdoc.CUTOUT_REGIONS`` is false."""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium import blink, blink_resolver, blink_tree
from _altium_pcb_read import read_pcbdoc

from fenolite.backends.altium.pcbrecords import to_units
from fenolite.dsl import placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput

LAST_LINE = 'd1.place(mm(38), mm(20), side="bottom")\n'


def build_blink_script(root: Path, text: str, new: str) -> BuildOutput:
    """The blink with ``text`` replaced by ``new``, built with the definitions its script generated."""
    project = blink_tree(root)
    design = blink(text, new)
    return build_altium(
        to_model(design),
        name=design.name,
        placed=tuple(placements(design)),
        placements=placements(design),
        resolver=blink_resolver(root, project),
        authored_footprints={key: fp.definition for key, fp in design.footprints.items()},
        authored_symbols={key: symbol.definition for key, symbol in design.symbols.items()},  # type: ignore[attr-defined]
    )


def test_a_plated_hole_and_a_slot_are_reported(tmp_path: Path) -> None:
    """Scenario "A plated hole and a slot are reported": the slot ``H3`` is written as a free slot pad, the
    plated ``H2`` is reported."""
    holes = (
        LAST_LINE
        + 'h2 = design.hole("H2", mm(46), mm(4), drill=mm(3.2), pad=mm(6))\n'
        + "connect(gnd, h2[1])\n"
        + 'design.hole("H3", mm(25), mm(4), drill=mm(1), length=mm(3))\n'
    )
    output = build_blink_script(tmp_path, LAST_LINE, holes)
    assert not [i for i in output.issues if i.severity == "error"]
    assert "blink.PcbDoc" in output.files
    pcb = output.summary["pcb"]
    assert pcb["not_lowered"]["hole"] == 1 and pcb["written"]["hole"] == 1  # type: ignore[index]
    reported = [i for i in output.issues if i.code == "altium.not-lowered" and i.where.startswith("hole/")]
    assert len(reported) == 1 and reported[0].severity == "info"
    assert "H2" in reported[0].message and "copper" in reported[0].message and "GND" in reported[0].message
    model = to_model(blink(LAST_LINE, holes))
    ids = {c.ref: c.id for c in model.circuit.components}
    assert reported[0].where == f"hole/{ids['H2']}"
    slots = [pad for pad in read_pcbdoc(output.files["blink.PcbDoc"]).pads if pad.hole == to_units(1_000_000)]
    assert len(slots) == 1 and slots[0].plated == 0 and slots[0].name == ""


@pytest.mark.parametrize(("rot", "angle"), [(0, 0.0), (30, 30.0), (-90, 270.0)])
def test_a_slot_part_is_turned_by_its_placement(tmp_path: Path, rot: int, angle: float) -> None:
    """The slot's axis is the part's rotation, its size the slot's length and drill."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc as read_document
    from fenolite.backends.altium.read.pcbprims import PadRecord

    hole = LAST_LINE + f'design.hole("H3", mm(25), mm(4), drill=mm(1), length=mm(3), rot={rot})\n'
    output = build_blink_script(tmp_path, LAST_LINE, hole)
    pads = [
        pad
        for pad in read_document(output.files["blink.PcbDoc"]).pads
        if isinstance(pad, PadRecord) and pad.hole == to_units(1_000_000)
    ]
    (pad,) = pads
    assert pad.hole_shape == 2 and pad.slot_length == to_units(3_000_000)
    assert pad.size_top == (to_units(3_000_000), to_units(1_000_000))
    assert pad.rotation == pytest.approx(angle)


SLOTS = Path(__file__).resolve().parents[2] / "data" / "slots" / "design.py"


def slots_design() -> object:
    import runpy

    return runpy.run_path(str(SLOTS))["design"]


def build_slots(root: Path) -> BuildOutput:
    """The shared fixture of c0167 built for Altium (no part but the round hole ``H1``)."""
    from fenolite.dsl import Design

    design = slots_design()
    assert isinstance(design, Design)
    return build_altium(
        to_model(design),
        name=design.name,
        placed=tuple(placements(design)),
        placements=placements(design),
        resolver=blink_resolver(root, blink_tree(root)),
        authored_footprints={key: fp.definition for key, fp in design.footprints.items()},
        authored_symbols={key: symbol.definition for key, symbol in design.symbols.items()},  # type: ignore[attr-defined]
    )


def test_gate_cutouts_while_the_gate_is_off(tmp_path: Path) -> None:
    """Scenario "Cut-outs while the gate is off": the document is planned, three cut-outs are counted
    under ``cutout`` of ``not_lowered`` and named by three infos; the merged L is one."""
    from fenolite.backends.altium import pcbdoc

    assert pcbdoc.CUTOUT_REGIONS is False
    output = build_slots(tmp_path)
    assert not [i for i in output.issues if i.severity == "error"]
    assert "slots.PcbDoc" in output.files
    assert not [i for i in output.issues if i.code == "altium.pcbdoc-not-written"]
    pcb = output.summary["pcb"]
    assert pcb["not_lowered"]["cutout"] == 3 and pcb["written"]["cutout"] == 0  # type: ignore[index]
    assert pcb["written"]["hole"] == 1  # type: ignore[index]
    reported = [
        i
        for i in output.issues
        if i.code == "altium.not-lowered" and i.where.startswith(("slot/", "cutout/"))
    ]
    assert sorted(i.where for i in reported) == ["cutout/1", "slot/S1", "slot/S2+slot/S3"]
    assert all(i.severity == "info" and "Part S" in i.message for i in reported)
    from fenolite.backends.altium.read.pcb import read_pcbdoc as read_document

    assert not read_document(output.files["slots.PcbDoc"]).regions


def test_gate_on_writes_the_regions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the gate on (the kit's form), the three cut-outs are written and counted under ``written``;
    the merge of the L needs the ``geo`` extra."""
    pytest.importorskip("pyclipper")
    from fenolite.backends.altium import pcbdoc

    monkeypatch.setattr(pcbdoc, "CUTOUT_REGIONS", True)
    output = build_slots(tmp_path)
    pcb = output.summary["pcb"]
    assert pcb["written"]["cutout"] == 3 and "cutout" not in pcb["not_lowered"]  # type: ignore[index]
    assert not [i for i in output.issues if i.where.startswith(("slot/", "cutout/"))]


def test_gate_an_arc_of_a_cut_out_plans_the_document(tmp_path: Path) -> None:
    """The arcs of a cut-out's ring do not refuse the document; an arc of the board ring still does."""
    output = build_slots(tmp_path)
    assert "slots.PcbDoc" in output.files
