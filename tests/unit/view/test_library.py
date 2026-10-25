# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library scenes and the pad data of board scenes (capability library-viewer, change c0179)."""

from __future__ import annotations

import json
from pathlib import Path

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.model.library import Library
from fenolite.view.library import SCHEMA, footprint_library_scene, layer_kind, summary, symbol_library_scene
from fenolite.view.scene import build_scene

ROOT = Path(__file__).resolve().parents[3]
PCBLIB = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbLib"
SCHLIB = ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchLib"
PRETTY = ROOT / "tests" / "data" / "acceptance" / "board_40parts_t9" / "lib" / "Mini.pretty"
KICAD_SYM = ROOT / "tests" / "data" / "libs" / "Mini_v9.kicad_sym"
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _library(path: Path) -> Library:
    backend = registry.for_path(path)
    assert backend is not None
    content = backend.read(path).content
    assert isinstance(content, Library)
    return content


def _um(nm: int) -> int:
    return (nm + 500) // 1000


def test_footprints_of_an_altium_library() -> None:
    """Scenario "Footprints of an Altium library"."""
    library = _library(PCBLIB)
    scene = footprint_library_scene(PCBLIB)
    assert scene["schema"] == SCHEMA and scene["kind"] == "library" and scene["lib"] == "pcb"
    assert [item["name"] for item in scene["items"]] == [fp.name for fp in library.footprints]
    for item, fp in zip(scene["items"], library.footprints, strict=True):
        pads = item["scene"]["pads"]
        assert len(pads) == len(fp.pads) == item["pads"]
        for entry, pad in zip(
            sorted(pads, key=lambda p: (p["x"], p["y"])),
            sorted(fp.pads, key=lambda p: (p.position.x, p.position.y)),
            strict=True,
        ):
            assert (entry["w"], entry["h"], entry["drill"]) == (pad.size.w, pad.size.h, pad.drill)
            assert (entry["x"], entry["y"]) == (_um(pad.position.x), _um(pad.position.y))
            assert entry["shape"] == pad.shape
        assert item["scene"]["theme"]["name"] == "altium"
    assert summary(scene)["counts"]["items"] == len(library.footprints)
    json.dumps(scene)


def test_footprints_of_a_kicad_folder() -> None:
    scene = footprint_library_scene(PRETTY)
    names = sorted(p.stem for p in PRETTY.glob("*.kicad_mod"))
    assert sorted(item["name"] for item in scene["items"]) == names
    assert all(item["scene"]["theme"]["name"] == "kicad" for item in scene["items"])
    qfp = next(item for item in scene["items"] if "QFP" in item["name"])
    assert qfp["pads"] == 32 and qfp["courtyard_nm"] is not None and qfp["copper_nm"] is not None
    assert len(scene["meta"]["sha256"]) == 64


def test_symbols_of_both_tools() -> None:
    """Scenario "Symbols of both tools"."""
    for path in (SCHLIB, KICAD_SYM):
        library = _library(path)
        scene = symbol_library_scene(path)
        assert scene["lib"] == "schematic"
        names = {item["name"].split(" : ")[0] for item in scene["items"]}
        assert names == {symbol.name for symbol in library.symbols}, path.name
        for item in scene["items"]:
            base = item["name"].split(" : ")[0]
            symbol = next(s for s in library.symbols if s.name == base)
            unit = 1
            if " : " in item["name"]:
                unit = ord(item["name"][-1]) - ord("A") + 1
            if symbol.extends:
                continue
            visible = [p for p in symbol.pins_of(unit, 1) if not p.hidden]
            pins = [obj for obj in item["scene"]["objects"] if obj["k"] == "pin"]
            assert len(pins) == len(visible), item["name"]
    dual = [
        item for item in symbol_library_scene(KICAD_SYM)["items"] if item["name"].startswith("Mini_DualGate")
    ]
    assert len(dual) > 1


def test_board_pads() -> None:
    """Scenario "Pads of a KiCad board"."""
    backend = registry.for_path(BOARD)
    assert backend is not None and isinstance(backend, BoardFrame)
    design = backend.read(BOARD).design
    scene = build_scene(design, backend, name=BOARD.name)
    assert design.board is not None
    model = [pad for fp in design.board.footprints for pad in fp.pads]
    assert len(scene["pads"]) == len(model)
    sizes = sorted((p.size.w, p.size.h) for p in model)
    assert sorted((p["w"], p["h"]) for p in scene["pads"]) == sizes


def test_layer_kinds() -> None:
    assert [
        layer_kind(n)
        for n in ("F.Cu", "B.SilkS", "F.Mask", "B.Paste", "F.CrtYd", "F.Fab", "Edge.Cuts", "Mech.13", "X")
    ] == [
        "copper",
        "silkscreen",
        "soldermask",
        "solderpaste",
        "courtyard",
        "fabrication",
        "edge",
        "mechanical",
        "user",
    ]
