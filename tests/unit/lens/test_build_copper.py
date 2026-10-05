# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper intents in a build (capability design-dsl, "Copper intents in a build"; design-model, "Identifier
derivation", scenario "Script copper ignores the seed"; change c0028). No tool runs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _buildhelp import blink, build
from _copper import ROUTED_DIR, routed_intents, routed_script
from _routed import NAME, Routed, codes, script_copper

from fenolite.backends.kicad import copper as copper_mod
from fenolite.backends.kicad import frame
from fenolite.backends.kicad.copper import copper_uuid, is_copper_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.evidence import Level, strength
from fenolite.dsl import arc_to, copper, mm
from fenolite.model.design import Design

ZERO = {"regenerated": 0, "stale": 0, "duplicates": 0}


def _shape(design: Design) -> list[tuple[object, ...]]:
    """Ids and modelled fields of the script copper, without what a read adds (provenance, slots)."""
    tracks, vias = script_copper(design)
    names = {net.id: net.name for net in design.circuit.nets}
    found: list[tuple[object, ...]] = [
        (t.id, t.native_ids["kicad"], t.start, t.end, t.width, t.layer, names[t.net_id or ""]) for t in tracks
    ]
    found += [
        (v.id, v.native_ids["kicad"], v.position, v.diameter, v.drill, v.layers, names[v.net_id or ""])
        for v in vias
    ]
    return found


def test_built_design_holds_the_script_copper() -> None:
    output = build(routed_script(), 10, project_dir=ROUTED_DIR, copper_intents=routed_intents())
    assert output.files and not [i for i in output.issues if i.severity == "error"]
    tracks, vias = script_copper(output.design)
    assert (len(tracks), len(vias)) == (11, 7)
    assert output.summary["copper"] == {"intents": 4, "tracks": 11, "arcs": 0, "vias": 7, **ZERO}
    written = read_board(output.files[f"{NAME}.kicad_pcb"].decode("utf-8"))
    assert _shape(written) == _shape(output.design)  # the written board is the built model
    assert output.layout is not None and _shape(output.layout) == _shape(output.design)
    for hypothesis in (*copper_mod.EVIDENCE.hypotheses, *frame.EVIDENCE.hypotheses):
        assert hypothesis in output.evidence.hypotheses
    assert strength(output.evidence.level) <= strength(Level.INFERRED)


def test_a_build_without_intents_is_unchanged() -> None:
    plain = build(blink(), 10)
    assert plain.summary["copper"] == {"intents": 0, "tracks": 0, "arcs": 0, "vias": 0, **ZERO}
    assert "H-G-FRAME-UUID" not in plain.evidence.hypotheses
    assert plain.design.board is not None and plain.design.board.tracks == ()
    routed = routed_script()
    same_parts = build(routed, 10, project_dir=ROUTED_DIR)  # intents not passed: the script alone adds none
    assert script_copper(same_parts.design) == ([], [])


def test_routed_blink_through_the_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch, confirm=False)
    code, env, err = project.build("--dry-run")
    assert code == 0, err
    assert env["result"]["copper"] == {"intents": 4, "tracks": 11, "arcs": 0, "vias": 7, **ZERO}
    assert not project.out.exists()
    code, env, _ = project.build("--confirm")
    assert code == 0
    tracks, vias = script_copper(project.read())
    assert (len(tracks), len(vias)) == (11, 7)
    assert all(is_copper_uuid(i.native_ids["kicad"]) for i in (*tracks, *vias))
    assert copper_uuid("led_drv", "seg[0]") in {t.native_ids["kicad"] for t in tracks}
    assert "H-G-FRAME-ROUTE" in env["evidence"]["hypotheses"]


def test_a_copper_error_stops_the_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch, confirm=False)
    project.edit_script("(mm(31.2), mm(7)), r1.pad(1),", "(mm(31.2), mm(7)), d1.pad(2),")
    code, env, _ = project.build("--confirm")
    assert code == 5 and "kicad.copper.net-conflict" in codes(env)
    assert not project.out.exists() and env["result"]["files"] == []


def test_intent_to_a_staged_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch, confirm=False)
    project.edit_script('d1.place(mm(38), mm(20), side="bottom")\n', "")
    code, env, _ = project.build("--confirm")
    assert code == 0
    found = codes(env)
    assert "layout.unplaced" in found and found.count("kicad.copper.end-unplaced") == 2
    unplaced = [i for i in env["issues"] if i["code"] == "kicad.copper.end-unplaced"]
    assert all("D1" in i["message"] and i["severity"] == "warning" for i in unplaced)
    assert sorted(i["where"] for i in unplaced) == ["gnd", "led_a"]
    tracks, vias = script_copper(project.read())
    keys = {copper_uuid("led_drv", f"seg[{i}]") for i in range(4)}
    assert {t.native_ids["kicad"] for t in tracks} == keys  # only the intent that ends at no staged part
    assert len(vias) == 5 and env["result"]["copper"]["intents"] == 4  # the stitch does not end at a part


def test_second_build_is_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch)
    first = project.files()
    code, env, _ = project.build("--confirm")
    assert code == 0 and project.files() == first
    assert env["result"]["copper"] == {"intents": 4, "tracks": 11, "arcs": 0, "vias": 7, **ZERO}
    assert not [c for c in codes(env) if c.startswith("kicad.copper.")]


@pytest.mark.parametrize("target", [9, 10])
def test_reproducible_routed_builds(tmp_path: Path, target: int) -> None:
    """Scenario "Reproducible routed builds" and "Script copper ignores the seed": two processes with
    different hash seeds and ``--seed`` values write every file with the same bytes."""
    outputs = []
    for seed in ("1", "2"):
        out = tmp_path / f"out-{seed}"
        command = [
            sys.executable, "-m", "fenolite", "--kicad-version", str(target), "--seed", seed, "build",
            str(ROUTED_DIR / "design.py"), "--out", str(out), "--confirm", "--json",
        ]  # fmt: skip
        env = {**os.environ, "PYTHONHASHSEED": seed, "KICAD_CONFIG_HOME": str(tmp_path / "config")}
        run = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
        assert run.returncode == 0, run.stderr
        outputs.append(
            {str(p.relative_to(out)): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}
        )
    assert outputs[0] == outputs[1] and f"{NAME}.kicad_pcb" in outputs[0]
    board = read_board(outputs[0][f"{NAME}.kicad_pcb"].decode("utf-8"))
    tracks, vias = script_copper(board)
    assert (len(tracks), len(vias)) == (11, 7)


def test_dsl_copper_is_what_the_command_passes() -> None:
    intents = copper(routed_script())
    assert intents == routed_intents() and [i.key for i in intents] == [
        "gnd",
        "gnd_fence",
        "led_a",
        "led_drv",
    ]


# --- arcs and via kinds in a build (change c0068) -----------------------------------------------------

IMPORT = "from fenolite.dsl import Design, Net, Part, Power, connect, mm, no_connect, via_step\n"
BEND = (
    '\ndesign.track("bend", (mm(20), mm(3)), arc_to((mm(21), mm(4)), (mm(20), mm(5))), (mm(24), mm(5)),'
    " net=gnd, width=mm(0.25))\n"
)
BURIED = (
    '\ndesign.via("core", mm(20), mm(20), net=gnd, kind="buried", layers=("In1.Cu", "In2.Cu"),'
    " diameter=mm(0.6), drill=mm(0.3))\n"
)


def _with_arcs(project: Routed) -> None:
    project.edit_script(IMPORT, IMPORT.replace("via_step", "arc_to, via_step"))
    project.edit_script("# Stitching vias", BEND.strip("\n") + "\n# Stitching vias")


def test_built_design_holds_the_script_arcs() -> None:
    """``result.copper.arcs`` counts the created arcs; the written board holds them with their uuids."""
    script = routed_script()
    script.track(
        "bend",
        (mm(20), mm(3)),
        arc_to((mm(21), mm(4)), (mm(20), mm(5))),
        (mm(24), mm(5)),
        net=script.nets["GND"],
        width=mm(0.25),
    )
    output = build(script, 10, project_dir=ROUTED_DIR, copper_intents=copper(script))
    assert output.files and not [i for i in output.issues if i.severity == "error"]
    assert output.summary["copper"] == {"intents": 5, "tracks": 12, "arcs": 1, "vias": 7, **ZERO}
    written = read_board(output.files[f"{NAME}.kicad_pcb"].decode("utf-8"))
    assert written.board is not None and output.layout is not None and output.layout.board is not None
    (made,) = written.board.arcs
    assert made.native_ids["kicad"] == copper_uuid("bend", "arc[1]")
    assert [a.native_ids["kicad"] for a in output.layout.board.arcs] == [made.native_ids["kicad"]]


@pytest.mark.parametrize("target", [9, 10])
def test_arcs_through_the_command_and_across_rebuilds(
    target: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = Routed(tmp_path, monkeypatch, target, confirm=False)
    _with_arcs(project)
    code, env, err = project.build("--confirm")
    assert code == 0, err
    assert env["result"]["copper"] == {"intents": 5, "tracks": 12, "arcs": 1, "vias": 7, **ZERO}
    board = project.read().board
    assert board is not None and [a.native_ids["kicad"] for a in board.arcs] == [
        copper_uuid("bend", "arc[1]")
    ]
    first = project.files()
    code, env, _ = project.build("--confirm")
    assert code == 0 and project.files() == first  # the arc is regenerated with the same bytes
    assert not [c for c in codes(env) if c.startswith("kicad.copper.")]
    # the intent is taken out of the script: its arc and its track are stale and removed
    project.edit_script(BEND.strip("\n") + "\n", "")
    code, env, _ = project.build("--confirm")
    stale = [i for i in env["issues"] if i["code"] == "kicad.copper.stale"]
    assert code == 0 and len(stale) == 2 and any("arc on F.Cu" in i["message"] for i in stale)
    board = project.read().board
    assert board is not None and board.arcs == ()
    assert env["result"]["copper"] == {
        "intents": 4, "tracks": 11, "arcs": 0, "vias": 7, "regenerated": 0, "stale": 2, "duplicates": 0,
    }  # fmt: skip


def _with_buried(project: Routed) -> None:
    project.edit_script("design.board(mm(50), mm(30))", "design.board(mm(50), mm(30), copper=4)")
    project.edit_script("# Stitching vias", BURIED.strip("\n") + "\n# Stitching vias")


def test_buried_target_9_is_refused_by_the_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Buried via refused for target 9": the kind is the script's, the target is the writer's."""
    project = Routed(tmp_path, monkeypatch, 9, confirm=False)
    _with_buried(project)
    code, env, err = project.build("--confirm")
    assert code == 7, (code, err)
    assert "via buried" in err and "KiCad 10" in err
    assert not project.out.exists()
    assert not [c for c in codes(env) if c.startswith("kicad.copper.")]


def test_buried_target_10_is_built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch, 10, confirm=False)
    _with_buried(project)
    code, env, err = project.build("--confirm")
    assert code == 0, err
    board = project.read().board
    assert board is not None
    (core,) = [v for v in board.vias if v.native_ids["kicad"] == copper_uuid("core", "via")]
    assert (core.via_type, core.layers) == ("buried", ("In1.Cu", "In2.Cu"))
    assert env["result"]["copper"]["vias"] == 8
