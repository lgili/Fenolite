# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Same-version rebuild and round-trip verdict of schematics (capability kicad-schematic: "Same-version
rebuild of schematics" and "Schematic round-trip verdict"; change c0060)."""

from __future__ import annotations

import dataclasses
import hashlib
from collections import Counter

import _schfix as fx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import Node, first_difference, parse, tree_equal
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.ids import derived_id
from fenolite.model.schematic import NoConnectFlag, SchematicSheet, SymbolInstance

FLAT = sch.read_schematic(fx.SCHEMATICS / "flat.kicad_sch")
FLAT_TREE = fx.tree_of("flat.kicad_sch")
GRID = 1_270_000


def replace_symbol(sheet: SchematicSheet, which: str, /, **changes: object) -> SchematicSheet:
    symbols = tuple(dataclasses.replace(s, **changes) if s.ref == which else s for s in sheet.symbols)  # type: ignore[arg-type]
    return dataclasses.replace(sheet, symbols=symbols)


def symbol_node(root: Node, ref: str) -> Node:
    return next(c for c in root.nodes("symbol") if fx.reference(c) == ref)


def by_ref(sheet: SchematicSheet, ref: str) -> SymbolInstance:
    return next(s for s in sheet.symbols if s.ref == ref)


# -- "Same-version rebuild of schematics"


@pytest.mark.parametrize("name", fx.FIXTURES)
def test_unchanged_sheet(name: str) -> None:
    text = fx.text_of(name)
    rebuilt = sch.rebuild_schematic(sch.read_schematic(text, file=name))
    original = parse(text)
    assert tree_equal(rebuilt, original), first_difference(rebuilt, original)


def test_moved_symbol() -> None:
    r1 = by_ref(FLAT, "R1")
    moved = replace_symbol(FLAT, "R1", position=Point(r1.position.x + 2_540_000, r1.position.y))
    rebuilt = sch.rebuild_schematic(moved)
    at = symbol_node(rebuilt, "R1").find("at")
    assert at is not None and [a.text for a in at.atoms()] == ["102.54", "50", "0"]
    undone = fx.edit_symbol(rebuilt, "R1", lambda kids: fx.set_child(kids, fx.fragment("(at 100 50 0)")))
    assert tree_equal(undone, FLAT_TREE)


def test_order_of_a_collection_does_not_matter() -> None:
    shuffled = dataclasses.replace(
        FLAT, symbols=tuple(reversed(FLAT.symbols)), labels=tuple(reversed(FLAT.labels))
    )
    assert tree_equal(sch.rebuild_schematic(shuffled), FLAT_TREE)


def test_changed_flags_and_unit_are_emitted() -> None:
    changed = replace_symbol(FLAT, "R1", dnp=True, on_board=False, unit=2, body_style=2)
    node = symbol_node(sch.rebuild_schematic(changed), "R1")
    assert [node.find(h).atoms()[0].text for h in ("dnp", "on_board", "unit", "body_style")] == [  # type: ignore[union-attr]
        "yes", "no", "2", "2",
    ]  # fmt: skip


def test_new_mirror_child_takes_its_canonical_place() -> None:
    node = symbol_node(sch.rebuild_schematic(replace_symbol(FLAT, "D1", mirror="x")), "D1")
    assert fx.heads(node.children)[:4] == ["lib_id", "at", "mirror", "unit"]
    again = sch.read_schematic(fx.text(sch.rebuild_schematic(replace_symbol(FLAT, "D1", mirror="x"))))
    assert by_ref(again, "D1").mirror == "x"


def test_moved_label_flag_and_sheet() -> None:
    label = FLAT.labels[0]
    flag = FLAT.no_connects[0]
    changed = dataclasses.replace(
        FLAT,
        labels=(dataclasses.replace(label, position=Point(0, GRID), rotation=180_000_000), *FLAT.labels[1:]),
        no_connects=(dataclasses.replace(flag, position=Point(GRID, GRID)), *FLAT.no_connects[1:]),
    )
    again = sch.read_schematic(fx.text(sch.rebuild_schematic(changed)))
    assert again.labels[0].position == Point(0, GRID) and again.labels[0].rotation == 180_000_000
    assert again.no_connects[0].position == Point(GRID, GRID)
    top = sch.read_schematic(fx.SCHEMATICS / "hier" / "top.kicad_sch")
    moved = dataclasses.replace(top, sheets=(dataclasses.replace(top.sheets[0], position=Point(GRID, 0)),))
    assert sch.read_schematic(fx.text(sch.rebuild_schematic(moved))).sheets[0].position == Point(GRID, 0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("value", "470"),
        ("ref", "R9"),
        ("footprint", "Mini:Other"),
        ("properties", {"Value": "1"}),
        ("uses", ()),
    ],
)
def test_edited_projection_refused(field: str, value: object) -> None:
    r1 = by_ref(FLAT, "R1")
    with pytest.raises(ValueError) as caught:
        sch.rebuild_schematic(replace_symbol(FLAT, "R1", **{field: value}))
    assert r1.id in str(caught.value) and repr(field) in str(caught.value)


def test_edited_sheet_projection_refused() -> None:
    top = sch.read_schematic(fx.SCHEMATICS / "hier" / "top.kicad_sch")
    ref = top.sheets[0]
    for field in ("name", "file"):
        changed = dataclasses.replace(top, sheets=(dataclasses.replace(ref, **{field: "other"}),))
        with pytest.raises(ValueError, match=field) as caught:
            sch.rebuild_schematic(changed)
        assert ref.id in str(caught.value)


def test_edited_title_and_embedded_symbol_refused() -> None:
    assert FLAT.title_block is not None
    with pytest.raises(ValueError, match="pins"):
        first = dataclasses.replace(FLAT.lib_symbols[0], pins=())
        sch.rebuild_schematic(dataclasses.replace(FLAT, lib_symbols=(first, *FLAT.lib_symbols[1:])))
    changed = dataclasses.replace(FLAT, title_block=dataclasses.replace(FLAT.title_block, title="Other"))
    again = sch.read_schematic(fx.text(sch.rebuild_schematic(changed)))
    assert again.title_block is not None and again.title_block.title == "Other"


def test_child_kept_as_written_cannot_change() -> None:
    root = fx.edit_symbol(
        fx.with_version(fx.tree_of("flat_v9.kicad_sch"), 20231120),
        "R1",
        lambda kids: kids.insert(3, fx.fragment("(convert 1)")),
    )
    sheet = sch.read_schematic(fx.text(root))
    with pytest.raises(ValueError, match="body_style"):
        sch.rebuild_schematic(replace_symbol(sheet, "R1", body_style=2))


def test_added_and_removed_entities_refused() -> None:
    with pytest.raises(ValueError, match="'symbols'"):
        sch.rebuild_schematic(dataclasses.replace(FLAT, symbols=FLAT.symbols[1:]))
    extra = NoConnectFlag(Point(0, 0), id=derived_id("ncf", "fenolite", "t:new"))
    with pytest.raises(ValueError, match="'no_connects'"):
        sch.rebuild_schematic(dataclasses.replace(FLAT, no_connects=(*FLAT.no_connects, extra)))
    with pytest.raises(ValueError, match="'labels'"):
        sch.rebuild_schematic(dataclasses.replace(FLAT, labels=FLAT.labels[:-1]))


def test_created_sheet_is_refused() -> None:
    created = SchematicSheet(id=derived_id("sch", "fenolite", "t"), name="t")
    with pytest.raises(ValueError, match="created sheets"):
        sch.rebuild_schematic(created)


@settings(max_examples=40, deadline=None)
@given(
    index=st.integers(0, len(FLAT.symbols) - 1),
    dx=st.integers(-200, 200),
    dy=st.integers(-200, 200),
    rotation=st.sampled_from([0, 90_000_000, 180_000_000, 270_000_000]),
    mirror=st.sampled_from(["", "x", "y"]),
)
def test_move_rotate_mirror_round_trips(index: int, dx: int, dy: int, rotation: int, mirror: str) -> None:
    target = FLAT.symbols[index]
    position = Point(target.position.x + dx * GRID, target.position.y + dy * GRID)
    symbols = tuple(
        dataclasses.replace(s, position=position, rotation=rotation, mirror=mirror) if s is target else s  # type: ignore[arg-type]
        for s in FLAT.symbols
    )
    rebuilt = sch.rebuild_schematic(dataclasses.replace(FLAT, symbols=symbols))
    again = sch.read_schematic(rebuilt, file="flat.kicad_sch")
    moved = again.symbols[index]
    assert (moved.position, moved.rotation, moved.mirror) == (position, rotation, mirror)
    assert moved.id == target.id and moved.properties == target.properties and moved.uses == target.uses
    others = [dataclasses.replace(s, provenance=None) for i, s in enumerate(again.symbols) if i != index]
    assert others == [
        dataclasses.replace(s, provenance=None) for i, s in enumerate(FLAT.symbols) if i != index
    ]
    assert sch.opaque_digests(again) == sch.opaque_digests(FLAT)


# -- "Schematic round-trip verdict"


@pytest.mark.parametrize("name", fx.FIXTURES)
def test_roundtrip_of_every_fixture(name: str) -> None:
    text = fx.text_of(name)
    verdict = sch.roundtrip_schematic(text, file=name)
    assert verdict.level == "RT1" and verdict.passed and verdict.difference == ""
    assert verdict.tree_equal and verdict.model_equal and verdict.opaque_equal
    assert verdict.opaque_count == sch.opaque_count(sch.read_schematic(text)) > 0


def test_roundtrip_counts_bus_content() -> None:
    text = fx.text_of("bus.kicad_sch")
    assert sch.roundtrip_schematic(text).passed
    sheet = sch.read_schematic(text)
    digests = sch.opaque_digests(sheet)
    assert isinstance(digests, Counter) and sum(digests.values()) == sch.opaque_count(sheet)
    root = parse(text)
    for head in ("bus", "bus_entry"):
        for child in root.nodes(head):
            compact = fx.fragment(fx.text(child))
            from fenolite.backends.kicad.sexpr import dumps

            digest = hashlib.sha256(dumps(compact, style="compact").encode("utf-8")).hexdigest()
            assert digests[digest] >= 1


def test_roundtrip_count_follows_the_slots() -> None:
    wire = fx.fragment(
        '(wire (pts (xy 1.27 1.27) (xy 2.54 1.27)) (stroke (width 0) (type default)) (uuid "0"))'
    )
    more = fx.edit_root(FLAT_TREE, lambda kids: kids.append(wire))
    assert sch.opaque_count(sch.read_schematic(fx.text(more))) == sch.opaque_count(FLAT) + 1


def test_roundtrip_read_error_propagates() -> None:
    with pytest.raises(FormatError):
        sch.roundtrip_schematic("(kicad_sch (version 20260306) (symbol (at a b 0)))")
    with pytest.raises(FormatError):
        sch.roundtrip_schematic("(kicad_pcb (version 20241229))")


def test_roundtrip_reports_a_tree_difference(monkeypatch: pytest.MonkeyPatch) -> None:
    real = sch.rebuild_schematic

    def broken(sheet: SchematicSheet) -> Node:
        root = real(sheet)
        return root.with_children(root.children[:-1])

    monkeypatch.setattr(sch, "rebuild_schematic", broken)
    verdict = sch.roundtrip_schematic(fx.text_of("flat.kicad_sch"))
    assert not verdict.passed and not verdict.tree_equal and verdict.difference.startswith("/kicad_sch")
