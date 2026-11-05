# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Accepted, manual and locked copper survive ``fenolite convert --to altium`` by readback (change c0370,
task 6; capability routing, "Reviewed completion acceptance").

On the authored completion board (``tests/_completion_project.py``), on two and four layers, both routes are
accepted through reviewed plans, then the board is converted to Altium and the written PcbDoc is read back by
Fenolite's own Altium reader. Every KiCad track comes back once with its net, layer, width and lock, its ends
equal up to one Altium unit (254 / 100 nm) under one translation (the Altium origin differs from the KiCad
board frame's). This is Fenolite reading what it wrote: the evidence stays ``INFERRED``; opening the document
in Altium Designer is a separate maintainer gate (``docs/evidence/router-completion.md``).
"""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any

import pytest
from _completion_project import by_hand, project
from _search_project import cli

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.pcb import read_board
from fenolite.model.design import Design

ROUTE = ("--router", "octilinear", "--router-option", "max-length=60mm")
UNIT_NM = 3
"""One Altium internal unit is 1/10 000 mil, 2.54 nm: an end may round by that much."""


def reviewed(*words: str) -> dict[str, Any]:
    code, env, err = cli(*words, "--dry-run")
    assert code == 0, (err, env.get("issues"))
    code, done, err = cli(*words, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, err
    return done


def tracks(design: Design) -> list[tuple[Any, ...]]:
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    return sorted(
        (names.get(t.net_id or ""), t.layer, t.width, t.locked, (t.start.x, t.start.y), (t.end.x, t.end.y))
        for t in design.board.tracks
    )


@pytest.mark.parametrize("layers", [2, 4])
def test_locked_routes_read_back_from_the_converted_altium_board(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layers: int
) -> None:
    monkeypatch.chdir(tmp_path)
    built = project(tmp_path, layers=layers)
    by_hand(built.board)
    board = built.board
    code, env, err = cli("route", str(board), *ROUTE, "--propose")
    assert code == 0, err
    for proposal in env["result"]["proposals"]:
        reviewed("route", str(board), *ROUTE, "--accept", proposal["candidates"][0]["id"])

    source = tracks(read_board(board.read_text(encoding="utf-8"), file=board.name))
    assert {row[0] for row in source if row[3]} == {"SIG", "SECOND", "BLOCK"}, source
    assert [row[0] for row in source if not row[3]] == ["MANUAL", "MANUAL"]

    converted = reviewed("convert", str(board), "--to", "altium", "--out", str(tmp_path / "altium"))
    assert converted["evidence"]["level"] in ("INFERRED", "UNKNOWN", "UNVERIFIED"), converted["evidence"]
    (pcbdoc,) = sorted((tmp_path / "altium").rglob("*.PcbDoc"))
    back = tracks(AltiumBackend().read(pcbdoc).design)

    # Identity: the same multiset of net, layer, width and lock.
    assert [row[:4] for row in back] == [row[:4] for row in source], (source, back)
    # Geometry: x' = x - ox and y' = y - oy for one (ox, oy), fitted on the tracks whose identity is unique;
    # then every source track matches one track read back, both ends within one Altium unit.
    unique = [
        (s, t) for s, t in zip(source, back, strict=True) if [row[:4] for row in source].count(s[:4]) == 1
    ]
    ox = median(s[4][0] - t[4][0] for s, t in unique)
    oy = median(s[4][1] - t[4][1] for s, t in unique)

    def near(a: tuple[float, float], b: tuple[int, int]) -> bool:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= UNIT_NM

    left = list(back)
    for row in source:
        ends = [(x - ox, y - oy) for x, y in (row[4], row[5])]
        match = next(
            t
            for t in left
            if t[:4] == row[:4]
            and (
                (near(ends[0], t[4]) and near(ends[1], t[5])) or (near(ends[0], t[5]) and near(ends[1], t[4]))
            )
        )
        left.remove(match)
    assert not left
