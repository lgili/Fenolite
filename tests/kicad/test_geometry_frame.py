# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad frame conventions against kicad-cli (hypotheses H-G-ROT-DIR, H-G-BOTTOM-PLACE, H-G-PAD-ANGLE-ABS).

An authored CC0 board (format 20241229) holds a front footprint at 90°, a front footprint at 30° and
a back footprint at 30° whose children are stored mirrored about local X. ``kicad-cli pcb export
ipcd356`` writes each through-hole pad with its position in 0.0001 in units (2540 nm), Y up, with a
constant origin per file (S-0019). Pad differences converted to the file frame must equal those that
``Transform.placement(at, θ)`` gives for the stored local positions: exactly at 90°, within 2 export
units per axis at 30° (each exported value is quantised once and a difference subtracts two).
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from _kicad import mm, run, supported_version

from fenolite.backends.kicad.ipcd356 import Ipcd356, read_ipcd356
from fenolite.geometry import Point, Transform

pytestmark = pytest.mark.needs_kicad

UNIT_NM = 2540
PITCH = 2_540_000
PAD1 = Point(0, 0)
PAD2 = Point(PITCH, 2 * PITCH)  # library position of pad 2 (front footprints store it as is)

# name, layer, at (nm), angle (µdeg), stored pad 2 position
FOOTPRINTS = [
    ("F90", "F.Cu", Point(40_000 * UNIT_NM, 20_000 * UNIT_NM), 90_000_000, PAD2),
    ("F30", "F.Cu", Point(50_000 * UNIT_NM, 20_000 * UNIT_NM), 30_000_000, PAD2),
    ("B30", "B.Cu", Point(60_000 * UNIT_NM, 20_000 * UNIT_NM), 30_000_000, Point(PAD2.x, -PAD2.y)),
]


def _board() -> str:
    nets = [f"{name}{pad}" for name, *_ in FOOTPRINTS for pad in "AB"]
    lines = [
        '(kicad_pcb (version 20241229) (generator "fenolite-test") (generator_version "9.0")',
        "  (general (thickness 1.6))",
        '  (paper "A4")',
        '  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))',
        "  (setup (pad_to_mask_clearance 0))",
        '  (net 0 "")',
        *(f'  (net {i + 1} "{net}")' for i, net in enumerate(nets)),
    ]
    for k, (name, layer, at, udeg, stored2) in enumerate(FOOTPRINTS):
        deg = udeg // 1_000_000
        lines.append(f'  (footprint "fenolite:{name}" (layer "{layer}") (at {mm(at.x)} {mm(at.y)} {deg})')
        for n, (pad, stored) in enumerate((("1", PAD1), ("2", stored2))):
            net = 2 * k + n + 1
            lines.append(
                f'    (pad "{pad}" thru_hole circle (at {mm(stored.x)} {mm(stored.y)} {deg}) (size 1.5 1.5)'
                f' (drill 0.8) (layers "*.Cu" "*.Mask") (net {net} "{nets[net - 1]}"))'
            )
        lines.append("  )")
    lines.append(")")
    return "\n".join(lines) + "\n"


def _export(tmp_path: Path) -> tuple[Ipcd356, dict[str, tuple[int, int, int | None]]]:
    board = tmp_path / "frame.kicad_pcb"
    board.write_text(_board(), encoding="utf-8")
    out = tmp_path / "frame.d356"
    run("pcb", "export", "ipcd356", "-o", out, board)
    export = read_ipcd356(out.read_text(encoding="utf-8", errors="replace"))
    pads = {r.net: (r.x, r.y, r.rotation) for r in export.records if r.code == "317"}
    return export, pads


def test_rotation_and_bottom_side_against_kicad_cli(tmp_path: Path) -> None:
    version = supported_version()
    export, pads = _export(tmp_path)
    assert export.unit_nm == UNIT_NM, "expected UNITS CUST 0 (0.0001 in)"
    observed_r: dict[str, tuple[int | None, int | None]] = {}
    for name, _layer, at, udeg, stored2 in FOOTPRINTS:
        placement = Transform.placement(at, udeg)
        p1, p2 = placement.apply(PAD1), placement.apply(stored2)
        expected_dx = Fraction(p2.x - p1.x, UNIT_NM)  # export units, file frame
        expected_dy = Fraction(p2.y - p1.y, UNIT_NM)
        x1, y1, r1 = pads[f"{name}A"]
        x2, y2, r2 = pads[f"{name}B"]
        got_dx, got_dy = Fraction(x2 - x1), Fraction(-(y2 - y1))  # Y up in the export
        observed_r[name] = (r1, r2)
        if udeg % 90_000_000 == 0:
            assert (got_dx, got_dy) == (expected_dx, expected_dy), name
        else:
            assert abs(got_dx - expected_dx) <= 2 and abs(got_dy - expected_dy) <= 2, (
                name,
                (got_dx, got_dy),
                (float(expected_dx), float(expected_dy)),
            )
    # H-G-PAD-ANGLE-ABS is an observation here: print the exported rotation field per footprint.
    print(f"kicad-cli {version}: ipcd356 R fields {observed_r}")


def test_board_is_authored_cc0() -> None:
    text = _board()
    assert "(version 20241229)" in text and "fenolite-test" in text
