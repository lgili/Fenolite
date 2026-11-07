# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact optional drawn font values (c0326); no native effective-style claim."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest

from fenolite.core.coords import Point, Size
from fenolite.model.canonical import to_data
from fenolite.model.drawn import DrawnField, DrawnFont, DrawnLabel, DrawnPin, DrawnSheetRef


def test_exact_canonical_presence_and_hashable_value() -> None:
    font = DrawnFont(Size(250_001, 350_003), thickness=0, bold=False, italic=True, face="Authored Sans")
    assert to_data(font) == {
        "size": {"w": 250_001, "h": 350_003},
        "thickness": 0,
        "bold": False,
        "italic": True,
        "face": "Authored Sans",
    }
    assert hash(font) == hash(dataclasses.replace(font))
    with pytest.raises(dataclasses.FrozenInstanceError):
        font.bold = True  # type: ignore[misc]
    assert to_data(DrawnFont(bold=False)) == {"bold": False}
    assert to_data(DrawnFont(italic=False)) == {"italic": False}
    assert to_data(DrawnFont(thickness=0)) == {"thickness": 0}


@pytest.mark.parametrize("size", (Size(1, 499), Size(499, 500), Size(500, 1)))
def test_positive_submicrometre_sizes_stay_exact_in_model(size: Size) -> None:
    assert DrawnFont(size).size == size


@pytest.mark.parametrize(
    "kwargs, error",
    (
        ({}, ValueError),
        ({"size": Size(0, 1)}, ValueError),
        ({"size": Size(1, -1)}, ValueError),
        ({"size": Size(True, 1)}, TypeError),
        ({"size": Size(1, 0.5)}, TypeError),
        ({"size": (1, 2)}, TypeError),
        ({"thickness": -1}, ValueError),
        ({"thickness": True}, TypeError),
        ({"thickness": 0.25}, TypeError),
        ({"bold": 0}, TypeError),
        ({"italic": 1}, TypeError),
        ({"face": 2}, TypeError),
        ({"face": ""}, ValueError),
        ({"face": "   "}, ValueError),
        ({"face": "Authored\nSans"}, ValueError),
        ({"face": "Authored\x1fSans"}, ValueError),
        ({"face": "/fonts/authored.ttf"}, ValueError),
        ({"face": "C:\\fonts\\authored.ttf"}, ValueError),
    ),
)
def test_invalid_font_refuses(kwargs: dict, error: type[Exception]) -> None:
    with pytest.raises(error):
        DrawnFont(**kwargs)


@pytest.mark.parametrize(
    "make",
    (
        lambda **kwargs: DrawnField("Value", Point(1, 2), **kwargs),
        lambda **kwargs: DrawnLabel("local", "SIG", Point(1, 2), **kwargs),
        lambda **kwargs: DrawnPin("SIG", "input", Point(1, 2), **kwargs),
    ),
)
def test_all_typed_text_surfaces_keep_optional_font(make: Callable[..., object]) -> None:
    legacy = to_data(make())
    assert "font" not in legacy
    font = DrawnFont(Size(5, 7))
    assert to_data(make(font=font)) == {**legacy, "font": {"size": {"w": 5, "h": 7}}}
    with pytest.raises(TypeError, match="DrawnFont"):
        make(font={"size": [1, 2]})


@pytest.mark.parametrize(
    "make",
    (
        lambda **kwargs: DrawnLabel("hierarchical", "SIG", Point(1, 2), **kwargs),
        lambda **kwargs: DrawnPin("SIG", "input", Point(1, 2), **kwargs),
    ),
)
def test_legacy_justification_and_explicit_centring_are_distinct(make: Callable[..., object]) -> None:
    assert "justify" not in to_data(make())
    assert to_data(make(justify=""))["justify"] == ""
    assert to_data(make(justify="right bottom"))["justify"] == "right bottom"
    with pytest.raises(ValueError, match="justify"):
        make(justify="unknown")
    with pytest.raises(TypeError, match="justify"):
        make(justify=False)


@pytest.mark.parametrize("justify", (" left", "left  bottom", "\tleft", " "))
@pytest.mark.parametrize(
    "make",
    (
        lambda justify: DrawnField("Value", Point(0, 0), justify=justify),
        lambda justify: DrawnLabel("local", "SIG", Point(0, 0), justify=justify),
        lambda justify: DrawnPin("SIG", "input", Point(0, 0), justify=justify),
    ),
)
def test_noncanonical_justification_cannot_make_unreadable_toml(
    justify: str, make: Callable[..., object]
) -> None:
    with pytest.raises(ValueError, match="justify"):
        make(justify)


def test_legacy_canonical_defaults_are_unchanged() -> None:
    assert to_data(DrawnField("Reference", Point(1, 2))) == {"name": "Reference", "at": {"x": 1, "y": 2}}
    assert to_data(DrawnLabel("local", "SIG", Point(1, 2))) == {
        "kind": "local",
        "text": "SIG",
        "at": {"x": 1, "y": 2},
    }
    assert to_data(DrawnPin("SIG", "input", Point(1, 2))) == {
        "name": "SIG",
        "shape": "input",
        "at": {"x": 1, "y": 2},
    }
    ref = DrawnSheetRef("a", "child", "ch0", "Channel", Point(0, 0), Size(1, 2), "2")
    assert "fields" not in to_data(ref)
    pose = DrawnField("Sheetname", Point(3, 4), font=DrawnFont(Size(5, 6)))
    styled = dataclasses.replace(ref, fields=(pose,))
    assert to_data(styled)["fields"] == [to_data(pose)]
    assert styled.name == ref.name and styled.file == ref.file
    assert hash(styled) == hash(dataclasses.replace(styled))


@pytest.mark.parametrize(
    "poses, error",
    (
        ((DrawnField("Value", Point(0, 0)),), ValueError),
        ((DrawnField("Sheetname", Point(0, 0)),) * 2, ValueError),
        (("Sheetname",), TypeError),
        ([DrawnField("Sheetfile", Point(0, 0))], TypeError),
    ),
)
def test_sheet_property_poses_are_closed_and_unique(poses: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        DrawnSheetRef("a", "child", "ch0", "Channel", Point(0, 0), Size(1, 2), "2", fields=poses)  # type: ignore[arg-type]
