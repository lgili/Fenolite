# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint fields written from the model (kicad-file-backend, "Footprint fields are written"; c0030)."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from _boards import FIXTURE, created_board, uid

from fenolite.backends.kicad.pcb import CANONICAL_ORDER, FLOOR_HEADS, read_board, write_board
from fenolite.backends.kicad.sexpr import Node, load, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.design import Design

DEG = 1_000_000
VALUES = (
    "name",
    "position",
    "layer",
    "size",
    "rotation",
    "thickness",
    "visible",
    "h_justify",
    "v_justify",
    "mirrored",
)


def footprint_of(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    target = design.by_ref[ref].id
    return next(fp for fp in design.board.footprints if fp.component_id == target)


def field_of(design: Design, ref: str, name: str) -> FootprintField:
    return next(f for f in footprint_of(design, ref).fields if f.name == name)


def values(field: FootprintField) -> tuple[Any, ...]:
    return tuple(getattr(field, name) for name in VALUES)


def edited(design: Design, ref: str, name: str, **changes: Any) -> Design:
    return design.replace_entity(dataclasses.replace(field_of(design, ref, name), **changes))


def property_nodes(root: Node) -> dict[tuple[str, str], Node]:
    """``(reference, property name) → node`` for every footprint of a board tree."""
    found: dict[tuple[str, str], Node] = {}
    for footprint in root.nodes("footprint"):
        nodes = footprint.nodes("property")
        ref = next(n.atoms()[1].value for n in nodes if n.atoms()[0].value == "Reference")
        for node in nodes:
            found[(ref, node.atoms()[0].value)] = node
    return found


def with_child(node: Node, head: str, new: Node) -> Node:
    return node.with_children([new if isinstance(c, Node) and c.name == head else c for c in node.children])


def source_text(replacements: dict[str, str]) -> str:
    text = FIXTURE.read_text(encoding="utf-8")
    for old, new in replacements.items():
        assert text.count(old) >= 1, old
        text = text.replace(old, new, 1)
    return text


def read_only(design: Design, target: int = 9) -> list[str]:
    with pytest.raises(LossyWriteError) as info:
        write_board(design, target=target)
    assert info.value.droppable is False
    assert {i.code for i in info.value.issues} == {"kicad.board.projection-read-only"}
    return [i.message for i in info.value.issues]


def test_canonical_order_of_a_property() -> None:
    assert CANONICAL_ORDER["property"] == ("name", "value", "at", "layer", "hide", "uuid", "effects")
    assert "hide" in FLOOR_HEADS


@pytest.mark.parametrize("target", [9, 10])
def test_unchanged_fields(target: int) -> None:
    result = write_board(read_board(FIXTURE), target=target)
    assert [i for i in result.issues if i.severity != "info"] == []
    written, source = property_nodes(parse(result.text)), property_nodes(load(FIXTURE))
    assert list(written) == list(source)
    for key, node in source.items():
        assert written[key] == node, key


def test_field_moved_and_turned_on_a_read_board() -> None:
    design = edited(read_board(FIXTURE), "R1", "Reference", position=Point(0, -2_000_000), rotation=90 * DEG)
    root = parse(write_board(design, target=9).text)
    node = property_nodes(root)[("R1", "Reference")]
    source = property_nodes(load(FIXTURE))[("R1", "Reference")]
    assert node.find("at") == parse("(at 0 -2 180)")
    at = source.find("at")
    assert at is not None and with_child(node, "at", at) == source
    again = field_of(read_board(write_board(design, target=9).text), "R1", "Reference")
    assert (again.position, again.rotation) == (Point(0, -2_000_000), 90 * DEG)


def test_hidden_resized_and_justified() -> None:
    design = edited(
        read_board(FIXTURE),
        "R1",
        "Value",
        visible=False,
        size=Size(800_000, 800_000),
        thickness=120_000,
        h_justify="left",
    )
    text = write_board(design, target=10).text
    node = property_nodes(parse(text))[("R1", "Value")]
    heads = [c.name for c in node.nodes()]
    assert heads == ["at", "layer", "hide", "uuid", "effects"]
    assert node.find("hide") == parse("(hide yes)")
    effects = node.find("effects")
    assert effects == parse("(effects (font (size 0.8 0.8) (thickness 0.12)) (justify left))")
    assert values(field_of(read_board(text), "R1", "Value")) == values(field_of(design, "R1", "Value"))


def test_bottom_field_justified() -> None:
    design = edited(read_board(FIXTURE), "D1", "Reference", h_justify="right")
    node = property_nodes(parse(write_board(design, target=9).text))[("D1", "Reference")]
    effects = node.find("effects")
    assert effects is not None and effects.find("justify") == parse("(justify right mirror)")


def test_every_justification_is_written_in_order() -> None:
    design = edited(read_board(FIXTURE), "D1", "Value", h_justify="left", v_justify="bottom")
    text = write_board(design, target=10).text
    effects = property_nodes(parse(text))[("D1", "Value")].find("effects")
    assert effects is not None and effects.find("justify") == parse("(justify left bottom mirror)")
    design = edited(design, "D1", "Value", h_justify="center", v_justify="top", mirrored=False)
    effects = property_nodes(parse(write_board(design, target=10).text))[("D1", "Value")].find("effects")
    assert effects is not None and effects.find("justify") == parse("(justify top)")
    design = edited(design, "D1", "Value", v_justify="center")
    effects = property_nodes(parse(write_board(design, target=10).text))[("D1", "Value")].find("effects")
    assert effects is not None and effects.find("justify") is None


def test_layer_and_thickness() -> None:
    design = edited(read_board(FIXTURE), "R1", "Value", layer="F.SilkS", thickness=None)
    node = property_nodes(parse(write_board(design, target=9).text))[("R1", "Value")]
    assert node.find("layer") == parse('(layer "F.SilkS")')
    assert node.find("effects") == parse("(effects (font (size 1 1)))")


def test_shown_again() -> None:
    hidden = source_text({'(layer "F.Fab")': '(layer "F.Fab")\n\t\t\t(hide yes)'})
    design = read_board(hidden)
    assert not field_of(design, "R1", "Value").visible
    node = property_nodes(parse(write_board(edited(design, "R1", "Value", visible=True), target=9).text))[
        ("R1", "Value")
    ]
    assert node.find("hide") is None
    assert node == property_nodes(load(FIXTURE))[("R1", "Value")]


def test_reference_renamed_through_the_field_node() -> None:
    design = read_board(FIXTURE)
    design = design.replace_entity(dataclasses.replace(design.by_ref["R1"], ref="R9"))
    design = edited(design, "R9", "Reference", position=Point(0, -3_000_000))
    node = property_nodes(parse(write_board(design, target=9).text))[("R9", "Reference")]
    assert [a.value for a in node.atoms()] == ["Reference", "R9"]
    assert node.find("at") == parse("(at 0 -3 90)")


def test_field_added_to_a_read_footprint() -> None:
    design = read_board(FIXTURE)
    r1 = footprint_of(design, "R1")
    new = FootprintField(
        id=derived_id("fld", "kicad", "x:field:MPN"),
        name="MPN",
        position=Point(0, 0),
        layer="F.Fab",
        size=Size(1_000_000, 1_000_000),
    )
    changed = design.replace_entity(dataclasses.replace(r1, fields=(*r1.fields, new)))
    with pytest.raises(ValueError, match="MPN"):
        write_board(changed, target=9)


def test_second_field_of_one_name() -> None:
    design = read_board(FIXTURE)
    r1 = footprint_of(design, "R1")
    twin = dataclasses.replace(r1.fields[1], id=derived_id("fld", "kicad", "x:field:twin"))
    changed = design.replace_entity(dataclasses.replace(r1, fields=(*r1.fields, twin)))
    with pytest.raises(ValueError, match="Value"):
        write_board(changed, target=9)


def test_removed_field_leaves_its_node_out() -> None:
    extra = (
        f'(property "MPN" "A-1" (at 0 0 90) (layer "F.Fab") (hide yes) (uuid "{uid(901)}")'
        " (effects (font (size 1 1) (thickness 0.15))))\n\t\t(attr smd)"
    )
    design = read_board(source_text({"(attr smd)": extra}))
    r1 = footprint_of(design, "R1")
    assert [f.name for f in r1.fields] == ["Reference", "Value", "MPN"]
    assert write_board(design, target=9).issues == ()
    removed = design.replace_entity(dataclasses.replace(r1, fields=r1.fields[:2]))
    messages = read_only(removed)
    assert len(messages) == 1 and "'properties'" in messages[0] and "MPN" in messages[0]
    component = removed.by_ref["R1"]
    properties = {k: v for k, v in component.properties.items() if k != "MPN"}
    consistent = removed.replace_entity(dataclasses.replace(component, properties=properties))
    nodes = property_nodes(parse(write_board(consistent, target=9).text))
    assert ("R1", "MPN") not in nodes and ("R1", "Value") in nodes
    without_reference = design.replace_entity(dataclasses.replace(r1, fields=r1.fields[1:]))
    assert any("Reference" in m for m in read_only(without_reference))


def test_other_property_value_stays_read_only() -> None:
    extra = (
        f'(property "MPN" "A-1" (at 0 0 90) (layer "F.Fab") (hide yes) (uuid "{uid(901)}")'
        " (effects (font (size 1 1) (thickness 0.15))))\n\t\t(attr smd)"
    )
    design = read_board(source_text({"(attr smd)": extra}))
    component = design.by_ref["R1"]
    changed = design.replace_entity(
        dataclasses.replace(component, properties={**component.properties, "MPN": "B-2"})
    )
    messages = read_only(changed)
    assert len(messages) == 1 and "MPN" in messages[0]


def test_projected_effects() -> None:
    """An ``effects`` with ``bold`` stays a projected slot: unchanged it keeps its fragment, a changed
    size is refused, and the rest of the field is still written from the model."""
    text = source_text({"(thickness 0.15)\n": "(thickness 0.15)\n\t\t\t\t\t(bold yes)\n"})
    design = read_board(text)
    source = property_nodes(parse(text))[("R1", "Reference")]
    assert write_board(design, target=9).issues == ()
    assert property_nodes(parse(write_board(design, target=9).text))[("R1", "Reference")] == source
    moved = edited(design, "R1", "Reference", position=Point(0, -2_000_000))
    node = property_nodes(parse(write_board(moved, target=9).text))[("R1", "Reference")]
    assert node.find("at") == parse("(at 0 -2 90)") and node.find("effects") == source.find("effects")
    messages = read_only(edited(design, "R1", "Reference", size=Size(800_000, 800_000)))
    assert len(messages) == 1 and "'effects'" in messages[0]


def test_respelled_effects_are_written_from_the_model() -> None:
    text = source_text({"(size 1 1)": "(size 1.0 1.000)"})
    design = read_board(text)
    source = property_nodes(parse(text))[("R1", "Reference")]
    assert property_nodes(parse(write_board(design, target=9).text))[("R1", "Reference")] == source
    resized = edited(design, "R1", "Reference", size=Size(800_000, 900_000))
    node = property_nodes(parse(write_board(resized, target=9).text))[("R1", "Reference")]
    assert node.find("effects") == parse("(effects (font (size 0.9 0.8) (thickness 0.15)))")


def test_negative_angle_is_kept_until_the_field_turns() -> None:
    """KiCad writes ``-90`` for some fields (census of the corpus): the node stays as written while the
    model agrees with it."""
    text = source_text({"(at 0 -1.43 90)": "(at 0 -1.43 -90)"})
    design = read_board(text)
    field = field_of(design, "R1", "Reference")
    assert field.rotation == 180 * DEG
    source = property_nodes(parse(text))[("R1", "Reference")]
    assert property_nodes(parse(write_board(design, target=9).text))[("R1", "Reference")] == source
    turned = edited(design, "R1", "Reference", rotation=0)
    node = property_nodes(parse(write_board(turned, target=9).text))[("R1", "Reference")]
    assert node.find("at") == parse("(at 0 -1.43 90)")


def test_bare_hide_atom_is_read_only() -> None:
    text = source_text({'(layer "F.Fab")': '(layer "F.Fab")\n\t\t\thide'})
    design = read_board(text)
    assert not field_of(design, "R1", "Value").visible
    written = property_nodes(parse(write_board(design, target=9).text))[("R1", "Value")]
    assert written == property_nodes(parse(text))[("R1", "Value")] and written.find("hide") is None
    messages = read_only(edited(design, "R1", "Value", visible=True))
    assert len(messages) == 1 and "'visible'" in messages[0]


def test_hide_no_becomes_hide_yes() -> None:
    text = source_text({'(layer "F.Fab")': '(layer "F.Fab")\n\t\t\t(hide no)'})
    design = read_board(text)
    source = property_nodes(parse(text))[("R1", "Value")]
    assert property_nodes(parse(write_board(design, target=9).text))[("R1", "Value")] == source
    hidden = edited(design, "R1", "Value", visible=False)
    node = property_nodes(parse(write_board(hidden, target=9).text))[("R1", "Value")]
    assert node.find("hide") == parse("(hide yes)")
    assert with_child(node, "hide", parse("(hide no)")) == source


# --- created footprints (task 5.2) -----------------------------------------------------------------


@pytest.mark.parametrize("target", [9, 10])
def test_created_footprint_with_fields(target: int) -> None:
    design = created_board()
    assert design.board is not None
    (footprint,) = design.board.footprints
    reference, value = footprint.fields
    assert reference.position == Point(0, -1_500_000) and not value.visible
    text = write_board(design, target=target).text
    again = read_board(text)
    assert again.board is not None
    read = again.board.footprints[0].fields
    assert [values(f) for f in read] == [values(f) for f in footprint.fields]
    nodes = property_nodes(parse(text))
    assert nodes[("U1", "Value")].find("hide") == parse("(hide yes)")
    assert nodes[("U1", "Reference")].find("hide") is None


def test_created_field_uuid_and_angle() -> None:
    design = created_board()
    assert design.board is not None
    (footprint,) = design.board.footprints
    turned = dataclasses.replace(
        footprint,
        rotation=90 * DEG,
        fields=(
            dataclasses.replace(
                footprint.fields[0], rotation=270 * DEG, native_ids={"kicad": uid(77)}, h_justify="left"
            ),
            footprint.fields[1],
        ),
    )
    text = write_board(design.replace_entity(turned), target=10).text
    node = property_nodes(parse(text))[("U1", "Reference")]
    assert node.find("at") == parse("(at 0 -1.5 0)")
    assert node.find("uuid") == parse(f'(uuid "{uid(77)}")')
    effects = node.find("effects")
    assert effects is not None and effects.find("justify") == parse("(justify left)")
    field = read_board(text).board.footprints[0].fields[0]  # type: ignore[union-attr]
    assert field.rotation == 270 * DEG and field.native_ids == {"kicad": uid(77)}


def test_created_property_without_a_field_keeps_the_defaults() -> None:
    design = created_board()
    assert design.board is not None
    (footprint,) = design.board.footprints
    bare = design.replace_entity(dataclasses.replace(footprint, fields=()))
    nodes = property_nodes(parse(write_board(bare, target=9).text))
    assert nodes[("U1", "Reference")].find("at") == parse("(at 0 0 0)")
    assert nodes[("U1", "Reference")].find("layer") == parse('(layer "F.SilkS")')
    assert nodes[("U1", "Value")].find("layer") == parse('(layer "F.Fab")')


def test_created_field_whose_name_the_component_lacks() -> None:
    design = created_board()
    assert design.board is not None
    (footprint,) = design.board.footprints
    extra = dataclasses.replace(footprint.fields[0], id=derived_id("fld", "kicad", "x:field:MPN"), name="MPN")
    changed = design.replace_entity(dataclasses.replace(footprint, fields=(*footprint.fields, extra)))
    with pytest.raises(ValueError, match="MPN"):
        write_board(changed, target=9)
    component = design.by_ref["U1"]
    named = changed.replace_entity(dataclasses.replace(component, properties={"MPN": "A-1"}))
    nodes = property_nodes(parse(write_board(named, target=9).text))
    assert nodes[("U1", "MPN")].find("at") == parse("(at 0 -1.5 0)")
