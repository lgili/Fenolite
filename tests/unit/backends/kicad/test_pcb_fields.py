# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint fields read from boards (kicad-file-backend, "Footprint fields on boards"; change c0030)."""

from __future__ import annotations

from _boards import FIXTURE, board, rt1_problems, uid

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.pcb import (
    FIELD_FIELDS,
    FIELD_POSITIONAL,
    FOOTPRINT_FIELDS,
    EmitContext,
    model_source,
    read_board,
    rebuild_board,
)
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.design import Design

DEG = 1_000_000


def assert_rt1(text: str) -> None:
    assert rt1_problems(text) == []


def _fp(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    component = design.by_ref[ref]
    return next(fp for fp in design.board.footprints if fp.component_id == component.id)


def _field(fp: FootprintInstance, name: str) -> FootprintField:
    return next(f for f in fp.fields if f.name == name)


def _slots(entity: FootprintField | FootprintInstance) -> tuple[Slot, ...]:
    return slotlib.from_ext(entity.ext["kicad"])


def _edited(edit: dict[tuple[str, str], str], *, extra: dict[str, str] | None = None) -> str:
    """The authored board with property nodes replaced (``(reference, name) → node text``) and extra
    nodes appended after a footprint's ``Value`` property (``reference → node text``)."""
    root = parse(FIXTURE.read_text(encoding="utf-8"))
    children: list[Node | object] = []
    for child in root.children:
        if not isinstance(child, Node) or child.name != "footprint":
            children.append(child)
            continue
        ref = next(
            p.atoms()[1].value
            for p in child.nodes()
            if p.name == "property" and p.atoms()[0].value == "Reference"
        )
        parts: list[object] = []
        for part in child.children:
            if isinstance(part, Node) and part.name == "property":
                name = part.atoms()[0].value
                if (ref, name) in edit:
                    part = parse(edit[(ref, name)])
                parts.append(part)
                if name == "Value" and extra and ref in extra:
                    wrapped = parse(f"(x {extra[ref]})")
                    parts.extend(wrapped.children)
            else:
                parts.append(part)
        children.append(child.with_children(parts))  # type: ignore[arg-type]
    return dumps(root.with_children(children), style="kicad")  # type: ignore[arg-type]


def _property(
    name: str, value: str, n: int, *, at: str = "0 1 90", inner: str = "", effects: str = ""
) -> str:
    effects = effects or "(effects (font (size 1 1) (thickness 0.15)))"
    return f'(property "{name}" "{value}" (at {at}) (layer "F.Fab"){inner} (uuid "{uid(n)}") {effects})'


def test_field_maps() -> None:
    assert FOOTPRINT_FIELDS["property"] == "fields"
    assert dict(FIELD_FIELDS) == {
        "at": "position",
        "layer": "layer",
        "hide": "visible",
        "uuid": "native_ids",
        "effects": "effects",
    }
    assert FIELD_POSITIONAL == ("name",)


def test_reference_of_a_rotated_top_footprint() -> None:
    design = read_board(FIXTURE)
    r1 = _fp(design, "R1")
    assert [f.name for f in r1.fields] == ["Reference", "Value"]
    reference = r1.fields[0]
    assert reference.position == Point(0, -1_430_000)
    assert reference.rotation == 0  # stored 90° on a footprint at 90°
    assert reference.layer == "F.SilkS" and reference.visible
    assert reference.size == Size(1_000_000, 1_000_000) and reference.thickness == 150_000
    assert (reference.h_justify, reference.v_justify, reference.mirrored) == ("center", "center", False)
    slots = _slots(reference)
    assert slots[0] == Modeled("name")
    assert slots[1] == Opaque('"R1"', "20241229")
    assert design.by_ref["R1"].ref == "R1"
    assert not hasattr(reference, "value")


def test_field_of_a_bottom_footprint() -> None:
    d1 = _fp(read_board(FIXTURE), "D1")
    reference = _field(d1, "Reference")
    assert reference.position == Point(1_270_000, 2_960_000)
    assert reference.rotation == 0  # stored 30° minus the footprint's 30°
    assert reference.layer == "B.SilkS" and reference.mirrored


def test_field_slots_and_ids() -> None:
    design = read_board(FIXTURE)
    r1 = _fp(design, "R1")
    property_slots = [s for s in _slots(r1) if s == Modeled("fields")]
    assert len(property_slots) == 2
    assert not any(isinstance(s, Opaque) and s.fragment.startswith("(property") for s in _slots(r1))
    key = r1.native_ids["kicad"]
    for field in r1.fields:
        assert field.id == derived_id("fld", "kicad", f"{key}:field:{field.name}")
        assert set(field.native_ids) == {"kicad"} and field.native_ids["kicad"] != key
        fields = [s.field for s in _slots(field) if isinstance(s, Modeled)]
        assert fields == ["name", "position", "layer", "native_ids", "effects"]
        assert field.provenance is not None and "/property[" in field.provenance.locator
    assert design.by_id[r1.fields[0].id] is r1.fields[0]


def test_values_stay_in_the_component() -> None:
    design = read_board(FIXTURE)
    r1 = design.by_ref["R1"]
    assert (r1.ref, r1.value) == ("R1", "330")
    assert r1.properties["Reference"] == "R1" and r1.properties["Value"] == "330"


def test_hidden_field_with_justification() -> None:
    value = _property(
        "Value",
        "330",
        900,
        at="0 1.43 90",
        inner=" (hide yes)",
        effects="(effects (font (size 1 1) (thickness 0.15)) (justify left bottom))",
    )
    issues: list[Issue] = []
    text = _edited({("R1", "Value"): value})
    field = _field(_fp(read_board(text, issues=issues), "R1"), "Value")
    assert not field.visible
    assert (field.h_justify, field.v_justify, field.mirrored) == ("left", "bottom", False)
    modeled = [s.field for s in _slots(field) if isinstance(s, Modeled)]
    assert "visible" in modeled and "effects" in modeled
    assert not [i for i in issues if i.code == "kicad.board.kept-opaque"]
    assert_rt1(text)


def test_justify_words() -> None:
    for words, expected in {
        "right": ("right", "center", False),
        "top": ("center", "top", False),
        "right top mirror": ("right", "top", True),
        "mirror": ("center", "center", True),
    }.items():
        value = _property(
            "Value", "330", 900, effects=f"(effects (font (size 1.2 0.8) (thickness 0.1)) (justify {words}))"
        )
        text = _edited({("R1", "Value"): value})
        field = _field(_fp(read_board(text), "R1"), "Value")
        assert (field.h_justify, field.v_justify, field.mirrored) == expected, words
        assert field.size == Size(800_000, 1_200_000) and field.thickness == 100_000
        assert_rt1(text)


def test_font_without_thickness() -> None:
    value = _property("Value", "330", 900, effects="(effects (font (size 1 1)))")
    text = _edited({("R1", "Value"): value})
    field = _field(_fp(read_board(text), "R1"), "Value")
    assert field.thickness is None
    assert Modeled("effects") in _slots(field)
    assert_rt1(text)


def test_unlocked_stays_opaque_in_place() -> None:
    value = (
        f'(property "Value" "330" (at 0 1.43 90) (unlocked yes) (layer "F.Fab") (uuid "{uid(900)}")'
        " (effects (font (size 1 1) (thickness 0.15))))"
    )
    text = _edited({("R1", "Value"): value})
    field = _field(_fp(read_board(text), "R1"), "Value")
    slots = _slots(field)
    assert slots[3] == Opaque("(unlocked yes)", "20241229")
    assert_rt1(text)


def test_effects_the_emitter_does_not_reproduce() -> None:
    value = _property("Value", "330", 900, effects="(effects (font (size 1 1) (thickness 0.15) (bold yes)))")
    issues: list[Issue] = []
    text = _edited({("R1", "Value"): value})
    field = _field(_fp(read_board(text, issues=issues), "R1"), "Value")
    assert field.size == Size(1_000_000, 1_000_000) and field.thickness == 150_000
    effects = [s for s in _slots(field) if isinstance(s, Opaque) and s.fragment.startswith("(effects")]
    assert len(effects) == 1 and "bold" in effects[0].fragment
    assert [i.code for i in issues if "effects" in i.message] == ["kicad.board.kept-opaque"]
    assert_rt1(text)


def test_at_without_an_angle() -> None:
    text = board(
        f'(footprint "Lib:FP" (layer "F.Cu") (uuid "{uid(1)}") (at 10 10 90)'
        f' (property "Reference" "U1" (at 0 -2) (layer "F.SilkS") (uuid "{uid(2)}")'
        " (effects (font (size 1 1) (thickness 0.15)))))"
    )
    design = read_board(text)
    assert design.board is not None
    (field,) = design.board.footprints[0].fields
    assert field.position == Point(0, -2_000_000)
    assert field.rotation == 270 * DEG  # stored 0 on a footprint at 90°
    assert_rt1(text)


# --- task 3.2: older spellings, repeated and bare properties, inexact numbers, rebuild ------------------


def test_eight_format_hidden_field() -> None:
    text = board(
        f'(footprint "Lib:FP" (layer "F.Cu") (uuid "{uid(1)}") (at 10 10)'
        f' (property "Value" "X" (at 0 1 0) (layer "F.Fab") hide (uuid "{uid(2)}")'
        " (effects (font (size 1 1) (thickness 0.15)))))",
        version=20240108,
    )
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    assert not [i for i in issues if i.severity == "error"]
    assert design.board is not None
    (field,) = design.board.footprints[0].fields
    assert field.name == "Value" and not field.visible
    hide = [s for s in _slots(field) if isinstance(s, Opaque) and s.fragment == "hide"]
    assert len(hide) == 1
    assert "visible" not in [s.field for s in _slots(field) if isinstance(s, Modeled)]
    assert_rt1(text)


def test_hide_inside_effects() -> None:
    value = _property("Value", "330", 900, effects="(effects (font (size 1 1) (thickness 0.15)) hide)")
    text = _edited({("R1", "Value"): value})
    field = _field(_fp(read_board(text), "R1"), "Value")
    assert not field.visible
    assert [s for s in _slots(field) if isinstance(s, Opaque) and s.fragment.startswith("(effects")]
    assert_rt1(text)


def test_hide_no_is_visible() -> None:
    value = _property("Value", "330", 900, inner=" (hide no)")
    text = _edited({("R1", "Value"): value})
    field = _field(_fp(read_board(text), "R1"), "Value")
    assert field.visible
    assert Opaque("(hide no)", "20241229") in _slots(field)
    assert_rt1(text)


def test_bare_and_repeated_properties() -> None:
    extra = (
        '(property ki_fp_filters "R_*") ' + _property("MPN", "A-1", 901) + " " + _property("MPN", "A-2", 902)
    )
    text = _edited({}, extra={"R1": extra})
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    r1 = _fp(design, "R1")
    assert [f.name for f in r1.fields] == ["Reference", "Value", "MPN"]
    opaque = [s.fragment for s in _slots(r1) if isinstance(s, Opaque) and s.fragment.startswith("(property")]
    assert len(opaque) == 2
    assert opaque[0] == '(property ki_fp_filters "R_*")' and '"A-2"' in opaque[1]
    kept = [i for i in issues if i.code == "kicad.board.kept-opaque"]
    assert len(kept) == 1 and kept[0].severity == "info" and kept[0].where.endswith("/property[4]")
    assert "MPN" in kept[0].message
    assert design.by_ref["R1"].properties["ki_fp_filters"] == "R_*"
    assert _field(r1, "MPN").native_ids == {"kicad": uid(901)}
    assert_rt1(text)


def test_inexact_field_numbers_stay_projected() -> None:
    cases = {
        "kicad.board.inexact-length": _property("Value", "330", 900, at="0.0000001 1.43 90"),
        "kicad.board.inexact-angle": _property("Value", "330", 900, at="0 1.43 30.0000001"),
        "kicad.board.inexact-length ": _property(
            "Value", "330", 900, effects="(effects (font (size 1.0000001 1) (thickness 0.15)))"
        ),
    }
    for code, value in cases.items():
        issues: list[Issue] = []
        text = _edited({("R1", "Value"): value})
        design = read_board(text, issues=issues)
        r1 = _fp(design, "R1")
        assert [f.name for f in r1.fields] == ["Reference"], code
        assert [s for s in _slots(r1) if isinstance(s, Opaque) and s.fragment.startswith('(property "Value"')]
        assert [i.code for i in issues if i.code.startswith("kicad.board.inexact")] == [code.strip()]
        assert design.by_ref["R1"].value == "330"
        assert_rt1(text)


def test_property_without_a_font_size_is_not_a_field() -> None:
    value = f'(property "Value" "330" (at 0 1 90) (layer "F.Fab") (uuid "{uid(900)}") (effects (font)))'
    text = _edited({("R1", "Value"): value})
    r1 = _fp(read_board(text), "R1")
    assert [f.name for f in r1.fields] == ["Reference"]
    assert_rt1(text)


def test_fields_are_rebuilt_from_their_slots() -> None:
    design = read_board(FIXTURE)
    r1 = _fp(design, "R1")
    ctx = EmitContext.of(design)
    source = model_source(r1, ctx)
    nodes = source.items("fields")
    assert [n.atoms()[0].value for n in nodes if isinstance(n, Node)] == ["Reference", "Value"]
    field_source = model_source(r1.fields[0], ctx)
    assert set(field_source.fields()) == {"name", "position", "layer", "native_ids", "effects"}
    original = parse(FIXTURE.read_text(encoding="utf-8"))
    assert rebuild_board(design) == original


def test_model_values_of_a_field_are_emitted() -> None:
    import dataclasses

    design = read_board(FIXTURE)
    r1 = _fp(design, "R1")
    moved = dataclasses.replace(r1.fields[0], position=Point(0, -2_000_000), rotation=90 * DEG)
    changed = design.replace_entity(moved)
    root = rebuild_board(changed)
    footprint = next(n for n in root.nodes() if n.name == "footprint")
    reference = next(n for n in footprint.nodes() if n.name == "property")
    at = reference.find("at")
    assert at is not None and [a.text for a in at.atoms()] == ["0", "-2", "180"]


def test_placed_copy_and_read_back_board_give_equal_field_ids() -> None:
    first, second = read_board(FIXTURE), read_board(FIXTURE.read_text(encoding="utf-8"))
    assert [f.id for f in _fp(first, "D1").fields] == [f.id for f in _fp(second, "D1").fields]
