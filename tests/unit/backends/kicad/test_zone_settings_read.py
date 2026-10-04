# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone settings are read (capability kicad-file-backend, "Zone settings are read" and the MODIFIED
"Zones, fills and rule areas"; change c0031)."""

from __future__ import annotations

from _boards import FIXTURE, SQUARE, board, rt1_problems, zone

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.pcb import ZONE_SETTING_FIELDS, read_board
from fenolite.backends.kicad.sexpr import Node, parse_fragment
from fenolite.core.errors import Issue
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.board import Keepout, Zone, ZoneHatch, ZoneSettings

TEN = 20260206
NINE = 20241229
KEPT = "kicad.board.kept-opaque"


def read(*zones: str, version: int = NINE) -> tuple[tuple[Zone, ...], tuple[Keepout, ...], list[Issue]]:
    issues: list[Issue] = []
    nets = None if version > NINE else ("", "A", "B")
    text = board(*zones, version=version, nets=nets)
    if nets is None:
        text = text.replace('(net 1) (net_name "A")', '(net "A")')
    design = read_board(text, issues=issues)
    assert design.board is not None
    assert rt1_problems(text, design) == []
    return design.board.zones, design.board.keepouts, issues


def setting_slots(entity: Zone | Keepout) -> dict[str, Slot]:
    """The slot of each setting child of a zone, by head."""
    out: dict[str, Slot] = {}
    fields = {field: head for head, field in ZONE_SETTING_FIELDS.items()}
    for slot in slotlib.from_ext(entity.ext["kicad"]):
        if isinstance(slot, Modeled):
            if slot.field in fields:
                out[fields[slot.field]] = slot
            continue
        node = parse_fragment(slot.fragment)
        if isinstance(node, Node) and node.name in ZONE_SETTING_FIELDS:
            out[node.name] = slot
    return out


def kinds(entity: Zone | Keepout) -> dict[str, str]:
    return {head: type(slot).__name__ for head, slot in setting_slots(entity).items()}


def kept(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.code == KEPT]


def test_ten_format_pour() -> None:
    settings = (
        "(connect_pads yes (clearance 0.3)) (min_thickness 0.2) (fill yes (thermal_gap 0.4)"
        " (thermal_bridge_width 0.35) (island_removal_mode 2) (island_area_min 2.5))"
    )
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=settings), version=TEN)
    assert found.settings == ZoneSettings(
        connection="solid",
        clearance=300_000,
        min_thickness=200_000,
        thermal_gap=400_000,
        thermal_spoke_width=350_000,
        island_removal="below_area",
        min_island_area=2_500_000_000_000,
    )
    assert found.filled is True
    assert kinds(found) == {"connect_pads": "Modeled", "min_thickness": "Modeled", "fill": "Modeled"}
    assert kept(issues) == []


def test_nine_format_island_forms() -> None:
    base = "(connect_pads (clearance 0.5)) (min_thickness 0.25) "
    first = zone(
        1,
        inner=SQUARE,
        settings=base + "(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)"
        " (island_removal_mode 1) (island_area_min 5))",
    )
    second = zone(
        2,
        inner=SQUARE,
        settings=base + "(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))",
    )
    (a, b), _, issues = read(first, second)
    assert a.settings.island_removal == "never" and a.settings.min_island_area == 5_000_000_000_000
    assert kinds(a)["fill"] == "Modeled"
    assert b.settings.island_removal == "always" and b.filled is True
    assert kinds(b)["fill"] == "Opaque"
    (info,) = kept(issues)
    assert info.where.endswith("/zone[1]/fill[0]")


def test_hatched_fill() -> None:
    fill = (
        "(fill yes (mode hatch) (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0)"
        " (hatch_thickness 0.8) (hatch_gap 1.2) (hatch_orientation 45)"
        " (hatch_border_algorithm min_thickness) (hatch_min_hole_area 0.3))"
    )
    settings = f"(connect_pads (clearance 0.5)) (min_thickness 0.25) {fill}"
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=settings), version=TEN)
    assert found.settings.fill_mode == "hatched"
    assert found.settings.hatch == ZoneHatch(
        thickness=800_000, gap=1_200_000, orientation=45_000_000, border="min_thickness", min_hole_area="0.3"
    )
    assert kinds(found)["fill"] == "Modeled" and kept(issues) == []


def test_unknown_fill_child() -> None:
    settings = (
        "(connect_pads (clearance 0.5)) (min_thickness 0.25)"
        " (fill yes (thermal_gap 0.6) (thermal_bridge_width 0.5) (frobnicate 1))"
    )
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=settings), version=TEN)
    assert found.settings.thermal_gap == 600_000 and found.filled is True
    assert kinds(found) == {"connect_pads": "Modeled", "min_thickness": "Modeled", "fill": "Opaque"}
    (info,) = kept(issues)
    assert "frobnicate" in info.message and info.where.endswith("/zone[0]/fill[0]")


def test_settings_absent() -> None:
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=""))
    assert found.settings == ZoneSettings() and found.filled is False and found.locked is False
    assert setting_slots(found) == {} and kept(issues) == []


def test_locked_zone() -> None:
    (found,), _, issues = read(zone(1, inner=SQUARE, head="(locked yes)"), version=TEN)
    assert found.locked is True
    assert kinds(found)["locked"] == "Modeled" and kept(issues) == []


def test_locked_no_is_projected() -> None:
    (found,), _, issues = read(zone(1, inner=SQUARE, head="(locked no)"), version=TEN)
    assert found.locked is False
    assert kinds(found)["locked"] == "Opaque" and len(kept(issues)) == 1


def test_repeated_child_stays_opaque() -> None:
    settings = "(connect_pads (clearance 0.5)) (min_thickness 0.2) (min_thickness 0.3)"
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=settings))
    assert found.settings.min_thickness == 200_000
    slots = [
        s
        for s in slotlib.from_ext(found.ext["kicad"])
        if isinstance(s, Opaque) and s.fragment.startswith("(min_thickness")
    ]
    assert [s.fragment for s in slots] == ["(min_thickness 0.2)", "(min_thickness 0.3)"]
    assert "min_thickness" not in {
        s.field for s in slotlib.from_ext(found.ext["kicad"]) if isinstance(s, Modeled)
    }
    assert len(kept(issues)) == 2 and all("repeated" in i.message for i in kept(issues))


def test_unknown_connection_atom() -> None:
    settings = "(connect_pads sometimes (clearance 0.3)) (min_thickness 0.25)"
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=settings))
    assert found.settings.connection == "thermal" and found.settings.clearance == 300_000
    assert kinds(found)["connect_pads"] == "Opaque" and len(kept(issues)) == 1


def test_inexact_length_follows_exact_numbers() -> None:
    settings = "(connect_pads (clearance 0.5)) (min_thickness 0.2500001)"
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=settings))
    assert found.settings.min_thickness == 250_000  # the default: the value could not be read
    assert kinds(found)["min_thickness"] == "Opaque"
    assert [i.code for i in issues if i.code.startswith("kicad.board.")] == ["kicad.board.inexact-length"]


def test_inexact_area_is_kept_opaque() -> None:
    settings = (
        "(connect_pads (clearance 0.5)) (min_thickness 0.25)"
        " (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 2)"
        " (island_area_min 0.0000000000001))"
    )
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=settings), version=TEN)
    assert found.settings.island_removal == "below_area"
    assert found.settings.min_island_area == ZoneSettings().min_island_area
    assert kinds(found)["fill"] == "Opaque" and len(kept(issues)) == 1


def test_spelling_is_kept_as_written() -> None:
    settings = "(connect_pads (clearance 0.50)) (min_thickness 0.25)"
    (found,), _, issues = read(zone(1, inner=SQUARE, settings=settings))
    assert found.settings.clearance == 500_000
    assert kinds(found) == {"connect_pads": "Opaque", "min_thickness": "Modeled"}
    assert len(kept(issues)) == 1


def test_other_children_stay_opaque() -> None:
    inner = f'(attr (island yes)) (placement (enabled no) (sheetname "/")) {SQUARE}'
    settings = "(connect_pads (clearance 0.5)) (min_thickness 0.25) (filled_areas_thickness no)"
    (found,), _, _ = read(zone(1, inner=inner, settings=settings))
    fragments = [s.fragment for s in slotlib.from_ext(found.ext["kicad"]) if isinstance(s, Opaque)]
    for head in ("hatch", "filled_areas_thickness", "attr", "placement", "net_name"):
        assert any(f.startswith(f"({head} ") for f in fragments), head


def test_settings_of_the_authored_zone() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    (found,) = design.board.zones
    assert found.name == "GND_B"
    assert found.settings == ZoneSettings() and found.filled is True and found.locked is False
    assert kinds(found) == {"connect_pads": "Modeled", "min_thickness": "Modeled", "fill": "Modeled"}
    (area,) = design.board.keepouts
    assert set(kinds(area).values()) == {"Opaque"}
    assert {"connect_pads", "min_thickness"} <= set(kinds(area))


def test_rule_area_keeps_its_children_opaque() -> None:
    keepout = (
        "(keepout (tracks not_allowed) (vias allowed) (pads allowed) (copperpour allowed)"
        " (footprints allowed))"
    )
    settings = (
        "(connect_pads yes (clearance 0)) (min_thickness 0.25)"
        " (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))"
    )
    zones, (area,), issues = read(
        zone(1, inner=f"{keepout} {SQUARE}", net="(net 0)", settings=settings, head="(locked yes)").replace(
            '(net_name "A")', '(net_name "")'
        )
    )
    assert zones == ()
    assert kinds(area) == {
        "locked": "Opaque", "connect_pads": "Opaque", "min_thickness": "Opaque", "fill": "Opaque"
    }  # fmt: skip
    assert kept(issues) == []
