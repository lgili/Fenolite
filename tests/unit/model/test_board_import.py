# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board fields for file backends and the duplicate-reference rule (capability design-model, c0009)."""

from __future__ import annotations

import json
import random

import _schema

from fenolite.core.coords import Point
from fenolite.core.ids import new_id
from fenolite.model import Board, Component, Design, FootprintInstance, Via, Zone, ZoneFill
from fenolite.model.canonical import dumps, loads

BOARD_SCHEMA = _schema.load("fenolite.model.v0/board.json")


def _old_board_json() -> str:
    """A board written before the fields of change c0009 existed (none of them present)."""
    rng = random.Random(7)
    return json.dumps(
        {
            "id": new_id("brd", rng),
            "footprints": [
                {"id": new_id("fp", rng), "component_id": "", "lib_ref": "L:F", "position": {"x": 0, "y": 0}}
            ],
            "vias": [
                {
                    "id": new_id("via", rng),
                    "position": {"x": 1, "y": 2},
                    "diameter": 600_000,
                    "drill": 300_000,
                }
            ],
            "zones": [
                {
                    "id": new_id("zon", rng),
                    "outline": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}],
                    "fills": [{"layer": "F.Cu", "polygon": [{"x": 0, "y": 0}]}],
                }
            ],
        }
    )


def test_old_documents_still_load() -> None:
    board = loads(_old_board_json(), Board)
    assert board.footprints[0].attributes == ()
    assert board.vias[0].via_type == "through"
    assert board.zones[0].name == "" and board.zones[0].fills[0].island is False


def test_new_fields_round_trip() -> None:
    rng = random.Random(8)
    board = Board(
        id=new_id("brd", rng),
        footprints=(
            FootprintInstance(
                id=new_id("fp", rng),
                component_id="",
                lib_ref="L:F",
                position=Point(0, 0),
                attributes=("smd", "dnp"),
            ),
        ),
        vias=(Via(id=new_id("via", rng), position=Point(0, 0), diameter=1, drill=1, via_type="blind"),),
        zones=(
            Zone(
                id=new_id("zon", rng),
                outline=(),
                name="GND_B",
                fills=(ZoneFill("B.Cu", (Point(0, 0),)), ZoneFill("B.Cu", (Point(1, 1),), island=True)),
            ),
        ),
    )
    text = dumps(board)
    assert loads(text, Board) == board
    assert _schema.validate(json.loads(text), BOARD_SCHEMA) == []


def test_unknown_attribute_rejected_by_the_schema() -> None:
    data = json.loads(_old_board_json())
    data["footprints"][0]["attributes"] = ["glued"]
    problems = _schema.validate(data, BOARD_SCHEMA)
    assert problems and problems[0].startswith("/footprints/0/attributes/0")


def test_schema_lists_the_new_fields() -> None:
    text = json.dumps(BOARD_SCHEMA)
    for name in ("attributes", "via_type", "island", "name"):
        assert f'"{name}"' in text


def _design(refs_and_attributes: list[tuple[str, tuple[str, ...]]]) -> Design:
    design = Design.new("t", seed=3)
    rng = random.Random(4)
    components: list[Component] = []
    footprints: list[FootprintInstance] = []
    for ref, attributes in refs_and_attributes:
        component = Component(id=new_id("cmp", rng), ref=ref)
        components.append(component)
        footprints.append(
            FootprintInstance(
                id=new_id("fp", rng),
                component_id=component.id,
                lib_ref="L:F",
                position=Point(0, 0),
                attributes=attributes,  # type: ignore[arg-type]
            )
        )
    assert design.board is not None
    board = design.board.__class__(id=design.board.id, footprints=tuple(footprints))
    circuit = design.circuit.__class__(components=tuple(components))
    return Design(header=design.header, circuit=circuit, board=board)


def _duplicate_refs(design: Design) -> dict[str, str]:
    return {i.where: i.severity for i in design.validate() if i.code == "model.duplicate-ref"}


def test_board_only_duplicates_are_warnings() -> None:
    design = _design(
        [
            ("LOGO", ("board_only",)),
            ("LOGO", ("board_only", "exclude_from_bom")),
            ("R1", ()),
            ("R1", ("smd",)),
        ]
    )
    assert _duplicate_refs(design) == {"LOGO": "warning", "R1": "error"}


def test_mixed_board_only_stays_an_error() -> None:
    design = _design([("H1", ("board_only",)), ("H1", ())])
    assert _duplicate_refs(design) == {"H1": "error"}


def test_unannotated_references_are_warnings() -> None:
    design = _design([("REF**", ()), ("REF**", ())])
    assert _duplicate_refs(design) == {"REF**": "warning"}
