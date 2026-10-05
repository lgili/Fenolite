# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Assign every catalog land pattern offline, using authored terminal-only audit symbols.

These fixtures prove resolution and serialization, not a device's functional pinout or routing.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from _buildhelp import resolver

from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board
from fenolite.catalog import get_footprint, list_entries
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Net, Part, connect, mm, no_connect, placements, to_model
from fenolite.lens.build import build_design
from fenolite.model.library import SymbolDef, SymbolGraphic, SymbolPin, SymbolUnit


@pytest.mark.parametrize("target", [9, 10])
def test_all_100_footprints_build_and_read_back_without_network_or_cad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    def forbidden_connect(*_args: object, **_kwargs: object) -> None:
        pytest.fail("The catalog build attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)
    design = Design("catalog_inventory")
    design.board(mm(400), mm(400))
    symbols = {}
    probe = Net("Probe")
    entries = list_entries(kind="footprint")
    assert len(entries) == 100
    for index, entry in enumerate(entries):
        footprint = get_footprint(entry.lib_id)
        numbers = sorted({p.number for p in footprint.pads if p.number})
        symbol = SymbolDef(
            id=derived_id("sym", "catalog-audit", str(index)),
            library="CatalogAudit",
            name=f"Terminals{index}",
            properties={"Reference": "U", "Value": f"Terminals{index}"},
            units=(SymbolUnit(1, 1),),
            pins=tuple(
                SymbolPin(
                    str(i + 1),
                    f"P{i + 1}",
                    "passive",
                    Point(-5_080_000, -i * 2_540_000),
                    rotation=180_000_000,
                    length=2_540_000,
                    unit=1,
                    body_style=1,
                )
                for i in range(len(numbers))
            ),
            graphics=(
                SymbolGraphic(
                    "rect",
                    (Point(-2_540_000, -max(1, len(numbers)) * 2_540_000), Point(2_540_000, 2_540_000)),
                ),
            ),
        )
        symbols[symbol.lib_id] = symbol
        part = Part(
            f"U{index + 1}",
            symbol.lib_id,
            footprint=entry.lib_id,
            pad_map={str(i + 1): number for i, number in enumerate(numbers)},
        )
        design.add(part)
        part.place(mm(20 + 40 * (index % 10)), mm(20 + 40 * (index // 10)))
        if numbers:
            connect(probe, part["1"])
            no_connect(*(part[str(i + 1)] for i in range(1, len(numbers))))
    output = build_design(
        to_model(design),
        placements(design),
        name=design.name,
        copper=2,
        resolver=resolver(target, project_dir=tmp_path),
        target=target,
        authored_symbols=symbols,
        authored_footprints={entry.lib_id: get_footprint(entry.lib_id) for entry in entries},
    )
    assert output.files and not output.issues
    assert all(output.summary["libraries"][e.lib_id] == "authored" for e in entries)
    restored = read_board(output.files["catalog_inventory.kicad_pcb"].decode())
    assert restored.board is not None and output.design.board is not None
    originals = {fp.lib_ref: fp for fp in output.design.board.footprints}
    assert set(originals) == {e.lib_id for e in entries}
    assert len(restored.board.footprints) == 100
    restored_nets = {n.id: n.name for n in restored.circuit.nets}
    original_nets = {n.id: n.name for n in output.design.circuit.nets}
    for fp in restored.board.footprints:
        original = originals[fp.lib_ref]
        assert (fp.position, fp.rotation, fp.side, fp.attributes) == (
            original.position,
            original.rotation,
            original.side,
            original.attributes,
        )
        for pad, expected in zip(fp.pads, original.pads, strict=True):
            assert (pad.number, pad.position, pad.size, pad.shape, pad.kind, pad.layers, pad.drill) == (
                expected.number,
                expected.position,
                expected.size,
                expected.shape,
                expected.kind,
                expected.layers,
                expected.drill,
            )
            assert restored_nets.get(pad.net_id) == original_nets.get(expected.net_id)
            if expected.padstack:
                assert pad.padstack is not None
                assert (pad.padstack.hole_length, pad.padstack.hole_rotation) == (
                    expected.padstack.hole_length,
                    expected.padstack.hole_rotation,
                )
        name = fp.lib_ref.removeprefix("Fenolite:")
        definition = read_footprint(
            output.files[f"lib/Fenolite.pretty/{name}.kicad_mod"].decode(), library="Fenolite"
        )
        assert definition.lib_id == fp.lib_ref
        assert definition.flags == get_footprint(fp.lib_ref).flags
