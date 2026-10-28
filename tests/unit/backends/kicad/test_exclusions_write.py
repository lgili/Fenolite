# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The keys and the project text of a written DRC exclusion (change c0209; ``backends.kicad.exclusions``),
without a tool: ``tests/kicad/check/test_exclusions_write.py`` runs them against ``kicad-cli``."""

from __future__ import annotations

import dataclasses
import json

from fenolite.backends.base import NIL_UUID, DrcItem, DrcViolation
from fenolite.backends.kicad.exclusions import (
    add_exclusions,
    anchors,
    exclusion_key,
    mirrored_keys,
    stored_keys,
    stored_position,
)
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.core.coords import Point
from fenolite.model.board import Board, Track, Via
from fenolite.model.design import Design

A = "AAAAAAAA-0000-4000-8000-000000000001"
B = "bbbbbbbb-0000-4000-8000-000000000002"
AT = Point(15_000_123, -17_000_000)


def entry(kind: str, *uuids: str) -> DrcViolation:
    items = tuple(DrcItem(uuid, "item", Point(index, 0)) for index, uuid in enumerate(uuids))
    return DrcViolation(kind, kind, "error", items)


def test_keys_in_both_orders() -> None:
    assert exclusion_key("clearance", AT, A, B) == f"clearance|15000123|-17000000|{A.lower()}|{B}"
    assert mirrored_keys("clearance", AT, A, B) == (
        f"clearance|15000123|-17000000|{A.lower()}|{B}",
        f"clearance|15000123|-17000000|{B}|{A.lower()}",
    )
    assert mirrored_keys("via_dangling", AT, A) == (
        f"via_dangling|15000123|-17000000|{A.lower()}|{NIL_UUID}",
    )


def test_add_to_a_missing_project_and_keep_other_keys() -> None:
    made = json.loads(add_exclusions(None, [("k1", "why")]))
    assert made == {"board": {"design_settings": {"drc_exclusions": [["k1", "why"]]}}}
    text = (
        '{\n  "board": {\n    "design_settings": {\n      "drc_exclusions": ["k0"],\n      "x": 1.50\n'
        '    }\n  },\n  "meta": {}\n}\n'
    )
    out = add_exclusions(text, [("k0", "again"), ("k1", "why"), ("k1", "twice")])
    assert '"x": 1.50' in out and out.endswith("}\n")
    assert json.loads(out)["board"]["design_settings"]["drc_exclusions"] == ["k0", ["k1", "why"]]
    assert list(json.loads(out)) == ["board", "meta"]
    assert stored_keys(out) == ("k0", "k1") and stored_keys(None) == ()


def test_stored_position_of_an_excluded_entry() -> None:
    keys = [[key, "why"] for key in mirrored_keys("clearance", AT, A, B)]
    text = json.dumps({"board": {"design_settings": {"drc_exclusions": keys}}})
    assert stored_position(text, entry("clearance", B, A)) == AT
    assert stored_position(text, entry("unconnected_items", A, B)) is None
    assert stored_position(None, entry("clearance", A, B)) is None


def test_anchors_of_the_named_items() -> None:
    track = Track(id="t1", start=Point(1, 2), end=Point(3, 4), width=10, layer="F.Cu")
    via = Via(id="v1", position=Point(5, 6), diameter=10, drill=5, layers=("F.Cu", "B.Cu"))
    other = Track(id="t2", start=Point(7, 8), end=Point(9, 9), width=10, layer="F.Cu")
    design = dataclasses.replace(Design.new("t"), board=Board(id="b", tracks=(track, other), vias=(via,)))
    found = anchors(design, entry("unconnected_items", kicad_uuid(track), kicad_uuid(via)))
    assert found == (Point(0, 0), Point(1, 0), Point(1, 2), Point(3, 4), Point(5, 6))
    assert anchors(None, entry("via_dangling", "x")) == (Point(0, 0),)
