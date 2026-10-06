# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Constrained dry-run/confirm, receipts and previews from exact board serialization."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from _checkcli import run
from _coppercheck import Copper
from _projects import tree_snapshot

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.core.coords import Point
from fenolite.model.board import Outline
from fenolite.placement.preview import placement_preview

MM = 1_000_000


def authored_board(tmp_path: Path) -> Path:
    made = Copper()
    made.pad("J1", "1", "A", kind="thru_hole", layers=("F.Cu", "B.Cu"))
    made.pad("R1", "1", "B")
    d = made.build()
    assert d.board is not None
    fps = tuple(
        replace(
            fp,
            position=Point(8 * MM, 8 * MM) if i == 0 else Point(60 * MM, 40 * MM),
            locked=i == 0,
            pads=tuple(replace(p, drill=MM // 2) if i == 0 else p for p in fp.pads),
        )
        for i, fp in enumerate(d.board.footprints)
    )
    outline = Outline(
        id="out_00000000-0000-0000-0000-000000000001",
        points=(Point(0, 0), Point(30 * MM, 0), Point(30 * MM, 20 * MM), Point(0, 20 * MM)),
    )
    d = replace(d, board=replace(d.board, footprints=fps, outline=outline))
    path = tmp_path / "authored.kicad_pcb"
    path.write_text(write_board(d, target=10).text, encoding="utf-8")
    path.with_suffix(".kicad_dru").write_text(
        "(version 1)\n(rule supplied (constraint clearance (min 0.2mm)))\n", encoding="utf-8"
    )
    return path


def test_confirm_preview_matches_serialized_readback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = authored_board(tmp_path)
    old = read_board(path)
    before = tree_snapshot(tmp_path)
    args = ("place", str(path), "--strategy", "constrained", "--only", "R1", "--preview-dir", "views")
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (env, err)
    assert tree_snapshot(tmp_path) == before
    proposal = env["result"]["placement"]
    assert proposal["unplaced"] == [] and proposal["assessment"]["state"] == "incomplete"
    assert len(proposal["request_sha256"]) == 64 and env["evidence"]["level"] == "INFERRED"
    assert len(env["result"]["plan"]) == 3
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0, (env, err)
    written = read_board(path)
    by_ref = {footprint_ref(written, fp): fp for fp in written.board.footprints}
    old_anchor = next(fp for fp in old.board.footprints if fp.locked)
    assert by_ref["J1"].position == old_anchor.position and by_ref["J1"].locked
    assert by_ref["R1"].position.x < 30 * MM
    assert {(n.name, n.members) for n in written.circuit.nets} == {
        (n.name, n.members) for n in old.circuit.nets
    }
    assert env["result"]["preview"]["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    for face in ("top", "bottom"):
        svg = tmp_path / "views" / f"placement-{face}.svg"
        rings = board_outline(written).rings
        queried = replace(
            written,
            board=replace(
                written.board, outline=Outline(id="query", points=rings[0], cutouts=tuple(rings[1:]))
            ),
        )
        assert svg.read_text(encoding="utf-8") == placement_preview(queried, KicadBackend(), face=face)
    assert len(env["receipt"]["written"]) == 3


def test_request_hash_and_invalid_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = authored_board(tmp_path)
    request = tmp_path / "placement.json"
    request.write_text(
        json.dumps(
            {
                "schema": "fenolite.placement-request.v0",
                "constraints": {"pitch": 1_000_000, "max_candidates": 1, "gap": 0},
            }
        ),
        encoding="utf-8",
    )
    code, env, err, _ = run(
        monkeypatch,
        tmp_path,
        "place",
        str(path),
        "--strategy",
        "constrained",
        "--constraints",
        str(request),
        "--dry-run",
    )
    assert code == 0, (env, err)
    hashes = env["result"]["placement"]["constraints"]["source_hashes"]
    assert hashes == [["placement.json", hashlib.sha256(request.read_bytes()).hexdigest()]]
    request.write_text(
        '{"schema":"fenolite.placement-request.v0","constraints":{"pitch":0.5}}', encoding="utf-8"
    )
    code, _, err, _ = run(
        monkeypatch,
        tmp_path,
        "place",
        str(path),
        "--strategy",
        "constrained",
        "--constraints",
        str(request),
        "--dry-run",
    )
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(
        monkeypatch, tmp_path, "place", str(path), "--strategy", "constrained", "--force", "--dry-run"
    )
    assert code == 2 and err["code"] == "FEN-2001"
