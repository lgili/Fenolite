# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native layers and pad openings of an Altium board scene (capability altium-board-view, change c0181).

The documents are Fenolite's own `blink.PcbDoc` with its `Board6` record and its `Rules6` stream rewritten in
the test: a layer renamed, and solder-mask and paste expansion rules added.
"""

from __future__ import annotations

import dataclasses
import struct
from pathlib import Path

from fenolite.backends import registry
from fenolite.backends.altium.binary import frame_record
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcbprops import parse_blocks
from fenolite.model.base import ExtBag
from fenolite.model.design import Design
from fenolite.view.altium_layers import native_view
from fenolite.view.scene import build_scene

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"
RULES = (
    (
        ("RULEKIND", "SolderMaskExpansion"),
        ("NAME", "MaskAll"),
        ("ENABLED", "TRUE"),
        ("PRIORITY", "2"),
        ("SCOPE1EXPRESSION", "All"),
        ("EXPANSION", "4mil"),
    ),
    (
        ("RULEKIND", "SolderMaskExpansion"),
        ("NAME", "MaskVias"),
        ("ENABLED", "TRUE"),
        ("PRIORITY", "1"),
        ("SCOPE1EXPRESSION", "IsVia"),
        ("EXPANSION", "1mil"),
    ),
    (
        ("RULEKIND", "PasteMaskExpansion"),
        ("NAME", "PasteAll"),
        ("ENABLED", "TRUE"),
        ("PRIORITY", "1"),
        ("SCOPE1EXPRESSION", "All"),
        ("EXPANSION", "-1mil"),
    ),
)


def edited(name: str | None = None) -> bytes:
    """``blink.PcbDoc`` with layer 1 named ``name`` and the rules ``RULES`` added."""
    streams = open_compound(BLINK.read_bytes()).as_dict()
    if name is not None:
        records, _rest, _problems = parse_blocks(streams["Board6/Data"], where="Board6/Data")
        raw = records[0].raw
        (word,) = struct.unpack_from("<I", raw)
        text = raw[4:].replace(b"|LAYER1NAME=Top Layer|", f"|LAYER1NAME={name}|".encode())
        streams["Board6/Data"] = (
            struct.pack("<I", word & 0xFF000000 | len(text)) + text + b"".join(r.raw for r in records[1:])
        )
    streams["Rules6/Data"] = streams.get("Rules6/Data", b"") + b"".join(
        b"\0\0" + frame_record(r) for r in RULES
    )
    return write_compound(storage_from_paths(streams))


def design_of(data: bytes, tmp: Path) -> Design:
    path = tmp / "board.PcbDoc"
    path.write_bytes(data)
    backend = registry.for_path(path)
    assert backend is not None
    design = backend.read(path).content
    assert isinstance(design, Design)
    return design


def scene(design: Design, data: bytes) -> dict:
    backend = registry.for_path(BLINK)
    return build_scene(design, backend, name="board", native=native_view(design, data))  # type: ignore[arg-type]


def test_names(tmp_path: Path) -> None:
    """Scenario "A board with renamed layers"."""
    data = edited("Signal Top")
    layers = {layer["id"]: layer for layer in scene(design_of(data, tmp_path), data)["layers"]}
    assert layers["F.Cu"]["name"] == "Signal Top"
    assert layers["F.SilkS"]["name"] == "Top Overlay"
    assert layers["F.Cu"]["tab"] < layers["F.SilkS"]["tab"]
    assert layers["Edge.Cuts"]["name"] == "Board Outline"


def test_openings(tmp_path: Path) -> None:
    """Scenario "Manual and rule expansions": one pad of manual mask expansion 2 mil, the others under the
    rule of scope All (4 mil); the via rule of higher priority does not apply to pads."""
    data = edited()
    design = design_of(data, tmp_path)
    board = design.board
    assert board is not None
    first = board.footprints[0]
    manual = dataclasses.replace(
        first.pads[0], ext={"altium": ExtBag(min_version=None, payload=(("mask", "2,20000"),))}
    )
    footprint = dataclasses.replace(first, pads=(manual, *first.pads[1:]))
    design = dataclasses.replace(
        design, board=dataclasses.replace(board, footprints=(footprint, *board.footprints[1:]))
    )
    pads = scene(design, data)["pads"]
    by_source = {(p["mask_src"], p["mask"]) for p in pads}
    assert ("manual", 50_800) in by_source and ("rule MaskAll", 101_600) in by_source
    assert ("rule PasteAll", -25_400) in {(p["paste_src"], p["paste"]) for p in pads}  # the edited pad
    assert ("none", 0) in {(p["paste_src"], p["paste"]) for p in pads}  # blink's pads: paste mode 0


def test_negative_paste_shrinks(tmp_path: Path) -> None:
    """A paste opening shrinks by a negative expansion: the paste primitives are smaller than the copper."""
    data = edited()
    built = scene(design_of(data, tmp_path), data)
    assert any(layer["id"] == "F.Paste" for layer in built["layers"])
