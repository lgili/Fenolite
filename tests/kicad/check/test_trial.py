# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.trial`` against the running ``kicad-cli`` (change c0209; capability kicad-oracle, "Trial
edits gated by DRC"; ``H-K-DRC-TRIAL``).

The bench, written for the running major: ``R1`` and ``R2`` with pads 2 and 1 on ``S``, ``R3`` and ``R4``
with pads 2 and 1 on ``T`` (two missing connections), and ``R5`` with its pads on ``U`` and ``V`` 0.7 mm
above the line from ``R3`` to ``R4``. The edit adds a 0.25 mm track on ``S`` from ``R1`` to ``R2`` and one
on ``T`` from ``R3`` to ``R4``: the second passes 0.1 mm from both pads of ``R5`` under KiCad's default
0.2 mm clearance.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection
from functools import cache
from pathlib import Path

import _rulebench as rb
import pytest
from _probes import major, runner

from fenolite.api import trial
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.core.coords import Point
from fenolite.model.board import Track
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad

BOARD = "bench.kicad_pcb"
Y = 20 * rb.MM
GOOD, BAD = "trk_trial_good", "trk_trial_bad"


@cache
def bench() -> rb.Bench:
    made = rb.Builder()
    made.part("r1", "R1", Point(12 * rb.MM, Y), target=major(), nets={"2": "S"})
    made.part("r2", "R2", Point(18 * rb.MM, Y), target=major(), nets={"1": "S"})
    made.part("r3", "R3", Point(12 * rb.MM, Y + 4 * rb.MM), target=major(), nets={"2": "T"})
    made.part("r4", "R4", Point(18 * rb.MM, Y + 4 * rb.MM), target=major(), nets={"1": "T"})
    made.part("r5", "R5", Point(15 * rb.MM, Y + 4_700_000), target=major(), nets={"1": "U", "2": "V"})
    return made.build()


def folder(root: Path) -> Path:
    (root / BOARD).write_text(write_board(bench().design, target=major()).text, encoding="utf-8")
    (root / "bench.kicad_pro").write_text("{}\n", encoding="utf-8")
    return root / BOARD


def two_tracks(design: Design) -> tuple[Design, Collection[str]]:
    board = design.board
    assert board is not None
    nets = {net.name: net.id for net in design.circuit.nets}
    tracks = (
        Track(id=GOOD, start=Point(12_800_000, Y), end=Point(17_200_000, Y), width=rb.WIDTH, layer="F.Cu",
              net_id=nets["S"]),
        Track(id=BAD, start=Point(12_800_000, Y + 4 * rb.MM), end=Point(17_200_000, Y + 4 * rb.MM),
              width=rb.WIDTH, layer="F.Cu", net_id=nets["T"]),
    )  # fmt: skip
    edited = dataclasses.replace(board, tracks=(*board.tracks, *tracks))
    return dataclasses.replace(design, board=edited), (GOOD, BAD)


def test_trial_maps_new_findings_to_the_edit(tmp_path: Path) -> None:
    result = trial(folder(tmp_path), two_tracks, kicad_cli=str(runner().path))
    assert result.findings and result.runs == 2 and not result.dropped
    assert {finding.type for finding in result.findings} == {"clearance"}
    assert all(finding.items == (BAD,) for finding in result.findings)
    pads = {*bench().uuids("r5")}
    assert all(set(finding.uuids) == {uuid(BAD), *(set(finding.uuids) & pads)} for finding in result.findings)
    assert all(set(finding.uuids) & pads for finding in result.findings)  # a pad of R5 (one per track)
    assert result.kept == (GOOD, BAD) and result.evidence.level == "KICAD-VERIFIED"


def test_trial_gate_drops_the_offending_track(tmp_path: Path) -> None:
    """Scenario "One offending track dropped"."""
    result = trial(folder(tmp_path), two_tracks, kicad_cli=str(runner().path), gate=True)
    assert result.clean and result.runs == 3
    assert result.kept == (GOOD,)
    ((dropped),) = result.dropped
    assert dropped.id == BAD and {f.type for f in dropped.findings} == {"clearance"}
    kept = read_board(result.board_text)
    assert kept.board is not None
    assert [t.native_ids.get("kicad") for t in kept.board.tracks] == [uuid(GOOD)]


def test_trial_of_a_clean_edit(tmp_path: Path) -> None:
    def good_only(design: Design) -> tuple[Design, Collection[str]]:
        edited, _ = two_tracks(design)
        assert edited.board is not None
        board = dataclasses.replace(edited.board, tracks=tuple(t for t in edited.board.tracks if t.id != BAD))
        return dataclasses.replace(edited, board=board), (GOOD,)

    result = trial(folder(tmp_path), good_only, kicad_cli=str(runner().path), gate=True)
    assert result.clean and result.runs == 2 and result.kept == (GOOD,) and not result.dropped
    assert result.edited == result.baseline - 1  # the missing connection on S is made


def uuid(track_id: str) -> str:
    """The KiCad uuid the writer gives a track of ``track_id`` (it depends on the id only)."""
    return kicad_uuid(Track(id=track_id, start=Point(0, 0), end=Point(1, 0), width=1, layer="F.Cu"))


def test_trial_refills_the_zones(tmp_path: Path) -> None:
    """With ``refill`` (KiCad 10) the zone is refilled around a track the edit lays across its stored
    fill; without it the stored fill touches the track, and the trial reports that."""
    if major() < 10:
        pytest.skip("pcb drc --refill-zones is 10.0 only (trial.not-refilled on 9)")
    made = rb.Builder()
    made.filled_zone("plane", "GND", 20 * rb.MM)
    made.via("sig", "SIG", Point(30 * rb.MM, 10 * rb.MM))  # keeps the net in the file
    (tmp_path / BOARD).write_text(write_board(made.build().design, target=major()).text, encoding="utf-8")
    (tmp_path / "bench.kicad_pro").write_text("{}\n", encoding="utf-8")

    def across(design: Design) -> tuple[Design, Collection[str]]:
        assert design.board is not None
        net = next(n.id for n in design.circuit.nets if n.name == "SIG")
        track = Track(id=BAD, start=Point(12 * rb.MM, 21 * rb.MM), end=Point(18 * rb.MM, 21 * rb.MM),
                      width=rb.WIDTH, layer="F.Cu", net_id=net)  # fmt: skip
        board = dataclasses.replace(design.board, tracks=(*design.board.tracks, track))
        return dataclasses.replace(design, board=board), (BAD,)

    filled = trial(tmp_path / BOARD, across, kicad_cli=str(runner().path))
    stored = trial(tmp_path / BOARD, across, kicad_cli=str(runner().path), refill=False)
    assert filled.refilled and not stored.refilled and not filled.issues
    touching = {"clearance", "shorting_items"}
    assert not {f.type for f in filled.findings} & touching
    assert {f.type for f in stored.findings} & touching
