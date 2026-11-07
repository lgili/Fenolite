# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rooms of a PCB document read as rule areas, and ``WithinRoom`` refused (change c0462, task 2.3;
capability imported-rules, "Altium rooms are rule areas"). Every record is authored for this test, with the
keys of the public rule file's rooms (S-0297)."""

from __future__ import annotations

import dataclasses
from fractions import Fraction
from types import SimpleNamespace
from typing import cast

from _convert import source_of, two_layer

from fenolite.backends.altium.adapter.board import _rooms  # pyright: ignore[reportPrivateUsage]
from fenolite.backends.altium.adapter.context import Context
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.adapter.layers import LayerMap
from fenolite.backends.altium.lower import ROOM_REASON
from fenolite.backends.altium.read.pcb import PcbDocument
from fenolite.backends.altium.read.rooms import LOCATOR, is_room_area, read_rooms
from fenolite.backends.altium.read.rul import read_rule_file
from fenolite.backends.altium.read.scope import Refusal, ScopeDocument, parse_scope
from fenolite.convert import convert_project
from fenolite.core.coords import Point
from fenolite.core.provenance import Provenance
from fenolite.model.board import Keepout

Fields = list[tuple[str, str]]
MIL = 25_400


def _vertex(k: int, x: str, y: str, kind: str = "0") -> Fields:
    return [
        (f"KIND{k}", kind), (f"VX{k}", x), (f"VY{k}", y), (f"CX{k}", "0mil"), (f"CY{k}", "0mil"),
        (f"SA{k}", "0.00000000000000E+0000"), (f"EA{k}", "0.00000000000000E+0000"), (f"R{k}", "0mil"),
    ]  # fmt: skip


def _record(kind: str, name: str, *pairs: tuple[str, str]) -> Fields:
    return [("RULEKIND", kind), ("NAME", name), ("ENABLED", "TRUE"), ("PRIORITY", "1"), *pairs]


def _room(name: str = "PWR", *, layer: str = "TOP", kind: str = "0", x: str = "2000mil") -> Fields:
    corners = (("0mil", "0mil"), (x, "0mil"), (x, "1000mil"), ("0mil", "1000mil"), ("0mil", "0mil"))
    vertices = [
        pair for k, (vx, vy) in enumerate(corners) for pair in _vertex(k, vx, vy, kind if k == 1 else "0")
    ]
    return _record(
        "RoomDefinition", name, ("LAYER", layer), ("SCOPE1EXPRESSION", "InComponentClass('PWR')"),
        ("SCOPE2EXPRESSION", "All"), *vertices, ("CONFINEMENTSTYLE", "ConfineIn"),
    )  # fmt: skip


CLEARANCE = _record("Clearance", "c", ("GAP", "10mil"))


def test_a_room_and_its_outline() -> None:
    (room,), issues = read_rooms([CLEARANCE, _room()])
    assert not issues
    read = (room.index, room.name, room.side, room.enabled, room.confinement)
    assert read == (1, "PWR", "F.Cu", True, "ConfineIn")
    assert room.lines and len(room.vertices) == 5
    assert (room.vertices[2].x, room.vertices[2].y) == (Fraction(20_000_000), Fraction(10_000_000))


def test_the_bottom_side_and_an_unknown_layer() -> None:
    (bottom, other), _ = read_rooms([_room(layer="BOTTOM"), _room(layer="MID1")])
    assert (bottom.side, other.side) == ("B.Cu", None)


def test_an_arc_outline_is_not_shaped() -> None:
    (room,), _ = read_rooms([_room(kind="1")])
    assert not room.lines


def test_a_key_that_does_not_parse_leaves_no_outline() -> None:
    (room,), issues = read_rooms([_room(x="far")])
    assert room.vertices == () and not room.lines
    assert [issue.code for issue in issues] == ["altium.pcb-read.bad-value"] * 2  # VX1 and VX2


def test_no_room() -> None:
    assert read_rooms([_record("Width", "w", ("MINLIMIT", "10mil"))]) == ((), [])


def test_the_records_of_a_rule_file() -> None:
    """A rule file's records hold the same keys: ``read_rooms`` takes their pairs as it takes a document's."""
    line = "|".join(f"{key}={value}" for key, value in _room("USB")).encode("latin-1")
    records = [[(k, v or "") for k, v in record.fields] for record in read_rule_file(line + b"\r\n").records]
    (room,), _ = read_rooms(records)
    assert (room.name, room.side, room.lines) == ("USB", "F.Cu", True)


def _context() -> Context:
    return Context(
        ids=Ids("altium_pcbdoc", EVIDENCE), layers=LayerMap((1, 32)), file="t.PcbDoc", sha256="0" * 64
    )


def _document(*records: Fields) -> PcbDocument:
    rules = [SimpleNamespace(fields=tuple(record)) for record in records]
    return cast(PcbDocument, SimpleNamespace(rules=rules))


def test_a_room_is_a_named_rule_area_that_restricts_nothing() -> None:
    """Scenario "A rule within a room": the design holds the rule area ``PWR``, on the room's side, its
    provenance the room's record; a room on no side or with an arc gives none."""
    ctx = _context()
    _rooms(_document(CLEARANCE, _room(), _room("MID", layer="MID1"), _room("ARC", kind="1")), ctx)
    (area,) = ctx.keepouts
    assert (area.name, area.layers) == ("PWR", ("F.Cu",))
    assert area.outline == (
        Point(0, 0),
        Point(2000 * MIL, 0),
        Point(2000 * MIL, -1000 * MIL),
        Point(0, -1000 * MIL),
    )
    assert not any((area.no_tracks, area.no_vias, area.no_pads, area.no_copper_pour, area.no_footprints))
    assert area.provenance is not None and area.provenance.locator == f"{LOCATOR}1" and is_room_area(area)


def test_within_room_is_refused() -> None:
    """A room the document holds is ``room-membership`` (letter case ignored), one it does not hold
    ``undefined``, and without the document's rooms ``document``."""
    held = ScopeDocument(rooms=("PWR",))
    for text in ("WithinRoom('PWR')", "WithinRoom('pwr')", "IsPad And WithinRoom('PWR')"):
        found = parse_scope(text, document=held)
        assert isinstance(found, Refusal) and found.reason == "room-membership", text
        assert "WithinRoom" in found
    missing = parse_scope("WithinRoom('BGA Decoupling')", document=ScopeDocument(rooms=()))
    assert isinstance(missing, Refusal) and missing.reason == "undefined"
    unknown = parse_scope("WithinRoom('PWR')", document=ScopeDocument())
    assert isinstance(unknown, Refusal) and unknown.reason == "document"


def test_the_altium_writer_writes_a_room_as_its_record() -> None:
    """A room's rule area is counted changed, not lost: the board's kept record writes it back."""
    design = two_layer()
    assert design.board is not None
    where = Provenance("altium", "t.PcbDoc", "0" * 64, f"{LOCATOR}0")
    outline = (Point(0, 0), Point(5_000_000, 0), Point(5_000_000, 5_000_000), Point(0, 5_000_000))
    room = Keepout(id="kpo-room", provenance=where, outline=outline, layers=("F.Cu",), name="PWR")
    board = dataclasses.replace(design.board, keepouts=(*design.board.keepouts, room))
    conversion = convert_project(
        source_of(dataclasses.replace(design, board=board)), to="altium", allow_lossy=True
    )
    row = next(row for row in conversion.report.rows if row.kind == "keep-out")
    assert (row.changed, row.lost) == (1, 0)
    assert any(ROOM_REASON in str(reason) for reason in row.reasons)
