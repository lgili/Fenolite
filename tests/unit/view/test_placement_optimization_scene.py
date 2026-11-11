# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

import hashlib
import json
from pathlib import Path
from shutil import copyfile

from fenolite.api import run
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model import canonical
from fenolite.placement.intent import PlacementIntent, ResolvedIntent
from fenolite.placement.optimization_contract import (
    OptimizationCandidate,
    PadProbe,
    PlacementOptimization,
    ProposedPose,
    candidate_id,
)
from fenolite.placement.topology import PadIdentity
from fenolite.view.export import embedded

BOARD = Path(__file__).resolve().parents[3] / "tests/data/kicad/board/two_layer.kicad_pcb"


def test_static_proposal_shows_pose_changes_and_exact_pad_links(tmp_path, monkeypatch):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    board_path = tmp_path / BOARD.name
    copyfile(BOARD, board_path)
    before = board_path.read_bytes()
    design = read_board(board_path)
    assert design.board is not None
    first, second = [fp for fp in design.board.footprints if not fp.locked and fp.pads][:2]
    first_at = first.position
    poses = (
        ProposedPose(
            first.id, Point(first_at.x + 1_000_000, first_at.y), first.rotation % 360_000_000, first.side
        ),
    )
    fingerprint = hashlib.sha256(b"authored proposal").hexdigest()
    ident = candidate_id(fingerprint, poses)
    intent = PlacementIntent(
        "return",
        "proximity",
        (PadIdentity(first.id, first.pads[0].id), PadIdentity(second.id, second.pads[0].id)),
        "declared",
        "authored fixture",
        "v0",
        "review the exact return pads",
    )
    result = PlacementOptimization(
        fingerprint,
        "complete",
        candidates=(
            OptimizationCandidate(
                ident,
                poses,
                (170_000,),
                ("capacity:net:RETURN",),
                {"F.Cu": 170_000},
                (PadProbe("return", "found", 1_700_000, 35),),
            ),
        ),
        movable=(first.id,),
        fixed={second.id: ("outside_scope",)},
        intent=(ResolvedIntent(intent.key, intent, ()),),
        score_fields=("channel_overflow_nm",),
    )
    saved = tmp_path / "proposal.json"
    saved.write_text(
        json.dumps(
            {
                "command": "place",
                "input": {"sha256": hashlib.sha256(before).hexdigest()},
                "result": {"optimization": canonical.to_data(result)},
            }
        )
    )
    page = tmp_path / "placement.html"
    reply = run(
        "view",
        str(board_path),
        "--placement",
        str(saved),
        "--cache",
        "off",
        "--no-models",
        "--no-review",
        "--export",
        str(page),
        "--confirm",
        cwd=tmp_path,
    )
    assert reply.exit_code == 0, reply.error
    assert board_path.read_bytes() == before
    data = embedded(page.read_text(encoding="utf-8"))
    assert data is not None
    (scene,) = data["scenes"].values()
    (motion, link) = scene["overlays"]
    assert motion["pts"][1][0] - motion["pts"][0][0] == 1000
    assert link["label"].startswith("return · pad distance ") and len(link["pts"]) == 2
    (group,) = scene["meta"]["findings"]
    assert group["id"] == "placement-" + ident
    assert "channel_overflow_nm=170000" in group["note"] and "capacity:net:RETURN" in group["note"]
    assert "F.Cu=170000" in group["note"] and "return found 1700000 nm" in group["note"]
    assert motion["component_id"] == first.component_id
    assert link["pad_ids"] == [first.pads[0].id, second.pads[0].id]

    board_path.write_bytes(before + b"\n")
    stale = run(
        "view",
        str(board_path),
        "--placement",
        str(saved),
        "--cache",
        "off",
        "--no-review",
        cwd=tmp_path,
    )
    assert stale.exit_code == 0, stale.error
    assert stale.result["summary"]["findings"] == {}
    assert any("another board revision" in text for text in stale.result["notes"])
