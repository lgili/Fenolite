# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite build --target altium --copper-from BOARD.kicad_pcb`` (change c0038, capability altium-build,
"Copper from a routed KiCad board").

The board is the KiCad build of the routed sample's script with the sample's copper, written by a test
helper beside a copy of the script. ``cmd_build`` reads it in-process; ``kicad-cli`` is not run.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from _altium import blink_tree
from _altium_copper import at, routed_board_text, routed_script
from _altium_pcb_read import read_pcbdoc

import fenolite.cli.main as cli_main
from fenolite.model.design import Design

BOARD = "routed.kicad_pcb"
FOUR = "design.board(mm(50), mm(30), copper=4)"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def project(
    tmp_path: Path, edit: Callable[[Design], Design] | None = None, board: str = FOUR
) -> tuple[Path, Path]:
    """A blink tree whose script is the sample's, and the routed board beside it."""
    folder = blink_tree(tmp_path / "tree")
    script = folder / "design.py"
    script.write_text(routed_script(board), encoding="utf-8")
    routed = folder / BOARD
    routed.write_text(routed_board_text(edit), encoding="utf-8")
    return script, routed


def build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: Path, routed: Path, *more: str
) -> tuple[int, dict[str, object], str]:
    out = tmp_path / "B"
    return run(
        monkeypatch, str(script), "--out", str(out), "--target", "altium", "--copper-from", str(routed), *more
    )


def board_of(design: Design, **changes: object) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, **changes))  # type: ignore[arg-type]


def edit_footprint(design: Design, ref: str, edit: Callable[[object], object]) -> Design:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    return board_of(
        design,
        footprints=tuple(edit(f) if refs[f.component_id] == ref else f for f in design.board.footprints),
    )


def test_copper_copied_from_the_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Copper copied from the board" (the byte comparison with the committed file is task 8.3)."""
    script, routed = project(tmp_path)
    code, env, _ = build(monkeypatch, tmp_path, script, routed, "--confirm")
    assert code == 0, env
    result = env["result"]
    assert isinstance(result, dict)
    copper = result["copper"]
    assert (copper["source"], copper["from"], copper["placements_from_board"]) == ("board", str(routed), 3)
    assert [copper[key] for key in ("layers", "tracks", "arcs", "vias", "zones")] == [4, 5, 1, 3, 2]
    issues = env["issues"]
    assert isinstance(issues, list)
    assert "altium.placement-from-board" not in [i["code"] for i in issues]
    assert not [i for i in issues if i["severity"] == "error"]
    doc = read_pcbdoc((tmp_path / "B" / "routed.PcbDoc").read_bytes())
    assert (
        len(doc.free_tracks) == 5
        and len(doc.free_arcs) == 1
        and len(doc.vias) == 3
        and len(doc.polygons) == 2
    )
    assert doc.copper_chain == [1, 2, 3, 32]
    version = result["copper_input"].pop("format_version")
    assert (
        version.isdigit()
        and len(version) == 8
        and f"(version {version})" in routed.read_text(encoding="utf-8")
    )
    assert result["copper_input"] == {
        "path": str(routed),
        "sha256": hashlib.sha256(routed.read_bytes()).hexdigest(),
        "kind": "kicad-board",
    }
    assert env["input"]["kind"] == "fenolite-dsl" and env["input"]["path"] == str(script)  # type: ignore[index]
    evidence = env["evidence"]
    assert isinstance(evidence, dict) and evidence["level"] == "INFERRED"
    assert "H-K-PCB-READ" in evidence["hypotheses"] and "H-A-PCB-CU-ROUNDTRIP" in evidence["hypotheses"]


def test_copper_from_gives_the_bytes_of_the_script_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The board route and a build without ``--copper-from`` differ only in the copper."""
    script, routed = project(tmp_path)
    code, _env, _ = build(monkeypatch, tmp_path, script, routed, "--confirm")
    assert code == 0
    with_copper = read_pcbdoc((tmp_path / "B" / "routed.PcbDoc").read_bytes())
    code, env, _ = run(
        monkeypatch, str(script), "--out", str(tmp_path / "C"), "--target", "altium", "--confirm"
    )
    assert code == 0 and env["result"]["copper"]["source"] == "none"  # type: ignore[index]
    assert "copper_input" not in env["result"]  # type: ignore[operator]
    plain = read_pcbdoc((tmp_path / "C" / "routed.PcbDoc").read_bytes())
    assert plain.streams["Components6/Data"] == with_copper.streams["Components6/Data"]
    assert plain.streams["Pads6/Data"] == with_copper.streams["Pads6/Data"]
    assert plain.vias == [] and plain.polygons == []


def test_moved_part_follows_the_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Moved part follows the board": ``R1`` and the copper on its pads moved by 1 mm."""

    def move(design: Design) -> Design:
        assert design.board is not None
        mm = 1_000_000
        moved = edit_footprint(
            design,
            "R1",
            lambda f: dataclasses.replace(f, position=dataclasses.replace(f.position, x=f.position.x + mm)),  # type: ignore[attr-defined]
        )
        assert moved.board is not None
        tracks = tuple(
            dataclasses.replace(t, end=at(32.2, 9.0))
            if t.end == at(31.2, 9.0)
            else dataclasses.replace(t, start=at(33.8, 9.0))
            if t.start == at(32.8, 9.0)
            else t
            for t in moved.board.tracks
        )
        vias = tuple(
            dataclasses.replace(v, position=at(33.8, 9.0)) if v.position == at(32.8, 9.0) else v
            for v in moved.board.vias
        )
        return board_of(moved, tracks=tracks, vias=vias)

    script, routed = project(tmp_path, move)
    code, env, _ = build(monkeypatch, tmp_path, script, routed, "--confirm")
    assert code == 0, env
    issues = env["issues"]
    assert isinstance(issues, list)
    (info,) = [i for i in issues if i["code"] == "altium.placement-from-board"]
    assert "R1" in info["message"] and "U1" not in info["message"] and str(routed) in info["message"]
    doc = read_pcbdoc((tmp_path / "B" / "routed.PcbDoc").read_bytes())
    (record,) = [c for c in doc.components if c["SOURCEDESIGNATOR"] == "R1"]
    assert (record["X"], record["Y"]) == (
        "2299.2126mil",
        "1826.7717mil",
    )  # 33 mm right, 21 mm up, plus 1000 mil
    assert max(t.x2 for t in doc.free_tracks if t.prefix.layer == 1) == 10_000_000 + 12_677_165  # 32.2 mm


def _without_d1(design: Design) -> Design:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    return board_of(
        design, footprints=tuple(f for f in design.board.footprints if refs[f.component_id] != "D1")
    )


def _other_footprint(design: Design) -> Design:
    return edit_footprint(design, "R1", lambda f: dataclasses.replace(f, lib_ref="Mini:Mini_R_0805"))  # type: ignore[type-var]


def _pad_on_gnd(design: Design) -> Design:
    gnd = next(net.id for net in design.circuit.nets if net.name == "GND")

    def rewire(footprint: object) -> object:
        pads = tuple(
            dataclasses.replace(pad, net_id=gnd) if pad.number == "2" else pad
            for pad in footprint.pads  # type: ignore[attr-defined]
        )
        return dataclasses.replace(footprint, pads=pads)  # type: ignore[type-var]

    return edit_footprint(design, "R1", rewire)


def _extra_net(design: Design) -> Design:
    assert design.board is not None
    extra = dataclasses.replace(
        design.circuit.nets[0], id="net_00000000-0000-4000-8000-000000000009", name="EXTRA", members=()
    )
    first, *tracks = design.board.tracks
    grown = dataclasses.replace(
        design, circuit=dataclasses.replace(design.circuit, nets=(*design.circuit.nets, extra))
    )
    return board_of(grown, tracks=(dataclasses.replace(first, net_id=extra.id), *tracks))


def _blind_via(design: Design) -> Design:
    assert design.board is not None
    first, *vias = design.board.vias
    return board_of(
        design, vias=(dataclasses.replace(first, via_type="blind", layers=("F.Cu", "In1.Cu")), *vias)
    )


MISMATCHES: dict[str, tuple[Callable[[Design], Design], str, str]] = {
    "component": (_without_d1, "altium.copper-board-mismatch", "D1"),
    "footprint": (_other_footprint, "altium.copper-board-mismatch", "R1"),
    "pad-net": (_pad_on_gnd, "altium.copper-board-mismatch", "R1.2"),
    "net": (_extra_net, "altium.copper-net-missing", "EXTRA"),
    "via": (_blind_via, "altium.via-unsupported", ""),
}


@pytest.mark.parametrize("name", sorted(MISMATCHES))
def test_mismatches_are_located(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str) -> None:
    """Scenario "Mismatches are located": one error each, exit 5, no planned file, the board's path named."""
    edit, wanted, where = MISMATCHES[name]
    script, routed = project(tmp_path, edit)
    code, env, _ = build(monkeypatch, tmp_path, script, routed, "--dry-run")
    assert code == 5, env
    assert env["result"]["files"] == [] and not (tmp_path / "B").exists()  # type: ignore[index]
    (error,) = [i for i in env["issues"] if i["severity"] == "error"]  # type: ignore[union-attr]
    assert error["code"] == wanted and str(routed) in error["message"]
    if where:
        assert error["where"] == where
    assert env["result"]["copper"] is None  # type: ignore[index]


def test_four_layer_board_for_a_two_layer_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The unchanged board given to a variant of the script with ``copper=2``."""
    script, routed = project(tmp_path, board="design.board(mm(50), mm(30), copper=2)")
    code, env, _ = build(monkeypatch, tmp_path, script, routed, "--dry-run")
    assert code == 5
    found = [i for i in env["issues"] if i["severity"] == "error"]  # type: ignore[union-attr]
    assert {i["code"] for i in found} == {"altium.copper-layer"} and len(found) == 3
    assert any("In1.Cu" in i["message"] for i in found) and any("In2.Cu" in i["message"] for i in found)
    assert all(str(routed) in i["message"] for i in found) and env["result"]["files"] == []  # type: ignore[index]


def test_option_without_the_altium_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Option without the Altium target"."""
    script, routed = project(tmp_path)
    out = tmp_path / "B"
    code, env, err = run(
        monkeypatch, str(script), "--out", str(out), "--copper-from", str(routed), "--dry-run"
    )
    assert code == 2 and "FEN-2001" in err and "--copper-from needs --target altium" in err
    assert env.get("ok") is not True and not out.exists()
    code, _env, err = run(
        monkeypatch,
        str(script),
        "--out",
        str(out),
        "--target",
        "kicad",
        "--copper-from",
        str(routed),
        "--confirm",
    )
    assert code == 2 and "FEN-2001" in err and not out.exists()


def test_copper_from_a_path_that_is_not_a_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script, routed = project(tmp_path)
    code, _env, err = build(monkeypatch, tmp_path, script, routed.with_name("nope.kicad_pcb"), "--dry-run")
    assert code == 2 and "FEN-2001" in err and "is not a file" in err
    code, _env, err = build(monkeypatch, tmp_path, script, routed.parent, "--dry-run")
    assert code == 2 and "FEN-2001" in err


def test_board_the_reader_refuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script, routed = project(tmp_path)
    routed.write_text("(kicad_pcb (version 20241229", encoding="utf-8")
    code, _env, err = build(monkeypatch, tmp_path, script, routed, "--dry-run")
    assert code == 3 and "FEN-3" in err and not (tmp_path / "B").exists()


def test_reader_issues_pass_into_the_envelope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A warning or info of the board reader is in ``issues`` unchanged."""
    from fenolite.backends.kicad.pcb import read_board

    script, routed = project(tmp_path)
    text = routed.read_text(encoding="utf-8")
    assert "(version 20260206)" in text
    routed.write_text(text.replace("(version 20260206)", "(version 20260207)"), encoding="utf-8")
    expected: list[object] = []
    read_board(routed, issues=expected)  # type: ignore[arg-type]
    code, env, _ = build(monkeypatch, tmp_path, script, routed, "--dry-run")
    assert code == 0, env
    codes = [i["code"] for i in env["issues"]]  # type: ignore[union-attr]
    assert expected and all(found.code in codes for found in expected)  # type: ignore[attr-defined]


def test_help_names_the_option(monkeypatch: pytest.MonkeyPatch) -> None:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    try:
        cli_main.main(["build", "--help"])
    except SystemExit:
        pass
    text = " ".join((out.getvalue() + err.getvalue()).split())
    assert "--copper-from" in text and "placements win" in text


def test_copper_from_equals_the_committed_sample(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Copper copied from the board": ``B/routed.PcbDoc`` equals the committed file."""
    committed = Path(__file__).resolve().parents[2] / "data" / "altium" / "routed" / "routed.PcbDoc"
    script, routed = project(tmp_path)
    code, env, _ = build(monkeypatch, tmp_path, script, routed, "--confirm")
    assert code == 0, env
    assert (tmp_path / "B" / "routed.PcbDoc").read_bytes() == committed.read_bytes()
