# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script zones merged with the zones of an existing board (capability layout-lens, "Zones declared in
the script"; ``backends/kicad/zones.merge_zones``; change c0031)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest
from _boards import square

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.backends.kicad.zones import (
    MERGE_ISSUE_CODES,
    OVERRIDE_HINT,
    ZoneMerge,
    merge_zones,
    script_zone_uuid,
)
from fenolite.core.ids import derived_id
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import Net as DslNet
from fenolite.dsl import mm, to_model
from fenolite.model.board import Zone, ZoneFill, ZoneHatch, ZoneSettings
from fenolite.model.circuit import Circuit, Net
from fenolite.model.design import Design

NETS = ("GND", "VIN")
DRAWN_UUID = "00000000-0000-4000-8000-0000000000a1"


def net_id(name: str) -> str:
    return derived_id("net", "dsl", f"net:{name}")


def script_zone(name: str = "GND", net: str | None = "GND", **changes: object) -> Zone:
    zone = Zone(
        id=derived_id("zon", "dsl", f"zone:{name}"),
        outline=square(100, 100, 150, 130),
        name=name,
        layers=("B.Cu",),
        net_id=net_id(net) if net is not None else None,
        settings=ZoneSettings(clearance=300_000, connection="solid"),
    )
    return dataclasses.replace(zone, **changes)  # type: ignore[arg-type]


def built(*zones: Zone, nets: tuple[str, ...] = NETS) -> Design:
    design = Design.new("merge", seed=1)
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=created_layers(2), zones=zones)
    circuit = Circuit(nets=tuple(Net(id=net_id(n), name=n) for n in nets))
    return dataclasses.replace(design, circuit=circuit, board=board)


def on_board(*zones: Zone, nets: tuple[str, ...] = NETS) -> Design:
    """The board that a build of these zones wrote, read back (its nets have the reader's ids)."""
    return read_board(write_board(built(*zones, nets=nets), target=10).text)


def edit(board: Design, zone_name: str, /, **changes: object) -> Design:
    assert board.board is not None
    (zone,) = [z for z in board.board.zones if z.name == zone_name]
    return board.replace_entity(dataclasses.replace(zone, **changes))  # type: ignore[arg-type]


def board_zone(board: Design, name: str) -> Zone:
    assert board.board is not None
    (zone,) = [z for z in board.board.zones if z.name == name]
    return zone


def codes(merge: ZoneMerge) -> list[tuple[str, str]]:
    return [(i.code, i.severity) for i in merge.issues]


# -- scenarios (also run by the closed-set test)


def unchanged() -> ZoneMerge:
    return merge_zones(built(script_zone()), on_board(script_zone()))


def overridden() -> ZoneMerge:
    board = edit(on_board(script_zone()), "GND", settings=ZoneSettings(clearance=500_000, connection="solid"))
    return merge_zones(built(script_zone()), board)


def forced() -> ZoneMerge:
    board = edit(
        on_board(script_zone()),
        "GND",
        settings=ZoneSettings(clearance=500_000, connection="solid"),
        fills=(ZoneFill("B.Cu", square(101, 101, 149, 129)),),
        filled=True,
    )
    return merge_zones(built(script_zone(locked=True)), board)


def orphan() -> ZoneMerge:
    return merge_zones(built(script_zone()), on_board(script_zone(), script_zone("VIN_TOP", "VIN")))


SCENARIOS: tuple[Callable[[], ZoneMerge], ...] = (unchanged, overridden, forced, orphan)


def test_unchanged_zone_is_kept_without_an_issue() -> None:
    merge = unchanged()
    (zone,) = merge.zones
    assert merge.issues == () and merge.kept == ("GND",)
    assert (merge.forced, merge.added, merge.removed) == ((), (), ())
    assert zone.id in merge.decided and zone.net_id == net_id("GND")
    assert slotlib.from_ext(zone.ext["kicad"])  # the board's zone, with its slots


def test_the_board_wins() -> None:
    merge = overridden()
    (zone,) = merge.zones
    assert zone.settings.clearance == 500_000 and merge.kept == ("GND",)
    (issue,) = merge.issues
    assert (issue.code, issue.severity, issue.where) == ("kicad.zone.overridden", "info", "GND")
    assert "GND" in issue.message and "settings" in issue.message and issue.hint == OVERRIDE_HINT


@pytest.mark.parametrize(
    ("what", "changes"),
    [
        ("outline", {"outline": square(100, 100, 140, 130)}),
        ("layers", {"layers": ("F.Cu",)}),
        ("priority", {"priority": 2}),
        ("locked", {"locked": True}),
        ("settings", {"settings": ZoneSettings(clearance=300_000)}),
    ],
)
def test_each_compared_value_is_named(what: str, changes: dict[str, object]) -> None:
    merge = merge_zones(built(script_zone()), edit(on_board(script_zone()), "GND", **changes))
    (issue,) = merge.issues
    assert issue.code == "kicad.zone.overridden" and f"script's {what} differ" in issue.message
    (zone,) = merge.zones
    assert all(getattr(zone, name) == value for name, value in changes.items())


def test_net_changed_on_the_board() -> None:
    board = on_board(script_zone())
    vin = board.nets_by_name.get("VIN")
    if vin is None:  # a net without a reference is not in a ten-format board: give the board one
        board = on_board(script_zone(), script_zone("VIN_TOP", "VIN"))
        vin = board.nets_by_name["VIN"]
    merge = merge_zones(
        built(script_zone(), script_zone("VIN_TOP", "VIN")), edit(board, "GND", net_id=vin.id)
    )
    (issue,) = merge.issues
    assert "script's net differ" in issue.message
    assert merge.zones[0].net_id == net_id("VIN")  # the built design's net of the board zone's net name


def test_values_without_effect_are_not_a_difference() -> None:
    idle = ZoneSettings(clearance=300_000, connection="solid", hatch=ZoneHatch(gap=2_000_000))
    merge = merge_zones(built(script_zone(settings=idle)), on_board(script_zone()))
    assert merge.issues == ()


def test_a_locked_zone_wins() -> None:
    merge = forced()
    (zone,) = merge.zones
    assert merge.forced == ("GND",) and merge.kept == ()
    assert zone.settings.clearance == 300_000 and zone.locked is True
    assert zone.fills == (ZoneFill("B.Cu", square(101, 101, 149, 129)),) and zone.filled is True
    assert "kicad" not in zone.ext and zone.id in merge.decided  # the script's zone, written as created
    (issue,) = merge.issues
    assert (issue.code, issue.severity, issue.where) == ("kicad.zone.forced", "warning", "GND")
    assert "settings" in issue.message and "locked" in issue.message


def test_a_locked_zone_equal_to_the_board_is_kept() -> None:
    locked = script_zone(locked=True)
    merge = merge_zones(built(locked), on_board(locked))
    assert merge.issues == () and merge.kept == ("GND",) and merge.forced == ()
    assert slotlib.from_ext(merge.zones[0].ext["kicad"])


def test_new_zones_are_added_in_name_order() -> None:
    wanted = (script_zone("ZED", "VIN"), script_zone(), script_zone("ALPHA", "VIN"))
    merge = merge_zones(built(*wanted), on_board(script_zone()))
    assert [z.name for z in merge.zones] == ["GND", "ALPHA", "ZED"]
    assert merge.added == ("ALPHA", "ZED") and merge.issues == ()
    assert {z.id for z in merge.zones} == merge.decided


def test_zone_removed_from_the_script() -> None:
    merge = orphan()
    assert [z.name for z in merge.zones] == ["GND"] and merge.removed == ("VIN_TOP",)
    (issue,) = merge.issues
    assert (issue.code, issue.severity, issue.where) == ("kicad.zone.orphan", "warning", "VIN_TOP")
    assert script_zone_uuid("VIN_TOP") in issue.message


def test_zone_drawn_in_kicad_is_not_the_scripts() -> None:
    drawn = dataclasses.replace(
        script_zone(), id=derived_id("zon", "kicad", DRAWN_UUID), native_ids={"kicad": DRAWN_UUID}
    )
    board = on_board(script_zone(), drawn)
    assert [z.name for z in board.board.zones] == ["GND", "GND"]  # type: ignore[union-attr]
    merge = merge_zones(built(script_zone()), board)
    assert len(merge.zones) == 2 and merge.issues == ()
    kept, other = merge.zones
    assert kept.id in merge.decided and other.id not in merge.decided
    assert other.native_ids == {"kicad": DRAWN_UUID} and other == board.board.zones[1]  # type: ignore[union-attr]
    # and it is not an orphan when the script declares no zone at all
    alone = merge_zones(built(), board)
    assert [z.native_ids["kicad"] for z in alone.zones] == [DRAWN_UUID]
    assert [i.code for i in alone.issues] == ["kicad.zone.orphan"] and alone.removed == ("GND",)


def test_names_alone_do_not_match() -> None:
    drawn = dataclasses.replace(
        script_zone(), id=derived_id("zon", "kicad", DRAWN_UUID), native_ids={"kicad": DRAWN_UUID}
    )
    merge = merge_zones(built(script_zone()), on_board(drawn))
    assert [z.native_ids.get("kicad") for z in merge.zones] == [DRAWN_UUID, None]
    assert merge.added == ("GND",) and merge.kept == () and merge.issues == ()


def test_zone_renamed_in_kicad_is_kept() -> None:
    board = edit(on_board(script_zone()), "GND", name="GND_MINE")
    merge = merge_zones(built(), board)
    assert [z.name for z in merge.zones] == ["GND_MINE"] and merge.issues == () and merge.removed == ()
    assert merge.decided == frozenset()
    # while the script still declares it, the uuid matches and the board's name is not compared
    again = merge_zones(built(script_zone()), board)
    assert again.kept == ("GND",) and again.issues == () and again.zones[0].name == "GND_MINE"


def test_zone_without_a_net() -> None:
    floating = script_zone("FLOATING", None)
    merge = merge_zones(built(floating), on_board(floating))
    assert merge.issues == () and merge.zones[0].net_id is None


def test_kept_zone_whose_net_left_the_design_takes_the_scripts_net() -> None:
    board = on_board(script_zone(net="VIN"), nets=NETS)
    merge = merge_zones(built(script_zone(), nets=("GND",)), board)
    (zone,) = merge.zones
    assert zone.net_id == net_id("GND")
    assert [i.code for i in merge.issues] == ["kicad.zone.overridden"]


def test_merge_is_pure_and_idempotent() -> None:
    wanted, board = built(script_zone(), script_zone("VIN_TOP", "VIN")), on_board(script_zone())
    first = merge_zones(wanted, board)
    assert merge_zones(wanted, board) == first
    written = dataclasses.replace(wanted, board=dataclasses.replace(wanted.board, zones=first.zones))  # type: ignore[arg-type]
    again = merge_zones(wanted, read_board(write_board(written, target=10).text))
    assert again.issues == () and again.kept == ("GND", "VIN_TOP") and again.added == ()


def test_designs_without_a_board() -> None:
    empty = dataclasses.replace(built(script_zone()), board=None)
    assert merge_zones(empty, on_board(script_zone())).removed == ("GND",)
    assert merge_zones(built(script_zone()), empty).added == ("GND",)


def test_script_zone_uuid_is_the_writers_uuid() -> None:
    d = DslDesign("pin")
    d.board(mm(50), mm(30))
    d.zone(DslNet("GND"), layers=("B.Cu",))
    (zone,) = to_model(d).board.zones  # type: ignore[union-attr]
    assert script_zone_uuid("GND") == kicad_uuid(zone)
    assert script_zone_uuid("GND") == kicad_uuid(script_zone())
    assert script_zone_uuid("GND") != script_zone_uuid("GND_BOTTOM")


def test_closed_set() -> None:
    produced: dict[str, str] = {}
    for scenario in SCENARIOS:
        produced.update(dict(codes(scenario())))
    assert produced == dict(MERGE_ISSUE_CODES)
    assert dict(MERGE_ISSUE_CODES) == {
        "kicad.zone.forced": "warning",
        "kicad.zone.orphan": "warning",
        "kicad.zone.overridden": "info",
    }
