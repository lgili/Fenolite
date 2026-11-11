# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import json
from dataclasses import replace
from pathlib import Path
from shutil import copyfile

import pytest
from _coppercheck import Copper
from _kicad import major
from _resources import kicad_cli
from _searchbench import MM, point

from fenolite.api import run
from fenolite.backends.base import PadCopper
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.core.coords import Point, Size
from fenolite.model.board import Outline

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("switching", [False, True], ids=["bypass", "gate-loop-and-sense"])
def test_reviewed_placement_and_routing_keep_fixed_geometry(tmp_path, monkeypatch, switching):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    target = major()
    native = kicad_cli()
    assert native is not None
    source = Copper()
    layer = "F.Cu"
    movable = "Q1" if switching else "C1"
    drive, ret = ("DRV", "RET") if switching else ("VDD", "GND")
    for ref in ("U1", movable):
        source.pad(ref, "1", drive, PadCopper(layer, (Point(0, -800_000),), 600_000))
        source.pad(ref, "2", ret, PadCopper(layer, (Point(0, 800_000),), 600_000))
    source.pad("J1", "1", "SENSE" if switching else None)
    if switching:
        source.pad("R1", "1", "SENSE")
        source.track("SENSE", point(2, 2), point(16, 2), width=200_000)
    design = source.build()
    assert design.board is not None
    at = {"U1": point(6, 6), movable: point(12, 6), "J1": point(2, 2), "R1": point(16, 2)}
    board = replace(
        design.board,
        outline=Outline(id="out_bypass", points=(point(0, 0), point(20, 0), point(20, 12), point(0, 12))),
        footprints=tuple(
            replace(
                fp,
                position=at[ref],
                locked=ref != movable,
                pads=tuple(replace(pad, size=Size(600_000, 600_000)) for pad in fp.pads),
            )
            for fp in design.board.footprints
            for ref in (footprint_ref(design, fp),)
        ),
    )
    path = tmp_path / "bypass.kicad_pcb"
    path.write_text(write_board(replace(design, board=board), target=target).text)
    fixture = Path(__file__).resolve().parents[2] / "data/kicad/project/empty_10.kicad_pro"
    copyfile(fixture, path.with_suffix(".kicad_pro"))
    reread = read_board(path)
    assert reread.board is not None
    parts = {footprint_ref(reread, fp): fp for fp in reread.board.footprints}
    ends = {
        number: [
            {"footprint_id": fp.id, "pad_id": next(pad.id for pad in fp.pads if pad.number == number)}
            for fp in (parts["U1"], parts[movable])
        ]
        for number in ("1", "2")
    }

    def intent(label, kind, endpoints):
        return {
            "key": label,
            "kind": kind,
            "endpoints": endpoints,
            "origin": "declared",
            "source": "authored fixture",
            "rule_version": "v0",
            "rationale": "local drive and return",
            "required": True,
            "max_distance_nm": 4 * MM,
        }

    intents = [intent(f"near-{number}", "proximity", pair) for number, pair in ends.items()]
    if switching:
        intents.append(intent("gate", "gate-loop", ends["1"] + ends["2"]))
    else:
        intents.extend(intent(f"bypass-{number}", "escape", pair) for number, pair in ends.items())
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-optimization.v0",
                "selected": [parts[ref].id for ref in ("J1", movable)],
                "budget": {"evaluations": 32, "beam_width": 2, "probe_expansions": 20000},
                "constraints": {"max_candidates": 16, "pitch": MM, "gap": 300_000},
                "intent": intents,
            }
        )
    )
    args = (str(path), "--strategy", "optimize", "--constraints", str(request))
    proposal = run("place", *args, "--dry-run", cwd=tmp_path)
    assert proposal.ok, proposal.error
    result = proposal.result["optimization"]
    assert "board_lock" in result["fixed"][parts["J1"].id]
    assert result["candidates"], result
    chosen = result["candidates"][0]
    assert len(chosen["probes"]) == 2 and all(row["status"] == "found" for row in chosen["probes"])
    saved = tmp_path / "proposal.json"
    saved.write_text(json.dumps(proposal.envelope))
    review_args = (*args, "--proposal", str(saved), "--candidate", chosen["id"])
    review = run("place", *review_args, "--dry-run", cwd=tmp_path)
    assert review.ok, review.error
    applied = run("place", *review_args, "--confirm", "--plan", review.result["plan_id"], cwd=tmp_path)
    assert applied.ok, applied.error
    moved = read_board(path)
    assert moved.board is not None
    positions = {footprint_ref(moved, fp): fp.position for fp in moved.board.footprints}
    assert positions["J1"] == at["J1"] and positions["U1"] == at["U1"]
    assert positions[movable] != at[movable]
    assert tuple(replace(item, provenance=None) for item in moved.board.tracks) == tuple(
        replace(item, provenance=None) for item in reread.board.tracks
    )
    routing = run("route", str(path), "--router", "octilinear", "--confirm", cwd=tmp_path)
    assert routing.ok, routing.envelope or routing.error
    assert not routing.result["unrouted"]
    checked = run("check", str(path), "--kicad-cli", str(native), cwd=tmp_path)
    assert checked.ok, checked.envelope or checked.error
