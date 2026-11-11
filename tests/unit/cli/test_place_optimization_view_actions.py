# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import json
import urllib.request
from dataclasses import replace

import pytest

from fenolite.api import run
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point

from .test_place_constrained import authored_board
from .test_view_actions import _Served

pytestmark = pytest.mark.long_flow


def test_served_refinement_uses_updated_anchor_and_exact_confirmation(tmp_path, monkeypatch):
    path = authored_board(tmp_path)
    original = read_board(path)
    assert original.board is not None
    anchor, moving = sorted(original.board.footprints, key=lambda fp: not fp.locked)
    request = tmp_path / "scope.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [moving.id],
                "budget": {"evaluations": 16, "beam_width": 2},
                "constraints": {"max_candidates": 10, "pitch": 500_000, "gap": 200_000},
                "intent": [
                    {
                        "key": "near-anchor",
                        "kind": "proximity",
                        "endpoints": [
                            {"footprint_id": fp.id, "pad_id": fp.pads[0].id} for fp in (anchor, moving)
                        ],
                        "origin": "declared",
                        "source": "authored fixture",
                        "rule_version": "v0",
                        "rationale": "keep both exact pads close",
                        "required": True,
                        "max_distance_nm": 1_500_000,
                    }
                ],
            }
        )
    )
    proposal = run(
        "place", str(path), "--strategy", "optimize", "--constraints", str(request), "--dry-run", cwd=tmp_path
    )
    assert proposal.ok, proposal.error
    initial = proposal.result["optimization"]["candidates"][0]["id"]
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(proposal.envelope))
    before = path.read_bytes()

    with _Served(
        monkeypatch,
        tmp_path,
        path,
        ("--placement", str(saved), "--placement-request", str(request)),
        copy_source=False,
    ) as served:
        offer = served.get("/actions?doc=doc1")["actions"]["placement"]
        assert initial in offer["options"]["candidate"]["choices"]
        old_plan = served.plan("placement", candidate=initial)
        assert old_plan["plan"]["confirmable"] and path.read_bytes() == before
        moved_anchor = replace(anchor, position=Point(anchor.position.x + 3_000_000, anchor.position.y))
        changed = replace(
            original,
            board=replace(
                original.board,
                footprints=tuple(
                    moved_anchor if fp.id == anchor.id else fp for fp in original.board.footprints
                ),
            ),
        )
        path.write_text(write_board(changed, target=10).text)
        anchored = path.read_bytes()
        stale = served.confirm(old_plan)
        assert stale["exit"] == 4 and path.read_bytes() == anchored
        assert "placement" not in served.get("/actions?doc=doc1")["actions"]

        refine = urllib.request.Request(
            f"http://127.0.0.1:{served.port}/run",
            data=json.dumps({"command": "placement", "doc": "doc1", "options": {}}).encode(),
            headers={"Content-Type": "application/json", "X-Fenolite-Run": "1"},
            method="POST",
        )
        with urllib.request.urlopen(refine, timeout=10) as response:
            job = json.loads(response.read())["job"]
        fresh = served.job(job)
        assert fresh["placement"] and path.read_bytes() == anchored
        candidate = fresh["envelope"]["result"]["optimization"]["candidates"][0]
        assert candidate["id"] != initial
        reviewed = served.plan("placement", candidate=candidate["id"])
        assert reviewed["plan"]["confirmable"] and path.read_bytes() == anchored
        applied = served.confirm(reviewed)
        assert applied["exit"] == 0 and path.read_bytes() != anchored

    final = read_board(path)
    assert final.board is not None
    positions = {fp.id: fp.position for fp in final.board.footprints}
    assert positions[anchor.id] == moved_anchor.position
    expected = candidate["poses"][0]["position"]
    assert positions[moving.id] == Point(expected["x"], expected["y"])
