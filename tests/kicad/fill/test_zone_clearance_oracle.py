# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What decides the gap of a zone's fill in KiCad 10.0.6 (change c0420, B6; ``docs/formats/kicad/board.md``,
``H-K-ZONE-CLEARANCE``).

An authored board: a zone of net ``A`` round a 0.25 mm track of net ``B``. KiCad refills it with the zone's
own clearance, a custom rule on ``B`` or a ``Default`` netclass clearance, and the copper-to-copper gap of the
fill is measured. A custom rule that matches the pair decides the gap, above or below the zone's clearance;
against a netclass clearance the larger of the two holds. So a converted zone may carry the smallest Altium
clearance that governs its polygon and leave every wider one to the DRU rules."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from _probes import runner

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.sexpr import Node, parse

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]

TRACK_HALF = 0.125
"""Half the track's width (mm)."""
SLACK = 0.005
"""The fill approximates the rounded ends of its hole with segments, which adds at most KiCad's default
maximum arc error to the gap (mm)."""


def _project(folder: Path, zone: float, rule: str | None, netclass: float = 0.2) -> Path:
    board = folder / "tie.kicad_pcb"
    board.write_text(
        f"""(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "9.0")
  (general (thickness 1.6) (legacy_teardrops no))
  (paper "A4")
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
  (setup (pad_to_mask_clearance 0))
  (net 0 "") (net 1 "A") (net 2 "B")
  (gr_rect (start 0 0) (end 20 20) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts")
    (uuid "c0420000-0000-4000-8000-000000000001"))
  (segment (start 5 10) (end 15 10) (width 0.25) (layer "F.Cu") (net 2)
    (uuid "c0420000-0000-4000-8000-000000000002"))
  (zone (net 1) (net_name "A") (layer "F.Cu") (uuid "c0420000-0000-4000-8000-000000000003") (hatch edge 0.5)
    (connect_pads (clearance {zone})) (min_thickness 0.2) (filled_areas_thickness no)
    (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))
    (polygon (pts (xy 1 1) (xy 19 1) (xy 19 19) (xy 1 19))))
)
""",
        encoding="utf-8",
    )
    classes = [{"name": "Default", "clearance": netclass, "track_width": 0.25, "via_diameter": 0.6,
                "via_drill": 0.3, "priority": 2147483647}]  # fmt: skip
    pro = {"meta": {"filename": "tie.kicad_pro", "version": 3},
           "net_settings": {"classes": classes, "meta": {"version": 4}}}  # fmt: skip
    (folder / "tie.kicad_pro").write_text(json.dumps(pro), encoding="utf-8")
    if rule is not None:
        (folder / "tie.kicad_dru").write_text(
            f"(version 1)\n(rule wide (constraint clearance (min {rule}mm))"
            " (condition \"A.NetName == 'B'\"))\n",
            encoding="utf-8",
        )
    return board


def _gap(cli: KicadCli, board: Path) -> float:
    files = {p.name: p for p in board.parent.iterdir() if p != board}
    run = cli.refill(board, files=files)
    assert run.board is not None, run.run.stderr
    tree = parse(run.board.decode("utf-8"))
    points: list[tuple[float, float]] = []
    for zone in tree.nodes("zone"):
        for fill in zone.nodes("filled_polygon"):
            pts = fill.find("pts")
            assert isinstance(pts, Node)
            points += [(float(p.atoms()[0].value), float(p.atoms()[1].value)) for p in pts.nodes("xy")]
    assert points

    def to_track(x: float, y: float) -> float:
        return math.hypot(x - min(max(x, 5.0), 15.0), y - 10.0)

    return min(to_track(x, y) for x, y in points) - TRACK_HALF


@pytest.mark.parametrize(
    ("zone", "rule", "netclass", "gap"),
    [
        (0.2, "1.0", 0.2, 1.0),  # a wider custom rule widens the gap
        (1.0, "0.2", 0.2, 0.2),  # a narrower custom rule narrows it below the zone's clearance
        (1.0, None, 0.2, 1.0),  # no rule: the zone's clearance above the netclass
        (0.2, None, 1.0, 1.0),  # no rule: the netclass above the zone's clearance
        (1.5, None, 1.0, 1.5),
    ],
)
def test_what_decides_the_gap(
    tmp_path: Path, zone: float, rule: str | None, netclass: float, gap: float
) -> None:
    measured = _gap(runner(), _project(tmp_path, zone, rule, netclass))
    assert gap <= measured <= gap + SLACK, measured
