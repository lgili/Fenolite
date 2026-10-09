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


# -- plane layers (capability kicad-file-backend, "Plane layers of a board"; change c0107)


def test_plane_layers_read_from_a_board() -> None:
    """Scenario "Plane layers read from a board": the row type is read, kept and written back, for both
    targets."""
    import dataclasses

    from _boards import bare_board

    from fenolite.backends.kicad.layers import plane_layers, with_plane_types
    from fenolite.backends.kicad.pcb import read_board, write_board

    design = bare_board(4)
    assert design.board is not None and plane_layers(design) == ()
    typed = dataclasses.replace(
        design,
        board=dataclasses.replace(design.board, layers=with_plane_types(design.board.layers, ("In1.Cu",))),
    )
    for target in (9, 10):
        text = write_board(typed, target=target).text
        assert '"In1.Cu" power)' in text and '"In2.Cu" signal)' in text
        back = read_board(text)
        assert plane_layers(back) == ("In1.Cu",)
        again = write_board(back, target=target).text
        assert '"In1.Cu" power)' in again and '"In2.Cu" signal)' in again
    assert '(4 "In1.Cu" power)' in write_board(typed, target=10).text
    assert '(6 "In2.Cu" signal)' in write_board(typed, target=10).text


def test_plane_types_set_on_created_layers() -> None:
    """Scenario "Types set on created layers"."""
    from fenolite.backends.kicad.layers import created_layers, with_plane_types

    created = created_layers(4)
    typed = with_plane_types(created, ("In2.Cu",))
    changed = [(a, b) for a, b in zip(created, typed, strict=True) if a != b]
    assert len(created) == 22 and len(changed) == 1 and changed[0][1].name == "In2.Cu"
    assert dict(changed[0][1].ext["kicad"].payload) == {"number": "6", "type": "power"}
    assert [key for key, _ in changed[0][1].ext["kicad"].payload] == ["number", "type"]
    assert with_plane_types(typed, ("In2.Cu",)) == typed and with_plane_types(created, ()) == created
    with pytest.raises(ValueError, match=r"Edge\.Cuts"):
        with_plane_types(created, ("Edge.Cuts",))
    with pytest.raises(ValueError, match="In3.Cu"):
        with_plane_types(created, ("In3.Cu",))


def test_plane_layers_in_stack_order_and_without_a_type() -> None:
    import dataclasses

    from fenolite.backends.kicad.layers import created_layers, plane_layers, with_plane_types
    from fenolite.model.design import Design

    design = Design.new("p", seed=0)
    assert design.board is not None
    layers = with_plane_types(created_layers(6), ("In4.Cu", "In1.Cu"))
    made = dataclasses.replace(design, board=dataclasses.replace(design.board, layers=layers))
    assert plane_layers(made) == ("In1.Cu", "In4.Cu")
    bare = tuple(dataclasses.replace(layer, ext={}) for layer in layers)
    assert plane_layers(dataclasses.replace(made, board=dataclasses.replace(design.board, layers=bare))) == ()
    assert plane_layers(dataclasses.replace(made, board=None)) == ()
