# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place`` on a board it did not lay out (change c0432; capability placement, "Findings the move
did not make" and "Locked parts of a converted board"; capability layout-reuse, "Copper dragged with a
moved group").

Two authored boards: the built blink of the place tests, and the authored Altium ``routed`` sample
converted to KiCad. In ``routed`` R1 has a via in pad 2 (``LED_A``, joined to D1 by an inner track) and a
track from pad 1 to U1; U1 is locked."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from _buildhelp import blink_variant
from _checkcli import run

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.core.coords import Point
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
ROUTED = ROOT / "tests" / "data" / "altium" / "routed"
MM = 1_000_000


def codes(env: dict[str, Any]) -> list[str]:
    return [found["code"] for found in env["issues"]]


def _built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    script = blink_variant(tmp_path / "p-src")
    text = script.read_text(encoding="utf-8")
    bottom = 'd1.place(mm(38), mm(20), side="bottom")'
    assert bottom in text
    script.write_text(text.replace(bottom, "d1.place(mm(38), mm(20))"), encoding="utf-8")  # D1 on top
    out = tmp_path / "p"
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, (env.get("issues"), err)
    return out


def _converted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    shutil.copytree(ROUTED, tmp_path / "src")
    argv = (
        "convert",
        str(tmp_path / "src" / "routed.PrjPcb"),
        "--to",
        "kicad",
        "--out",
        str(tmp_path / "conv"),
    )
    code, env, err, _ = run(monkeypatch, tmp_path, *argv, "--allow-lossy", "--confirm")
    assert code == 0, (env.get("issues"), err)
    return tmp_path / "conv" / "routed.kicad_pcb"


def _parts(design: Design) -> dict[str, FootprintInstance]:
    assert design.board is not None
    return {footprint_ref(design, fp): fp for fp in design.board.footprints}


def _pad(design: Design, ref: str, number: str) -> Point:
    return next(p.position for p in KicadBackend().board_pads(design) if p.ref == ref and p.number == number)


# --- (a) findings the move did not make ----------------------------------------------------------------


def test_an_overlap_left_where_it_was_does_not_refuse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "An overlap left where it was": R1 is forced onto D1 first; a legal move of U1 then reports
    that overlap as ``place.existing`` and exits 0. Moving R1 again, still on D1, stays an error."""
    folder = _built(monkeypatch, tmp_path)
    board = folder / "blink.kicad_pcb"
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", str(folder), "--move", "R1=38mm,20mm", "--force", "--confirm"
    )
    assert code == 5 and codes(env) == ["place.courtyard-overlap"]
    code, env, err, _ = run(
        monkeypatch, tmp_path, "place", str(folder), "--move", "U1=16mm,15mm", "--force", "--confirm"
    )
    assert code == 0, (env["issues"], err)
    existing = [found for found in env["issues"] if found["code"] == "place.existing"]
    assert [(found["severity"], found["where"]) for found in existing] == [("warning", "D1,R1")]
    assert existing[0]["message"].startswith("place.courtyard-overlap on D1,R1 was on the board before")
    assert "place.courtyard-overlap" not in codes(env)
    assert env["result"]["legality"] == {"place.courtyard-overlap": 1}
    assert _parts(read_board(board))["U1"].position.x == 100 * MM + 16 * MM


def test_a_finding_on_a_moved_part_is_judged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Negative case: the same overlap on a part the command moves is an error, and nothing is planned."""
    folder = _built(monkeypatch, tmp_path)
    run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=38mm,20mm", "--force", "--confirm")
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", str(folder), "--move", "R1=38.2mm,20mm", "--dry-run"
    )
    assert code == 5 and codes(env) == ["place.courtyard-overlap"]
    assert "plan" not in env["result"]


# --- (b) locked parts of a converted board -------------------------------------------------------------


def test_a_locked_converted_part_names_force(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _converted(monkeypatch, tmp_path)
    assert _parts(read_board(board))["U1"].locked
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", str(board), "--shift", "U1", "--by", "1mm,0mm", "--dry-run"
    )
    assert code == 5 and codes(env) == ["place.locked"]
    hint = env["issues"][0]["hint"]
    assert "--force" in hint and "keeps each part's lock" in hint
    code, env, err, _ = run(
        monkeypatch, tmp_path, "place", str(board), "--shift", "U1", "--by", "1mm,0mm", "--force", "--dry-run"
    )
    assert code == 0, (env["issues"], err)
    assert [row["ref"] for row in env["result"]["moved"]] == ["U1"]


# --- (c) copper dragged with a moved group -------------------------------------------------------------


@pytest.mark.parametrize(
    "move",
    [("--shift", "R1", "--by", "1mm,0mm"), ("--turn", "R1", "--about", "32mm,9mm", "--angle", "90")],
    ids=["shift", "turn"],
)
def test_group_drags_the_copper_on_its_pads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, move: tuple[str, ...]
) -> None:
    """Scenario "A via in a pad and a track to another part": the via in R1's pad 2 moves with it, the
    track ends on R1 and on that via follow, their other ends and every other item stay."""
    board = _converted(monkeypatch, tmp_path)
    before = read_board(board)
    assert before.board is not None
    pad1, pad2 = _pad(before, "R1", "1"), _pad(before, "R1", "2")
    code, env, err, _ = run(monkeypatch, tmp_path, "place", str(board), *move, "--confirm")
    assert code == 0, (env["issues"], err)
    assert "place.copper-left" not in codes(env) and "place.group-failed" not in codes(env)
    assert env["result"]["group"]["copper_check"]["new"] == 0
    after = read_board(board)
    assert after.board is not None
    new1, new2 = _pad(after, "R1", "1"), _pad(after, "R1", "2")
    assert new1 != pad1 and new2 != pad2
    vias_before = {via.id: via for via in before.board.vias}
    vias_after = {via.id: via for via in after.board.vias}
    moved_vias = {i for i in vias_before if vias_before[i].position != vias_after[i].position}
    assert {vias_after[i].position for i in moved_vias} == {new2}
    assert {vias_before[i].position for i in moved_vias} == {pad2}
    tracks_before = {track.id: track for track in before.board.tracks}
    changed = [
        t
        for t in after.board.tracks
        if (t.start, t.end) != (tracks_before[t.id].start, tracks_before[t.id].end)
    ]
    assert len(changed) == 2
    for track in changed:
        old = tracks_before[track.id]
        kept = {old.start, old.end} & {track.start, track.end}
        assert len(kept) == 1  # one end stays
        assert ({track.start, track.end} - kept) <= {new1, new2}
    assert [(a.start, a.mid, a.end) for a in after.board.arcs] == [
        (a.start, a.mid, a.end) for a in before.board.arcs
    ]
    assert [z.outline for z in after.board.zones] == [z.outline for z in before.board.zones]


def test_flip_on_a_converted_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Flip is reached through --move: D1 (bottom) to the top, R1 (top) to the bottom, U1 (locked) with
    --force."""
    board = _converted(monkeypatch, tmp_path)
    for move, ref, side, extra in (
        ("D1=38mm,20mm,0,top", "D1", "top", ()),
        ("R1=32mm,9mm,0,bottom", "R1", "bottom", ()),
        ("U1=14mm,15mm,0,bottom", "U1", "bottom", ("--force",)),
    ):
        code, env, err, _ = run(
            monkeypatch, tmp_path, "place", str(board), "--move", move, *extra, "--confirm"
        )
        assert code == 0, (move, env["issues"], err)
        assert _parts(read_board(board))[ref].side == side
