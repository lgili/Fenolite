# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.tidy.straighten`` (change c0214; capability copper-tidy, "Straighten runs", "Turn costs" and
"Runs left alone"), on authored boards of ``tests/_tidybench.py``. Hermetic."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

import pytest
from _groundties import _p, _via
from _tidybench import CLEARANCE, ONE, staircase
from _ties import MM, TieBoard

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.kicad.frame import board_pads
from fenolite.checks.copper import check_copper
from fenolite.core.coords import Point
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector
from fenolite.tidy import Clash, find_runs, straighten
from fenolite.tidy.angles import turn_kind, vector
from fenolite.tidy.graph import net_pieces
from fenolite.tidy.straighten import shapes, weight


def check(design: Design) -> Sequence[Clash]:
    report = check_copper(design, pads=board_pads(design))
    return [
        Clash(found.code, found.layer, tuple(sorted({item.entity_id for item in found.items})), found.gap)
        for found in report.findings
    ]


def _groups(design: Design) -> dict[str, tuple[tuple[str, ...], ...]]:
    return {row.name: row.pads for row in connectivity(design, pads=board_pads(design)).nets}


def _path(design: Design, net: str = "SIG") -> list[Point]:
    """The points of the net's tracks walked from (10, 10) mm: the tracks form one path."""
    assert design.board is not None
    net_id = next(n.id for n in design.circuit.nets if n.name == net)
    left = [t for t in design.board.tracks if t.net_id == net_id]
    path = [_p(10, 10)]
    while left:
        track = next(t for t in left if path[-1] in (t.start, t.end))
        left.remove(track)
        path.append(track.end if track.start == path[-1] else track.start)
    return path


def _turns(path: Sequence[Point]) -> list[str]:
    kinds = [turn_kind(vector(a, b), vector(b, c)) for a, b, c in zip(path, path[1:], path[2:], strict=False)]
    return [kind for kind in kinds if kind != "straight"]


def test_a_staircase_becomes_one_corner() -> None:
    """Scenario "A staircase becomes one corner": eight steps between two pads give one 45° turn."""
    design = staircase()
    assert len(_turns(_path(design))) == 16
    result = straighten(design, pads=board_pads(design), check=check)
    path = _path(result.design)
    assert path == [_p(10, 10), _p(14, 14), _p(20, 14)]
    assert _turns(path) == ["45"]
    (edit,) = result.edits
    assert (edit.step, edit.reason, edit.net, edit.layer, edit.at) == (
        "straighten",
        "fewer-turns",
        "SIG",
        "F.Cu",
        _p(10, 10),
    )
    assert len(edit.replaced) == 2 and len(edit.removed) == 15 and edit.added == ()
    assert _groups(result.design) == _groups(design) and check(result.design) == []
    assert result.issues == ()


def test_a_blocked_shape_is_passed_over() -> None:
    """Scenario "A blocked shape is passed over": a pad of ``OTHER`` on the diagonal of the lightest shape
    leaves the other shape of one 45° turn."""
    design = staircase(blocker=True)
    assert check(design) == []
    result = straighten(design, pads=board_pads(design), check=check)
    assert _path(result.design) == [_p(10, 10), _p(16, 10), _p(20, 14)]
    assert check(result.design) == [] and _groups(result.design) == _groups(design)


def test_a_pair_stays() -> None:
    """Scenario "A pair stays": ``D_P`` has the coupled net ``D_N`` on the board."""
    design = staircase(net="D_P", partner="D_N")
    result = straighten(design, pads=board_pads(design), check=check)
    assert result.edits == () and result.design == design
    (found,) = result.issues
    assert (found.code, found.severity, found.where) == ("tidy.straighten-skipped", "info", "D_P")


def test_a_length_rule_keeps_the_net() -> None:
    design = staircase()
    rule = Rule(
        id="rul_00000000-0000-4000-8000-000000000001",
        name="sig-length",
        kind="length",
        selector_a=Selector("net", "SIG"),
        max=40 * MM,
    )
    ruled = dataclasses.replace(
        design, rules=RuleSet(id="rls_00000000-0000-4000-8000-000000000001", rules=(rule,))
    )
    result = straighten(ruled, pads=board_pads(ruled), check=check)
    assert result.edits == () and [found.code for found in result.issues] == ["tidy.straighten-skipped"]


def test_a_contact_along_the_run_keeps_it() -> None:
    """A via that a track of the run touches between two joints would be dropped: the run stays."""
    design = staircase()
    assert design.board is not None
    net_id = design.circuit.nets[0].id
    board = dataclasses.replace(design.board, vias=(_via(1, net_id, _p(15.5, 12)),))
    held = dataclasses.replace(design, board=board)
    assert find_runs(held, pads=board_pads(held))[0] == ()
    assert straighten(held, pads=board_pads(held), check=check).edits == ()


def test_locked_and_kept_tracks_end_runs() -> None:
    design = staircase()
    assert design.board is not None
    middle = design.board.tracks[8]
    locked = tuple(dataclasses.replace(t, locked=t.id == middle.id) for t in design.board.tracks)
    held = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=locked))
    runs, _ = find_runs(held, pads=board_pads(held))
    assert len(runs) == 2 and all(middle.id not in run.ids for run in runs)
    result = straighten(held, pads=board_pads(held), check=check)
    assert result.design.board is not None
    assert dataclasses.replace(middle, locked=True) in result.design.board.tracks
    assert _groups(result.design) == _groups(design) and check(result.design) == []
    runs, _ = find_runs(design, pads=board_pads(design), keep={middle.id})
    assert len(runs) == 2
    assert find_runs(design, pads=board_pads(design), nets={"OTHER"})[0] == ()


def test_an_l_between_pads_takes_a_45_degree_turn() -> None:
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 10), nets={"1": "SIG"})
    board.place("U2", ONE, _p(30, 20), nets={"1": "SIG"})
    board.track("t1", "SIG", _p(10, 10), _p(30, 10))
    board.track("t2", "SIG", _p(30, 10), _p(30, 20))
    design = board.build()
    result = straighten(design, pads=board_pads(design), check=check)
    assert _path(result.design) == [_p(10, 10), _p(20, 20), _p(30, 20)]
    (edit,) = result.edits
    assert edit.removed == () and edit.added == () and len(edit.replaced) == 2


@pytest.mark.parametrize("end", [(7, 3), (3, 7), (-7, 3), (-3, -7), (5, 0), (4, 4), (2, -9)])
def test_every_shape_is_on_the_lattice(end: tuple[int, int]) -> None:
    start = _p(10, 10)
    target = Point(start.x + end[0] * MM, start.y + end[1] * MM)
    found = shapes(start, target)
    assert found and len(found) <= 10
    for shape in found:
        assert shape[0] == start and shape[-1] == target and len(shape) <= 4
        for a, b in zip(shape, shape[1:], strict=False):
            dx, dy = abs(b.x - a.x), abs(b.y - a.y)
            assert (dx, dy) != (0, 0) and (dx == 0 or dy == 0 or dx == dy)
        assert weight(shape, "F.Cu") is not None


def test_turn_weights() -> None:
    """45° weighs 1, 90° weighs 3, an acute turn is refused unless asked; joints at the ends count."""
    a, b, c = _p(0, 0), _p(1, 0), _p(2, 1)
    assert weight((a, b, c), "F.Cu") == 1
    assert weight((a, b, _p(1, 1)), "F.Cu") == 3
    assert weight((a, b, _p(0, 1)), "F.Cu") is None
    assert weight((a, b, _p(0, 1)), "F.Cu", acute=True) == 4
    assert weight((a, b), "F.Cu", before=[(0, MM)]) == 3
    assert weight((a, b), "F.Cu", after=[(MM, MM)]) == 1
    assert weight((a, b), "F.Cu", before=[(MM, MM)]) is None


def test_a_turn_inside_an_end_pad_is_free() -> None:
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 10), nets={"1": "SIG"})
    design = board.build()
    pads = [
        p for held in net_pieces(design, board_pads(design)).pieces.values() for p in held if p.kind == "pad"
    ]
    path = (_p(10, 10), _p(10.2, 10), _p(12, 11.8))
    assert weight(path, "F.Cu") == 1 and weight(path, "F.Cu", pads=pads) == 0


def test_runs_are_in_a_fixed_order() -> None:
    design = staircase()
    assert design.board is not None
    shuffled = dataclasses.replace(design.board, tracks=tuple(reversed(design.board.tracks)))
    other = dataclasses.replace(design, board=shuffled)
    a = straighten(design, pads=board_pads(design), check=check)
    b = straighten(other, pads=board_pads(other), check=check)
    assert a.edits == b.edits
    assert a.design.board is not None and b.design.board is not None
    assert sorted(a.design.board.tracks, key=lambda t: t.id) == sorted(
        b.design.board.tracks, key=lambda t: t.id
    )


def test_a_track_alone_is_no_run() -> None:
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 10), nets={"1": "SIG"})
    board.place("U2", ONE, _p(20, 10), nets={"1": "SIG"})
    board.track("t", "SIG", _p(10, 10), _p(20, 10))
    design = board.build()
    assert find_runs(design, pads=board_pads(design)) == ((), ())


def test_a_tee_entry_is_not_redrawn() -> None:
    """A stem with its 45° entry ends on the bar's middle: the bar counts as a joint, so the run of the stem
    and the entry keeps its shape although a turn inside the stem's pad would be free."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 30), nets={"1": "BUS"})
    board.place("U2", ONE, _p(25, 30), nets={"1": "BUS"})
    board.place("U3", ONE, _p(18, 36), nets={"1": "BUS"})
    board.track("k", "BUS", _p(10, 30), _p(25, 30))
    board.track("m", "BUS", _p(18, 36), _p(18, 30.5))
    board.track("e", "BUS", _p(18, 30.5), _p(17.5, 30))
    design = board.build()
    (run,) = find_runs(design, pads=board_pads(design))[0]
    assert len(run.tracks) == 2
    assert straighten(design, pads=board_pads(design), check=check).edits == ()
