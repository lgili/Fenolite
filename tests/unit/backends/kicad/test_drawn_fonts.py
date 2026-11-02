# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawn symbol/power fonts use native field syntax and effective defaults (c0326)."""

from __future__ import annotations

import dataclasses

import _drawn
import pytest

from fenolite.backends.kicad import _drawn_font, sch
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.model.drawn import DrawnField, DrawnFont


def _property(font: str) -> Node:
    return parse(f'(property "Value" "FontProbe" (at 1 2 0) (effects {font}))')


def test_field_native_axis_order_and_supported_true_flags() -> None:
    value = DrawnFont(Size(250_001, 350_003), 150_000, True, True, "Authored Sans")
    native = _drawn_font.font_node(value, default_nm=sch.TEXT_SIZE)
    size = native.find("size")
    assert size is not None and [atom.to_nm() for atom in size.atoms()] == [350_003, 250_001]
    assert [child.value for child in native.children if isinstance(child, Atom)] == ["bold", "italic"]
    assert (
        _drawn_font.read_font(
            _property('(font (face "Authored Sans") (size 0.350003 0.250001) (thickness 0.15) bold italic)'),
            default_nm=sch.TEXT_SIZE,
            where="Value.font",
        )
        == value
    )


@pytest.mark.parametrize(
    "font",
    (
        "",
        "(font)",
        "(font (size 1.27 1.27))",
        "(font (size 1.27 1.27) (thickness 0))",
        "(font (size 1.27 1.27) (bold no) (italic no))",
    ),
)
def test_field_native_default_spellings_have_one_effective_value(font: str) -> None:
    assert _drawn_font.read_font(_property(font), default_nm=sch.TEXT_SIZE, where="Value.font") is None
    disabled = _drawn_font.font_node(DrawnFont(bold=False, italic=False), default_nm=sch.TEXT_SIZE)
    assert disabled == parse("(font (size 1.27 1.27))")


@pytest.mark.parametrize("target", (9, 10))
def test_field_style_survives_written_byte_readback_with_code_text(target: int) -> None:
    value = _drawn.drawn("full")
    root = value.sheets[0]
    symbol = root.symbols[0]
    font = DrawnFont(Size(250_001, 350_003), thickness=150_000, bold=True, italic=True, face="Authored Sans")
    fields = tuple(
        dataclasses.replace(field, font=font) if field.name == "Value" else field for field in symbol.fields
    )
    changed = dataclasses.replace(symbol, fields=fields)
    drawing = dataclasses.replace(
        value, sheets=(dataclasses.replace(root, symbols=(changed, *root.symbols[1:])), *value.sheets[1:])
    )
    output = _drawn.build("full", target, value=drawing)
    extracted, _, _ = _drawn.resolved(output)
    again = extracted.sheets[0].symbols[0]
    assert next(field for field in again.fields if field.name == "Value").font == font
    native = sch.read_schematic(output.files[_drawn.root_name(output)].decode("utf-8"))
    instance = native.symbols[0]
    component = next(
        part for part in output.design.circuit.components if part.properties["fenolite.path"] == symbol.part
    )
    assert instance.value == component.value
    assert instance.ref == component.ref
    assert instance.footprint == component.lib_footprint_ref


@pytest.mark.parametrize("target", (9, 10))
def test_power_visible_field_font_keeps_existing_hidden_reference_rule(target: int) -> None:
    value = _drawn.drawn("full")
    root = value.sheets[0]
    power = root.powers[0]
    font = DrawnFont(Size(762_000, 762_000))
    field = DrawnField("Value", Point(power.at.x, power.at.y + 1_270_000), font=font)
    changed = dataclasses.replace(power, fields=(field,))
    drawing = dataclasses.replace(
        value, sheets=(dataclasses.replace(root, powers=(changed,)), *value.sheets[1:])
    )
    output = _drawn.build("full", target, value=drawing)
    extracted, _, _ = _drawn.resolved(output)
    again = extracted.sheets[0].powers[0]
    assert again.fields == (field,)
    assert again.net == power.net and again.symbol == power.symbol


@pytest.mark.parametrize("target", (9, 10))
def test_hidden_field_with_nondefault_font_keeps_its_pose(target: int) -> None:
    value = _drawn.drawn("full")
    root = value.sheets[0]
    symbol = root.symbols[0]
    field = DrawnField(
        "Footprint", Point(1_000_000, 2_000_000), hide=True, font=DrawnFont(Size(250_000, 350_000))
    )
    changed = dataclasses.replace(symbol, fields=(*symbol.fields, field))
    drawing = dataclasses.replace(
        value, sheets=(dataclasses.replace(root, symbols=(changed, *root.symbols[1:])), *value.sheets[1:])
    )
    output = _drawn.build("full", target, value=drawing)
    extracted, _, _ = _drawn.resolved(output)
    assert field in extracted.sheets[0].symbols[0].fields


@pytest.mark.parametrize(
    "font",
    (
        "(font (size 0.2500001 0.35))",
        "(font (size 0.25))",
        "(font (size 0.25 0.35) future_effect)",
        "(font (size 0.25 0.35) (future_effect yes))",
        "(font (size 0.25 0.35) bold (bold no))",
        "(font (size 0.25 0.35) (bold false))",
        "(font (size 0.25 0.35) (thickness -1))",
    ),
)
def test_unsupported_field_font_refuses_with_locator(font: str) -> None:
    with pytest.raises(FormatError) as caught:
        _drawn_font.read_font(_property(font), default_nm=sch.TEXT_SIZE, where="R1.fields.Value.font")
    assert caught.value.locator == "R1.fields.Value.font"


@pytest.mark.parametrize("nm", (1, 499, 500))
def test_submicrometre_field_font_refuses_at_native_boundary(nm: int) -> None:
    value = DrawnFont(Size(nm, 1_270_000))
    assert value.size == Size(nm, 1_270_000)
    with pytest.raises(FormatError, match="sub-micrometre"):
        _drawn_font.font_node(value, default_nm=sch.TEXT_SIZE)


@pytest.mark.parametrize("target", (9, 10))
@pytest.mark.parametrize("justify", (None, "", "left", "right", "right bottom"))
def test_all_label_kinds_keep_font_and_effective_justification(target: int, justify: str | None) -> None:
    value = _drawn.drawn("full")
    font = DrawnFont(Size(250_001, 350_003), thickness=150_000, bold=True, italic=True)
    drawing = dataclasses.replace(
        value,
        sheets=tuple(
            dataclasses.replace(
                sheet,
                labels=tuple(
                    dataclasses.replace(label, font=font, justify=justify) for label in sheet.labels
                ),
            )
            for sheet in value.sheets
        ),
    )
    output = _drawn.build("full", target, value=drawing)
    extracted, _, _ = _drawn.resolved(output)
    assert {label.kind for sheet in extracted.sheets for label in sheet.labels} == {
        "local",
        "global",
        "hierarchical",
    }
    for before, after in zip(drawing.sheets, extracted.sheets, strict=True):
        for label, again in zip(before.labels, after.labels, strict=True):
            assert (again.kind, again.text, again.at, again.rotation) == (
                label.kind,
                label.text,
                label.at,
                label.rotation,
            )
            assert again.font == font
            expected = None if justify == _drawn_font.label_justify(label.rotation) else justify
            assert again.justify == expected


@pytest.mark.parametrize("target", (9, 10))
@pytest.mark.parametrize("justify", (None, "", "left bottom"))
def test_sheet_pins_and_sheet_property_poses_keep_font_and_code_text(
    target: int, justify: str | None
) -> None:
    value = _drawn.drawn("full")
    root = value.sheets[0]
    ref = root.sheet_refs[0]
    font = DrawnFont(Size(250_001, 350_003), thickness=150_000, bold=True)
    fields = (
        DrawnField(
            "Sheetname", Point(ref.at.x - 2_000_000, ref.at.y - 3_000_000), 90_000_000, "right", font=font
        ),
        DrawnField(
            "Sheetfile", Point(ref.at.x + 2_000_000, ref.at.y + ref.size.h + 3_000_000), hide=True, font=font
        ),
    )
    changed = dataclasses.replace(
        ref,
        fields=fields,
        pins=tuple(dataclasses.replace(pin, font=font, justify=justify) for pin in ref.pins),
    )
    drawing = dataclasses.replace(
        value, sheets=(dataclasses.replace(root, sheet_refs=(changed,)), *value.sheets[1:])
    )
    output = _drawn.build("full", target, value=drawing)
    extracted, _, _ = _drawn.resolved(output)
    again = extracted.sheets[0].sheet_refs[0]
    assert again.fields == fields
    for pin, recovered in zip(ref.pins, again.pins, strict=True):
        assert recovered.font == font
        expected = None if justify == _drawn_font.pin_justify(pin.rotation) else justify
        assert recovered.justify == expected
        assert (recovered.name, recovered.shape, recovered.at, recovered.rotation) == (
            pin.name,
            pin.shape,
            pin.at,
            pin.rotation,
        )
    native = sch.read_schematic(output.files[_drawn.root_name(output)].decode("utf-8"))
    assert native.sheets[0].name == ref.name
    assert native.sheets[0].file in output.files


def _without_justify(item: Node) -> Node:
    return item.with_children(
        [
            child.with_children(
                [part for part in child.children if not isinstance(part, Node) or part.name != "justify"]
            )
            if isinstance(child, Node) and child.name == "effects"
            else child
            for child in item.children
        ]
    )


@pytest.mark.parametrize("target", (9, 10))
def test_missing_native_justification_extracts_explicit_centring(target: int) -> None:
    output = _drawn.build("full", target)
    root_name = _drawn.root_name(output)
    native = parse(output.files[root_name].decode("utf-8"))
    items = []
    for item in native.children:
        if isinstance(item, Node) and item.name in {"label", "global_label", "hierarchical_label"}:
            item = _without_justify(item)
        elif isinstance(item, Node) and item.name == "sheet":
            item = item.with_children(
                [
                    _without_justify(child)
                    if isinstance(child, Node) and child.name in {"pin", "property"}
                    else child
                    for child in item.children
                ]
            )
        items.append(item)
    output = dataclasses.replace(
        output, files={**output.files, root_name: dumps(native.with_children(items)).encode()}
    )
    extracted, _, _ = _drawn.resolved(output)
    root = extracted.sheets[0]
    assert root.labels and all(label.justify == "" for label in root.labels)
    assert all(pin.justify == "" for ref in root.sheet_refs for pin in ref.pins)
    assert {pose.name for pose in root.sheet_refs[0].fields} == {"Sheetname", "Sheetfile"}
    assert all(pose.justify == "" for pose in root.sheet_refs[0].fields)
    again, _, _ = _drawn.resolved(_drawn.build("full", target, value=extracted))
    assert again == extracted


@pytest.mark.parametrize("surface", ("label", "pin"))
def test_hidden_unrepresented_text_refuses(surface: str) -> None:
    output = _drawn.build("full", 9)
    root_name = _drawn.root_name(output)
    native = parse(output.files[root_name].decode("utf-8"))
    changed = False

    def hide(item: Node) -> Node:
        return item.with_children(
            [
                child.with_children([*child.children, parse("(hide yes)")])
                if isinstance(child, Node) and child.name == "effects"
                else child
                for child in item.children
            ]
        )

    items = []
    for item in native.children:
        if not changed and isinstance(item, Node):
            if surface == "label" and item.name == "label":
                item, changed = hide(item), True
            elif surface == "pin" and item.name == "sheet":
                item = item.with_children(
                    [
                        hide(child) if isinstance(child, Node) and child.name == "pin" else child
                        for child in item.children
                    ]
                )
                changed = True
        items.append(item)
    assert changed
    output = dataclasses.replace(
        output, files={**output.files, root_name: dumps(native.with_children(items)).encode()}
    )
    with pytest.raises(FormatError, match="hidden drawn"):
        _drawn.resolved(output)
