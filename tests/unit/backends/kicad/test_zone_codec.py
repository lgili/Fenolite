# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The zone settings codec (``backends/kicad/zones.py``; change c0031): every form that
``docs/formats/kicad/board.md`` lists round-trips through ``project_settings`` and ``emit_settings`` for
its major, and what the emitter does not write does not."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import zones
from fenolite.backends.kicad.sexpr import Node, dumps, parse_fragment
from fenolite.model.board import ZoneHatch, ZoneSettings


def nodes(text: str) -> list[Node]:
    wrapped = parse_fragment(f"(x {text})")
    assert isinstance(wrapped, Node)
    return list(wrapped.nodes())


def emitted(read: zones.SettingsRead, major: int) -> str:
    children = zones.emit_settings(read.settings, filled=read.filled, locked=read.locked, major=major)
    return " ".join(dumps(child, style="compact") for child in children.values())


HATCH_FULL = (
    "(fill yes (mode hatch) (thermal_gap 0.5) (thermal_bridge_width 0.5) (smoothing fillet) (radius 0.5)"
    " (island_removal_mode 2) (island_area_min 2.5) (hatch_thickness 0.8) (hatch_gap 1.2)"
    " (hatch_orientation 45) (hatch_smoothing_level 1) (hatch_smoothing_value 0.1)"
    " (hatch_border_algorithm min_thickness) (hatch_min_hole_area 0.3))"
)
FORMS: list[tuple[int, str]] = [
    # the 10.0.6 re-save of a zone without setting children (H-K-ZONE-DEFAULTS)
    (
        10,
        "(connect_pads (clearance 0.5)) (min_thickness 0.25)"
        " (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))",
    ),
    # the same zone as 9.0 writes it: no island child for mode 0
    (
        9,
        "(connect_pads (clearance 0.5)) (min_thickness 0.25)"
        " (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))",
    ),
    (10, "(connect_pads yes (clearance 0.3)) (min_thickness 0.2) (fill yes (thermal_gap 0.4)"
         " (thermal_bridge_width 0.35) (island_removal_mode 2) (island_area_min 2.5))"),
    (10, "(connect_pads no (clearance 0)) (min_thickness 0.25)"
         " (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 1))"),
    (10, "(connect_pads thru_hole_only (clearance 0.508)) (min_thickness 0.254)"
         " (fill yes (thermal_gap 0.508) (thermal_bridge_width 0.508) (island_removal_mode 0))"),
    (9, "(connect_pads (clearance 0.5)) (min_thickness 0.25)"
        " (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 1)"
        " (island_area_min 5))"),
    (9, "(connect_pads (clearance 0.5)) (min_thickness 0.25)"
        " (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 2)"
        " (island_area_min 10))"),
    (10, "(connect_pads (clearance 0.5)) (min_thickness 0.25) (fill yes (thermal_gap 0.5)"
         " (thermal_bridge_width 0.5) (smoothing chamfer) (radius 1) (island_removal_mode 0))"),
    (10, "(connect_pads (clearance 0.5)) (min_thickness 0.25) (fill yes (mode hatch) (thermal_gap 0.5)"
         " (thermal_bridge_width 0.5) (island_removal_mode 0) (hatch_thickness 1) (hatch_gap 1.5)"
         " (hatch_orientation 0) (hatch_border_algorithm hatch_thickness) (hatch_min_hole_area 0.15))"),
    (10, f"(connect_pads (clearance 0.5)) (min_thickness 0.25) {HATCH_FULL}"),
    (9, f"(connect_pads (clearance 0.5)) (min_thickness 0.25) {HATCH_FULL}"),
    (10, "(locked yes) (connect_pads (clearance 0.5)) (min_thickness 0.25)"
         " (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))"),
]  # fmt: skip


@pytest.mark.parametrize(("major", "text"), FORMS)
def test_forms_round_trip(major: int, text: str) -> None:
    read = zones.project_settings(nodes(text), major=major)
    assert read.reasons == {} and read.inexact == frozenset()
    assert emitted(read, major) == text


def test_values_of_the_ten_format_pour() -> None:
    read = zones.project_settings(nodes(FORMS[2][1]), major=10)
    assert read.settings == ZoneSettings(
        connection="solid",
        clearance=300_000,
        min_thickness=200_000,
        thermal_gap=400_000,
        thermal_spoke_width=350_000,
        island_removal="below_area",
        min_island_area=2_500_000_000_000,
    )
    assert read.filled is True and read.locked is False


def test_values_of_the_full_hatch() -> None:
    read = zones.project_settings(nodes(HATCH_FULL), major=10)
    assert read.settings.fill_mode == "hatched"
    assert read.settings.smoothing == "fillet" and read.settings.smoothing_radius == 500_000
    assert read.settings.hatch == ZoneHatch(
        thickness=800_000,
        gap=1_200_000,
        orientation=45_000_000,
        smoothing_level=1,
        smoothing_value="0.1",
        border="min_thickness",
        min_hole_area="0.3",
    )


def test_nine_format_mode_zero_is_not_reproduced() -> None:
    text = "(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))"
    read = zones.project_settings(nodes(text), major=9)
    assert read.reasons == {} and read.settings == ZoneSettings() and read.filled
    assert "island_removal_mode" not in emitted(read, 9)
    assert text in emitted(read, 10)


def test_absent_children_give_the_defaults() -> None:
    read = zones.project_settings(nodes("(hatch edge 0.5) (priority 2)"), major=10)
    assert read == zones.SettingsRead(ZoneSettings(), False, False, {})
    assert emitted(read, 10) == FORMS[0][1]


def test_defaults_of_a_created_zone_per_target() -> None:
    nine = zones.emit_settings(ZoneSettings(), filled=False, locked=False, major=9)
    assert list(nine) == ["connect_pads", "min_thickness", "fill"]
    assert dumps(nine["fill"], style="compact") == "(fill (thermal_gap 0.5) (thermal_bridge_width 0.5))"
    locked = zones.emit_settings(ZoneSettings(), filled=True, locked=True, major=10)
    assert list(locked) == ["locked", "connect_pads", "min_thickness", "fill"]
    assert dumps(locked["locked"], style="compact") == "(locked yes)"
    assert dumps(zones.HATCH_EDGE, style="compact") == "(hatch edge 0.5)"


@pytest.mark.parametrize(
    ("text", "head", "kept"),
    [
        ("(fill yes (thermal_gap 0.6) (frobnicate 1))", "fill", {"thermal_gap": 600_000}),
        ("(fill maybe (thermal_gap 0.6))", "fill", {"thermal_gap": 600_000}),
        ("(fill (mode polygon) (thermal_gap 0.6))", "fill", {"thermal_gap": 600_000}),
        ("(fill (smoothing wavy) (thermal_gap 0.6))", "fill", {"thermal_gap": 600_000}),
        ("(fill (island_removal_mode 7) (thermal_gap 0.6))", "fill", {"thermal_gap": 600_000}),
        ("(fill (island_removal_mode 2) (island_area_min 1e-13))", "fill", {"island_removal": "below_area"}),
        ("(fill (thermal_gap 0.6) (thermal_gap 0.7))", "fill", {"thermal_gap": 600_000}),
        ("(fill (hatch_border_algorithm other) (thermal_gap 0.6))", "fill", {"thermal_gap": 600_000}),
        ("(connect_pads sometimes (clearance 0.3))", "connect_pads", {"clearance": 300_000}),
        ("(connect_pads yes (clearance 0.3) (extra 1))", "connect_pads", {"clearance": 300_000}),
        ("(min_thickness 0.2 0.3)", "min_thickness", {}),
        ("(min_thickness thin)", "min_thickness", {}),
    ],
)  # fmt: skip
def test_what_is_outside_the_model_gives_a_reason(text: str, head: str, kept: dict[str, object]) -> None:
    read = zones.project_settings(nodes(text), major=10)
    assert list(read.reasons) == [head] and read.reasons[head]
    assert read.inexact == frozenset()
    for name, value in kept.items():
        assert getattr(read.settings, name) == value


def test_inexact_values_are_named() -> None:
    read = zones.project_settings(nodes("(min_thickness 0.2500001) (connect_pads (clearance 0.3))"), major=10)
    assert list(read.reasons) == ["min_thickness"] and read.inexact == {"min_thickness"}
    assert read.settings.min_thickness == 250_000 and read.settings.clearance == 300_000
    angle = zones.project_settings(
        nodes("(fill (mode hatch) (hatch_orientation 45.0000001) (hatch_gap 1.2))"), major=10
    )
    assert angle.inexact == {"fill"} and angle.settings.hatch == ZoneHatch(gap=1_200_000)


def test_repeated_child_is_projected_from_the_first() -> None:
    read = zones.project_settings(nodes("(min_thickness 0.2) (min_thickness 0.3)"), major=10)
    assert read.settings.min_thickness == 200_000
    assert read.reasons == {"min_thickness": "'min_thickness' is repeated"}


LOCKS = [("(locked yes)", True, False), ("(locked no)", False, False), ("(locked maybe)", False, True)]


@pytest.mark.parametrize(("text", "locked", "reason"), [*LOCKS, ("(locked)", False, True)])
def test_locked(text: str, locked: bool, reason: bool) -> None:
    read = zones.project_settings(nodes(text), major=10)
    assert read.locked is locked and bool(read.reasons) is reason


def test_area_conversion_is_exact() -> None:
    assert zones.area_from_mm2("2.5") == 2_500_000_000_000
    assert zones.area_from_mm2("10") == 10_000_000_000_000
    assert zones.area_from_mm2("0.000000000001") == 1
    assert zones.area_to_mm2(2_500_000_000_000) == "2.5"
    assert zones.area_to_mm2(10_000_000_000_000) == "10"
    assert zones.area_to_mm2(1) == "0.000000000001"
    assert zones.area_to_mm2(0) == "0"
    with pytest.raises(ValueError, match="whole"):
        zones.area_from_mm2("0.0000000000001")


def test_projection_differences() -> None:
    fill = nodes("(fill yes (thermal_gap 0.6) (frobnicate 1))")[0]
    same = ZoneSettings(thermal_gap=600_000)
    assert zones.projection_differences(fill, same, filled=True, locked=False, major=10) == ()
    assert zones.projection_differences(fill, same, filled=False, locked=False, major=10) == ("filled",)
    changed = ZoneSettings(thermal_gap=700_000)
    assert zones.projection_differences(fill, changed, filled=False, locked=False, major=10) == (
        "settings",
        "filled",
    )
    # a change outside the child's part is not its difference
    other = ZoneSettings(thermal_gap=600_000, clearance=100_000)
    assert zones.projection_differences(fill, other, filled=True, locked=False, major=10) == ()
    lock = nodes("(locked no)")[0]
    assert zones.projection_differences(lock, same, filled=True, locked=True, major=10) == ("locked",)
    pads = nodes("(connect_pads yes (clearance 0.3) (extra 1))")[0]
    assert zones.projection_differences(pads, same, filled=True, locked=False, major=10) == ("settings",)


def test_pad_codes() -> None:
    for code, connection in zones.PAD_CONNECT_CODES.items():
        node = nodes(f"(zone_connect {code})")[0]
        assert zones.read_pad_connect(node) == connection
        assert zones.pad_connect_node(connection) == node
    for text in (
        "(zone_connect 7)",
        "(zone_connect)",
        "(zone_connect 1 2)",
        "(zone_connect yes)",
        "(zone_connect 1.5)",
    ):
        assert zones.read_pad_connect(nodes(text)[0]) is None


def test_tables_are_closed() -> None:
    assert dict(zones.CONNECT_ATOMS) == {
        "thermal": None,
        "solid": "yes",
        "none": "no",
        "thru_hole_only": "thru_hole_only",
    }
    assert dict(zones.ISLAND_CODES) == {0: "always", 1: "never", 2: "below_area"}
    assert dict(zones.PAD_CONNECT_CODES) == {0: "none", 1: "thermal", 2: "solid", 3: "thru_hole_only"}
    assert zones.SETTING_HEADS == ("locked", "connect_pads", "min_thickness", "fill")
