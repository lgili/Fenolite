# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two heads of a zone's layers, ``layer`` and ``layers`` (capability kicad-file-backend, "Singular
and plural layer heads of a zone", change c0145).

The boards are the authored ``two_layer.kicad_pcb`` (copper rows ``F.Cu`` and ``B.Cu``; one zone on
``B.Cu``, one rule area on ``F.Cu``) with the layer child of the zone or of the rule area replaced by a
token edit.
"""

from __future__ import annotations

import dataclasses

import pytest
from _boards import FIXTURE, SQUARE, board, rt1_problems, zone

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.model.base import Opaque
from fenolite.model.board import Keepout, Zone
from fenolite.model.design import Design

KINDS = ("zone", "area")
WRITTEN = {"zone": ('(layer "B.Cu")', "44edb74d-faf2-4793-bbd2-aef0794c6dcc"),
           "area": ('(layer "F.Cu")', "178d1501-3f49-496b-b907-7d6a94fc0f4a")}  # fmt: skip
"""Per kind, the layer child of the authored board and the uuid that follows it."""
BOTH = ("F.Cu", "B.Cu")
SINGULAR_WILDCARD = '(layer "*.Cu")'
SINGULAR_MASK = '(layer "F&B.Cu")'
SINGULAR_LIST = '(layer "F.Cu" "B.Cu")'
PLURAL_WILDCARD = '(layers "*.Cu")'
PLURAL_MASK = '(layers "F&B.Cu")'
PLURAL_LIST = '(layers "F.Cu" "B.Cu")'
PLURAL_ONE = '(layers "B.Cu")'
SINGULAR_ONE = '(layer "B.Cu")'
WILDCARDS = (SINGULAR_WILDCARD, SINGULAR_MASK, PLURAL_WILDCARD, PLURAL_MASK)
EVERY = (*WILDCARDS, SINGULAR_LIST, PLURAL_LIST, PLURAL_ONE, SINGULAR_ONE)
AREA = (
    "(keepout (tracks not_allowed) (vias allowed) (pads allowed) (copperpour allowed) (footprints allowed))"
)


def variant(kind: str, child: str) -> str:
    """The authored board with ``child`` as the layer child of its zone or of its rule area."""
    old, uuid = WRITTEN[kind]
    before = f'\t\t{old}\n\t\t(uuid "{uuid}")'
    text = FIXTURE.read_text(encoding="utf-8")
    assert text.count(before) == 1
    return text.replace(before, f'\t\t{child}\n\t\t(uuid "{uuid}")')


def entity(design: Design, kind: str) -> Zone | Keepout:
    assert design.board is not None
    (found,) = design.board.zones if kind == "zone" else design.board.keepouts
    return found


def node_of(text: str, kind: str) -> Node:
    (found,) = [n for n in parse(text).nodes("zone") if (n.find("keepout") is not None) == (kind == "area")]
    return found


def layer_children(text: str, kind: str) -> list[str]:
    return [dumps(c, style="compact") for c in node_of(text, kind).nodes() if c.name in ("layer", "layers")]


def with_layers(design: Design, kind: str, layers: tuple[str, ...]) -> Design:
    return design.replace_entity(dataclasses.replace(entity(design, kind), layers=layers))


def refused(design: Design) -> list[tuple[str, str]]:
    with pytest.raises(LossyWriteError) as info:
        write_board(design, target=9)
    assert info.value.droppable is False
    return [(i.code, i.message) for i in info.value.issues]


# --- read ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("child", WILDCARDS)
def test_wildcard_is_expanded_under_both_heads(kind: str, child: str) -> None:
    """Scenarios "Singular head with a wildcard is read" and "Plural head with a wildcard or a mask"."""
    found = entity(read_board(variant(kind, child)), kind)
    assert found.layers == BOTH
    assert Opaque(child, "20241229") in slotlib.from_ext(found.ext["kicad"])


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("child", [SINGULAR_ONE, PLURAL_ONE])
def test_one_layer_is_read_under_both_heads(kind: str, child: str) -> None:
    """Scenario "Singular head with one layer"."""
    assert entity(read_board(variant(kind, child)), kind).layers == ("B.Cu",)


def test_authored_board_keeps_both_zone_nodes() -> None:
    """Scenario "Singular head with one layer"."""
    source = FIXTURE.read_text(encoding="utf-8")
    design = read_board(source)
    assert entity(design, "zone").layers == ("B.Cu",) and entity(design, "area").layers == ("F.Cu",)
    text = write_board(design, target=9).text
    for kind in KINDS:
        assert dumps(node_of(text, kind)) == dumps(node_of(source, kind))


def test_singular_wildcard_on_three_copper_rows() -> None:
    text = board(zone(1, net="(net 0)", layer=SINGULAR_WILDCARD, inner=f"{AREA} {SQUARE}"))
    design = read_board(text)
    assert entity(design, "area").layers == ("F.Cu", "In1.Cu", "B.Cu")
    assert rt1_problems(text, design) == []
    assert layer_children(write_board(design, target=9).text, "area") == [SINGULAR_WILDCARD]


# --- written back unchanged ------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("child", EVERY)
def test_unchanged_board_keeps_the_layer_child(kind: str, child: str) -> None:
    """Scenario "An unchanged board keeps its layer child": the round trip holds, the write raises
    nothing, and the zone is written as it was read, with one layer child."""
    source = variant(kind, child)
    design = read_board(source)
    assert rt1_problems(source, design) == []
    result = write_board(design, target=9)
    assert [i for i in result.issues if i.severity != "info"] == []
    assert layer_children(result.text, kind) == [child]
    assert dumps(node_of(result.text, kind)) == dumps(node_of(source, kind))


@pytest.mark.parametrize("child", WILDCARDS)
def test_another_field_changed_keeps_the_layer_child(child: str) -> None:
    """A change elsewhere in the zone or the rule area leaves the kept child alone and adds no second
    layer child."""
    design = read_board(variant("zone", child))
    renamed = design.replace_entity(dataclasses.replace(entity(design, "zone"), name="RENAMED"))
    assert layer_children(write_board(renamed, target=9).text, "zone") == [child]
    design = read_board(variant("area", child))
    area = entity(design, "area")
    assert isinstance(area, Keepout)
    opened = design.replace_entity(dataclasses.replace(area, no_vias=not area.no_vias))
    assert layer_children(write_board(opened, target=9).text, "area") == [child]


# --- written after a change of the layers ----------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    ("child", "layers", "written"),
    [
        (SINGULAR_ONE, BOTH, PLURAL_LIST),
        (PLURAL_ONE, BOTH, PLURAL_LIST),
        (PLURAL_LIST, ("F.Cu",), '(layer "F.Cu")'),
        (SINGULAR_ONE, ("F.Cu",), '(layer "F.Cu")'),
    ],
)
def test_changed_layers_are_written_by_their_number(
    kind: str, child: str, layers: tuple[str, ...], written: str
) -> None:
    """Scenario "A changed layer set is written by the number of layers"."""
    design = with_layers(read_board(variant(kind, child)), kind, layers)
    assert layer_children(write_board(design, target=9).text, kind) == [written]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("child", [*WILDCARDS, SINGULAR_LIST])
def test_changed_layers_of_a_kept_child_are_refused(kind: str, child: str) -> None:
    """Scenario "A changed layer set of a wildcard child is refused": the same answer under both heads,
    and never a write that keeps the old child."""
    design = with_layers(read_board(variant(kind, child)), kind, ("F.Cu",))
    ((code, message),) = refused(design)
    assert code == "kicad.board.projection-read-only"
    assert "'layers'" in message and child in message
