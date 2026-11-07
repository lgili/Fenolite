# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original exact field correspondence guards, independent of SVG paint order (c0348)."""

from __future__ import annotations

from decimal import Decimal

import _intersheet
import pytest


def svg(points):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        + "".join(
            f'<g transform="rotate(-90 {x} {y})"><text x="{x}" y="{y}" font-size="0.6666">'
            "NATIVE_FIELD[]</text></g>"
            for x, y in points
        )
        + "</svg>"
    ).encode()


def test_reversed_identical_text_paint_order_keeps_complete_exact_translated_fields():
    before = {"svg/root.svg": svg((("13.5712", "22.3908"), ("15.0908", "20.8712")))}
    after = {"svg/root.svg": svg((("20.0908", "27.8712"), ("18.5712", "29.3908")))}
    old_zip_delta = Decimal("20.0908") - Decimal("13.5712")
    assert old_zip_delta == Decimal("6.5196") and old_zip_delta != 5
    expected = _intersheet.shift_field_poses(
        _intersheet.field_poses(before, "NATIVE_FIELD["), {"svg/root.svg": (Decimal(5), Decimal(7))}
    )
    assert _intersheet.field_poses(after, "NATIVE_FIELD[") == expected
    assert sum(expected.values()) == 2


@pytest.mark.parametrize("wrong", ("position", "missing-duplicate", "wrong-sheet", "font", "rotation"))
def test_exact_field_correspondence_rejects_real_deltas(wrong):
    before = {"svg/root.svg": svg((("13.5712", "22.3908"), ("15.0908", "20.8712")))}
    points = (("20.0908", "27.8712"), ("18.5712", "29.3908"))
    after = {"svg/root.svg": svg(points)}
    if wrong == "position":
        after["svg/root.svg"] = svg((("20.0909", "27.8712"), points[1]))
    elif wrong == "missing-duplicate":
        after["svg/root.svg"] = svg(points[:1])
    elif wrong == "wrong-sheet":
        after = {"svg/child.svg": after["svg/root.svg"]}
    elif wrong == "font":
        after["svg/root.svg"] = after["svg/root.svg"].replace(b'font-size="0.6666"', b'font-size="0.6667"', 1)
    else:
        after["svg/root.svg"] = after["svg/root.svg"].replace(b"rotate(-90 ", b"rotate(-89 ", 1)
    expected = _intersheet.shift_field_poses(
        _intersheet.field_poses(before, "NATIVE_FIELD["), {"svg/root.svg": (Decimal(5), Decimal(7))}
    )
    assert _intersheet.field_poses(after, "NATIVE_FIELD[") != expected


def test_child_fields_are_unchanged_and_duplicate_multiplicity_remains_exact():
    before = {"svg/root.svg": svg((("10", "20"), ("10", "20"))), "svg/child.svg": svg((("30", "40"),))}
    after = {"svg/child.svg": before["svg/child.svg"], "svg/root.svg": svg((("15", "27"), ("15", "27")))}
    expected = _intersheet.shift_field_poses(
        _intersheet.field_poses(before, "NATIVE_FIELD["), {"svg/root.svg": (Decimal(5), Decimal(7))}
    )
    assert _intersheet.field_poses(after, "NATIVE_FIELD[") == expected
    assert sum(expected.values()) == 3


def test_unknown_selected_transform_refuses_but_unrelated_art_is_not_a_field():
    unknown = svg((("10", "20"),)).replace(b"rotate(-90 10 20)", b"matrix(1 0 0 1 0 0)")
    with pytest.raises(ValueError, match="transform"):
        _intersheet.field_poses({"svg/root.svg": unknown}, "NATIVE_FIELD[")
    unrelated = (
        b'<svg xmlns="http://www.w3.org/2000/svg"><g transform="translate(0 0)"><text>OTHER</text></g></svg>'
    )
    assert not _intersheet.field_poses({"svg/child.svg": unrelated}, "NATIVE_FIELD[")
