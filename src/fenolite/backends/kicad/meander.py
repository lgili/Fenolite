# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Meanders: a square-wave detour on one straight segment of a script track, up to a target length
(capability manual-copper, "Meanders from intents"; user guide ``docs/copper.md``, "Meanders").

``resolve_meanders`` runs right after ``copper.resolve_copper`` on the same design. It finds the copper of
a track intent by its copper uuids (``seg[i]``, ``arc[i]``, ``via[i]``), measures it as KiCad of the
target major counts it, and replaces the track ``seg[segment]`` by tracks that add the missing length:
``N`` bumps of height ``E / 2N`` on one side of the run, every corner square. The new tracks carry
``copper_uuid(key, "m[k]")``, so a rebuild keeps, regenerates and drops them as script copper.

The resolver does not avoid other copper; the copper guard of the build judges what it wrote.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt
from types import MappingProxyType
from typing import Protocol

from fenolite.backends.kicad import lengths
from fenolite.backends.kicad.copper import copper_uuid, is_copper_uuid
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.stackup import copper_names
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, format_length
from fenolite.geometry import arc_length, segment_length
from fenolite.model.board import Arc, Board, Track, Via
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-NETLEN-MEANDER",))
LENGTH_TOLERANCE_NM = 10
"""How far the length of a meandered intent may lie from its target."""
CORRECTIONS = 2
"""How many times the last bump is adjusted after the first shape."""
_BITS = 64
SIDES = ("left", "right")

MEANDER_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.meander.bad-intent": "error",
        "kicad.meander.bad-shape": "error",
        "kicad.meander.too-long": "error",
        "kicad.meander.no-room": "error",
        "kicad.meander.bad-match": "error",
        "kicad.meander.inexact": "error",
        "kicad.meander.no-segment": "warning",
        "kicad.meander.not-needed": "info",
    }
)
"""The closed table of the codes this module gives."""


class MeanderIntentLike(Protocol):
    """A meander intent as the resolver reads it, by attribute (``fenolite.dsl.MeanderIntent``)."""

    @property
    def key(self) -> str: ...
    @property
    def track(self) -> str: ...
    @property
    def segment(self) -> int: ...
    @property
    def amplitude(self) -> Nm: ...
    @property
    def pitch(self) -> Nm: ...
    @property
    def target(self) -> Nm | None: ...
    @property
    def match(self) -> str | None: ...
    @property
    def side(self) -> str: ...
    @property
    def margin(self) -> Nm | None: ...


class _Refused(Exception):
    def __init__(self, code: str, message: str, key: str, hint: str = "") -> None:
        super().__init__(message)
        self.issue = Issue(code, MEANDER_ISSUE_CODES[code], message, where=key, hint=hint)


def _mm(value: int) -> str:
    return format_length(value)[:-2] + " mm"


def _native(item: Track | Arc | Via) -> str:
    return item.native_ids.get("kicad", "")


@dataclass(slots=True)
class _State:
    """The board while meanders are resolved: its tracks in order, and every copper item by uuid."""

    design: Design
    board: Board
    major: int
    tracks: list[Track]
    by_uuid: dict[str, Track | Arc | Via]
    bound: int
    depths: Mapping[str, Nm]
    copper: tuple[str, ...]

    def items(self, key: str, meanders: Sequence[str]) -> list[Track | Arc | Via]:
        """The copper of the track intent ``key``: its segments, arcs and vias, and the tracks of the
        meanders already resolved on it."""
        found: list[Track | Arc | Via] = []
        for index in range(self.bound):
            for kind in ("seg", "arc", "via"):
                item = self.by_uuid.get(copper_uuid(key, f"{kind}[{index}]"))
                if item is not None:
                    found.append(item)
        for name in meanders:
            for index in range(self.bound):
                item = self.by_uuid.get(copper_uuid(name, f"m[{index}]"))
                if item is None:
                    break
                found.append(item)
        return found

    def length(self, items: Sequence[Track | Arc | Via]) -> int:
        """The length of an intent as KiCad of the target major counts its copper alone: tracks, arcs, the
        height of each via between the layers of the intent's own segments that end in it, and the die
        lengths of the pads at its two ends."""
        total = 0
        ends: dict[Point, set[str]] = {}
        linear = [item for item in items if not isinstance(item, Via)]
        for item in linear:
            if isinstance(item, Arc):
                total += arc_length(item.start, item.mid, item.end)
            else:
                total += segment_length(item.start, item.end)
            ends.setdefault(item.start, set()).add(item.layer)
            ends.setdefault(item.end, set()).add(item.layer)
        for item in items:
            if isinstance(item, Via):
                joined = ends.get(item.position, set())
                total += lengths.via_height(item, joined, self.depths, self.copper, major=self.major)
        return total + self._die(linear)

    def _die(self, linear: Sequence[Track | Arc]) -> int:
        die = lengths.die_lengths(self.design)
        if not die or not linear:
            return 0
        count: dict[Point, int] = {}
        for item in linear:
            for point in (item.start, item.end):
                count[point] = count.get(point, 0) + 1
        loose = {point for point, times in count.items() if times == 1}
        net = linear[0].net_id
        return sum(
            die.get(pad.pad_id, 0)
            for pad in board_pads(self.design)
            if pad.net_id == net and pad.position in loose
        )


def _state(design: Design, board: Board, major: int) -> _State:
    by_uuid: dict[str, Track | Arc | Via] = {}
    for item in (*board.tracks, *board.arcs, *board.vias):
        native = _native(item)
        if is_copper_uuid(native):
            by_uuid[native] = item
    depths, _ = lengths.layer_depths(board, major=major)
    return _State(
        design,
        board,
        major,
        list(board.tracks),
        by_uuid,
        len(by_uuid) + 2,
        depths,
        copper_names(board.layers),
    )


# --- the shape --------------------------------------------------------------------------------------


def _round(value: Fraction) -> int:
    floor = value.numerator // value.denominator
    rest = value - floor
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and floor % 2):
        return floor + 1
    return floor


def _shape(
    start: Point, end: Point, side: str, margin: int, pitch: int, heights: Sequence[Fraction]
) -> list[Point]:
    """The points of the meander from ``start`` to ``end``: for bump ``i``, the run at ``margin + 2i·pitch``,
    the same point raised by its height, the raised point one pitch on, and the run there. The unit vectors
    are taken with ``_BITS`` fractional bits and each coordinate is rounded half to even once."""
    dx, dy = end.x - start.x, end.y - start.y
    norm = isqrt((dx * dx + dy * dy) << (2 * _BITS))  # |PQ| with _BITS fractional bits
    one = 1 << _BITS
    nx, ny = (dy, -dx) if side == "left" else (-dy, dx)

    def at(along: Fraction | int, up: Fraction | int) -> Point:
        x = Fraction(start.x) + (Fraction(along) * dx + Fraction(up) * nx) * one / norm
        y = Fraction(start.y) + (Fraction(along) * dy + Fraction(up) * ny) * one / norm
        return Point(_round(x), _round(y))

    points = [start]
    for index, height in enumerate(heights):
        first, second = margin + 2 * index * pitch, margin + (2 * index + 1) * pitch
        points += [at(first, 0), at(first, height), at(second, height), at(second, 0)]
    points.append(end)
    return [point for index, point in enumerate(points) if index == 0 or point != points[index - 1]]


def _tracks(key: str, replaced: Track, points: Sequence[Point]) -> list[Track]:
    made: list[Track] = []
    for index, (a, b) in enumerate(zip(points, points[1:], strict=False)):
        native = copper_uuid(key, f"m[{index}]")
        made.append(
            Track(
                id=derived_id("trk", "kicad", native),
                native_ids={"kicad": native},
                start=a,
                end=b,
                width=replaced.width,
                layer=replaced.layer,
                net_id=replaced.net_id,
                locked=replaced.locked,
            )
        )
    return made


# --- one meander ------------------------------------------------------------------------------------


def _checked(intent: MeanderIntentLike) -> tuple[str, str, int, int, int, int]:
    """Key, track, segment, amplitude, pitch and margin of a well-formed intent."""
    key = getattr(intent, "key", None)
    name = key if isinstance(key, str) and key else "?"
    track, segment = getattr(intent, "track", None), getattr(intent, "segment", None)
    amplitude, pitch = getattr(intent, "amplitude", None), getattr(intent, "pitch", None)
    margin = getattr(intent, "margin", None)
    problems: list[str] = []
    if not isinstance(key, str) or not key:
        problems.append("its key is not a text")
    if not isinstance(track, str) or not track:
        problems.append("its track is not a key")
    if type(segment) is not int or segment < 0:
        problems.append(f"its segment {segment!r} is not an index")
    for what, value in (("amplitude", amplitude), ("pitch", pitch)):
        if type(value) is not int or value <= 0:
            problems.append(f"its {what} is not a positive length")
    if margin is not None and (type(margin) is not int or margin < 0):
        problems.append("its margin is negative")
    if getattr(intent, "side", None) not in SIDES:
        problems.append(f"its side {getattr(intent, 'side', None)!r} is not 'left' or 'right'")
    target, match = getattr(intent, "target", None), getattr(intent, "match", None)
    if (target is None) == (match is None):
        problems.append("it needs either a target or a match")
    elif target is not None and (type(target) is not int or target <= 0):
        problems.append("its target is not a positive length")
    elif match is not None and (not isinstance(match, str) or match == track):
        problems.append("its match is not the key of another track")
    if problems:
        raise _Refused("kicad.meander.bad-intent", f"{name}: {'; '.join(problems)}", name)
    assert isinstance(key, str) and isinstance(track, str)
    assert type(segment) is int and type(amplitude) is int and type(pitch) is int
    return key, track, segment, amplitude, pitch, pitch if margin is None else margin


def _resolve(state: _State, intent: MeanderIntentLike, done: Mapping[str, list[str]]) -> bool:
    """Resolve one meander on ``state``; true when it changed copper."""
    key, track, segment, amplitude, pitch, margin = _checked(intent)
    replaced = state.by_uuid.get(copper_uuid(track, f"seg[{segment}]"))
    if not isinstance(replaced, Track):
        if copper_uuid(track, f"arc[{segment + 1}]") in state.by_uuid:
            raise _Refused(
                "kicad.meander.bad-intent",
                f"{key}: segment {segment} of track {track} is an arc; a meander needs a straight segment",
                key,
            )
        raise _Refused(
            "kicad.meander.no-segment",
            f"{key}: track {track} created no segment {segment}, so the meander creates nothing",
            key,
            "check the issues of that track, or place the part its end waits for",
        )
    own = state.items(track, done.get(track, ()))
    length = state.length(own)
    target = intent.target
    if target is None:
        match = intent.match or ""
        matched = state.items(match, done.get(match, ()))
        if not matched:
            raise _Refused(
                "kicad.meander.bad-match",
                f"{key}: the matched track {match} created no copper",
                key,
                "check the issues of that track",
            )
        target = state.length(matched)
    if pitch <= replaced.width:
        raise _Refused(
            "kicad.meander.bad-shape",
            f"{key}: the pitch {_mm(pitch)} is not above the track width {_mm(replaced.width)}, so "
            "neighbouring legs would touch",
            key,
            "give a pitch of at least the track width plus the clearance of its net",
        )
    extra = target - length
    if 0 <= extra <= LENGTH_TOLERANCE_NM:
        raise _Refused(
            "kicad.meander.not-needed",
            f"{key}: track {track} is {_mm(length)} long, already within {LENGTH_TOLERANCE_NM} nm of the "
            f"target {_mm(target)}",
            key,
        )
    if extra < 0:
        raise _Refused(
            "kicad.meander.too-long",
            f"{key}: track {track} is {_mm(length)} long, already above the target {_mm(target)}",
            key,
            "shorten the track, or meander the other track of the pair",
        )
    bumps = -(-extra // (2 * amplitude))
    run2 = (replaced.end.x - replaced.start.x) ** 2 + (replaced.end.y - replaced.start.y) ** 2
    needed = (2 * bumps - 1) * pitch + 2 * margin
    if needed * needed > run2:
        run = isqrt(run2)
        most = max(((run - 2 * margin) // pitch + 1) // 2, 0) * 2 * amplitude if run >= 2 * margin else 0
        raise _Refused(
            "kicad.meander.no-room",
            f"{key}: {_mm(extra)} needed, and segment {segment} of track {track} can add at most {_mm(most)} "
            f"with amplitude {_mm(amplitude)}, pitch {_mm(pitch)} and margin {_mm(margin)}",
            key,
            "raise the amplitude, lower the pitch, or meander a longer segment",
        )
    heights = [Fraction(extra, 2 * bumps)] * bumps
    rest = [item for item in own if item is not replaced]
    for attempt in range(CORRECTIONS + 1):
        points = _shape(replaced.start, replaced.end, intent.side, margin, pitch, heights)
        made = _tracks(key, replaced, points)
        missing = target - state.length([*rest, *made])
        if abs(missing) <= LENGTH_TOLERANCE_NM:
            break
        if attempt == CORRECTIONS:
            raise _Refused(
                "kicad.meander.inexact",
                f"{key}: after {CORRECTIONS} corrections track {track} is {_mm(target - missing)} long, more "
                f"than {LENGTH_TOLERANCE_NM} nm from the target {_mm(target)}",
                key,
                "choose a segment along an axis, or a target a few nanometres away",
            )
        heights = [*heights[:-1], heights[-1] + Fraction(missing, 2)]
        if not 0 < heights[-1] <= amplitude + LENGTH_TOLERANCE_NM:
            raise _Refused(
                "kicad.meander.inexact",
                f"{key}: the correction of the last bump leaves the band of the amplitude {_mm(amplitude)}",
                key,
            )
    else:  # pragma: no cover - the loop always breaks or raises
        raise AssertionError
    at = next(index for index, item in enumerate(state.tracks) if item is replaced)
    state.tracks[at : at + 1] = made
    del state.by_uuid[_native(replaced)]
    for item in made:
        state.by_uuid[_native(item)] = item
    state.bound += len(made)
    return True


def _order(meanders: Sequence[MeanderIntentLike]) -> tuple[list[MeanderIntentLike], list[MeanderIntentLike]]:
    """The meanders in key order, a meander after every meander of the track it matches; and those whose
    matches form a cycle."""
    by_key = sorted(meanders, key=lambda item: str(getattr(item, "key", "")))
    ordered: list[MeanderIntentLike] = []
    waiting = list(by_key)
    placed: set[int] = set()
    while waiting:
        progress = False
        for item in list(waiting):
            match = getattr(item, "match", None)
            blocked = match is not None and any(
                getattr(other, "track", None) == match and id(other) not in placed and other is not item
                for other in by_key
            )
            if not blocked:
                ordered.append(item)
                placed.add(id(item))
                waiting.remove(item)
                progress = True
        if not progress:
            break
    return ordered, waiting


def resolve_meanders(
    design: Design,
    meanders: Sequence[MeanderIntentLike],
    *,
    major: int,
    issues: list[Issue] | None = None,
) -> Design:
    """``design`` with each meander of ``meanders`` in place of the track ``seg[segment]`` of its track
    intent, as resolved by ``resolve_copper`` before. A refused meander changes nothing and the others are
    still resolved; the issues are appended to ``issues`` in key order. Nothing is read or written."""
    board = design.board
    if board is None or not meanders:
        return design
    state = _state(design, board, major)
    found: list[Issue] = []
    done: dict[str, list[str]] = {}
    ordered, cyclic = _order(meanders)
    seen: set[str] = set()
    for intent in ordered:
        try:
            key = getattr(intent, "key", None)
            if isinstance(key, str) and key in seen:
                raise _Refused(
                    "kicad.meander.bad-intent", f"{key}: the key is used by an earlier meander", key
                )
            if isinstance(key, str):
                seen.add(key)
            if _resolve(state, intent, done):
                done.setdefault(intent.track, []).append(intent.key)
        except _Refused as refused:
            found.append(refused.issue)
    for intent in cyclic:
        key = str(getattr(intent, "key", "?"))
        found.append(
            _Refused(
                "kicad.meander.bad-match",
                f"{key}: the matches of the meanders form a cycle through track "
                f"{getattr(intent, 'match', '?')}",
                key,
                "give one of the meanders a target length",
            ).issue
        )
    if issues is not None:
        issues.extend(sorted(found, key=lambda issue: (issue.where, issue.code, issue.message)))
    if not done:
        return design
    return dataclasses.replace(design, board=dataclasses.replace(board, tracks=tuple(state.tracks)))


def changed(design: Design, meanders: Sequence[MeanderIntentLike]) -> int:
    """How many of ``meanders`` hold copper in ``design`` (the tracks ``m[0]`` of their keys)."""
    board = design.board
    if board is None:
        return 0
    natives = {_native(track) for track in board.tracks}
    return sum(
        1
        for intent in meanders
        if isinstance(getattr(intent, "key", None), str) and copper_uuid(intent.key, "m[0]") in natives
    )


__all__ = [
    "EVIDENCE",
    "LENGTH_TOLERANCE_NM",
    "MEANDER_ISSUE_CODES",
    "MeanderIntentLike",
    "changed",
    "resolve_meanders",
]
