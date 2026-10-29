# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stress board of the viewer's frame budget (change c0245, decision 7), authored for Fenolite.

A four-layer KiCad board of 160 x 100 mm, written deterministically by ``write(path)``: 500 parts of four
SMD pads (2 000 pads), 10 000 track segments, 1 500 vias and 40 zones with their saved fills. It is about
1.2 times the largest public board of the corpus (8 355 tracks, ``docs/viewer.md``, "Speed and size"). No
file is committed: the visual tests write it into their temporary folder.
"""

from __future__ import annotations

import uuid
from pathlib import Path

PARTS_X, PARTS_Y = 25, 20
PITCH_X, PITCH_Y = 6.4, 5.0
ORIGIN_X, ORIGIN_Y = 3.0, 2.5
WIDTH, HEIGHT = 160.0, 100.0
NETS = 400
TRACKS = 10_000
VIAS = 1_500
ZONES = 40
COPPER = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
_NS = uuid.UUID("6b3c1d2e-0c45-4f5e-9a1b-7f2e5c0a2450")


def _uuid(kind: str, n: int) -> str:
    return str(uuid.uuid5(_NS, f"{kind}:{n}"))


def _mm(v: float) -> str:
    text = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _header() -> list[str]:
    out = [
        "(kicad_pcb",
        "\t(version 20241229)",
        '\t(generator "fenolite-tests")',
        '\t(generator_version "9.0")',
        "\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)",
        '\t(paper "A4")',
        "\t(layers",
        '\t\t(0 "F.Cu" signal)',
        '\t\t(4 "In1.Cu" signal)',
        '\t\t(6 "In2.Cu" signal)',
        '\t\t(2 "B.Cu" signal)',
        '\t\t(13 "F.Paste" user)',
        '\t\t(15 "B.Paste" user)',
        '\t\t(5 "F.SilkS" user "F.Silkscreen")',
        '\t\t(7 "B.SilkS" user "B.Silkscreen")',
        '\t\t(1 "F.Mask" user)',
        '\t\t(3 "B.Mask" user)',
        '\t\t(25 "Edge.Cuts" user)',
        "\t)",
        "\t(setup\n\t\t(pad_to_mask_clearance 0)\n\t)",
        '\t(net 0 "")',
    ]
    out += [f'\t(net {n} "N{n:03d}")' for n in range(1, NETS + 1)]
    return out


def _net(n: int) -> int:
    return n % NETS + 1


def _footprints() -> list[str]:
    out: list[str] = []
    k = 0
    for j in range(PARTS_Y):
        for i in range(PARTS_X):
            k += 1
            x, y = ORIGIN_X + i * PITCH_X, ORIGIN_Y + j * PITCH_Y
            back = (i + j) % 2 == 1
            side = "B" if back else "F"
            out.append(f'\t(footprint "Fenolite_Test:Q4_{side}"')
            out.append(f'\t\t(layer "{side}.Cu")')
            out.append(f'\t\t(uuid "{_uuid("fp", k)}")')
            out.append(f"\t\t(at {_mm(x)} {_mm(y)})")
            out.append(
                f'\t\t(property "Reference" "U{k}"\n\t\t\t(at 0 -1.6)\n\t\t\t(layer "{side}.SilkS")\n'
                f'\t\t\t(uuid "{_uuid("ref", k)}")\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 0.6 0.6)\n"
                "\t\t\t\t\t(thickness 0.1)\n\t\t\t\t)"
                + ("\n\t\t\t\t(justify mirror)" if back else "")
                + "\n\t\t\t)\n\t\t)"
            )
            out.append("\t\t(attr smd)")
            for p in range(4):
                px = -1.5 + p
                out.append(
                    f'\t\t(pad "{p + 1}" smd rect\n\t\t\t(at {_mm(px)} 0)\n\t\t\t(size 0.6 0.9)\n'
                    f'\t\t\t(layers "{side}.Cu" "{side}.Paste" "{side}.Mask")\n'
                    f'\t\t\t(net {_net(k * 4 + p)} "N{_net(k * 4 + p):03d}")\n'
                    f'\t\t\t(uuid "{_uuid("pad", k * 4 + p)}")\n\t\t)'
                )
            out.append("\t)")
    return out


def _outline() -> list[str]:
    corners = [(0.0, 0.0), (WIDTH, 0.0), (WIDTH, HEIGHT), (0.0, HEIGHT)]
    out: list[str] = []
    for n, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1], strict=True)):
        out.append(
            f"\t(gr_line\n\t\t(start {_mm(a[0])} {_mm(a[1])})\n\t\t(end {_mm(b[0])} {_mm(b[1])})\n"
            '\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n\t\t(layer "Edge.Cuts")\n'
            f'\t\t(uuid "{_uuid("edge", n)}")\n\t)'
        )
    return out


def _tracks() -> list[str]:
    """Octilinear zig-zags of ten segments, 1 000 of them, each on one copper layer."""
    out: list[str] = []
    n = 0
    chains = TRACKS // 10
    for c in range(chains):
        layer = COPPER[c % 4]
        x = 2.0 + (c * 7.3) % (WIDTH - 20.0)
        y = 1.5 + (c * 3.1) % (HEIGHT - 6.0)
        net = _net(c)
        for s in range(10):
            dx, dy = (1.2, 0.0) if s % 2 == 0 else (0.8, 0.8 if (c + s) % 4 < 2 else -0.8)
            nx, ny = x + dx, min(max(y + dy, 0.5), HEIGHT - 0.5)
            out.append(
                f"\t(segment\n\t\t(start {_mm(x)} {_mm(y)})\n\t\t(end {_mm(nx)} {_mm(ny)})\n"
                f'\t\t(width 0.2)\n\t\t(layer "{layer}")\n\t\t(net {net})\n'
                f'\t\t(uuid "{_uuid("seg", n)}")\n\t)'
            )
            x, y, n = nx, ny, n + 1
    return out


def _vias() -> list[str]:
    out: list[str] = []
    for v in range(VIAS):
        x = 1.0 + (v * 4.7) % (WIDTH - 2.0)
        y = 1.0 + (v * 2.9) % (HEIGHT - 2.0)
        out.append(
            f"\t(via\n\t\t(at {_mm(x)} {_mm(y)})\n\t\t(size 0.6)\n\t\t(drill 0.3)\n"
            f'\t\t(layers "F.Cu" "B.Cu")\n\t\t(net {_net(v)})\n\t\t(uuid "{_uuid("via", v)}")\n\t)'
        )
    return out


def _zones() -> list[str]:
    """Ten strips per copper layer, each with a fill that has a notch."""
    out: list[str] = []
    strip = WIDTH / 10
    for z in range(ZONES):
        layer = COPPER[z // 10]
        x0 = (z % 10) * strip + 0.3
        x1 = x0 + strip - 0.6
        y0, y1 = 0.3 + (z // 10) * 0.2, HEIGHT - 0.3 - (z // 10) * 0.2
        net = _net(z * 7)
        poly = " ".join(f"(xy {_mm(a)} {_mm(b)})" for a, b in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
        mx = (x0 + x1) / 2
        fill = (
            f"(xy {_mm(x0 + 0.25)} {_mm(y0 + 0.25)}) (xy {_mm(mx - 1)} {_mm(y0 + 0.25)}) "
            f"(xy {_mm(mx - 1)} {_mm(y0 + 6)}) (xy {_mm(mx + 1)} {_mm(y0 + 6)}) "
            f"(xy {_mm(mx + 1)} {_mm(y0 + 0.25)}) (xy {_mm(x1 - 0.25)} {_mm(y0 + 0.25)}) "
            f"(xy {_mm(x1 - 0.25)} {_mm(y1 - 0.25)}) (xy {_mm(x0 + 0.25)} {_mm(y1 - 0.25)})"
        )
        out.append(
            f'\t(zone\n\t\t(net {net})\n\t\t(net_name "N{net:03d}")\n\t\t(layer "{layer}")\n'
            f'\t\t(uuid "{_uuid("zone", z)}")\n\t\t(name "Z{z:02d}")\n\t\t(hatch edge 0.5)\n'
            "\t\t(connect_pads\n\t\t\t(clearance 0.25)\n\t\t)\n\t\t(min_thickness 0.25)\n"
            "\t\t(filled_areas_thickness no)\n"
            "\t\t(fill yes\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n\t\t)\n"
            f"\t\t(polygon\n\t\t\t(pts\n\t\t\t\t{poly}\n\t\t\t)\n\t\t)\n"
            f'\t\t(filled_polygon\n\t\t\t(layer "{layer}")\n\t\t\t(pts\n\t\t\t\t{fill}\n\t\t\t)\n\t\t)\n\t)'
        )
    return out


def text() -> str:
    """The board file's text."""
    lines = _header() + _footprints() + _outline() + _tracks() + _vias() + _zones()
    return "\n".join([*lines, "\t(embedded_fonts no)", ")", ""])


def write(path: Path) -> Path:
    """Write the board to ``path`` and return it."""
    path.write_text(text(), encoding="utf-8")
    return path


__all__ = ["text", "write"]
