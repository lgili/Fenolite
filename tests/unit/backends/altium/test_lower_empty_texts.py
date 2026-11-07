# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Empty texts of a component (capability altium-pcb-writer, "Empty texts of a component"; change c0451).

A saved document holds a comment text record with no characters (four in ``altium-third-party-pcbdoc-01``),
which the import reads as the component's ``Value`` field. The fixture is the authored Altium sample
``tests/data/altium/routed``: ``R1`` gets an empty value with its hidden ``Value`` field, ``U1`` a footprint
text without characters, and the board a text without characters."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.backends.altium import lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import FootprintInstance, Text
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
ROUTED = ROOT / "tests" / "data" / "altium" / "routed" / "routed.PcbDoc"


def _footprint(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    comps = {c.id: c.ref for c in design.circuit.components}
    return next(fp for fp in design.board.footprints if comps.get(fp.component_id) == ref)


def _edited() -> Design:
    design = AltiumBackend().read(ROUTED).design
    board = design.board
    assert board is not None
    r1, u1 = _footprint(design, "R1"), _footprint(design, "U1")
    reference = next(f for f in u1.fields if f.name == "Reference")
    empty = Text(
        id=derived_id("txt", "c0451", "empty"),
        text="",
        position=Point(0, 1_000_000),
        layer="F.SilkS",
        size=reference.size,
        thickness=reference.thickness or 150_000,
    )
    footprints = tuple(
        dataclasses.replace(fp, texts=(*fp.texts, empty)) if fp.id == u1.id else fp for fp in board.footprints
    )
    board_text = dataclasses.replace(empty, id=derived_id("txt", "c0451", "board"), position=Point(0, 0))
    board = dataclasses.replace(board, footprints=footprints, texts=(*board.texts, board_text))
    components = tuple(
        dataclasses.replace(c, value="") if c.id == r1.component_id else c for c in design.circuit.components
    )
    circuit = dataclasses.replace(design.circuit, components=components)
    return dataclasses.replace(design, board=board, circuit=circuit)


def test_empty_value_and_empty_text(tmp_path: Path) -> None:
    """Scenario "Empty value and empty text": ``R1`` keeps its hidden ``Value`` field with an empty value,
    ``U1`` its empty text; since c0460 task 2.5 the empty board text is written as well."""
    design = _edited()
    before = next(f for f in _footprint(design, "R1").fields if f.name == "Value")
    assert not before.visible
    written = lower.write_design(design, allow_lossy=True, rewrite=True)
    assert derived_id("txt", "c0451", "board") not in written.inputs.not_lowered.get("text", ())
    for name, data in written.files.items():
        (tmp_path / name).write_bytes(data)
    back = AltiumBackend().read(next(tmp_path.glob("*.PcbDoc"))).design
    r1 = _footprint(back, "R1")
    value = next(f for f in r1.fields if f.name == "Value")
    assert (value.layer, value.visible, value.position) == (before.layer, before.visible, before.position)
    assert next(c.value for c in back.circuit.components if c.ref == "R1") == ""
    assert [t.text for t in _footprint(back, "U1").texts].count("") == 1
    assert [t.text for t in back.board.texts if t.position == Point(0, 0)].count("") == 1


def test_a_component_without_field_or_comment_has_no_comment_record(tmp_path: Path) -> None:
    """Negative case: without a placed ``Value`` field an empty comment writes no comment record."""
    design = _edited()
    assert design.board is not None
    r1 = _footprint(design, "R1")
    bare = dataclasses.replace(r1, fields=tuple(f for f in r1.fields if f.name != "Value"))
    board = dataclasses.replace(
        design.board, footprints=tuple(bare if fp.id == r1.id else fp for fp in design.board.footprints)
    )
    written = lower.write_design(dataclasses.replace(design, board=board), allow_lossy=True, rewrite=True)
    for name, data in written.files.items():
        (tmp_path / name).write_bytes(data)
    back = AltiumBackend().read(next(tmp_path.glob("*.PcbDoc"))).design
    assert [f.name for f in _footprint(back, "R1").fields] == ["Reference"]
