# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import json
from dataclasses import replace
from shutil import copyfile

import pytest
from _checkcli import run
from _coppercheck import Copper
from _projects import tree_snapshot

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli.cmd_place import _query_outline  # pyright: ignore[reportPrivateUsage]
from fenolite.cli.errors import CliError
from fenolite.cli.place_optimize import propose
from fenolite.core.coords import Point
from fenolite.model.board import Outline
from fenolite.placement.constraints import GroupRegion, PlacementConstraints
from fenolite.placement.optimization_contract import (
    OptimizationBudget,
    OptimizationCandidate,
    OptimizationRequest,
    ProposedPose,
    candidate_id,
)

from .test_place_constrained import authored_board

MM = 1_000_000


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


@pytest.mark.parametrize("net", ['(net "A")', ""])
def test_netted_copper_polygon_away_from_the_part_does_not_hold_it(monkeypatch, tmp_path, net):
    path = authored_board(tmp_path)
    text = path.read_text(encoding="utf-8").rstrip()
    assert text.endswith(")")
    # an authored solid copper polygon in the bottom-right corner, far from where R1 is placed
    polygon = (
        "(gr_poly (pts (xy 26 16) (xy 29 16) (xy 29 19) (xy 26 19)) (stroke (width 0.1) (type solid))"
        f' (fill yes) (layer "F.Cu") {net} (uuid "00000000-0000-0000-0000-00000000c486"))'
    )
    path.write_text(f"{text[:-1]}\n  {polygon}\n)\n", encoding="utf-8")
    design = read_board(path)
    assert design.board is not None
    assert [g.kind for g in design.board.graphics if g.layer == "F.Cu"] == ["polygon"]
    movable = next(fp for fp in design.board.footprints if not fp.locked)
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [movable.id],
                "budget": {"evaluations": 32, "beam_width": 2},
                "constraints": {"max_candidates": 16, "pitch": 1_000_000, "edge_clearance": 1_000_000},
            }
        )
    )
    args = ("place", str(path), "--strategy", "optimize", "--constraints", str(request), "--dry-run")
    code, env, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0, (env, err)
    result = env["result"]["optimization"]
    if net:
        assert result["movable"] == [movable.id] and result["candidates"], result
        assert all("attachment_unchecked" not in reasons for reasons in result["fixed"].values())
    else:
        assert result["fixed"][movable.id] == ["attachment_unchecked"], result


def _overlap_board(tmp_path, free: bool):
    """D1 and R2 (locked) overlap by 0.2 mm; with ``free``, a capacitor C1 lies far from them, else R1
    stands in for D1 and is not locked (change c0487)."""
    made = Copper()
    first = "D1" if free else "R1"
    for ref in (first, "R2", *(("C1",) if free else ())):
        made.pad(ref, "1", None)
    d = made.build()
    assert d.board is not None
    at = {first: Point(5 * MM, 5 * MM), "R2": Point(5_800_000, 5 * MM), "C1": Point(20 * MM, 10 * MM)}
    refs = {c.id: c.ref for c in d.circuit.components}
    fps = tuple(
        replace(
            fp, position=at[refs[fp.component_id]], locked=refs[fp.component_id] != ("C1" if free else "R1")
        )
        for fp in d.board.footprints
    )
    outline = Outline(
        id="out_00000000-0000-0000-0000-000000000001",
        points=(Point(0, 0), Point(30 * MM, 0), Point(30 * MM, 20 * MM), Point(0, 20 * MM)),
    )
    d = replace(d, board=replace(d.board, footprints=fps, outline=outline))
    path = tmp_path / "overlap.kicad_pcb"
    path.write_text(write_board(d, target=10).text, encoding="utf-8")
    design = _query_outline(read_board(path))
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    ids = {refs[fp.component_id]: fp.id for fp in design.board.footprints}
    return path, design, ids


def _request(selected: str, region: GroupRegion | None = None) -> OptimizationRequest:
    return OptimizationRequest(
        "fenolite.placement-optimization.v0",
        (selected,),
        OptimizationBudget(evaluations=8, beam_width=2),
        PlacementConstraints(max_candidates=4, pitch=MM, regions=(region,) if region else ()),
    )


def test_an_overlap_far_from_the_scope_is_a_baseline(tmp_path):
    path, design, ids = _overlap_board(tmp_path, free=True)
    result = propose(design, path, _request(ids["C1"]), frozenset())
    assert result.candidates, result
    old = "place.courtyard-overlap:" + ",".join(sorted((ids["D1"], ids["R2"])))
    assert all(old in row.baseline for row in result.candidates)


@pytest.mark.parametrize(("x", "rejected"), [(5_300_000, True), (4_900_000, False)])
def test_a_moved_part_is_judged_by_its_overlap_area(tmp_path, x, rejected):
    path, design, ids = _overlap_board(tmp_path, free=False)
    half = MM // 2
    box = (
        Point(x - half, 5 * MM - half),
        Point(x + half, 5 * MM - half),
        Point(x + half, 5 * MM + half),
        Point(x - half, 5 * MM + half),
    )
    request = _request(ids["R1"], GroupRegion("pin", (ids["R1"],), box))
    first = propose(design, path, request, frozenset())
    pose = ProposedPose(ids["R1"], Point(x, 5 * MM), 0, "top")
    review = OptimizationCandidate(candidate_id(first.input_sha256, (pose,)), (pose,), (), ())
    old = "place.courtyard-overlap:" + ",".join(sorted((ids["R1"], ids["R2"])))
    if rejected:
        with pytest.raises(CliError, match="place.courtyard-overlap"):
            propose(
                design, path, request, frozenset(), review=review, expected_fingerprint=first.input_sha256
            )
    else:
        result = propose(
            design, path, request, frozenset(), review=review, expected_fingerprint=first.input_sha256
        )
        assert result.candidates[0].baseline == (old,)
