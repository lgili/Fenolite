# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import hashlib
import json

import pytest
from _visual import DATA, job, run

from fenolite.api import run as command
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model import canonical
from fenolite.placement.intent import PlacementIntent, ResolvedIntent
from fenolite.placement.optimization_contract import (
    OptimizationCandidate,
    PlacementOptimization,
    ProposedPose,
    candidate_id,
)
from fenolite.placement.topology import PadIdentity

pytestmark = pytest.mark.needs_browser


def test_keyboard_compares_candidates_and_cross_probes_exact_pad_net(tmp_path):
    board = DATA / "kicad/board/two_layer.kicad_pcb"
    before = board.read_bytes()
    design = read_board(board)
    assert design.board is not None
    pads = KicadBackend().board_pads(design)
    movable = {part.id: part for part in design.board.footprints if not part.locked}
    first, second = next(
        (pad, other)
        for pad in pads
        if pad.footprint_id in movable and pad.net
        for other in pads
        if other.footprint_id != pad.footprint_id and other.net == pad.net
    )
    footprint = movable[first.footprint_id]
    intent = PlacementIntent(
        "return",
        "proximity",
        (PadIdentity(first.footprint_id, first.pad_id), PadIdentity(second.footprint_id, second.pad_id)),
        "declared",
        "authored fixture",
        "v0",
        "inspect the exact physical return pads",
    )
    fingerprint = hashlib.sha256(b"viewer keyboard fixture").hexdigest()
    candidates = []
    for dx in (1_000_000, -1_000_000):
        poses = (
            ProposedPose(
                footprint.id,
                Point(footprint.position.x + dx, footprint.position.y),
                footprint.rotation % 360_000_000,
                footprint.side,
            ),
        )
        candidates.append(OptimizationCandidate(candidate_id(fingerprint, poses), poses, (abs(dx),), ()))
    result = PlacementOptimization(
        fingerprint,
        "complete",
        candidates=tuple(candidates),
        movable=(footprint.id,),
        intent=(ResolvedIntent(intent.key, intent, ()),),
        score_fields=("movement_manhattan_nm",),
    )
    reply = tmp_path / "placement.json"
    reply.write_text(
        json.dumps(
            {
                "command": "place",
                "input": {"sha256": hashlib.sha256(before).hexdigest()},
                "result": {"optimization": canonical.to_data(result)},
            }
        )
    )
    page = tmp_path / "placement.html"
    rendered = command(
        "view",
        str(board),
        "--placement",
        str(reply),
        "--cache",
        "off",
        "--no-review",
        "--no-models",
        "--export",
        str(page),
        "--confirm",
        cwd=tmp_path,
    )
    assert rendered.ok, rendered.error
    (observed,) = run(
        [
            job(
                "placement_keyboard",
                page,
                tmp_path,
                ref=tmp_path / "no-reference.png",
                script="sectionEl('findings').open = true; return {};",
                keys=[
                    {"selector": "#overlays .fg:nth-child(2) .ft", "key": "Enter"},
                    {"selector": "#overlays .ov:last-child", "key": "Enter"},
                ],
                afterKeysScript="""
const selected = S.overlays[st.selOv];
return {readonly:!LIVE, pads:selected.pad_ids || [], net:S.nets[st.selNet],
        groups:S.meta.findings.length,
        different:JSON.stringify(S.overlays[1].pts)!==JSON.stringify(S.overlays[3].pts),
        actions:document.querySelectorAll('.actPlan').length};
""",
            )
        ],
        tmp_path,
    )
    assert observed["errors"] == [], observed
    assert observed["result"] == {
        "readonly": True,
        "pads": [first.pad_id, second.pad_id],
        "net": first.net,
        "groups": 2,
        "different": True,
        "actions": 0,
    }
    assert board.read_bytes() == before
