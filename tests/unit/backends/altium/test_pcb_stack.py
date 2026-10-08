# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layer stacks of any even count in the Altium PCB document (capability altium-pcb-writer, "Layer stacks
of any even count" and "Copper layer map"; change c0085)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from _altium_board6 import LAYERS, PLANES, STACKUP, bare_spec, board6_build, read_back, read_document

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.libboard import Dielectric, StackSpec, valid_stack
from fenolite.backends.altium.read.pcbprops import parse_mil
from fenolite.lens.altium_copper import dielectric_kinds, layer_names

ROOT = Path(__file__).resolve().parents[4]
FACTS = ROOT / "docs" / "formats" / "altium" / "pcb-copper.md"


def test_layer_map_by_position() -> None:
    assert pcbrecords.copper_stack(("F.Cu", "B.Cu")) == (1, 32)
    assert pcbrecords.copper_stack(LAYERS) == (1, 2, 3, 4, 5, 32)
    assert pcbrecords.copper_stack(LAYERS, ("In2.Cu",)) == (1, 2, 39, 4, 5, 32)
    assert pcbrecords.copper_stack(LAYERS, ("In4.Cu", "In1.Cu")) == (1, 39, 3, 4, 40, 32)
    assert pcbrecords.copper_stack(("top", "a", "b", "bottom")) == (1, 2, 3, 32)  # names are free


@pytest.mark.parametrize("count", range(2, 33, 2))
def test_two_model_layers_never_share_an_altium_layer(count: int) -> None:
    """The layer map assigns each copper layer one Altium layer, for every even count and plane choice."""
    names = layer_names(count)
    inner = names[1:-1]
    for planes in ((), inner[::2], inner[1::2], inner[: max(0, count - 16)], inner[:16]):
        signal = count - len(planes)
        if signal > pcbrecords.MAX_SIGNAL or len(planes) > pcbrecords.MAX_PLANES:
            with pytest.raises(ValueError, match="at most"):
                pcbrecords.copper_stack(names, planes)
            continue
        ids = pcbrecords.copper_stack(names, planes)
        assert len(set(ids)) == count and valid_stack(ids)
        assert all(1 <= i <= 32 or 39 <= i <= 54 for i in ids)


@pytest.mark.parametrize(
    ("count", "planes", "message"),
    [
        (5, 0, "5 copper layers is not written: the count must be even"),
        (0, 0, "0 copper layers"),
        (34, 16, "34 copper layers is not written: at most 32"),
        (18, 0, "18 signal layers is not written: at most 16"),
        (32, 14, "18 signal layers"),
    ],
)
def test_stacks_the_rules_exclude(count: int, planes: int, message: str) -> None:
    problem = pcbrecords.stack_problem(count, planes)
    assert problem is not None and message in problem
    assert pcbrecords.stack_problem(32, 16) is None and pcbrecords.stack_problem(16, 0) is None


def test_layer_texts() -> None:
    assert [pcbrecords.layer_text(i) for i in (1, 2, 31, 32, 39, 54)] == [
        "TOP", "MID1", "MID30", "BOTTOM", "PLANE1", "PLANE16",
    ]  # fmt: skip
    with pytest.raises(ValueError, match="layer 33 is not a copper layer"):
        pcbrecords.layer_text(33)


def test_stack_spec_refuses_ids_out_of_place() -> None:
    six = StackSpec.default((1, 2, 3, 4, 5, 32))
    assert [d.kind for d in six.dielectrics] == ["prepreg", "core", "prepreg", "core", "prepreg"]
    assert [d.thickness for d in six.dielectrics] == [200_000, 500_000, 200_000, 500_000, 200_000]
    four = StackSpec.default((1, 2, 3, 32))  # as before change c0085
    assert [(d.kind, d.thickness) for d in four.dielectrics] == [
        ("prepreg", 200_000), ("core", 1_000_000), ("prepreg", 200_000),
    ]  # fmt: skip
    for bad in ((1, 3, 2, 32), (1, 40, 39, 32), (1, 2, 32), (2, 32), (1, 5, 32, 32)):
        with pytest.raises(ValueError, match="not a stack that is written"):
            StackSpec(bad, (35_000,) * len(bad), (Dielectric("core", 100_000),) * (len(bad) - 1))
    assert dielectric_kinds(1) == ("core",) and dielectric_kinds(3) == ("prepreg", "core", "prepreg")


def test_six_layers_read_back(tmp_path: Path) -> None:
    """Scenario "Six layers read back": the order, the plane and the dielectric thicknesses."""
    output = board6_build(tmp_path)
    document, design = read_document(output.files["board6.PcbDoc"], "board6.PcbDoc")
    board = design.board
    assert board is not None and board.stackup is not None
    assert tuple(layer.name for layer in board.layers if layer.kind == "copper") == LAYERS
    assert document.board.copper_chain == (1, 2, 39, 4, 5, 32)  # In2.Cu is Internal Plane 1
    assert dict(document.board.plane_nets) == {1: PLANES["In2.Cu"]}
    read = [layer for layer in board.stackup.layers if layer.kind in ("copper", "dielectric")]
    assert len(read) == len(STACKUP)
    for found, (name, kind, thickness, material, epsilon) in zip(read, STACKUP, strict=True):
        assert found.kind == kind and abs(found.thickness - thickness) <= 2, name
        if kind == "copper":
            assert found.name == name
        else:
            assert found.material == material and Fraction(found.epsilon_r) == Fraction(epsilon)
    numbered = {layer.id: layer for layer in document.board.layers}
    for position, layer_id in enumerate(document.board.copper_chain[:-1]):
        below = STACKUP[2 * position + 1]
        height = parse_mil(numbered[layer_id].diel_height)
        assert height is not None and abs(height * Fraction(127, 50) - below[2]) <= 2
        assert numbered[layer_id].diel_material == below[3]
    kinds = [numbered[layer_id].diel_type for layer_id in document.board.copper_chain[:-1]]
    assert kinds == ["2", "1", "2", "1", "2"]  # prepreg and core in turn


def test_sixteen_layers_with_planes_read_back() -> None:
    names = layer_names(16)
    planes = (names[2], names[13])
    ids = pcbrecords.copper_stack(names, planes)
    stack = StackSpec.default(ids, ("GND", "VCC"))
    document, design = read_back(bare_spec(copper_layers=names, stack=stack, nets=("GND", "VCC")))
    assert document.board.copper_chain == ids and dict(document.board.plane_nets) == {1: "GND", 2: "VCC"}
    assert design.board is not None
    assert tuple(layer.name for layer in design.board.layers if layer.kind == "copper") == names
    physical = [
        entry.kind for entry in document.board.stack if entry.kind in ("signal", "plane", "dielectric")
    ]
    assert physical.count("dielectric") == 15 + 0 and physical.count("plane") == 2


def test_the_map_is_recorded_in_the_facts_page() -> None:
    text = FACTS.read_text(encoding="utf-8")
    assert "the k-th inner copper layer is Mid-Layer k" in text
    assert "at most 16 signal layers and 16 internal planes" in text
