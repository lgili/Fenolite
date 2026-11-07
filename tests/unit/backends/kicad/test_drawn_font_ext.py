# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Versioned typed font adapters preserve legacy six-part field records (c0326)."""

from __future__ import annotations

import dataclasses
import json

import pytest

from fenolite.backends.kicad import _drawn_style as style
from fenolite.backends.kicad import sch
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.model.base import ExtBag
from fenolite.model.drawn import DrawnFont
from fenolite.model.schematic import NetLabel, SheetRef, SymbolInstance

FONT = DrawnFont(Size(250_001, 350_003), thickness=0, bold=False, italic=True, face="Authored Ω")
POSES = (
    sch.FieldPose("Reference", Point(1, -2)),
    sch.FieldPose("Value", Point(3, 4), 90_000_000, "right", True),
)
LEGACY = (
    ("field", "Reference\x1f1\x1f-2\x1f0\x1f\x1f0"),
    ("field", "Value\x1f3\x1f4\x1f90000000\x1fright\x1f1"),
)


def symbol(payload: tuple[tuple[str, str], ...]) -> SymbolInstance:
    return SymbolInstance(
        id="sym_00000000-0000-4000-8000-000000000001",
        lib_ref="Authored:Part",
        position=Point(0, 0),
        ext={sch.DRAWN_EXT: ExtBag(None, payload)},
    )


def test_legacy_six_part_records_are_exact_and_unchanged() -> None:
    assert sch.field_pose_ext(POSES) == ExtBag(None, LEGACY)
    assert sch.field_poses(symbol(LEGACY)) == {pose.name: pose for pose in POSES}
    assert sch.field_pose_ext(tuple(sch.field_poses(symbol(LEGACY)).values())).payload == LEGACY


def test_named_font_is_separate_and_roundtrips_for_symbol_and_sheet_properties() -> None:
    poses = (POSES[0], dataclasses.replace(POSES[1], font=FONT))
    bag = sch.field_pose_ext(poses)
    assert bag.payload[:2] == LEGACY
    assert bag.payload[2:] == (
        (
            style.FIELD_FONT,
            '{"name":"Value","size":{"w":250001,"h":350003},"thickness":0,"bold":false,'
            '"italic":true,"face":"Authored Ω"}',
        ),
    )
    assert sch.field_poses(symbol(bag.payload)) == {pose.name: pose for pose in poses}
    # Decoding does not depend on whether the separate style precedes or follows its legacy pose.
    assert sch.field_poses(symbol(tuple(reversed(bag.payload)))) == {
        pose.name: pose for pose in reversed(poses)
    }
    ref = SheetRef(
        id="shr_00000000-0000-4000-8000-000000000001",
        name="Child",
        file="child.kicad_sch",
        position=Point(0, 0),
        size=Size(1, 2),
        ext={sch.DRAWN_EXT: bag},
    )
    assert sch.field_poses(ref) == sch.field_poses(symbol(bag.payload))


@pytest.mark.parametrize(
    "payload",
    (
        (("field", "only\x1ftwo"),),
        (("field", "Value\x1f1.5\x1f2\x1f0\x1f\x1f0"),),
        (("field", "Value\x1f1\x1f2\x1f0\x1f\x1f2"),),
        (LEGACY[0], LEGACY[0]),
        ((style.FIELD_FONT, '{"name":"Value","bold":true}'),),
        (LEGACY[1], (style.FIELD_FONT, '{"name":"Unknown","bold":true}')),
        (
            LEGACY[1],
            (style.FIELD_FONT, '{"name":"Value","bold":true}'),
            (style.FIELD_FONT, '{"name":"Value","bold":true}'),
        ),
        (LEGACY[1], ("field-font-v2", '{"name":"Value","bold":true}')),
        (LEGACY[1], (style.FONT, '{"bold":true}')),
    ),
)
def test_field_bag_refuses_malformed_duplicate_unknown_and_orphan_records(payload: tuple) -> None:
    with pytest.raises(FormatError):
        sch.field_poses(symbol(payload))


@pytest.mark.parametrize(
    "text",
    (
        "{",
        "null",
        "[]",
        "{}",
        '{"unknown":1}',
        '{"size":{"w":1,"h":2,"extra":3}}',
        '{"size":[1,2]}',
        '{"size":{"w":0,"h":1}}',
        '{"size":{"w":true,"h":1}}',
        '{"size":{"w":1.0,"h":1}}',
        '{"thickness":-1}',
        '{"thickness":NaN}',
        '{"bold":null}',
        '{"bold":1}',
        '{"bold":true,"bold":false}',
        '{"size":{"w":1,"w":2,"h":3}}',
        '{"face":null}',
    ),
)
def test_font_payload_is_closed_duplicate_safe_and_integer_only(text: str) -> None:
    with pytest.raises(FormatError) as caught:
        style.read_font(text)
    assert caught.value.locator == style.FONT


@pytest.mark.parametrize("justify", (None, "", "left bottom"))
def test_label_pin_style_preserves_absence_and_centring(justify: str | None) -> None:
    bag = style.text_ext(FONT, justify)
    label = NetLabel(
        id="lbl_00000000-0000-4000-8000-000000000001",
        kind="local",
        name="SIG",
        position=Point(0, 0),
        ext={sch.DRAWN_EXT: bag},
    )
    assert style.text_style(label) == (FONT, justify)
    assert style.text_ext(None, None) == ExtBag()
    assert style.text_style(dataclasses.replace(label, ext={})) == (None, None)
    empty = style.text_ext(None, "")
    assert empty.payload == ((style.JUSTIFY, '""'),)


@pytest.mark.parametrize(
    "payload",
    (
        ((style.FONT, '{"bold":false}'), (style.FONT, '{"bold":false}')),
        (("font-v2", '{"bold":true}'),),
        ((style.FIELD_FONT, '{"name":"Value","bold":true}'),),
        ((style.JUSTIFY, "false"),),
        ((style.JUSTIFY, '"unknown"'),),
        ((style.JUSTIFY, '""'), (style.JUSTIFY, '""')),
    ),
)
def test_text_bag_refuses_unknown_duplicate_and_invalid_style(payload: tuple) -> None:
    with pytest.raises(FormatError):
        style.text_style(symbol(payload))


@pytest.mark.parametrize("justify", (" left", "left  bottom", "\tleft", " "))
def test_noncanonical_private_justification_refuses_on_encode_and_decode(justify: str) -> None:
    with pytest.raises(FormatError, match="justification"):
        style.text_ext(None, justify)
    with pytest.raises(FormatError, match="justification"):
        style.text_style(symbol(((style.JUSTIFY, json.dumps(justify)),)))
