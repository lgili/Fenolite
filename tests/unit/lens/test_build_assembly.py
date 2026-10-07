# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Assembly and test pad marks in a build (capability altium-build, "Assembly and test features in an
Altium build"; design-dsl, "Assembly and test features in a build"; change c0118).

What is tested here is the part that needs no other change: a part whose authored footprint holds a marked
pad is written like any authored part, the mark goes to no Altium record, and one ``altium.not-lowered``
info of the kind "pad properties" names the footprint. Leaving the parts of ``fiducial()`` and
``tooling_hole()`` out of an Altium build waits for those calls (changes c0102 and c0103)."""

from __future__ import annotations

from fenolite.backends.kicad.pcb import read_board
from fenolite.dsl import Design, Footprint, Net, Part, connect, mm, placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput


def _design(mark: str | None) -> tuple[Design, Footprint]:
    design = Design("marked")
    design.board(mm(20), mm(20))
    r1 = Part("R1", "Demo.SchLib:Res", footprint="Local:TwoPin", value="1k")
    tp1 = Part("TP1", "Demo.SchLib:TestPad", footprint="Local:TestPad")
    design.add(r1, tp1)
    connect(Net("SIG"), r1[1], tp1[1])
    r1.place(mm(10), mm(10))
    tp1.place(mm(5), mm(5))
    two = Footprint("Local", "TwoPin", kind="smd")
    two.pad("1", at=(mm(-1), mm(0)), size=(mm(1), mm(1)))
    two.pad("2", at=(mm(1), mm(0)), size=(mm(1), mm(1)))
    pad = Footprint("Local", "TestPad", kind="smd")
    pad.pad(
        "1", at=(mm(0), mm(0)), size=(mm(1.5), mm(1.5)), shape="circle", layers=("F.Cu", "F.Mask"),
        fab_property=mark,
    )  # fmt: skip
    design.add_footprint(two)
    design.add_footprint(pad)
    return design, pad


def _altium(mark: str | None) -> BuildOutput:
    design, _ = _design(mark)
    return build_altium(
        to_model(design),
        name=design.name,
        placed=("R1", "TP1"),
        placements=placements(design),
        authored_footprints={k: v.definition for k, v in design.footprints.items()},
    )


def _kinds(output: BuildOutput) -> list[tuple[str, str]]:
    return [(i.where, i.message) for i in output.issues if i.code == "altium.not-lowered"]


def test_altium_test_point_is_written_and_its_mark_is_named() -> None:
    """Scenario "Test point written, fiducial left out", the test-point half."""
    output = _altium("test_point")
    assert not [i for i in output.issues if i.severity == "error"]
    codes = {i.code for i in output.issues}
    assert "altium.footprint-unsupported" not in codes and "altium.pcbdoc-not-written" not in codes
    assert {"marked.PcbLib", "marked.PcbDoc"} <= set(output.files)
    marked = [(where, message) for where, message in _kinds(output) if where == "pad properties"]
    assert len(marked) == 1
    assert "Local:TestPad" in marked[0][1] and "Local:TwoPin" not in marked[0][1]
    assert b"pad_prop" not in b"".join(
        data if isinstance(data, bytes) else data.encode("utf-8") for data in output.files.values()
    )


def test_altium_build_without_marks_plans_the_same_files() -> None:
    """A script without a mark gets no new info, and the mark changes no written file."""
    plain, marked = _altium(None), _altium("test_point")
    assert [where for where, _ in _kinds(plain) if where == "pad properties"] == []
    assert sorted(plain.files) == sorted(marked.files)
    documents = [name for name in plain.files if name.endswith((".PcbLib", ".PcbDoc", ".SchDoc", ".SchLib"))]
    assert documents and all(plain.files[name] == marked.files[name] for name in documents)
    rest = [i for i in marked.issues if i.where != "pad properties"]
    assert [(i.code, i.where) for i in rest] == [(i.code, i.where) for i in plain.issues]


def test_one_info_names_every_marked_footprint() -> None:
    design, _ = _design("test_point")
    ball = Footprint("Local", "Ball", kind="smd")
    ball.pad("A1", at=(mm(0), mm(0)), size=(mm(0.4), mm(0.4)), shape="circle", fab_property="bga")
    design.add_footprint(ball)
    u1 = Part("U1", "Demo.SchLib:Ball", footprint="Local:Ball")
    design.add(u1)
    u1.place(mm(15), mm(15))
    output = build_altium(
        to_model(design),
        name=design.name,
        placed=("R1", "TP1", "U1"),
        placements=placements(design),
        authored_footprints={k: v.definition for k, v in design.footprints.items()},
    )
    (message,) = [message for where, message in _kinds(output) if where == "pad properties"]
    assert "Local:Ball, Local:TestPad" in message


def test_a_marked_pad_reaches_the_kicad_board() -> None:
    """The KiCad build of the same idea: the mark of an authored pad is on the placed pad and in the
    vendored footprint file (design-dsl, "Assembly and test features in a build", for an authored pad)."""
    from _asmfeatures import features_design
    from _buildhelp import build

    design = features_design()
    for target in (9, 10):
        output = build(
            design,
            target,
            authored_footprints={k: v.definition for k, v in design.footprints.items()},
            authored_symbols={k: v.definition for k, v in design.symbols.items()},
        )
        board = read_board(output.files["blink.kicad_pcb"].decode("utf-8"))
        assert board.board is not None
        marks = sorted(p.fab_property for fp in board.board.footprints for p in fp.pads if p.fab_property)
        assert marks == ["fiducial_global", "fiducial_global", "test_point"]
        mods = [
            d.decode("utf-8")
            for rel, d in output.files.items()
            if rel.endswith(".kicad_mod") and "Local" in rel
        ]
        assert sorted(text.count("(property pad_prop_") for text in mods) == [1, 1]
