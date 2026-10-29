# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The parts of ``fenolite.api.trial`` that need no tool (change c0209; capability kicad-oracle, "Trial
edits gated by DRC"): new findings counted by type and item set, the edit's items named by uuid, the gate's
revert, and the missing tool. ``tests/kicad/check/test_trial.py`` runs the trial on ``kicad-cli``."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _projects import authored_project

import fenolite.api.trials as trial_module
from fenolite.api import ToolMissingError, trial
from fenolite.api.trials import new_entries, owners, revert
from fenolite.backends.base import DrcItem, DrcReport, DrcViolation
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.core.coords import Point
from fenolite.model.board import Board, Track, Via
from fenolite.model.design import Design


def entry(kind: str, *uuids: str) -> DrcViolation:
    return DrcViolation(kind, kind, "error", tuple(DrcItem(u, "item", Point(0, 0)) for u in uuids))


def report(*entries: DrcViolation) -> DrcReport:
    return DrcReport("b.kicad_pcb", "", "10.0.7", "mm", violations=entries)


def test_new_entries_are_counted_by_type_and_item_set() -> None:
    before = report(entry("clearance", "a", "b"), entry("track_dangling", "c"))
    after = report(entry("clearance", "B", "A"), entry("clearance", "a", "b"), entry("via_dangling", "c"))
    assert [(e.type, [i.uuid for i in e.items]) for e in new_entries(before, after)] == [
        ("clearance", ["a", "b"]),
        ("via_dangling", ["c"]),
    ]


def design(*tracks: Track, vias: tuple[Via, ...] = ()) -> Design:
    return dataclasses.replace(Design.new("t"), board=Board(id="b", tracks=tracks, vias=vias))


def track(track_id: str, x: int = 0) -> Track:
    return Track(id=track_id, start=Point(x, 0), end=Point(x + 1000, 0), width=100, layer="F.Cu")


def test_owners_and_revert() -> None:
    old, changed = track("t1"), track("t2")
    baseline = design(old, changed)
    moved = dataclasses.replace(changed, start=Point(5, 5))
    edited = design(old, moved, track("t3"))
    assert owners(edited, {"t2", "t3"}) == {
        kicad_uuid(moved).lower(): "t2",
        kicad_uuid(track("t3")).lower(): "t3",
    }
    back = revert(edited, baseline, {"t2", "t3"})
    assert back.board is not None and back.board.tracks == (old, changed)
    removed = revert(design(old), baseline, {"t2"})
    assert removed.board is not None and [t.id for t in removed.board.tracks] == ["t1", "t2"]


def test_trial_without_kicad_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = authored_project(tmp_path, major=10) / "board.kicad_pcb"
    monkeypatch.setattr(trial_module, "find_kicad_cli", lambda _explicit: None)
    with pytest.raises(ToolMissingError) as caught:
        trial(board, lambda d: (d, ()))
    assert caught.value.cli_code == "FEN-6001"


class _FakeCli:
    def version(self) -> str:
        return "10.0.7"

    def major(self) -> int:
        return 10


def test_trial_gate_drops_a_group_whole(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A chamfer undone whole" (change c0225): a finding names ``a1`` alone, and ``a2`` of its
    group goes with it, with the same finding; ``b`` outside the group stays."""
    board = authored_project(tmp_path, major=10) / "board.kicad_pcb"
    added = (track("a1", 0), track("a2", 2000), track("b", 4000))
    bad = kicad_uuid(added[0]).lower()

    def drc(_cli: object, _project: object, text: str, *, refill: bool) -> DrcReport:
        return report(entry("clearance", bad)) if bad in text else report()

    def edit(found: Design) -> tuple[Design, tuple[str, ...]]:
        assert found.board is not None
        board = dataclasses.replace(found.board, tracks=(*found.board.tracks, *added))
        return dataclasses.replace(found, board=board), ("a1", "a2", "b")

    monkeypatch.setattr(trial_module, "_tool", lambda _path, _timeout: _FakeCli())
    monkeypatch.setattr(trial_module, "_drc", drc)
    result = trial(board, edit, gate=True, together=[("a1", "a2"), ("zz",)])
    assert result.clean and result.runs == 3 and result.kept == ("b",)
    assert [item.id for item in result.dropped] == ["a1", "a2"]
    assert result.dropped[0].findings == result.dropped[1].findings
    assert [finding.items for finding in result.dropped[1].findings] == [("a1",)]
    alone = trial(board, edit, gate=True)
    assert alone.kept == ("a2", "b") and [item.id for item in alone.dropped] == ["a1"]
