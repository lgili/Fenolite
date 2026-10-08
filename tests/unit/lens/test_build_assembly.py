# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Assembly and test pad marks in a build (capability altium-build, "Assembly and test features in an
Altium build"; design-dsl, "Assembly and test features in a build"; change c0118).

A part whose footprint holds a marked pad is written like any authored part, the mark goes to no Altium
record, and one ``altium.not-lowered`` info of the kind "pad properties" names the footprint. The parts of
``fiducial()``, ``test_point()`` and ``tooling_hole()`` build in KiCad as parts with generated definitions;
in an Altium build the fiducials are left out with one info of the kind "assembly features", and the
tooling holes are holes of ``hole()`` (change c0102)."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pytest
from _asmfeatures import calls_design
from _outlinehelp import board_text, build_script, codes, rebuild_script

from fenolite.backends.kicad.frame import placed_extents
from fenolite.backends.kicad.pcb import read_board
from fenolite.dsl import Design, Footprint, Net, Part, connect, mm, placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design as ModelDesign


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


# -- the parts of design.fiducial(), design.test_point() and design.tooling_hole()

MM = 1_000_000
FEATURE_FILES = (
    "lib/Fenolite_Assembly.pretty/Fiducial_1mm_Mask2mm.kicad_mod",
    "lib/Fenolite_Assembly.pretty/TestPoint_Pad_D1.5mm.kicad_mod",
    "lib/Fenolite_Assembly.pretty/ToolingHole_3mm_Clear5mm.kicad_mod",
    "lib/Fenolite_Assembly.kicad_sym",
    "lib/Fenolite_Holes.kicad_sym",
)


def _footprint(board: ModelDesign, ref: str) -> FootprintInstance:
    assert board.board is not None
    refs = {c.id: c.ref for c in board.circuit.components}
    (found,) = [fp for fp in board.board.footprints if refs[fp.component_id] == ref]
    return found


@pytest.mark.parametrize("target", [9, 10])
def test_features_in_a_build(target: int) -> None:
    """Scenario "Features in a build"."""
    output = build_script(calls_design(), target)
    assert output.files and not [i for i in output.issues if i.severity == "error"]
    assert set(FEATURE_FILES) <= set(output.files)
    rows = output.files["fp-lib-table"].decode("utf-8") + output.files["sym-lib-table"].decode("utf-8")
    assert len(re.findall(r'\(name "?Fenolite_Assembly"?\)', rows)) == 2
    board = read_board(board_text(output))
    assert board.board is not None
    nets = {net.id: net.name for net in board.circuit.nets}
    for ref, layer in (("FID1", "F.Cu"), ("FID2", "B.Cu")):
        fid = _footprint(board, ref)
        (copper,) = [p for p in fid.pads if p.fab_property]
        assert copper.fab_property == "fiducial_global" and layer in copper.layers and copper.number == ""
        assert fid.locked and "exclude_from_bom" in fid.attributes
    (tp,) = _footprint(board, "TP1").pads
    assert tp.number == "1" and tp.fab_property == "test_point" and nets[tp.net_id or ""] == "LED_A"
    (th,) = _footprint(board, "TH1").pads
    assert th.kind == "np_thru_hole" and th.drill == 3 * MM
    areas = {k.name: k.layers for k in board.board.keepouts}
    assert areas == {"clear_FID1": ("F.Cu",), "clear_FID2": ("B.Cu",), "clear_TH1": ("F.Cu", "B.Cu")}
    marked = output.files[FEATURE_FILES[0]].decode("utf-8") + output.files[FEATURE_FILES[1]].decode("utf-8")
    assert marked.count("(property pad_prop_fiducial_glob)") == 1
    assert marked.count("(property pad_prop_testpoint)") == 1
    symbols = output.files["lib/Fenolite_Assembly.kicad_sym"].decode("utf-8")
    assert '(symbol "Fiducial"' in symbols and '(symbol "TestPoint"' in symbols


def test_features_are_judged_by_their_courtyards() -> None:
    """The placement guard reads the courtyards of the generated parts: a tooling hole has one per side."""
    output = build_script(calls_design())
    board = read_board(board_text(output))
    extents = {e.footprint_id: e for e in placed_extents(board)}
    for ref in ("FID1", "TP1", "TH1"):
        assert extents[_footprint(board, ref).id].source == "courtyard"
    th1 = extents[_footprint(board, "TH1").id]
    assert th1.front and th1.back
    assert not [code for code in codes(output) if code.startswith("layout.place")]


def test_features_rebuild_to_the_same_bytes() -> None:
    """Scenario "Features rebuild to the same bytes"."""
    first = build_script(calls_design(), 9)
    again = rebuild_script(calls_design(), board_text(first), 9)
    assert dict(again.files) == dict(first.files)


def test_a_script_without_the_calls_builds_the_same_bytes() -> None:
    """Migration plan: the calls add files; a script without them is the blink of before."""
    plain = build_script(calls_design(append=""))
    assert not [name for name in plain.files if "Fenolite_Assembly" in name]
    assert b"Fenolite_Assembly" not in b"".join(plain.files.values())


ALTIUM_CALLS = (
    'design.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))\n'
    'design.tooling_hole("TH1", mm(46), mm(4), drill=mm(3))\n'
    'design.test_point("TP1", led_a, mm(30), mm(12), size=mm(1.5))\n'
)
"""The lines of "Test point written, fiducial left out"."""


def _altium_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, append: str, *flags: str
) -> tuple[int, dict[str, Any], Path]:
    from _buildhelp import blink_variant

    import fenolite.cli.main as cli_main

    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    script = blink_variant(tmp_path / "src", append="\n" + append if append else "")
    out = tmp_path / "out"
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main(["build", str(script), "--out", str(out), "--target", "altium", *flags, "--json"])
    return code, json.loads(stdout.getvalue() or "{}"), out


def _holds(data: bytes, text: str) -> bool:
    return text.encode("ascii") in data or text.encode("utf-16-le") in data


def test_altium_test_point_written_fiducial_left_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Test point written, fiducial left out": the fiducial is left out with one info of the kind
    "assembly features"; the tooling hole is a hole of ``design.hole()`` and is written as a board hole of
    the document (design Decision 13, corrected after c0102's "PCB document output")."""
    code, env, out = _altium_build(monkeypatch, tmp_path, ALTIUM_CALLS, "--dry-run")
    assert code == 0, env.get("issues")
    planned = {Path(p["path"]).name for p in env["result"]["plan"]}
    assert {"blink.PcbLib", "blink.PcbDoc", "blink.SchDoc"} <= planned
    issues = env["issues"]
    codes_found = {i["code"] for i in issues}
    assert (
        "altium.footprint-unsupported" not in codes_found and "altium.pcbdoc-not-written" not in codes_found
    )
    features = [i for i in issues if i["code"] == "altium.not-lowered" and i["where"] == "assembly features"]
    assert len(features) == 1 and features[0]["severity"] == "info"
    assert "FID1" in features[0]["message"] and "TH1" not in features[0]["message"]
    marked = [i for i in issues if i["code"] == "altium.not-lowered" and i["where"] == "pad properties"]
    assert len(marked) == 1 and "Fenolite_Assembly:TestPoint_Pad_D1.5mm" in marked[0]["message"]
    assert not [i for i in issues if i["where"].startswith("hole/")]
    code, env, out = _altium_build(monkeypatch, tmp_path, ALTIUM_CALLS, "--confirm")
    assert code == 0, env.get("issues")
    documents = {
        p.name: p.read_bytes()
        for p in out.iterdir()
        if p.suffix in (".SchDoc", ".SchLib", ".PcbLib", ".PcbDoc")
    }
    assert set(documents) == {"blink.SchDoc", "blink.SchLib", "blink.PcbLib", "blink.PcbDoc"}
    assert not [name for name, data in documents.items() if _holds(data, "FID1") or _holds(data, "Fiducial")]
    assert not [name for name, data in documents.items() if _holds(data, "TH1")]
    assert _holds(documents["blink.PcbDoc"], "TP1") and _holds(
        documents["blink.PcbLib"], "TestPoint_Pad_D1.5mm"
    )
    stored = json.loads((out / ".fenolite" / "board.json").read_text(encoding="utf-8"))
    assert any(hole.get("drill") == 3_000_000 for hole in stored.get("holes", []))


def test_the_lens_names_the_fiducial_symbol_of_the_dsl() -> None:
    from fenolite.dsl import assembly
    from fenolite.lens import altium

    assert altium.FIDUCIAL_SYMBOL == f"{assembly.ASSEMBLY_LIBRARY}:{assembly.FIDUCIAL_SYMBOL}"


def test_altium_build_without_the_calls_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An Altium build of a script without the three calls plans the same files as the blink of before."""
    code, env, _ = _altium_build(monkeypatch, tmp_path, "", "--dry-run")
    assert code == 0
    assert not [i for i in env["issues"] if i["where"] in ("assembly features", "pad properties")]
    assert env["result"]["footprints"] == 3
