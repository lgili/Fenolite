# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Derived libraries retain portable native names (c0319 task 1.15)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.equivalence import compare_designs
from fenolite.convert.altium_to_kicad import Ledger, _name, prepare
from fenolite.convert.direction import Options
from fenolite.convert.sources import SourceProject, read_source
from fenolite.convert.to_kicad import write_altium

ROOT = Path(__file__).resolve().parents[3]


def _source(names: tuple[str, ...]) -> tuple[SourceProject, tuple[str, ...]]:
    """Rename only authored footprint identities; retain their independent geometry and pins."""
    source = read_source(ROOT / "tests/data/altium/blink/blink.PrjPcb")
    design = source.design
    assert design.board is not None and len(design.board.footprints) >= len(names)
    refs = {c.id: c.ref for c in design.circuit.components}
    selected = sorted(design.board.footprints, key=lambda fp: (refs[fp.component_id], fp.id))[: len(names)]
    by_id = {fp.id: name for fp, name in zip(selected, names, strict=True)}
    by_component = {fp.component_id: name for fp, name in zip(selected, names, strict=True)}
    board = replace(
        design.board,
        footprints=tuple(replace(fp, lib_ref=by_id.get(fp.id, fp.lib_ref)) for fp in design.board.footprints),
    )
    circuit = replace(
        design.circuit,
        components=tuple(
            replace(c, lib_footprint_ref=by_component.get(c.id, c.lib_footprint_ref))
            for c in design.circuit.components
        ),
    )
    return replace(source, design=replace(design, board=board, circuit=circuit)), tuple(by_id)


@pytest.mark.parametrize("target", (9, 10))
def test_native_space_and_underscore_have_distinct_library_files(target: int) -> None:
    source, selected = _source(("M Mount", "M_Mount"))
    result = write_altium(source, Options(kicad_version=target, name="authored"))
    board = read_board(result.files[result.read_back].decode("utf-8"))
    assert board.board is not None and result.design.board is not None
    prepared = {fp.id: fp for fp in result.design.board.footprints}
    component_links = {c.id: c.lib_footprint_ref for c in result.design.circuit.components}
    for ident, expected in zip(selected, ("M Mount", "M_Mount"), strict=True):
        link = f"authored:{expected}"
        assert prepared[ident].lib_ref == component_links[prepared[ident].component_id] == link
        assert any(fp.lib_ref == link for fp in board.board.footprints)
        definition = read_footprint(result.files[f"authored.pretty/{expected}.kicad_mod"].decode("utf-8"))
        assert definition.name == expected
        assert [(p.number, p.size, p.drill) for p in definition.pads] == [
            (p.number, p.size, p.drill) for p in prepared[ident].pads
        ]
    # This repair changes identity allocation, not comparison: a real rename still fails level 3.
    renamed = replace(
        result.design,
        board=replace(
            result.design.board,
            footprints=tuple(
                replace(fp, lib_ref="authored:M_Mount") if fp.id == selected[0] else fp
                for fp in result.design.board.footprints
            ),
        ),
    )
    differences = compare_designs(result.design, renamed, level=3).differences
    assert [(d.kind, d.a, d.b) for d in differences] == [("footprint-name", "M Mount", "M_Mount")]


@pytest.mark.parametrize(
    ("name", "expected"),
    (("../bad/path", "_bad_path"), (r"bad\path", "bad_path"), ("CON", "_CON"), ("...", "unnamed")),
)
def test_footprint_names_retain_portable_path_guards(name: str, expected: str) -> None:
    source, selected = _source((name,))
    prepared = prepare(source, "authored", 10, Ledger())
    assert prepared.board is not None
    assert next(fp.lib_ref for fp in prepared.board.footprints if fp.id == selected[0]) == (
        f"authored:{expected}"
    )
    assert _name("project and symbol") == "project_and_symbol"


def test_casefold_collisions_remain_deterministic() -> None:
    source, selected = _source(("M Mount", "m mount"))
    first = prepare(source, "authored", 10, Ledger())
    second = prepare(source, "authored", 10, Ledger())
    assert first == second and first.board is not None
    links = {fp.lib_ref for fp in first.board.footprints if fp.id in selected}
    assert links == {"authored:M Mount", "authored:m mount_2"}
