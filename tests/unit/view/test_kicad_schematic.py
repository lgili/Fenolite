# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of a KiCad schematic sheet (capability native-themes, change c0178)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends.kicad.sch import opaque_wires, read_schematic
from fenolite.backends.kicad.schlayout import pin_point
from fenolite.view.kicad_schematic import SCHEMA, build_kicad_schematic_scene
from fenolite.view.themes import palette

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "kicad"
FLAT = DATA / "schematic" / "flat.kicad_sch"
SHEETS = [FLAT, DATA / "schematic" / "units.kicad_sch", DATA / "parity" / "agree" / "blink.kicad_sch"]


def _scene(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return build_kicad_schematic_scene(text, name=path.name, data=text.encode(), palette=palette("kicad"))


def _kinds(scene: dict[str, Any]) -> list[str]:
    return [obj["k"] for obj in scene["objects"]]


@pytest.mark.parametrize("path", SHEETS, ids=lambda p: p.name)
def test_counts_and_pin_points(path: Path) -> None:
    """Scenario "Counts and pin points of a KiCad sheet"."""
    sheet = read_schematic(path)
    scene = _scene(path)
    text = path.read_text(encoding="utf-8")
    kinds = _kinds(scene)
    assert scene["schema"] == SCHEMA and scene["kind"] == "schematic" and scene["sheet"]["text"] == "stroke"
    assert len(scene["comps"]) == len(sheet.symbols)
    assert kinds.count("wire") == len(opaque_wires(sheet))
    assert kinds.count("label") == len(sheet.labels)
    assert kinds.count("noerc") == len(sheet.no_connects)
    assert kinds.count("junction") == text.count("(junction")
    defs = {d.lib_id: d for d in sheet.lib_symbols} | {d.name: d for d in sheet.lib_symbols}
    starts = {
        (p["p"][0], p["p"][1])
        for p in scene["prims"]
        if p["k"] == "l" and p["o"] >= 0 and scene["objects"][p["o"]]["k"] == "pin"
    }
    expected = 0
    for symbol in sheet.symbols:
        definition = defs.get(symbol.lib_name) or defs.get(symbol.lib_ref)
        assert definition is not None
        for pin in definition.pins_of(symbol.unit, symbol.body_style):
            if pin.hidden:
                continue
            point = pin_point(symbol.position, pin.position, symbol.rotation // 1_000_000, symbol.mirror)
            expected += 1
            assert (round(point.x / 1000), round(point.y / 1000)) in starts, (symbol.ref, pin.number)
    assert kinds.count("pin") == expected
    meta = scene["meta"]
    assert meta["backend"] == "kicad" and meta["theme"] == "kicad" and len(meta["sha256"]) == 64
    json.dumps(scene)


def _on(x: int, y: int, flat: list[int]) -> bool:
    for i in range(0, len(flat) - 2, 2):
        x1, y1, x2, y2 = flat[i : i + 4]
        if (x2 - x1) * (y - y1) == (y2 - y1) * (x - x1) and min(x1, x2) <= x <= max(x1, x2):
            if min(y1, y2) <= y <= max(y1, y2):
                return True
    return False


def test_wires_carry_their_label_net() -> None:
    """Scenario "Wires carry their label's net"."""
    scene = _scene(FLAT)
    sheet = read_schematic(FLAT)
    wires = [k for k, obj in enumerate(scene["objects"]) if obj["k"] == "wire"]
    assert wires
    checked = 0
    for label in sheet.labels:
        x, y = round(label.position.x / 1000), round(label.position.y / 1000)
        under = {
            scene["objects"][p["o"]]["net"]
            for p in scene["prims"]
            if p["k"] == "l" and p["o"] in wires and _on(x, y, p["p"])
        }
        for net in under:
            assert scene["nets"][net]["name"] == label.name
            checked += 1
    assert checked > 0


def test_power_symbols_name_their_net() -> None:
    scene = _scene(FLAT)
    names = {net["name"] for net in scene["nets"]}
    assert {"VCC", "GND"} <= names
    assert all(not c["ref"].startswith("#") for c in scene["comps"] if not c.get("power"))


def test_palette_colours_the_sheet() -> None:
    mine = palette("kicad")
    mine["schematic"]["wire"] = "#123456"
    text = FLAT.read_text(encoding="utf-8")
    scene = build_kicad_schematic_scene(text, name=FLAT.name, palette=mine)
    colours = {p["c"] for p in scene["prims"] if p["o"] >= 0 and scene["objects"][p["o"]]["k"] == "wire"}
    assert colours == {"#123456"}
    assert scene["sheet"]["workspace"] == mine["schematic"]["background"]
