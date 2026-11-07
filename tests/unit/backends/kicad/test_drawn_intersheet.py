# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed fixed inter-sheet fields preserve poses rather than hiding native data (c0348)."""

from __future__ import annotations

import dataclasses

import _drawn
import pytest

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import dumps as native_dump
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.lens.drawn import read_drawn, write_drawn
from fenolite.model.canonical import dumps, loads, to_data
from fenolite.model.drawn import DrawnField, DrawnFont, DrawnLabel


def typed_label(*, hidden: bool = False) -> DrawnLabel:
    return DrawnLabel(
        "global",
        "AUTH_TYPED",
        Point(10_000_000, 20_000_000),
        shape="input",
        intersheet_refs=DrawnField(
            "Intersheetrefs",
            Point(15_000_001, 22_000_003),
            90_000_000,
            "right",
            hidden,
            DrawnFont(Size(500_000, 600_000), bold=True),
        ),
    )


def test_default_bytes_and_appended_canonical_presence() -> None:
    default = DrawnLabel("global", "AUTH_TYPED", Point(1, 2), shape="input")
    assert "intersheet_refs" not in to_data(default)
    assert list(dataclasses.fields(DrawnLabel))[-1].name == "intersheet_refs"
    marked = typed_label(hidden=True)
    assert to_data(marked)["intersheet_refs"]["name"] == "Intersheetrefs"
    assert loads(dumps(marked), DrawnLabel) == marked
    assert loads(dumps(default), DrawnLabel).intersheet_refs is None


@pytest.mark.parametrize("kind", ["local", "hierarchical"])
def test_only_global_kind_can_carry_reference_pose(kind: str) -> None:
    with pytest.raises(ValueError, match="global"):
        dataclasses.replace(typed_label(), kind=kind)


def test_wrong_name_or_nonfield_pose_refuses() -> None:
    with pytest.raises(ValueError, match="Intersheetrefs"):
        dataclasses.replace(typed_label(), intersheet_refs=DrawnField("Custom", Point(1, 2)))
    with pytest.raises(TypeError, match="DrawnField"):
        dataclasses.replace(typed_label(), intersheet_refs="not-a-field")


def test_toml_default_omission_and_exact_field_pose() -> None:
    drawing = _drawn.drawn("flat")
    original = write_drawn(drawing)
    assert "intersheet_refs" not in original
    changed = dataclasses.replace(
        drawing, sheets=(dataclasses.replace(drawing.sheets[0], labels=(typed_label(),)),)
    )
    assert read_drawn(write_drawn(changed)) == changed
    assert write_drawn(read_drawn(original)) == original
    with pytest.raises(FormatError, match="global"):
        read_drawn(
            write_drawn(changed).replace('shape = "input"\n', "").replace('kind = "global"', 'kind = "local"')
        )
    with pytest.raises(FormatError):
        read_drawn(write_drawn(changed).replace("intersheet_refs = {", 'intersheet_refs = { text = "bad",'))


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("hidden", [False, True])
def test_typed_native_field_survives_extract_lower_write(target: int, hidden: bool) -> None:
    drawing = _drawn.drawn("full")
    root = drawing.sheets[0]
    label = next(label for label in root.labels if label.kind == "global")
    pose = typed_label(hidden=hidden).intersheet_refs
    changed = dataclasses.replace(label, intersheet_refs=pose)
    drawing = dataclasses.replace(
        drawing,
        sheets=(
            dataclasses.replace(
                root, labels=tuple(changed if item is label else item for item in root.labels)
            ),
            *drawing.sheets[1:],
        ),
    )
    output = _drawn.build("full", target, value=drawing)
    assert output.files and not [i for i in output.issues if i.severity == "error"]
    extracted, _, _ = _drawn.resolved(output)
    again = next(
        item for item in extracted.sheets[0].labels if item.text == label.text and item.kind == "global"
    )
    assert again.intersheet_refs == pose
    tree = parse(output.files[_drawn.root_name(output)].decode())
    native = next(item for item in tree.nodes("global_label") if item.atoms()[0].value == label.text)
    (prop,) = native.nodes("property")
    assert tuple(a.value for a in prop.atoms()[:2]) == sch.INTERSHEET
    assert "15.000001" in native_dump(prop) and "22.000003" in native_dump(prop)


@pytest.mark.parametrize(
    "defect",
    [
        "duplicate",
        "wrong-name",
        "wrong-text",
        "local",
        "hierarchical",
        "rotation",
        "position",
        "show-name",
        "autoplace",
        "hide-flag",
        "duplicate-position",
        "unknown-metadata",
    ],
)
def test_unsupported_native_property_refuses_locally(defect: str) -> None:
    output = _drawn.build("full", 9)
    name = _drawn.root_name(output)
    root = parse(output.files[name].decode())
    item = root.nodes("global_label")[0]
    property_text = (
        '(property "Intersheetrefs" "${INTERSHEET_REFS}" (at 15 22 0) '
        "(effects (font (size 1.27 1.27)) (justify left) (hide yes)))"
    )
    if defect == "wrong-name":
        property_text = property_text.replace('"Intersheetrefs"', '"Custom"')
    elif defect == "wrong-text":
        property_text = property_text.replace('"${INTERSHEET_REFS}"', '"unrelated text"')
    elif defect == "rotation":
        property_text = property_text.replace("15 22 0", "15 22 180")
    elif defect == "position":
        property_text = property_text.replace("15 22 0", "15.0000001 22 0")
    elif defect == "show-name":
        property_text = property_text[:-1] + " (show_name yes))"
    elif defect == "autoplace":
        property_text = property_text[:-1] + " (do_not_autoplace yes))"
    elif defect == "hide-flag":
        property_text = property_text.replace("hide yes", "hide perhaps")
    elif defect == "duplicate-position":
        property_text = property_text[:-1] + " (at 15 22 0))"
    elif defect == "unknown-metadata":
        property_text = property_text[:-1] + " (unknown yes))"
    prop = parse(property_text)
    added = (prop, prop) if defect == "duplicate" else (prop,)
    if defect in {"local", "hierarchical"}:
        head = "label" if defect == "local" else "hierarchical_label"
        item = dataclasses.replace(item, head=dataclasses.replace(item.head, text=head))
    changed = item.with_children((*item.children, *added))
    original = root.nodes("global_label")[0]
    output = dataclasses.replace(
        output,
        files={
            **output.files,
            name: native_dump(
                root.with_children(tuple(changed if child is original else child for child in root.children))
            ).encode(),
        },
    )
    with pytest.raises(FormatError) as found:
        _drawn.resolved(output)
    assert found.value.locator.startswith("label[") and found.value.file == name
