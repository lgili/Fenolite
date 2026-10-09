# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board items of a script on a KiCad board: marked uuids and the merge with an existing board
(capability kicad-file-backend, "Board items of a script are written"; layout-lens, "Board items declared
in the script"; change c0103)."""

from __future__ import annotations

import dataclasses
import hashlib
import uuid

from fenolite.backends.kicad import boarditems
from fenolite.backends.kicad.boarditems import (
    ITEM_MARKER,
    MERGE_ISSUE_CODES,
    is_item_uuid,
    item_uuid,
    mark_items,
    merge_items,
    unknown_areas,
)
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.board import Dimension, Graphic, Keepout, Text
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

MM = 1_000_000
SQUARE = (Point(0, 0), Point(10 * MM, 0), Point(10 * MM, 10 * MM), Point(0, 10 * MM))
SEEN: list[Issue] = []
"""Every issue ``merge_items`` produced in this module, for the closed-set test."""


def area(name: str, **more: object) -> Keepout:
    ident = derived_id("kpo", "dsl", f"area:{name}")
    return Keepout(id=ident, outline=SQUARE, layers=("F.Cu", "B.Cu"), name=name, **more)  # type: ignore[arg-type]


def label(key: str = "rev", **more: object) -> Text:
    fields: dict[str, object] = {
        "text": "REV A", "position": Point(2 * MM, 2 * MM), "layer": "F.SilkS", "size": Size(MM, MM),
        "thickness": 150_000, **more,
    }  # fmt: skip
    return Text(id=derived_id("txt", "dsl", f"text:{key}"), **fields)  # type: ignore[arg-type]


def line(key: str = "edge") -> Graphic:
    return Graphic(
        id=derived_id("gfx", "dsl", f"graphic:{key}"), kind="line", layer="F.Fab",
        points=(Point(0, 0), Point(5 * MM, 0)), width=100_000,
    )  # fmt: skip


def measure(key: str = "width") -> Dimension:
    return Dimension(
        id=derived_id("dim", "dsl", f"dimension:{key}"), kind="aligned", layer="Dwgs.User",
        start=Point(0, 0), end=Point(40 * MM, 0), offset=-3 * MM,
    )  # fmt: skip


def design(**collections: object) -> Design:
    made = Design.new("items", seed=1)
    assert made.board is not None
    return dataclasses.replace(made, board=dataclasses.replace(made.board, **collections))  # type: ignore[arg-type]


def merge(existing: Design, built: Design) -> boarditems.ItemMerge:
    found = merge_items(existing, built)
    SEEN.extend(found.issues)
    return found


def test_item_uuids_are_marked() -> None:
    """Scenario "Item uuids are marked"."""
    ident = derived_id("txt", "dsl", "text:rev")
    first, second = item_uuid(ident), item_uuid(ident)
    assert first == second and is_item_uuid(first)
    value = uuid.UUID(first).int
    assert value >> 80 == ITEM_MARKER == int.from_bytes(b"fenitm", "big")
    assert (value >> 76) & 0xF == 8 and (value >> 62) & 0b11 == 0b10
    digest = int.from_bytes(hashlib.sha256(f"kicad-item:{ident}".encode()).digest(), "big") >> (256 - 74)
    assert ((value >> 64) & 0xFFF) == digest >> 62 and value & ((1 << 62) - 1) == digest & ((1 << 62) - 1)
    assert not is_item_uuid(copper_uuid("led_a", "seg[0]"))
    assert not is_item_uuid(str(uuid.UUID(int=7, version=4)))
    assert not is_item_uuid(first.upper()) and not is_item_uuid("not a uuid")
    assert item_uuid(derived_id("txt", "dsl", "text:other")) != first


def test_mark_items_sets_only_the_native_ids() -> None:
    made = design(keepouts=(area("ANT"),), texts=(label(),), graphics=(line(),), dimensions=(measure(),))
    marked = mark_items(made)
    assert marked.board is not None and made.board is not None
    for name in ("keepouts", "texts", "graphics", "dimensions"):
        (before,), (after,) = getattr(made.board, name), getattr(marked.board, name)
        assert after.native_ids == {"kicad": item_uuid(before.id)} and kicad_uuid(after) == item_uuid(
            before.id
        )
        assert dataclasses.replace(after, native_ids={}) == before
    assert dataclasses.replace(marked.board, keepouts=(), texts=(), graphics=(), dimensions=()) == (
        dataclasses.replace(made.board, keepouts=(), texts=(), graphics=(), dimensions=())
    )
    assert mark_items(design()) == design()


def test_merge_keeps_what_was_drawn_in_kicad() -> None:
    drawn = dataclasses.replace(label("hand"), native_ids={"kicad": str(uuid.UUID(int=9, version=4))})
    plain = dataclasses.replace(area("HAND"), native_ids={})
    existing = design(keepouts=(plain,), texts=(drawn,))
    built = mark_items(design(texts=(label(),)))
    found = merge(existing, built)
    assert found.texts == (drawn,) and found.keepouts == (plain,)
    assert (found.regenerated, found.stale, found.issues) == (0, 0, ())


def test_merge_regenerates_and_reports_an_edit() -> None:
    built = mark_items(design(keepouts=(area("ANT", no_tracks=True),), texts=(label(),),
                              graphics=(line(),), dimensions=(measure(),)))  # fmt: skip
    assert built.board is not None
    same = merge(built, built)
    assert (same.keepouts, same.texts, same.graphics, same.dimensions) == ((), (), (), ())
    assert (same.regenerated, same.stale, same.issues) == (0, 0, ())
    (text,) = built.board.texts
    moved = dataclasses.replace(text, position=Point(3 * MM, 2 * MM), h_justify="left")
    (zone,) = built.board.keepouts
    opened = dataclasses.replace(zone, no_tracks=False, name="ANT2")
    (dimension,) = built.board.dimensions
    longer = dataclasses.replace(dimension, end=Point(41 * MM, 0), size=Size(2 * MM, 2 * MM))
    edited = dataclasses.replace(
        built,
        board=dataclasses.replace(built.board, texts=(moved,), keepouts=(opened,), dimensions=(longer,)),
    )
    found = merge(edited, built)
    assert found.regenerated == 3 and found.stale == 0 and found.texts == ()
    by_where = {i.where: i for i in found.issues}
    note = by_where[item_uuid(text.id)]
    assert (note.code, note.severity) == ("kicad.board-item.regenerated", "info")
    assert "text" in note.message and "position" in note.message and "justification" in note.message
    assert "name, settings" in by_where[item_uuid(zone.id)].message
    assert by_where[item_uuid(dimension.id)].message.endswith(": points")  # size is not compared


def test_merge_drops_a_stale_item() -> None:
    old = mark_items(design(keepouts=(area("ANT"), area("HV")), graphics=(line(),)))
    new = mark_items(design(keepouts=(area("ANT"),)))
    found = merge(old, new)
    assert found.stale == 2 and found.keepouts == () and found.graphics == ()
    stale = sorted(i.message for i in found.issues)
    assert all(i.code == "kicad.board-item.stale" and i.severity == "warning" for i in found.issues)
    assert "graphic" in stale[0] and "F.Fab" in stale[0]
    assert "rule area" in stale[1] and "HV" in stale[1]
    assert merge(design(), new) == boarditems.ItemMerge()


def test_closed_set_of_merge_codes() -> None:
    """Scenario "Board item merge codes are closed" (after the tests above in this module)."""
    assert dict(MERGE_ISSUE_CODES) == {
        "kicad.board-item.stale": "warning",
        "kicad.board-item.regenerated": "info",
    }
    assert {i.code for i in SEEN} == set(MERGE_ISSUE_CODES)
    assert all(MERGE_ISSUE_CODES[i.code] == i.severity for i in SEEN)


def test_unknown_areas() -> None:
    def rule(name: str, a: Selector, b: Selector | None = None) -> Rule:
        return Rule(id=derived_id("rul", "dsl", f"rule:named:{name}"), name=name, kind="clearance",
                    selector_a=a, selector_b=b, min=MM)  # fmt: skip

    leaf = Selector("area", "HV")
    rules = (
        rule("exact", leaf),
        rule("glob", Selector("and", items=(Selector("area", "H*"), Selector("item_kind", "track")))),
        rule("case", Selector("area", "hv")),
        rule("both", Selector("net", "A"), Selector("not", items=(Selector("area", "NOPE"),))),
        rule("twice", Selector("or", items=(Selector("area", "X"), Selector("area", "X")))),
    )
    made = dataclasses.replace(
        design(keepouts=(area("HV"), dataclasses.replace(area("ANT"), name=""))),
        rules=RuleSet(id=derived_id("rst", "dsl", "rules"), rules=rules),
    )
    assert unknown_areas(made) == (("case", "hv"), ("both", "NOPE"), ("twice", "X"))
    assert unknown_areas(design()) == ()
