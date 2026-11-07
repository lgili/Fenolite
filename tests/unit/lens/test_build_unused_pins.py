# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Unused pins and two-pin parts in a build (capability design-dsl, "Unused pins resolved in a build",
"Must-connect pins", "Two-pin parts checked in a build"; change c0247): an unused-pin request becomes the
same marks as the explicit ones, in the KiCad and the Altium build, and the two codes stop the build."""

from __future__ import annotations

from pathlib import Path

from _altium import EXAMPLE_DIR, example, example_resolver
from _buildhelp import authored, blink, build, codes

from fenolite.dsl import Design, Net, Part, connect, mm, no_connect, to_model
from fenolite.dsl.convert import key_id, two_terminal, unused_marks
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BUILD_ISSUE_CODES, BuildOutput
from fenolite.model import PinRef

U1 = key_id("component", "U1")
MARKED = tuple(sorted(PinRef(U1, str(pin)) for pin in set(range(1, 33)) - {1, 9, 10}))
"""The 29 marks of the blink, in ``PinRef`` order."""


def requested(design: Design) -> BuildOutput:
    """``build`` of ``design`` with its side channels."""
    return build(design, unused=unused_marks(design), two_terminal=two_terminal(design))


def unmarked_blink() -> Design:
    """The blink without its no-connect marks, whatever form they take in the example."""
    design = blink(marks=False)
    assert not design.parts["U1"].no_connects and design.parts["U1"].unused_request is None
    return design


def test_the_request_gives_the_explicit_marks() -> None:
    explicit = unmarked_blink()
    no_connect(*(explicit.parts["U1"][pin] for pin in range(1, 33) if pin not in (1, 9, 10)))
    asked = unmarked_blink()
    asked.parts["U1"].unused_no_connect()
    assert to_model(asked).circuit.no_connects == ()
    plain, out = build(explicit), requested(asked)
    assert out.files and not [i for i in out.issues if i.severity == "error"]
    assert out.design.circuit.no_connects == MARKED == plain.design.circuit.no_connects
    assert out.files == plain.files, "every written file, .fenolite/circuit.json too, is the same"


def test_kept_pins_stay_open_without_a_mark() -> None:
    design = unmarked_blink()
    design.parts["U1"].unused_no_connect(keep=(5, "PA7"))  # PA7 is pin 8 of the mini controller
    out = requested(design)
    assert out.files
    assert out.design.circuit.no_connects == tuple(m for m in MARKED if m.pin not in ("5", "8"))


def test_explicit_marks_and_the_request_join_without_duplicates() -> None:
    design = unmarked_blink()
    no_connect(design.parts["U1"]["NRST"])  # pin 11 by name
    design.parts["U1"].unused_no_connect()
    assert requested(design).design.circuit.no_connects == MARKED


def test_an_open_supply_pin_is_not_marked() -> None:
    design = unmarked_blink()
    del design.parts["U1"].connections["9"]
    design.parts["U1"].unused_no_connect()
    out = requested(design)
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.must-connect-unconnected"]
    assert found.severity == "error" and found.where == "U1"
    assert "U1" in found.message and "9" in found.message and "VDD" in found.message
    assert found.hint == "connect it, or list it in keep="


def test_a_kept_supply_pin_is_not_reported() -> None:
    design = unmarked_blink()
    del design.parts["U1"].connections["9"]
    design.parts["U1"].unused_no_connect(keep=(9,))
    out = requested(design)
    assert "build.must-connect-unconnected" not in codes(out) and out.files
    assert PinRef(U1, "9") not in out.design.circuit.no_connects


def test_an_unknown_kept_designator() -> None:
    design = unmarked_blink()
    design.parts["U1"].unused_no_connect(keep=("XYZ",))
    out = requested(design)
    assert out.files == {} and "build.unknown-pin" in codes(out)


def _three_pin(tmp_path: Path) -> tuple[Design, Path]:
    folder = authored(
        tmp_path, {"Q": [("1", "B"), ("2", "C"), ("3", "E")], "R": [("1", "~"), ("2", "~")]},
        {"SOT": ["1", "2", "3"], "R2": ["1", "2"]},
    )  # fmt: skip
    design = Design("t")
    design.board(mm(20), mm(20))
    q1 = Part("Q1", "T:Q", footprint="T:SOT")
    r1 = Part("R1", "T:R", footprint="T:R2")
    design.add(q1, r1)
    q1.place(mm(5), mm(5))
    r1.place(mm(12), mm(5))
    return design, folder


def test_a_three_pin_part_used_through_its_ends(tmp_path: Path) -> None:
    design, folder = _three_pin(tmp_path)
    q1, r1 = design.parts["Q1"], design.parts["R1"]
    connect(Net("VIN"), q1.a, r1.a)
    connect(Net("OUT"), q1.b, r1.b)
    out = build(design, project_dir=folder, unused=unused_marks(design), two_terminal=two_terminal(design))
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.not-two-terminal"]
    assert found.severity == "error" and found.where == "Q1"
    assert "Q1" in found.message and "3" in found.message


def test_a_two_pin_part_used_through_its_ends(tmp_path: Path) -> None:
    design, folder = _three_pin(tmp_path)
    q1, r1 = design.parts["Q1"], design.parts["R1"]
    connect(Net("VIN"), q1[1], r1.a)
    connect(Net("OUT"), q1[2], r1.b)
    no_connect(q1[3])
    out = build(design, project_dir=folder, unused=unused_marks(design), two_terminal=two_terminal(design))
    assert out.files and "build.not-two-terminal" not in codes(out)


def test_both_codes_are_errors_of_the_table() -> None:
    assert BUILD_ISSUE_CODES["build.not-two-terminal"] == "error"
    assert BUILD_ISSUE_CODES["build.must-connect-unconnected"] == "error"


# -- the Altium build resolves the same marks


def _altium(tmp_path: Path, design: Design) -> BuildOutput:
    return build_altium(
        to_model(design),
        name=design.name,
        resolver=example_resolver(tmp_path, project_dir=EXAMPLE_DIR),
        unused=unused_marks(design),
        two_terminal=two_terminal(design),
    )


def test_altium_request_gives_the_explicit_marks(tmp_path: Path) -> None:
    explicit, asked = example(), example()
    u2 = explicit.parts["U2"]
    no_connect(u2[2], u2[4], u2[8])
    asked.parts["U2"].unused_no_connect()
    plain, out = _altium(tmp_path, explicit), _altium(tmp_path, asked)
    assert out.files and not [i for i in out.issues if i.severity == "error"]
    u2_id = key_id("component", "U2")
    assert out.design.circuit.no_connects == tuple(PinRef(u2_id, pin) for pin in ("2", "4", "8"))
    assert out.files == plain.files


def test_altium_open_supply_pin_and_kept_pins(tmp_path: Path) -> None:
    design = example("u2[1], u2[6], r1[1]", "u2[1], r1[1]")
    design.parts["U2"].unused_no_connect(keep=("TP",))
    out = _altium(tmp_path, design)
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.must-connect-unconnected"]
    assert "U2" in found.message and "6" in found.message
    kept = example("u2[1], u2[6], r1[1]", "u2[1], r1[1]")
    kept.parts["U2"].unused_no_connect(keep=(6, "TP", "NOPE"))
    out = _altium(tmp_path, kept)
    assert "build.must-connect-unconnected" not in codes(out) and "altium.unknown-pin" in codes(out)
