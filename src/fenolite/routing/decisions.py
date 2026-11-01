# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The route decision record ``fenolite.route-decisions.v0`` (change c0280; capability cli-contract, "Route
decision record"; ``docs/routing.md``, "Proposals").

The record keeps what the user decided on the proposals of ``fenolite route --propose``: each accepted
candidate (``locked``: its subject, net, ends, the items it placed, the corridors of a group candidate, its
relaxations and the decision id) and each rejected candidate or proposal (``rejected``: its id, subject and
reason). It is canonical JSON with sorted keys, integers and no clock, so equal decisions give equal bytes.
A built project keeps it at ``.fenolite/route-decisions.json``; any other board beside it, as
``<board stem>.route-decisions.json``. A record that is not of this schema, holds an unknown key or a value
of the wrong type raises ``FormatError``, which ``fenolite route`` reports as ``FEN-3004``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fenolite.core.coords import Point
from fenolite.core.errors import FormatError

SCHEMA = "fenolite.route-decisions.v0"
FILE = ".fenolite/route-decisions.json"
"""The record of a built project, relative to the board's folder."""
SUFFIX = ".route-decisions.json"
"""The record of any other board: ``<board stem>`` and this suffix, beside the board."""


@dataclass(frozen=True, slots=True)
class RecordEnd:
    """One end of a decided subject: its kind (``pad``, ``track-end``, ``zone``), name, position (none for a
    zone) and copper layers."""

    kind: str
    name: str
    at: Point | None = None
    layers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecordTrack:
    """A placed polyline: its layer, width and points (one track per segment on the board)."""

    layer: str
    width: int
    points: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class RecordVia:
    """A placed via: its position, diameter, drill and the layers it spans."""

    at: Point
    diameter: int
    drill: int
    layers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecordCorridor:
    """A corridor of a group candidate: its rule-area name, layers and outline."""

    name: str
    layers: tuple[str, ...]
    outline: tuple[Point, ...]


RecordItem = RecordTrack | RecordVia


@dataclass(frozen=True, slots=True)
class Locked:
    """An accepted candidate."""

    candidate: str
    proposal: str
    subject: str
    net: str
    ends: tuple[RecordEnd, ...] = ()
    items: tuple[RecordItem, ...] = ()
    corridors: tuple[RecordCorridor, ...] = ()
    relaxed: tuple[str, ...] = ()
    plan: str = ""


@dataclass(frozen=True, slots=True)
class Rejected:
    """A rejected candidate (``c-…``) or proposal (``p-…``), with the user's reason (may be empty)."""

    id: str
    subject: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Decisions:
    """The decisions of one board: the board's file name, the locked and the rejected entries."""

    board: str
    locked: tuple[Locked, ...] = ()
    rejected: tuple[Rejected, ...] = ()

    def sorted(self) -> Decisions:
        """The record with its entries sorted by subject, then id, each id once (the last one kept)."""
        locked = {entry.candidate: entry for entry in self.locked}
        rejected = {entry.id: entry for entry in self.rejected}
        return Decisions(
            self.board,
            tuple(sorted(locked.values(), key=lambda e: (e.subject, e.candidate))),
            tuple(sorted(rejected.values(), key=lambda e: (e.subject, e.id))),
        )


def record_path(board: Path, *, built: bool) -> Path:
    """Where the record of ``board`` lives: in ``.fenolite/`` of a built project, else beside the board."""
    if built:
        return board.parent / FILE
    return board.with_name(board.stem + SUFFIX)


# --- writing ---------------------------------------------------------------------------------------------


def _point(point: Point) -> list[int]:
    return [point.x, point.y]


def _end(end: RecordEnd) -> dict[str, Any]:
    data: dict[str, Any] = {"kind": end.kind, "name": end.name, "layers": list(end.layers)}
    if end.at is not None:
        data["at"] = _point(end.at)
    return data


def item_data(item: RecordItem) -> dict[str, Any]:
    """The JSON form of one item, as the record and the reply's ``geometry`` spell it."""
    if isinstance(item, RecordTrack):
        return {
            "kind": "track",
            "layer": item.layer,
            "width": item.width,
            "points": [_point(p) for p in item.points],
        }
    return {
        "kind": "via",
        "at": _point(item.at),
        "diameter": item.diameter,
        "drill": item.drill,
        "layers": list(item.layers),
    }


def corridor_data(corridor: RecordCorridor) -> dict[str, Any]:
    return {
        "name": corridor.name,
        "layers": list(corridor.layers),
        "outline": [_point(p) for p in corridor.outline],
    }


def to_data(decisions: Decisions) -> dict[str, Any]:
    """The JSON value of the record, its entries sorted."""
    held = decisions.sorted()
    return {
        "schema": SCHEMA,
        "board": held.board,
        "locked": [
            {
                "candidate": e.candidate,
                "proposal": e.proposal,
                "subject": e.subject,
                "net": e.net,
                "ends": [_end(end) for end in e.ends],
                "items": [item_data(item) for item in e.items],
                "corridors": [corridor_data(c) for c in e.corridors],
                "relaxed": list(e.relaxed),
                "plan": e.plan,
            }
            for e in held.locked
        ],
        "rejected": [{"id": e.id, "subject": e.subject, "reason": e.reason} for e in held.rejected],
    }


def dumps(decisions: Decisions) -> bytes:
    """The canonical bytes of the record: sorted keys, two-space indent, a final newline, no clock."""
    text = json.dumps(to_data(decisions), sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


# --- reading ---------------------------------------------------------------------------------------------


class _Reader:
    def __init__(self, file: str) -> None:
        self.file = file

    def fail(self, message: str, where: str) -> FormatError:
        return FormatError(message, file=self.file, locator=where or "/")

    def obj(
        self, value: object, where: str, keys: Sequence[str], optional: Sequence[str] = ()
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise self.fail("expected a JSON object", where)
        held = cast(dict[str, Any], value)
        unknown = sorted(set(held) - set(keys) - set(optional))
        if unknown:
            raise self.fail(f"unexpected property {unknown[0]!r}", f"{where}/{unknown[0]}")
        missing = [key for key in keys if key not in held]
        if missing:
            raise self.fail(f"missing property {missing[0]!r}", where)
        return held

    def text(self, value: object, where: str) -> str:
        if not isinstance(value, str):
            raise self.fail("expected a string", where)
        return value

    def integer(self, value: object, where: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise self.fail("expected an integer", where)
        return value

    def items(self, value: object, where: str) -> list[Any]:
        if not isinstance(value, list):
            raise self.fail("expected a JSON array", where)
        return cast(list[Any], value)

    def point(self, value: object, where: str) -> Point:
        pair = self.items(value, where)
        if len(pair) != 2:
            raise self.fail("expected a point [x, y]", where)
        return Point(self.integer(pair[0], f"{where}/0"), self.integer(pair[1], f"{where}/1"))

    def texts(self, value: object, where: str) -> tuple[str, ...]:
        return tuple(self.text(v, f"{where}/{i}") for i, v in enumerate(self.items(value, where)))

    def points(self, value: object, where: str) -> tuple[Point, ...]:
        return tuple(self.point(v, f"{where}/{i}") for i, v in enumerate(self.items(value, where)))

    def end(self, value: object, where: str) -> RecordEnd:
        data = self.obj(value, where, ("kind", "name", "layers"), ("at",))
        at = self.point(data["at"], f"{where}/at") if "at" in data else None
        return RecordEnd(
            self.text(data["kind"], f"{where}/kind"),
            self.text(data["name"], f"{where}/name"),
            at,
            self.texts(data["layers"], f"{where}/layers"),
        )

    @staticmethod
    def _kind(value: object) -> object:
        if isinstance(value, dict):
            return cast(dict[str, Any], value).get("kind")
        return None

    def item(self, value: object, where: str) -> RecordItem:
        kind = self._kind(value)
        if kind == "via":
            data = self.obj(value, where, ("kind", "at", "diameter", "drill", "layers"))
            return RecordVia(
                self.point(data["at"], f"{where}/at"),
                self.integer(data["diameter"], f"{where}/diameter"),
                self.integer(data["drill"], f"{where}/drill"),
                self.texts(data["layers"], f"{where}/layers"),
            )
        data = self.obj(value, where, ("kind", "layer", "width", "points"))
        if data["kind"] != "track":
            raise self.fail("an item is a track or a via", f"{where}/kind")
        points = self.points(data["points"], f"{where}/points")
        if len(points) < 2:
            raise self.fail("a track has two points or more", f"{where}/points")
        return RecordTrack(
            self.text(data["layer"], f"{where}/layer"), self.integer(data["width"], f"{where}/width"), points
        )

    def corridor(self, value: object, where: str) -> RecordCorridor:
        data = self.obj(value, where, ("name", "layers", "outline"))
        return RecordCorridor(
            self.text(data["name"], f"{where}/name"),
            self.texts(data["layers"], f"{where}/layers"),
            self.points(data["outline"], f"{where}/outline"),
        )

    def locked(self, value: object, where: str) -> Locked:
        keys = ("candidate", "proposal", "subject", "net", "ends", "items", "corridors", "relaxed", "plan")
        data = self.obj(value, where, keys)
        return Locked(
            self.text(data["candidate"], f"{where}/candidate"),
            self.text(data["proposal"], f"{where}/proposal"),
            self.text(data["subject"], f"{where}/subject"),
            self.text(data["net"], f"{where}/net"),
            tuple(
                self.end(v, f"{where}/ends/{i}")
                for i, v in enumerate(self.items(data["ends"], f"{where}/ends"))
            ),
            tuple(
                self.item(v, f"{where}/items/{i}")
                for i, v in enumerate(self.items(data["items"], f"{where}/items"))
            ),
            tuple(
                self.corridor(v, f"{where}/corridors/{i}")
                for i, v in enumerate(self.items(data["corridors"], f"{where}/corridors"))
            ),
            self.texts(data["relaxed"], f"{where}/relaxed"),
            self.text(data["plan"], f"{where}/plan"),
        )

    def rejected(self, value: object, where: str) -> Rejected:
        data = self.obj(value, where, ("id", "subject", "reason"))
        return Rejected(
            self.text(data["id"], f"{where}/id"),
            self.text(data["subject"], f"{where}/subject"),
            self.text(data["reason"], f"{where}/reason"),
        )


def from_data(value: object, *, file: str = "") -> Decisions:
    """The record of a JSON value; ``FormatError`` naming the JSON pointer of the first fault."""
    reader = _Reader(file)
    data = reader.obj(value, "", ("schema", "board", "locked", "rejected"))
    if data["schema"] != SCHEMA:
        raise reader.fail(f"the schema must be {SCHEMA!r}", "/schema")
    locked = reader.items(data["locked"], "/locked")
    rejected = reader.items(data["rejected"], "/rejected")
    return Decisions(
        reader.text(data["board"], "/board"),
        tuple(reader.locked(v, f"/locked/{i}") for i, v in enumerate(locked)),
        tuple(reader.rejected(v, f"/rejected/{i}") for i, v in enumerate(rejected)),
    ).sorted()


def loads(data: bytes | str, *, file: str = "") -> Decisions:
    """The record of its bytes or text; ``FormatError`` for invalid JSON or a malformed record."""
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise FormatError(f"invalid JSON: {error.msg}", file=file, offset=error.pos) from None
    return from_data(value, file=file)


def read(path: Path, *, board: str) -> Decisions:
    """The record at ``path``, or an empty record of ``board`` when no file is there; ``FormatError`` for a
    file that cannot be read or is malformed."""
    if not path.is_file():
        return Decisions(board)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise FormatError(f"cannot be read: {error.strerror or error}", file=path.name) from None
    return loads(data, file=path.name)


def with_entries(
    decisions: Decisions,
    *,
    locked: Sequence[Locked] = (),
    rejected: Sequence[Rejected] = (),
    forget: Mapping[str, object] | Sequence[str] = (),
) -> Decisions:
    """``decisions`` with the given entries added (replacing entries of the same id) and the ids of
    ``forget`` removed, sorted."""
    gone = set(forget)
    return Decisions(
        decisions.board,
        tuple(e for e in (*decisions.locked, *locked) if e.candidate not in gone),
        tuple(e for e in (*decisions.rejected, *rejected) if e.id not in gone),
    ).sorted()


__all__ = [
    "FILE",
    "SCHEMA",
    "SUFFIX",
    "Decisions",
    "Locked",
    "RecordCorridor",
    "RecordEnd",
    "RecordItem",
    "RecordTrack",
    "RecordVia",
    "Rejected",
    "corridor_data",
    "dumps",
    "from_data",
    "item_data",
    "loads",
    "read",
    "record_path",
    "to_data",
    "with_entries",
]
