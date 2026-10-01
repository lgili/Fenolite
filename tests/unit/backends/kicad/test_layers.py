# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad layer kinds and wildcard expansion (capability kicad-file-backend, change c0009)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.layers import expand_layers, has_wildcard, is_canonical, layer_kind


@pytest.mark.parametrize(
    ("name", "row_type", "kind"),
    [
        ("F.Cu", "signal", "copper"),
        ("B.Cu", "signal", "copper"),
        ("In3.Cu", "power", "copper"),
        ("F.SilkS", "user", "silkscreen"),
        ("B.Mask", "user", "soldermask"),
        ("F.Paste", "user", "solderpaste"),
        ("B.CrtYd", "user", "courtyard"),
        ("F.Fab", "user", "fabrication"),
        ("Edge.Cuts", "user", "edge"),
        ("Margin", "user", "mechanical"),
        ("F.Adhes", "user", "mechanical"),
        ("Dwgs.User", "user", "user"),
        ("Eco2.User", "user", "user"),
        ("User.4", "user", "user"),
        ("Foo", "signal", "copper"),
        ("Foo", "jumper", "copper"),
        ("Foo", "user", "user"),
    ],
)
def test_layer_kind(name: str, row_type: str, kind: str) -> None:
    assert layer_kind(name, row_type) == kind


def test_inner_and_unknown_layers() -> None:
    assert [
        layer_kind("In3.Cu"),
        layer_kind("User.4"),
        layer_kind("F.Adhes"),
        layer_kind("Foo", "signal"),
    ] == [
        "copper",
        "user",
        "mechanical",
        "copper",
    ]


def test_canonical_names() -> None:
    assert [is_canonical("In3.Cu"), is_canonical("Edge.Cuts"), is_canonical("Foo")] == [True, True, False]
    assert not is_canonical("In0.Cu") and not is_canonical("X.Cu")


def test_expand_wildcards() -> None:
    copper = ("F.Cu", "In1.Cu", "B.Cu")
    assert expand_layers(["*.Cu", "*.Mask"], copper) == ("F.Cu", "In1.Cu", "B.Cu", "F.Mask", "B.Mask")
    assert expand_layers(["F&B.Cu", "*.Mask"], copper) == ("F.Cu", "B.Cu", "F.Mask", "B.Mask")
    assert expand_layers(["F.Cu", "F.Paste"], copper) == ("F.Cu", "F.Paste")
    assert expand_layers(["*.Cu", "F.Cu"], copper) == copper
    assert has_wildcard(["F.Cu", "*.Mask"]) and has_wildcard(["F&B.Cu"]) and not has_wildcard(["F.Cu"])
