# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import json
from shutil import copyfile

import pytest
from _checkcli import run
from _projects import tree_snapshot

from fenolite.backends.kicad.pcb import read_board

from .test_place_constrained import authored_board


def test_joint_proposal_checks_board_and_never_stages_a_write(monkeypatch, tmp_path):
    path = authored_board(tmp_path)
    design = read_board(path)
    assert design.board is not None
    locked = next(fp for fp in design.board.footprints if fp.locked)
    movable = next(fp for fp in design.board.footprints if not fp.locked)
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [locked.id, movable.id],
                "budget": {"evaluations": 32, "beam_width": 2},
                "constraints": {"max_candidates": 16, "pitch": 1_000_000, "edge_clearance": 1_000_000},
            }
        )
    )
    before = tree_snapshot(tmp_path)
    args = ("place", str(path), "--strategy", "optimize", "--constraints", str(request))
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (env, err)
    result = env["result"]["optimization"]
    assert result["fixed"][locked.id] == ["board_lock"]
    assert result["movable"] == [movable.id] and result["candidates"], result
    assert not env["result"].get("plan") and not env["result"].get("plan_id")
    assert result["candidates"][0]["poses"][0]["footprint_id"] == movable.id
    assert result["candidates"][0]["poses"][0]["position"]["x"] < 30_000_000
    code, repeated, err, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0 and repeated["result"]["optimization"] == result, (repeated, err)
    assert tree_snapshot(tmp_path) == before

    relocated = tmp_path / "copy"
    relocated.mkdir()
    copyfile(path, relocated / path.name)
    rules = path.with_suffix(".kicad_dru")
    copyfile(rules, relocated / rules.name)
    code, copied, err, _ = run(
        monkeypatch, tmp_path, "place", str(relocated / path.name), *args[2:], "--dry-run"
    )
    assert code == 0 and copied["result"]["optimization"] == result, (copied, err)


@pytest.mark.parametrize("limit", [1, 1_500_000])
def test_reviewed_pad_distance_drives_sampling_and_refuses_infeasible_poses(monkeypatch, tmp_path, limit):
    path = authored_board(tmp_path)
    design = read_board(path)
    assert design.board is not None
    anchor, part = sorted(design.board.footprints, key=lambda fp: not fp.locked)
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [part.id],
                "budget": {"evaluations": 12, "beam_width": 2},
                "constraints": {"max_candidates": 8, "pitch": 5_000_000, "gap": 200_000},
                "intent": [
                    {
                        "key": "near-anchor",
                        "kind": "proximity",
                        "endpoints": [
                            {"footprint_id": fp.id, "pad_id": fp.pads[0].id} for fp in (anchor, part)
                        ],
                        "origin": "declared",
                        "source": "authored fixture",
                        "rule_version": "v0",
                        "rationale": "exercise a strict proximity bound",
                        "required": True,
                        "max_distance_nm": limit,
                    }
                ],
            }
        )
    )
    before = tree_snapshot(tmp_path)
    code, env, err, _ = run(
        monkeypatch,
        tmp_path,
        "place",
        str(path),
        "--strategy",
        "optimize",
        "--constraints",
        str(request),
        "--dry-run",
    )
    assert code == 0, (env, err)
    result = env["result"]["optimization"]
    if limit == 1:
        assert result["candidates"] == [] and result["unplaced"] == [part.id]
        assert "intent:near-anchor:distance" in result["blockers"]
    else:
        assert result["candidates"] and result["unplaced"] == [], result
        assert all(1 < row["score"][0] <= limit for row in result["candidates"])
    assert tree_snapshot(tmp_path) == before
