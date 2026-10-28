# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.tidy.chamfer`` (change c0208; capability copper-tidy, "Chamfer joints"), on the authored
boards of ``tests/_tidybench.py``. Hermetic."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from _groundties import _box, _p, _via, _zone
from _tidybench import CLEARANCE, LEG, ONE, bench, corner
from _ties import MM, TieBoard

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.kicad.frame import board_pads
from fenolite.checks.copper import check_copper
from fenolite.model.board import Track
from fenolite.model.design import Design
from fenolite.tidy import Clash, Tee, chamfer, cut_zones, find_corners, find_joints

T1 = "trk_00000000-0000-4000-8000-000000000001"
T2 = "trk_00000000-0000-4000-8000-000000000002"
T3 = "trk_00000000-0000-4000-8000-000000000003"


def check(design: Design) -> Sequence[Clash]:
    report = check_copper(design, pads=board_pads(design))
    return [
        Clash(found.code, found.layer, tuple(sorted({item.entity_id for item in found.items})), found.gap)
        for found in report.findings
    ]


def _tracks(design: Design) -> dict[str, Track]:
    assert design.board is not None
    return {track.id: track for track in design.board.tracks}


def _groups(design: Design) -> dict[str, tuple[tuple[str, ...], ...]]:
    return {row.name: row.pads for row in connectivity(design, pads=board_pads(design)).nets}


def test_a_right_angle() -> None:
    """Scenario "A right angle": two 0.3 mm tracks; legs of 0.6 mm; the net keeps its groups."""
    design = corner(3 * MM // 10)
    result = chamfer(design, pads=board_pads(design), check=check)
    tracks = _tracks(result.design)
    assert tracks[T1].start == _p(10, 10) and tracks[T1].end == _p(29.4, 10)
    assert tracks[T2].start == _p(30, 10.6) and tracks[T2].end == _p(30, 20)
    (edit,) = result.edits
    assert (edit.step, edit.reason, edit.net, edit.layer, edit.at) == (
        "chamfer",
        "right-angle",
        "SIG",
        "F.Cu",
        _p(30, 10),
    )
    assert edit.replaced == (T1, T2) and edit.removed == ()
    (diagonal,) = (tracks[ident] for ident in edit.added)
    assert (diagonal.start, diagonal.end, diagonal.width) == (_p(29.4, 10), _p(30, 10.6), 3 * MM // 10)
    assert _groups(result.design) == _groups(design) and check(result.design) == []
    assert result.issues == ()


def test_the_leg_is_shortened_to_half_the_shorter_track() -> None:
    design = corner(MM // 4)
    (found,) = find_corners(design, pads=board_pads(design), leg=20 * MM)[0]
    assert found.leg == 5 * MM
    (found,) = find_corners(design, pads=board_pads(design))[0]
    assert found.leg == LEG


def test_a_track_cut_to_nothing_is_removed() -> None:
    """A step of 1 mm between two right angles: both chamfers take half of it, so it goes."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 10), nets={"1": "SIG"})
    board.place("U2", ONE, _p(12, 11), nets={"1": "SIG"})
    board.track("a", "SIG", _p(10, 10), _p(11, 10))
    board.track("b", "SIG", _p(11, 10), _p(11, 11))
    board.track("c", "SIG", _p(11, 11), _p(12, 11))
    design = board.build()
    result = chamfer(design, pads=board_pads(design), check=check)
    tracks = _tracks(result.design)
    assert T2 not in tracks and len(tracks) == 4
    assert [(edit.removed, edit.replaced) for edit in result.edits] == [((T2,), (T1,)), ((), (T3,))]
    assert _groups(result.design) == _groups(design)


def test_a_chamfer_too_close_is_undone() -> None:
    """``V1-1`` sits inside the corner, clear of both tracks but not of the chamfer: it is undone."""
    design = bench(stub=False, lead=False, bus=False, intruder=True)
    assert check(design) == []
    result = chamfer(design, pads=board_pads(design), check=check)
    assert result.edits == () and result.design == design
    (found,) = result.issues
    assert (found.code, found.severity) == ("tidy.chamfer-undone", "info")
    assert "copper.clearance" in found.message


def test_an_unattributed_finding_undoes_every_chamfer() -> None:
    design = corner(MM // 4)

    def stubborn(seen: Design) -> Sequence[Clash]:
        return [] if seen == design else [Clash("copper.clearance", "F.Cu", ("elsewhere",), 0)]

    result = chamfer(design, pads=board_pads(design), check=stubborn)
    assert result.edits == () and [found.code for found in result.issues] == ["tidy.chamfer-undone"]


def test_joints_left_alone() -> None:
    """A locked track, a T-joint, a joint at 45° and kept tracks give no corner."""
    design = corner(MM // 4)
    pads = board_pads(design)
    assert design.board is not None
    locked = tuple(dataclasses.replace(t, locked=t.id == T1) for t in design.board.tracks)
    assert (
        find_corners(
            dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=locked)), pads=pads
        )[0]
        == ()
    )
    assert find_corners(design, pads=pads, keep={T2})[0] == ()
    assert find_corners(design, pads=pads, nets={"OTHER"})[0] == ()
    tee = TieBoard(clearance=CLEARANCE)
    for name, end in (("a", _p(10, 10)), ("b", _p(20, 20)), ("c", _p(30, 10))):
        tee.track(name, "SIG", _p(20, 10), end)
    built = tee.build()
    assert find_corners(built, pads=board_pads(built))[0] == ()
    slant = TieBoard(clearance=CLEARANCE)
    slant.track("a", "SIG", _p(10, 10), _p(20, 10))
    slant.track("b", "SIG", _p(20, 10), _p(30, 20))
    built = slant.build()
    assert find_corners(built, pads=board_pads(built))[0] == ()


def _tee(*, split: bool) -> Design:
    """``SIG``: ``U1-1`` at (10, 10) mm, ``U2-1`` at (30, 10) mm (at (26, 10) mm when ``split``) and
    ``U3-1`` at (20, 20) mm; a bar along y 10 mm, in one track or split at (20, 10) mm, and a stem from
    ``U3-1`` that ends on it."""
    board = TieBoard(clearance=CLEARANCE)
    right = _p(26, 10) if split else _p(30, 10)
    board.place("U1", ONE, _p(10, 10), nets={"1": "SIG"})
    board.place("U2", ONE, right, nets={"1": "SIG"})
    board.place("U3", ONE, _p(20, 20), nets={"1": "SIG"})
    if split:
        board.track("a", "SIG", _p(10, 10), _p(20, 10))
        board.track("b", "SIG", _p(20, 10), right)
    else:
        board.track("a", "SIG", _p(10, 10), right)
    board.track("stem", "SIG", _p(20, 20), _p(20, 10))
    return board.build()


def test_a_tee_becomes_a_45_degree_entry() -> None:
    """Scenario "A T-joint": the stem ends on the middle of the bar; on a tie the entry goes to +x."""
    design = _tee(split=False)
    result = chamfer(design, pads=board_pads(design), check=check)
    tracks = _tracks(result.design)
    (edit,) = result.edits
    assert (edit.step, edit.reason, edit.at, edit.replaced, edit.removed) == (
        "chamfer",
        "t-joint",
        _p(20, 10),
        (T2,),
        (),
    )
    assert (tracks[T2].start, tracks[T2].end) == (_p(20, 20), _p(20, 10.5))
    assert tracks[T1].start == _p(10, 10) and tracks[T1].end == _p(30, 10)
    (diagonal,) = (tracks[ident] for ident in edit.added)
    assert (diagonal.start, diagonal.end) == (_p(20, 10.5), _p(20.5, 10))
    assert _groups(result.design) == _groups(design) and check(result.design) == []
    assert result.issues == ()


def test_a_tee_of_a_split_bar_enters_on_the_longer_side() -> None:
    design = _tee(split=True)
    (joint,) = find_joints(design, pads=board_pads(design))[0]
    assert isinstance(joint, Tee) and joint.diagonal.end == _p(19.5, 10)
    result = chamfer(design, pads=board_pads(design), check=check, leg=MM)
    (edit,) = result.edits
    assert edit.reason == "t-joint" and edit.replaced == (T3,)
    (diagonal,) = (_tracks(result.design)[ident] for ident in edit.added)
    assert (diagonal.start, diagonal.end) == (_p(20, 11), _p(19, 10))
    assert _groups(result.design) == _groups(design) and check(result.design) == []


def test_a_tee_with_a_locked_stem_or_a_via_stays() -> None:
    design = _tee(split=False)
    assert design.board is not None
    pads = board_pads(design)
    assert find_joints(design, pads=pads, keep={T2})[0] == ()
    locked = tuple(dataclasses.replace(t, locked=t.id == T2) for t in design.board.tracks)
    held = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=locked))
    assert find_joints(held, pads=pads)[0] == ()
    via = _via(1, design.circuit.nets[0].id, _p(20, 10))
    held = dataclasses.replace(design, board=dataclasses.replace(design.board, vias=(via,)))
    assert find_joints(held, pads=board_pads(held))[0] == ()


def _zoned(*, pad: bool) -> Design:
    """A zone of ``GND`` over (30, 20)-(50, 36) mm on ``F.Cu``, filled, joining ``G2-1``; with ``pad``,
    ``G1-1`` of ``GND`` at (29.8, 19.8) mm, which meets the zone only inside the cut of its corner."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("G2", ONE, _p(40, 28), nets={"1": "GND"})
    if pad:
        board.place("G1", ONE, _p(29.8, 19.8), nets={"1": "GND"})
    design = board.build()
    assert design.board is not None
    zone = _zone(1, board.net("GND"), _box(30, 20, 50, 36))
    return dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(zone,)))


def _with_zone(design: Design, **changes: object) -> Design:
    assert design.board is not None
    (zone,) = design.board.zones
    changed = dataclasses.replace(zone, **changes)  # type: ignore[arg-type]
    return dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(changed,)))


def test_a_zone_corner() -> None:
    """Scenario "A zone corner": three corners are cut by 1 mm, the one with ``G1-1`` stays."""
    design = _zoned(pad=True)
    assert chamfer(design, pads=board_pads(design), check=check).design == design
    result = chamfer(design, pads=board_pads(design), check=check, zones=True)
    assert result.design.board is not None
    (zone,) = result.design.board.zones
    assert zone.outline == (
        _p(30, 20),
        _p(49, 20),
        _p(50, 21),
        _p(50, 35),
        _p(49, 36),
        _p(31, 36),
        _p(30, 35),
    )
    assert zone.fills == () and zone.filled is False
    assert [(edit.reason, edit.layer, edit.at, edit.replaced) for edit in result.edits] == [
        ("zone-corner", "", _p(50, 20), (zone.id,)),
        ("zone-corner", "", _p(50, 36), (zone.id,)),
        ("zone-corner", "", _p(30, 36), (zone.id,)),
    ]
    (found,) = result.issues
    assert found.code == "tidy.chamfer-undone" and found.where == zone.id


def test_zone_corners_left_alone() -> None:
    """A locked zone and a zone of another net are not cut, nor is a reflex corner; ``leg`` sets the
    cut."""
    design = _zoned(pad=False)
    locked = _with_zone(design, locked=True)
    assert cut_zones(locked, pads=board_pads(locked))[1] == ()
    assert cut_zones(design, pads=board_pads(design), nets={"SIG"})[1] == ()
    notch = (_p(30, 20), _p(50, 20), _p(50, 36), _p(40, 36), _p(40, 30), _p(30, 30))
    shaped = _with_zone(design, outline=notch)
    _, edits, _ = cut_zones(shaped, pads=board_pads(shaped), leg=MM // 2)
    assert [edit.at for edit in edits] == [_p(30, 20), _p(50, 20), _p(50, 36), _p(40, 36), _p(30, 30)]
