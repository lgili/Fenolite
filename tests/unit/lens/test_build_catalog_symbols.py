# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Offline use of new functional symbols with deliberate physical pad mapping."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from _buildhelp import resolver

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.catalog import get_footprint, get_symbol, list_entries
from fenolite.dsl import Design, Net, Part, connect, mm, placements, to_model
from fenolite.lens.build import build_design


@pytest.mark.parametrize("target", [9, 10])
def test_conceptual_transistor_and_button_roles_build_offline_with_exact_pad_maps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Offline symbol build attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert len(list_entries(kind="symbol")) == 49
    design = Design("symbol_mapping")
    design.board(mm(80), mm(50))
    # Public B/E/C package order differs from this generic B/C/E symbol.
    # SOT23 here is only a resolution fixture, not qualification of a purchasable part.
    transistor = Part(
        "Q1", "Fenolite:BJT_PNP", footprint="Fenolite:SOT23_3", pad_map={"1": "1", "2": "3", "3": "2"}
    )
    smd = Part(
        "SW1",
        "Fenolite:Pushbutton_NO",
        footprint="Fenolite:SW_Tact_Wurth_430181038816",
        pad_map={"1": "1", "2": "2", "3": "3", "4": "4"},
    )
    tht = Part(
        "SW2",
        "Fenolite:Pushbutton_NO",
        footprint="Fenolite:SW_Tact_Wurth_430186043716",
        pad_map={"1": "1", "2": "3", "3": "2", "4": "4"},
    )
    design.add(transistor, smd, tht)
    for i, part in enumerate((transistor, smd, tht)):
        part.place(mm(15 + 25 * i), mm(25))
    connect(Net("Base"), transistor["1"], smd["1"], smd["2"])
    connect(Net("Collector"), transistor["2"], smd["3"], smd["4"])
    connect(Net("Emitter"), transistor["3"], tht["1"], tht["2"])
    connect(Net("Return"), tht["3"], tht["4"])
    output = build_design(
        to_model(design),
        placements(design),
        name=design.name,
        copper=2,
        target=target,
        resolver=resolver(target, project_dir=tmp_path),
        authored_symbols={name: get_symbol(name) for name in ("Fenolite:BJT_PNP", "Fenolite:Pushbutton_NO")},
        authored_footprints={
            part.footprint: get_footprint(part.footprint) for part in (transistor, smd, tht)
        },
    )
    assert output.files and not output.issues
    restored = read_board(output.files["symbol_mapping.kicad_pcb"].decode())
    assert restored.board is not None
    net_names = {net.id: net.name for net in restored.circuit.nets}
    expected = (
        {"1": "Base", "2": "Emitter", "3": "Collector"},
        {"1": "Base", "2": "Base", "3": "Collector", "4": "Collector"},
        {"1": "Emitter", "2": "Return", "3": "Emitter", "4": "Return"},
    )
    for part, mapping in zip((transistor, smd, tht), expected, strict=True):
        footprint = next(fp for fp in restored.board.footprints if fp.lib_ref == part.footprint)
        assert {pad.number: net_names[pad.net_id] for pad in footprint.pads} == mapping
    symbols = read_symbol_library(output.files["lib/Fenolite.kicad_sym"].decode(), library="Fenolite")
    for symbol in symbols:
        original = get_symbol(symbol.lib_id)
        assert symbol.graphics == original.graphics
        assert [(p.number, p.name) for p in symbol.pins] == [(p.number, p.name) for p in original.pins]
        assert not symbol.properties.get("Footprint")


@pytest.mark.parametrize("name", ["BJT_NPN", "MOSFET_N_Channel", "Relay_SPDT", "Transformer"])
def test_generic_symbols_never_supply_a_default_package(tmp_path: Path, name: str) -> None:
    design = Design("unassigned")
    design.board(mm(30), mm(20))
    part = Part("X1", f"Fenolite:{name}")
    design.add(part)
    part.place(mm(15), mm(10))
    output = build_design(
        to_model(design),
        placements(design),
        name=design.name,
        copper=2,
        target=10,
        resolver=resolver(10, project_dir=tmp_path),
        authored_symbols={f"Fenolite:{name}": get_symbol(f"Fenolite:{name}")},
    )
    assert not output.files
    assert any(issue.code == "build.no-footprint" for issue in output.issues)
