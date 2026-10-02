# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Units, framing, layer map, tracks and arcs of the Altium PCB records (change c0035, capability
altium-pcb-writer, "PCB units and record framing", "PCB layer map", "Footprint line and arc records")."""

from __future__ import annotations

import ast
import math
import struct
from pathlib import Path

import pytest

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.binary import frame_record
from fenolite.backends.altium.pcbrecords import (
    FLIP_PAIRS,
    LAYER_MAP,
    LAYER_NAMES,
    NO_INDEX,
    angle_degrees,
    arc_from_points,
    arc_record,
    circle_geometry,
    mil_text,
    prefix,
    property_block,
    string_block,
    to_units,
    track_record,
)
from fenolite.core.coords import Point

ALTIUM = Path(pcbrecords.__file__).parent


def test_units() -> None:
    assert [to_units(v) for v in (0, 254, 1_000_000, -1_000_000, 127)] == [0, 100, 393701, -393701, 50]


def test_units_round_half_away_from_zero() -> None:
    assert to_units(127 // 2) == 25  # 63 nm = 24.8 units
    assert to_units(-127) == -50
    assert to_units(1) == 0 and to_units(2) == 1  # 0.39 and 0.79 units


def test_units_outside_int32() -> None:
    with pytest.raises(ValueError, match="32-bit"):
        to_units(6_000_000_000)


def test_mil_text() -> None:
    assert [mil_text(v) for v in (10_000_000, 3_937_008, -5)] == ["1000mil", "393.7008mil", "-0.0005mil"]
    assert mil_text(0) == "0mil" and mil_text(15_000) == "1.5mil"


def test_string_block() -> None:
    assert string_block("R1") == b"\x03\x00\x00\x00\x02R1"
    for bad in ("", "a|b", "é", " x", "x" * 256):
        with pytest.raises(ValueError):
            string_block(bad)


def test_property_block_is_the_schematic_framing() -> None:
    fields = (("PATTERN", "R"), ("HEIGHT", "0mil"))
    assert property_block(fields) == frame_record(fields)


def test_prefix() -> None:
    data = prefix(33, net=2, component=1)
    assert data == bytes((33, 0x0C, 0x00)) + struct.pack("<HHH", 2, NO_INDEX, 1) + b"\xff" * 4
    assert len(prefix(1)) == 13


def test_map_and_pairs() -> None:
    assert dict(LAYER_MAP) == {
        "F.Cu": 1,
        "B.Cu": 32,
        "F.SilkS": 33,
        "B.SilkS": 34,
        "F.Fab": 69,
        "B.Fab": 70,
        "F.CrtYd": 71,
        "B.CrtYd": 72,
    }
    for layer in (*LAYER_MAP.values(), 74):
        assert FLIP_PAIRS[FLIP_PAIRS[layer]] == layer
    assert FLIP_PAIRS[74] == 74 and FLIP_PAIRS[1] == 32 and FLIP_PAIRS[69] == 70


def test_layer_names() -> None:
    assert list(LAYER_NAMES) == list(range(1, 75))
    assert LAYER_NAMES[1] == "Top Layer" and LAYER_NAMES[32] == "Bottom Layer"
    assert LAYER_NAMES[57] == "Mechanical 1" and LAYER_NAMES[72] == "Mechanical 16"
    assert LAYER_NAMES[2] == "Mid-Layer 1" and LAYER_NAMES[54] == "Internal Plane 16"
    assert LAYER_NAMES[74] == "Multi-Layer"


def test_track_record() -> None:
    data = track_record(33, (1, 2), (3, 4), 5, component=0)
    assert data[0] == 4 and struct.unpack_from("<I", data, 1) == (36,) and len(data) == 41
    body = data[5:]
    assert struct.unpack_from("<5iHB", body, 13) == (1, 2, 3, 4, 5, 0, 0)
    assert struct.unpack_from("<H", body, 7) == (0,)


def test_arc_record() -> None:
    arc = circle_geometry(Point(0, 0), Point(1_500_000, 0))
    data = arc_record(69, arc, to_units(100_000))
    assert data[0] == 1 and struct.unpack_from("<I", data, 1) == (47,) and len(data) == 52
    cx, cy, r, sa, ea, w, sub = struct.unpack_from("<3iddiH", data, 5 + 13)
    assert (cx, cy, r, sa, ea, w, sub) == (0, 0, 590551, 0.0, 360.0, 39370, 0)


# The silkscreen arc of the mini LED, start (-0.29, -1.08), mid (1.27, -1.65), end (2.83, -1.08) mm in
# KiCad's Y-down frame, here with Y negated. The doubles are computed once with decimal at 40 digits.
LED_ARC = (Point(-290_000, 1_080_000), Point(1_270_000, 1_650_000), Point(2_830_000, 1_080_000))
PINNED_START = 49.856948270922544
PINNED_END = 130.14305172907746


def test_angle_pinned() -> None:
    arc = arc_from_points(*LED_ARC)
    assert arc.start == PINNED_START and arc.end == PINNED_END
    assert (arc.cx, arc.cy, arc.radius) == (500_000, -303_046, 952_652)


def test_angle_close_to_the_platform() -> None:
    """The decimal angles agree with the C library to about 1e-12 (math only in the test)."""
    for dx, dy in ((1, 1), (-3, 4), (5, -12), (-7, -24), (1, 0), (0, 1), (-1, 0), (0, -1)):
        expected = math.degrees(math.atan2(dy, dx)) % 360
        assert abs(angle_degrees(dx, dy) - expected) < 1e-9


def test_angle_quadrants() -> None:
    assert [angle_degrees(*v) for v in ((1, 0), (0, 1), (-1, 0), (0, -1), (1, 1))] == [
        0.0,
        90.0,
        180.0,
        270.0,
        45.0,
    ]


def test_arc_direction() -> None:
    """Counter-clockwise points keep their order; clockwise points swap start and end."""
    ccw = arc_from_points(Point(1000, 0), Point(0, 1000), Point(-1000, 0))
    assert (ccw.start, ccw.end) == (0.0, 180.0)
    cw = arc_from_points(Point(-1000, 0), Point(0, 1000), Point(1000, 0))
    assert (cw.start, cw.end) == (0.0, 180.0)
    below = arc_from_points(Point(-1000, 0), Point(0, -1000), Point(1000, 0))
    assert (below.start, below.end) == (180.0, 0.0)


def test_arc_radius_matches_the_points() -> None:
    arc = arc_from_points(*LED_ARC)
    for point in LED_ARC:
        dx = point.x * 50 / 127 - arc.cx
        dy = point.y * 50 / 127 - arc.cy
        assert abs(math.hypot(dx, dy) - arc.radius) <= 1.5


def test_collinear_arc_refused() -> None:
    with pytest.raises(ValueError, match="collinear"):
        arc_from_points(Point(0, 0), Point(1, 1), Point(2, 2))


def test_no_trigonometry_from_math() -> None:
    """No module of ``backends/altium`` imports ``math`` (its trigonometric functions)."""
    for path in sorted(ALTIUM.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "math" for alias in node.names), path.name
            if isinstance(node, ast.ImportFrom):
                assert node.module != "math", path.name


def test_evidence_names_every_pcb_row() -> None:
    assert pcbrecords.EVIDENCE.level.value == "INFERRED"
    assert len(pcbrecords.EVIDENCE.hypotheses) == 13
    assert all(h.startswith("H-A-PCB-") for h in pcbrecords.EVIDENCE.hypotheses)
