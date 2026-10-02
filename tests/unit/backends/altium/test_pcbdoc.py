# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium PCB document writer (change c0035, capability altium-pcb-writer, "PCB document file",
"PCB document placement", "PCB document links and nets")."""

from __future__ import annotations

import struct
from functools import cache

from _altium import blink_pcbdoc_spec
from _altium_pcb_read import PcbDoc, read_pcbdoc

from fenolite.backends.altium.pcbdoc import EMPTY_STORAGES, PcbDocSpec, degrees_text, write_pcbdoc

STORAGES = ("Board6", "Nets6", "Components6", "Pads6", "Tracks6", "Arcs6", "Texts6", "WideStrings6")


@cache
def blink_doc() -> tuple[PcbDoc, PcbDocSpec]:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    return read_pcbdoc(write_pcbdoc(spec)), spec


# --- 4.1: headers, board, nets --------------------------------------------------------------------


def test_storages_of_the_sample() -> None:
    """Scenario "Storages of the sample": root streams and 20 storages, counts equal, empty ones empty."""
    doc, _spec = blink_doc()
    assert sorted(doc.storages) == sorted((*STORAGES, *EMPTY_STORAGES)) and len(doc.storages) == 20
    for name in EMPTY_STORAGES:
        assert doc.storages[name] == (0, b"")
    assert doc.file_header == struct.pack("<I", 19) + "PCB 5.0 Bi".encode("utf-16-le")
    assert doc.file_header_six == struct.pack("<IB", 19, 19) + b"PCB 6.0 Binary File" + struct.pack(
        "<d", 5.01
    )


def test_two_layer_stack() -> None:
    """Scenario "Two-layer stack": NEXT from 1 gives 32, then 0; five outline vertices, closed."""
    doc, _spec = blink_doc()
    board = doc.board
    layer, walk = 1, []
    while layer:
        walk.append(layer)
        layer = int(board[f"LAYER{layer}NEXT"])
    assert walk == [1, 32] and board["LAYER32PREV"] == "1"
    assert board["LAYER1NAME"] == "Top Layer" and board["LAYER74NAME"] == "Multi-Layer"
    assert all(f"LAYER{i}NAME" in board for i in range(1, 75)) and "LAYER75NAME" not in board
    assert [board[f"LAYER{i}MECHENABLED"] for i in (69, 70, 71, 72)] == ["TRUE"] * 4
    vertices = [(board[f"VX{k}"], board[f"VY{k}"]) for k in range(5)]
    assert (
        "VX5" not in board
        and vertices[0] == vertices[-1]
        and [board[f"KIND{k}"] for k in range(5)] == ["0"] * 5
    )
    assert vertices[0] == ("1000mil", "1000mil") or ("1000mil", "1000mil") in vertices
    assert board["ORIGINX"] == board["ORIGINY"] == "1000mil"
    assert board["KIND"] == "Protel_Advanced_PCB" and board["VERSION"] == "5.00"


def test_nets_in_name_order() -> None:
    doc, _spec = blink_doc()
    assert [n["NAME"] for n in doc.nets] == ["GND", "LED_A", "LED_DRV", "VIN"]


def test_bytes_depend_only_on_the_spec() -> None:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    assert write_pcbdoc(spec) == write_pcbdoc(spec)


def test_degrees_text() -> None:
    assert [degrees_text(u) for u in (0, 90_000_000, 12_500_000, -90_000_000, 1)] == [
        "0", "90", "12.5", "270", "0.000001",
    ]  # fmt: skip
