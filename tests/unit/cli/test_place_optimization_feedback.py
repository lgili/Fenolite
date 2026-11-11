# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import json
from dataclasses import replace
from pathlib import Path
from shutil import copyfile

from _checkcli import run
from _coppercheck import Copper
from _searchbench import MM, point

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli import place_optimize
from fenolite.cli.placement_capacity import Capacity
from fenolite.core.coords import Point, Size
from fenolite.model.board import Outline


def test_escape_feedback_can_recover_a_longer_feasible_placement(monkeypatch, tmp_path):
    copper = Copper()
    copper.pad("J1", "1", "SIG")
    copper.pad("R1", "1", "SIG")
    copper.track("WALL", Point(5_550_000, 650_000), Point(5_550_000, 9_350_000), width=200_000)
    design = copper.build()
    board = replace(
        design.board,
        outline=Outline(id="out_authored", points=(point(0, 0), point(12, 0), point(12, 10), point(0, 10))),
        footprints=tuple(
            replace(
                fp,
                position=Point(x, 5 * MM),
                locked=x == 4_700_000,
                pads=tuple(replace(pad, size=Size(MM, 1_600_000)) for pad in fp.pads),
            )
            for fp, x in zip(design.board.footprints, (4_700_000, 7_800_000), strict=True)
        ),
    )
    path = tmp_path / "feedback.kicad_pcb"
    path.write_text(write_board(replace(design, board=board), target=10).text)
    fixture = Path(__file__).resolve().parents[3] / "tests/data/kicad/project/empty_10.kicad_pro"
    copyfile(fixture, path.with_suffix(".kicad_pro"))
    actual = read_board(path)
    anchor, movable = sorted(actual.board.footprints, key=lambda fp: not fp.locked)
    request = tmp_path / "request.json"
    relationship = {
        "key": "supply",
        "kind": "proximity",
        "endpoints": [{"footprint_id": fp.id, "pad_id": fp.pads[0].id} for fp in (anchor, movable)],
        "origin": "declared",
        "source": "authored fixture",
        "rule_version": "v0",
        "rationale": "keep the supply connection short",
        "required": True,
        "max_distance_nm": 4 * MM,
    }
    config = {
        "schema": "fenolite.placement-optimization.v0",
        "selected": [movable.id],
        "budget": {"evaluations": 32, "beam_width": 1, "probe_expansions": 18_000},
        "constraints": {
            "max_candidates": 10,
            "pitch": 2_500_000,
            "gap": 700_000,
            "regions": [
                {
                    "key": "fixture",
                    "footprint_ids": [movable.id],
                    "outline": [
                        {"x": p.x, "y": p.y} for p in (point(4, 1), point(10, 1), point(10, 9), point(4, 9))
                    ],
                }
            ],
        },
        "intent": [relationship],
    }
    original = path.read_bytes()

    def propose():
        request.write_text(json.dumps(config))
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
        return env["result"]["optimization"]

    with monkeypatch.context() as control:
        control.setattr(place_optimize, "placement_capacity", lambda *_: Capacity())
        config["intent"] = []
        distance_only = propose()
        assert distance_only["candidates"] and not distance_only["candidates"][0].get("probes")
        config["intent"] = [relationship]
        electrical_only = propose()
        assert electrical_only["candidates"]
    baseline = propose()
    (short,) = baseline["candidates"]
    assert electrical_only["candidates"][0]["poses"] == short["poses"]
    assert short["poses"][0]["position"]["x"] > 5_550_000, baseline
    config["intent"].append({**relationship, "kind": "escape", "key": "supply-escape"})
    result = propose()
    assert len(result["candidates"]) == 1, result
    (routed,) = result["candidates"]
    assert {
        "probe:supply-escape:no-room",
        "probe:supply-escape:too-long",
        "probe:supply-escape:state-limit",
    }.intersection(result["blockers"])
    assert routed["poses"][0]["position"]["x"] < 5_550_000, result
    assert routed["score"][0] > short["score"][0] and routed["score"][-1] > 0
    assert result["work"] <= config["budget"]["evaluations"]
    assert path.read_bytes() == original
