# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 sheet-property controls: native preservation, exact S and honest scene support (c0329)."""

from __future__ import annotations

import dataclasses

import pytest

from fenolite.backends.kicad import _drawn_style as style
from fenolite.backends.kicad import drawn, sch
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind
from fenolite.checks.equivalence import compare_drawn
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.core.ids import derived_id
from fenolite.model.base import ExtBag
from fenolite.model.drawn import DrawnFont, DrawnSchematic, DrawnSheet, DrawnSheetProperty, DrawnSheetRef
from fenolite.model.schematic import SchematicSheet, SheetRef
from fenolite.view.kicad_schematic import build_kicad_schematic_scene
from fenolite.view.themes import palette


def source(prop: str, target: int = 10) -> str:
    version = FORMAT_VERSIONS[FileKind.SCHEMATIC][target]
    return f"""(kicad_sch (version {version}) (generator "fenolite_authored_property_probe")
      (uuid "00000000-0000-4000-8000-000000000001") (paper A4)
      (sheet (at 10 20) (size 30 20) (uuid "00000000-0000-4000-8000-000000000002")
        (property "Sheetname" "Child" (at 10 17.46 0) (effects (font (size 1.27 1.27)) (justify left)))
        (property "Sheetfile" "child.kicad_sch" (at 10 42.54 0)
          (effects (font (size 1.27 1.27)) (justify left)))
        {prop}))"""


def extract(text: str):
    sheet = sch.read_schematic(text, file="authored.kicad_sch")
    info = sch.source_info(sheet)
    assert info is not None
    return drawn._sheet_properties(sheet.sheets[0], file="authored.kicad_sch", version=info.version)


def reference(props) -> DrawnSheetRef:
    return DrawnSheetRef("child", "child", "m", "Child", Point(10_000_000, 20_000_000),
                         Size(30_000_000, 20_000_000), "2", "child.kicad_sch", properties=props)  # fmt: skip


def write(props, target: int) -> str:
    ref = reference(props)
    native = SheetRef(id=derived_id("shr", "owned-property", "child"), name=ref.name, file=ref.file,
                     position=ref.at, size=ref.size, ext=drawn._sheet_ext(ref))  # fmt: skip
    sheet = SchematicSheet(id=derived_id("sch", "owned-property", "root"), name="root", sheets=(native,))
    return sch.write_schematic(sheet, target=target).text


def scene(text: str):
    return build_kicad_schematic_scene(text, name="authored.kicad_sch", palette=palette("kicad"))


@pytest.mark.parametrize("target", (9, 10))
@pytest.mark.parametrize("hidden", (False, True))
def test_native_property_keeps_text_pose_font_and_order(target: int, hidden: bool) -> None:
    properties = (
        DrawnSheetProperty('z = "name"', 'Authored µV "quoted"', Point(10_000_001, 20_000_002),
                           90_000_000, "right top", hidden, DrawnFont(Size(750_000, 1_250_000))),
        DrawnSheetProperty("a", "", Point(3_000_000, 4_000_000)),
    )  # fmt: skip
    text = write(properties, target)
    assert extract(text) == properties
    assert '"Sheetname" "Child"' in text and '"Sheetfile" "child.kicad_sch"' in text


@pytest.mark.parametrize(
    "prop",
    (
        '(property "Field2" "x" (effects (font (size 1.27 1.27))))',
        '(property "Field2" 3 (at 1 2 0))',
        '(property "Field2" "x" (at 1 2 0) (show_name))',
        '(property "Field2" "x" (at 1 2 0) (at 3 4 0))',
        '(property "Field2" "x" (at 1 2 180))',
        '(property "Field2" "x" (at 0.0000001 2 0))',
        '(property "Field2" "x" (at 1 2 0) (hide maybe))',
        '(property "Field2" "${UNKNOWN}" (at 1 2 0))',
        '(property "Field2" "x" (at 1 2 0) (effects (font (size 1.27 1.27) invented)))',
    ),
)
def test_unrepresented_native_data_refuses_in_extraction_and_scene(prop: str) -> None:
    text = source(prop)
    with pytest.raises(FormatError):
        extract(text)
    with pytest.raises(FormatError):
        scene(text)


def test_duplicate_property_names_refuse_in_both_paths() -> None:
    prop = '(property "Field2" "x" (at 1 2 0))'
    with pytest.raises(FormatError, match="repeated"):
        extract(source(prop + prop))
    with pytest.raises(FormatError, match="repeated"):
        scene(source(prop + prop))


def test_literal_tilde_is_version_bound_without_invented_ink() -> None:
    prop = '(property "Field2" "~" (at 5 5 0) (effects (font (size 1.27 1.27)) (justify left)))'
    with pytest.raises(FormatError, match="tilde"):
        extract(source(prop, 9))
    with pytest.raises(FormatError, match="tilde"):
        scene(source(prop, 9))
    assert extract(source(prop, 10))[0].text == "~"
    primitives = scene(source(prop, 10))["prims"]
    assert any(p["k"] == "t" and p["s"] == "~" for p in primitives)
    with pytest.raises(FormatError, match="tilde"):
        write((DrawnSheetProperty("Field2", "~", Point(5_000_000, 5_000_000)),), 9)


@pytest.mark.parametrize(
    "text,hidden,expected",
    [
        ("Authored visible property", False, True),
        ("", False, False),
        ("Authored visible property", True, False),
    ],
)
def test_visible_hidden_and_empty_text_scenes(text: str, hidden: bool, expected: bool) -> None:
    native = write((DrawnSheetProperty("Field2", text, Point(5_000_000, 5_000_000), hide=hidden),), 10)
    assert (
        any(p["k"] == "t" and p["s"] == "Authored visible property" for p in scene(native)["prims"])
        is expected
    )


@pytest.mark.parametrize(
    "change",
    [
        {"text": "changed"},
        {"name": "Other"},
        {"at": Point(5, 6)},
        {"rotation": 90_000_000},
        {"hide": True},
        {"justify": "left"},
        {"font": DrawnFont(Size(500_000, 750_000))},
    ],
)
def test_s_detects_each_property_attribute(change) -> None:
    original = DrawnSheetProperty("Field2", "Authored", Point(1, 2))

    def drawing(prop):
        return DrawnSchematic(
            "root", (DrawnSheet("root", sheet_refs=(reference((prop,)),)), DrawnSheet("child"))
        )

    before = drawing(original)
    result = compare_drawn(before, drawing(dataclasses.replace(original, **change)), pins_a={}, pins_b={})
    assert result.differences
    assert not compare_drawn(before, before, pins_a={}, pins_b={}).differences


@pytest.mark.parametrize(
    "record",
    [
        ("sheet-property-v2", '{"name":"Field2","text":"x"}'),
        (style.SHEET_PROPERTY, '{"name":"Field2","text":"x","extra":1}'),
        (style.SHEET_PROPERTY, '{"name":"Sheetname","text":"override"}'),
        (style.SHEET_PROPERTY, '{"name":"Field2","text":3}'),
        (style.SHEET_PROPERTY, '{"name":"Field2","text":"${VAR}"}'),
    ],
)
def test_private_text_adapter_refuses_unknown_versions_or_unowned_text(record) -> None:
    entity = SheetRef(
        id=derived_id("shr", "owned-property", "bad"),
        name="Child",
        file="child.kicad_sch",
        position=Point(0, 0),
        size=Size(1, 1),
        ext={sch.DRAWN_EXT: ExtBag(None, (record,))},
    )
    with pytest.raises(FormatError):
        sch.field_poses(entity)
