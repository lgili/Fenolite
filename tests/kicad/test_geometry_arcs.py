# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Arcs as KiCad re-saves them (hypotheses H-G-ARC-ROUND, H-G-ARC-DIR, H-G-PTS-ARC).

An authored CC0 footprint (format 20241229) holds shallow ``fp_arc``s in both orientations, and an
``fp_poly``, a custom pad's ``gr_poly`` primitive and a keepout ``zone`` polygon whose ``pts`` contain
an ``arc``. After ``kicad-cli fp
upgrade --force`` every ``fp_arc`` must keep ``mid`` and the set ``{start, end}`` and be written with
positive ``orient2d(start, mid, end)``; every ``pts`` arc must keep its three points in order.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest
from _kicad import mm, run, supported_version

from fenolite.core.units import parse_length
from fenolite.geometry import Arc, Point, orient2d

pytestmark = pytest.mark.needs_kicad

# radius (nm), sweep (µdeg)
SHALLOW = [(100_000, 10_000_000), (1_000_000, 1_000_000), (10_000_000, 100_000), (50_000_000, 50_000)]

Triple = tuple[Point, Point, Point]


def _shallow_arcs() -> list[Triple]:
    arcs: list[Triple] = []
    for k, (r, sweep) in enumerate(SHALLOW):
        half = math.radians(sweep / 2e6)  # test data only: any integer points define an arc
        a, b = round(r * math.sin(half)), round(r * math.cos(half))
        ox = 1_000_000 * k
        start, mid, end = Point(ox - a, b), Point(ox, r), Point(ox + a, b)
        arcs.append((start, mid, end))  # negative orientation
        arcs.append((end, mid, start))  # positive orientation
    return arcs


POLY_ARC: Triple = (Point(2_000_000, 0), Point(3_000_000, 1_000_000), Point(2_000_000, 2_000_000))  # positive
ZONE_ARC: Triple = (
    Point(-2_000_000, 0),
    Point(-3_000_000, 1_000_000),
    Point(-2_000_000, 2_000_000),
)  # negative
PAD_ARC: Triple = (Point(500_000, -500_000), Point(700_000, 0), Point(500_000, 500_000))  # positive


def _xy(p: Point) -> str:
    return f"{mm(p.x)} {mm(p.y)}"


def _arc(t: Triple) -> str:
    return f"(start {_xy(t[0])}) (mid {_xy(t[1])}) (end {_xy(t[2])})"


def _footprint() -> str:
    stroke = '(stroke (width 0.1) (type solid)) (layer "F.SilkS")'
    lines = ['(footprint "probe" (version 20241229) (generator "fenolite-test") (layer "F.Cu")']
    lines += [f"  (fp_arc {_arc(t)} {stroke})" for t in _shallow_arcs()]
    lines.append(f"  (fp_poly (pts (xy 0 0) (arc {_arc(POLY_ARC)}) (xy 0 2)) {stroke} (fill no))")
    lines += [
        '  (pad "1" smd custom (at 0 -5) (size 0.5 0.5) (layers "F.Cu" "F.Mask")',
        "    (options (clearance outline) (anchor rect))",
        f"    (primitives (gr_poly (pts (xy -0.5 -0.5) (arc {_arc(PAD_ARC)}) (xy -0.5 0.5))"
        " (width 0) (fill yes))))",
    ]
    lines += [
        '  (zone (net 0) (net_name "") (layers "F.Cu") (hatch edge 0.5)',
        "    (connect_pads (clearance 0)) (min_thickness 0.25)",
        "    (keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed)"
        " (footprints allowed))",
        "    (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))",
        f"    (polygon (pts (xy 0 2) (xy 0 0) (arc {_arc(ZONE_ARC)}))))",
        ")",
    ]
    return "\n".join(lines) + "\n"


NUM = r"(-?[\d.]+)"
POINT = rf"\(\s*{{}}\s+{NUM}\s+{NUM}\s*\)"
TRIPLE = r"\s*".join(POINT.format(k) for k in ("start", "mid", "end"))
FP_ARC = re.compile(r"\(fp_arc\s*" + TRIPLE)
PTS_ARC = re.compile(r"\(arc\s*" + TRIPLE)


def _points(match: re.Match[str]) -> Triple:
    v = [parse_length(g, default_unit="mm") for g in match.groups()]
    return Point(v[0], v[1]), Point(v[2], v[3]), Point(v[4], v[5])


def _resave(tmp_path: Path) -> str:
    library = tmp_path / "in.pretty"
    library.mkdir()
    (library / "probe.kicad_mod").write_text(_footprint(), encoding="utf-8")
    out = tmp_path / "out.pretty"
    run("fp", "upgrade", "--force", "-o", out, library)
    return (out / "probe.kicad_mod").read_text(encoding="utf-8")


def test_arcs_survive_a_kicad_resave(tmp_path: Path) -> None:
    version = supported_version()
    written = _resave(tmp_path)
    resaved = [_points(m) for m in FP_ARC.finditer(written)]
    authored = _shallow_arcs()
    assert len(resaved) == len(authored)
    for before in authored:
        Arc(*before)  # the authored data are valid arcs
        same = [
            after
            for after in resaved
            if after[1] == before[1] and {after[0], after[2]} == {before[0], before[2]}
        ]
        assert same, (
            f"H-G-ARC-ROUND: no re-saved fp_arc keeps mid {before[1]} and ends {before[0]}, {before[2]}"
        )
    for after in resaved:
        assert orient2d(*after) > 0, f"H-G-ARC-DIR: re-saved fp_arc {after} is not positively oriented"
    pts_arcs = [_points(m) for m in PTS_ARC.finditer(written)]
    for authored_arc in (POLY_ARC, ZONE_ARC, PAD_ARC):
        assert authored_arc in pts_arcs, (
            f"H-G-PTS-ARC: pts arc {authored_arc} not kept in order; got {pts_arcs}"
        )
    print(f"kicad-cli {version}: {len(resaved)} fp_arcs and {len(pts_arcs)} pts arcs checked")


def test_footprint_is_authored_cc0() -> None:
    text = _footprint()
    assert "(version 20241229)" in text and "fenolite-test" in text
    assert orient2d(*POLY_ARC) > 0 > orient2d(*ZONE_ARC)
    assert orient2d(*PAD_ARC) > 0
