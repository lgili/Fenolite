# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import json
import shutil
from pathlib import Path

import pytest
from _checkcli import run
from _projects import tree_snapshot

from fenolite.backends.altium.backend import AltiumBackend

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests/data/altium/blink"


@pytest.mark.parametrize("filename", ["blink.PcbDoc", "blink.PrjPcb"])
def test_altium_proposal_inspects_native_input_without_changing_it(filename, tmp_path, monkeypatch):
    project = tmp_path / "source"
    shutil.copytree(BLINK, project)
    design = AltiumBackend().read(project / filename).design
    assert design.board is not None
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [fp.id for fp in design.board.footprints],
                "budget": {"evaluations": 32, "beam_width": 2},
                "constraints": {"max_candidates": 12, "pitch": 500_000},
            }
        )
    )
    before = tree_snapshot(project)
    code, env, err, _ = run(
        monkeypatch,
        tmp_path,
        "place",
        str(project / filename),
        "--strategy",
        "optimize",
        "--constraints",
        str(request),
        "--dry-run",
    )
    assert code == 0, (env, err)
    result = env["result"]["optimization"]
    assert len(result["input_sha256"]) == 64
    assert result["sampled"] or result["fixed"]
    assert result["candidates"], result
    assert env["input"]["kind"] == "altium_pcbdoc"
    assert not env["result"].get("plan_id") and tree_snapshot(project) == before


def test_altium_copy_can_be_converted_placed_and_exported_without_touching_source(tmp_path, monkeypatch):
    from fenolite.backends.kicad.pcb import read_board
    from fenolite.backends.kicad.replace import footprint_ref

    project = tmp_path / "source"
    shutil.copytree(BLINK, project)
    before = tree_snapshot(project)
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))

    def dry(*args):
        code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
        assert code == 0, (env, err)
        return env

    def apply(args, env):
        code, reply, err, _ = run(
            monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"]
        )
        assert code == 0, (reply, err)

    to_kicad = ("convert", str(project / "blink.PcbDoc"), "--to", "kicad", "--out", "working")
    apply(to_kicad, dry(*to_kicad))
    (working,) = (tmp_path / "working").glob("*.kicad_pcb")
    design = read_board(working)
    assert design.board is not None
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [fp.id for fp in design.board.footprints],
                "budget": {"evaluations": 64, "beam_width": 2},
                "constraints": {"max_candidates": 12, "pitch": 500_000},
            }
        )
    )
    propose = ("place", str(working), "--strategy", "optimize", "--constraints", str(request))
    env = dry(*propose)
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(env))
    initial = {fp.id: {"x": fp.position.x, "y": fp.position.y} for fp in design.board.footprints}
    candidate = next(
        row
        for row in env["result"]["optimization"]["candidates"]
        if any(initial[pose["footprint_id"]] != pose["position"] for pose in row["poses"])
    )
    review = (*propose, "--proposal", str(saved), "--candidate", candidate["id"])
    apply(review, dry(*review))
    to_altium = ("convert", str(working), "--to", "altium", "--out", "exported", "--altium-pour", "outline")
    apply(to_altium, dry(*to_altium))
    (exported,) = (tmp_path / "exported").glob("*.PcbDoc")
    result = AltiumBackend().read(exported).design
    checked = read_board(working)
    assert result.board is not None and checked.board is not None
    actual = {footprint_ref(result, footprint): footprint.position for footprint in result.board.footprints}
    expected = {
        footprint_ref(checked, footprint): footprint.position for footprint in checked.board.footprints
    }
    assert set(actual) == set(expected)
    anchor = min(expected)
    for ref in sorted(expected):
        for axis in ("x", "y"):
            observed = getattr(actual[ref], axis) - getattr(actual[anchor], axis)
            requested = getattr(expected[ref], axis) - getattr(expected[anchor], axis)
            assert abs(observed - requested) <= 3
    assert tree_snapshot(project) == before
