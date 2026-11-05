# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native ordinary fill caches across the import/build round trip (c0384 0.3, coordinator option A).

The authored two-sheet project's GND zone on B.Cu is given a fill flag and one filled polygon. A verified
import keeps them in ``native/fill.cache.json``; a build of the unchanged code carries them back exactly and
says so in ``preserved.native_fill_cache``; any copper edit, inside the zone or elsewhere on its layer,
drops the whole carrier with the reason, and the build still succeeds without fills."""

from __future__ import annotations

import json
from pathlib import Path

from _importcode import build, copy_project, imported

from fenolite.backends.kicad.sexpr import dumps, parse_bytes

FILL = '(filled_polygon (layer "B.Cu") (pts (xy 136 113) (xy 154 113) (xy 154 127) (xy 136 127)))'


def _filled(tmp_path: Path) -> Path:
    project = copy_project(tmp_path)
    board = project.with_suffix(".kicad_pcb")
    text = board.read_text(encoding="utf-8")
    old = "\t\t(fill\n\t\t\t(thermal_gap 0.5)"
    assert text.count(old) == 1
    text = text.replace(old, "\t\t(fill yes\n\t\t\t(thermal_gap 0.5)")
    start = text.index("(polygon", text.index('(name "GND")'))
    end = text.index("\n\t)\n", start)
    board.write_text(text[:end] + "\n\t\t" + FILL + text[end:], encoding="utf-8")
    return project


def _gnd_zone(board: Path) -> tuple[str, tuple[str, ...]]:
    root = parse_bytes(board.read_bytes())
    zones = [z for z in root.nodes("zone") if z.find("keepout") is None]
    assert len(zones) == 1
    fill = zones[0].nodes("fill")[0]
    return dumps(fill, style="compact"), tuple(
        dumps(f, style="compact") for f in zones[0].nodes("filled_polygon")
    )


def _imported(tmp_path: Path) -> Path:
    reply = imported(tmp_path, _filled(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    return tmp_path / "out"


def test_the_round_trip_keeps_the_source_fill_caches_as_native_carry_over(tmp_path: Path) -> None:
    out = _imported(tmp_path)
    carrier = json.loads((out / "native" / "fill.cache.json").read_bytes())
    assert carrier["origin"] == "native-carry-over" and carrier["fenolite_computed"] is False
    assert [row["fills"] for row in carrier["zones"]] == [[FILL]]
    reply = build(out)
    assert reply.exit_code == 0, reply.error
    assert reply.envelope["result"]["preserved"]["native_fill_cache"] == {
        "origin": "native-carry-over",
        "fenolite_computed": False,
        "status": "carried",
        "reason": None,
        "zones": 1,
        "fills": 1,
    }
    flag, fills = _gnd_zone(out / "built" / "two_sheet.kicad_pcb")
    source_flag, source_fills = _gnd_zone(tmp_path / "src" / "two_sheet.kicad_pcb")
    assert (flag, fills) == (source_flag, source_fills) and flag.startswith("(fill yes")


def _edit_copper(out: Path, old: str, new: str) -> None:
    copper = out / "copper.py"
    text = copper.read_text(encoding="utf-8")
    assert text.count(old) == 1
    copper.write_text(text.replace(old, new), encoding="utf-8")


def _dropped(out: Path) -> None:
    reply = build(out)
    assert reply.exit_code == 0, reply.error
    receipt = reply.envelope["result"]["preserved"]["native_fill_cache"]
    assert (receipt["status"], receipt["reason"], receipt["fills"]) == ("dropped", "board-changed", 0)
    flag, fills = _gnd_zone(out / "built" / "two_sheet.kicad_pcb")
    assert fills == () and not flag.startswith("(fill yes")  # today's no-cache board


def test_a_copper_edit_inside_the_zone_drops_the_carrier(tmp_path: Path) -> None:
    out = _imported(tmp_path)
    # a new GND track on B.Cu inside the zone outline (135..155 x 112..128; rows are relative to 100, 100)
    _edit_copper(
        out,
        "            (48_000_000, 34_000_000, 50_000_000, 33_000_000),\n        ),\n        locked=True,",
        "            (48_000_000, 34_000_000, 50_000_000, 33_000_000),\n"
        "            (40_000_000, 20_000_000, 44_000_000, 20_000_000),\n        ),\n        locked=True,",
    )
    _dropped(out)


def test_a_copper_edit_elsewhere_on_the_same_layer_drops_the_carrier(tmp_path: Path) -> None:
    out = _imported(tmp_path)
    # the last GND track on B.Cu, well outside the zone outline, ends 1 mm further right
    _edit_copper(
        out,
        "(48_000_000, 34_000_000, 50_000_000, 33_000_000),",
        "(48_000_000, 34_000_000, 51_000_000, 33_000_000),",
    )
    _dropped(out)


def test_a_missing_carrier_builds_the_ordinary_board(tmp_path: Path) -> None:
    out = _imported(tmp_path)
    (out / "native" / "fill.cache.json").unlink()
    reply = build(out)
    assert reply.exit_code == 0, reply.error
    assert "native_fill_cache" not in reply.envelope["result"]["preserved"]
    assert _gnd_zone(out / "built" / "two_sheet.kicad_pcb")[1] == ()


def test_unfilled_sources_write_no_carrier(tmp_path: Path) -> None:
    reply = imported(tmp_path, copy_project(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert not (tmp_path / "out" / "native" / "fill.cache.json").exists()
