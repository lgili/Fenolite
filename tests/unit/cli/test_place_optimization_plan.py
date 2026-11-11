# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import json

import pytest
from _checkcli import run

from fenolite.backends.kicad.pcb import read_board
from fenolite.cli import place_optimize

from .test_place_constrained import authored_board


@pytest.fixture
def review(monkeypatch, tmp_path):
    path = authored_board(tmp_path)
    board = read_board(path).board
    assert board is not None
    part = next(fp for fp in board.footprints if not fp.locked)
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [part.id],
                "budget": {"evaluations": 12, "beam_width": 2},
                "constraints": {"max_candidates": 12, "pitch": 1_000_000},
            }
        )
    )
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    args = ("place", str(path), "--strategy", "optimize", "--constraints", str(request))
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (env, err)
    result = env["result"]["optimization"]
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(result))
    return path, proposal, (*args, "--proposal", str(proposal), "--candidate", result["candidates"][0]["id"])


def test_exact_review_and_confirmation_replay_staged_bytes(review, monkeypatch, tmp_path):
    path, _, args = review
    before = path.read_bytes()
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0 and path.read_bytes() == before, (env, err)
    plan = env["result"]["plan_id"]
    planned = env["result"]["optimization"]["candidates"][0]

    def never(*args, **kwargs):
        pytest.fail("confirmation reran the optimizer")

    monkeypatch.setattr(place_optimize, "propose", never)
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan)
    assert code == 0 and path.read_bytes() != before, (env, err)
    moved = read_board(path).board
    assert moved is not None
    fp = next(fp for fp in moved.footprints if fp.id == planned["poses"][0]["footprint_id"])
    assert fp.position.x == planned["poses"][0]["position"]["x"]
    assert next(f for f in moved.footprints if f.locked).position.x == 8_000_000


def test_review_refuses_tampering_and_confirmation_requires_a_staged_plan(review, monkeypatch, tmp_path):
    path, proposal, args = review
    before = path.read_bytes()
    code, _, err, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 4 and err["code"] == "FEN-4002"
    data = json.loads(proposal.read_text())
    data["candidates"][0]["poses"][0]["position"]["x"] += 1
    proposal.write_text(json.dumps(data))
    code, _, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 3 and err["code"] == "FEN-3004"
    assert path.read_bytes() == before


def test_changed_project_rules_invalidate_staged_plan(review, monkeypatch, tmp_path):
    path, _, args = review
    before = path.read_bytes()
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (env, err)
    path.with_suffix(".kicad_dru").write_text("(version 1)\n")
    code, _, err, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 4 and err["code"] == "FEN-4002"
    assert path.read_bytes() == before


def test_export_of_reviewed_placement_reads_back_in_altium_format(review, monkeypatch, tmp_path):
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.backends.kicad.replace import footprint_ref

    path, _, args = review
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (env, err)
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, (env, err)
    moved = read_board(path)
    assert moved.board is not None
    expected = {footprint_ref(moved, fp): fp.position for fp in moved.board.footprints}
    conversion = ("convert", str(path), "--to", "altium", "--out", "altium-copy", "--altium-pour", "outline")
    code, env, err, _ = run(monkeypatch, tmp_path, *conversion, "--dry-run")
    assert code == 0, (env, err)
    code, env, err, _ = run(
        monkeypatch, tmp_path, *conversion, "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 0, (env, err)
    (output,) = (tmp_path / "altium-copy").glob("*.PcbDoc")
    found = AltiumBackend().read(output).design
    assert found.board is not None
    refs = {part.id: part.ref for part in found.circuit.components}
    actual = {refs[fp.component_id]: fp.position for fp in found.board.footprints}
    # Compare relative placement because conversion may change the absolute frame origin.
    assert set(actual) == set(expected)
    for axis in ("x", "y"):
        original_delta = getattr(expected["R1"], axis) - getattr(expected["J1"], axis)
        exported_delta = getattr(actual["R1"], axis) - getattr(actual["J1"], axis)
        assert abs(exported_delta - original_delta) <= 3


def test_rule_change_during_candidate_review_is_not_staged(review, monkeypatch, tmp_path):
    path, _, args = review
    before = path.read_bytes()
    propose = place_optimize.propose

    def change_rule(*args, **kwargs):
        result = propose(*args, **kwargs)
        path.with_suffix(".kicad_dru").write_text("(version 1)\n")
        return result

    monkeypatch.setattr(place_optimize, "propose", change_rule)
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 4 and err["code"] == "FEN-4002"
    assert not env["result"].get("plan_id") and path.read_bytes() == before


def test_failed_backup_write_restores_board_and_can_retry(review, monkeypatch, tmp_path):
    import os
    from pathlib import Path

    path, _, args = review
    before = path.read_bytes()
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (env, err)
    confirm = (*args, "--confirm", "--plan", env["result"]["plan_id"])
    replace_file = os.replace

    def fail_backup(source, target):
        if Path(target).name == path.name + ".bak":
            raise PermissionError("authored backup failure")
        replace_file(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", fail_backup)
        code, env, err, _ = run(patch, tmp_path, *confirm)
        assert code == 1 and err["code"] == "FEN-1002"
        assert env["receipt"] is None and path.read_bytes() == before
    code, env, err, _ = run(monkeypatch, tmp_path, *confirm)
    assert code == 0 and path.read_bytes() != before, (env, err)


def test_build_keeps_the_applied_layout_and_source_lock(tmp_path, monkeypatch):
    from _project import Project

    from fenolite.backends.kicad.replace import footprint_ref

    project = Project(tmp_path, monkeypatch)
    design = read_board(project.board)
    assert design.board is not None
    by_ref = {footprint_ref(design, fp): fp for fp in design.board.footprints}
    movable, fixed = by_ref["R1"], by_ref["U1"]
    assert fixed.locked
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [movable.id, fixed.id],
                "budget": {"evaluations": 32, "beam_width": 8},
                "constraints": {"max_candidates": 24, "pitch": 1_000_000},
            }
        )
    )
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    args = ("place", str(project.board), "--strategy", "optimize", "--constraints", str(request))
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (env, err)
    result = env["result"]["optimization"]
    candidate = next(
        row
        for row in result["candidates"]
        if row["poses"][0]["position"] != {"x": movable.position.x, "y": movable.position.y}
    )
    saved = tmp_path / "proposal.json"
    saved.write_text(json.dumps(result))
    args = (*args, "--proposal", str(saved), "--candidate", candidate["id"])
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (env, err)
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, (env, err)
    code, env, err = project.build("--confirm")
    assert code == 0, (env, err)
    rebuilt = read_board(project.board)
    assert rebuilt.board is not None
    by_ref = {footprint_ref(rebuilt, fp): fp for fp in rebuilt.board.footprints}
    assert by_ref["U1"].position == fixed.position and by_ref["U1"].locked
    assert by_ref["R1"].position.x == candidate["poses"][0]["position"]["x"]
    assert by_ref["R1"].position.y == candidate["poses"][0]["position"]["y"]
