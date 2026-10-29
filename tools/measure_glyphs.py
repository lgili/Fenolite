# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Measure the glyph metrics of KiCad's stroke font with ``kicad-cli`` (change c0212; capability
silkscreen-layout, "Text ink extents"; ``docs/formats/kicad/text.md``).

    uv run python tools/measure_glyphs.py                  # (re)write src/fenolite/silk/data/glyphs.toml
    uv run python tools/measure_glyphs.py --check          # exit 1 when a fresh measurement differs
    uv run python tools/measure_glyphs.py --kicad-cli PATH

Every text is drawn by ``kicad-cli pcb export svg`` on a scratch board (``backends.kicad.textink``) and
only the box of its ink is read back. For a glyph ``c``, centred at a width and height of 1 mm, the box of
``c`` and of ``cc`` give its advance ``2 x (right(cc) - right(c))``, the right of its skeleton
``right(cc)`` and its left ``left(c) + advance / 2``, all from the start of its cell; ``left(cc)`` must
then be ``left - advance`` (checked). Its top and bottom are taken from the baseline, the bottom of ``H``.
The layout constants come from ``H`` drawn at other heights, strokes and justifications, each fitted from
two measurements and checked on the others. No glyph shape is read: the file holds boxes only.
"""

from __future__ import annotations

import argparse
import string
import sys
from collections.abc import Sequence
from datetime import date
from fractions import Fraction
from pathlib import Path

from fenolite.backends.kicad.cli import cli_for, find_kicad_cli
from fenolite.backends.kicad.textink import InkRequest, measure_ink

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "src" / "fenolite" / "silk" / "data" / "glyphs.toml"
GLYPHS = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-_.+/"
"""The glyphs of designators and of the usual values beside them."""
MM = 1_000_000
STROKE = 100_000
TOLERANCE = 1_000
"""How far a check may miss: 1 µm (a plot gives 0.1 µm; derived values add a few of those)."""


def _request(
    text: str, *, w: int = MM, h: int = MM, t: int = STROKE, hj: str = "center", vj: str = "center"
) -> InkRequest:
    return (text, w, h, t, hj, vj)  # type: ignore[return-value]


def _skeleton(box: tuple[int, int, int, int] | None, stroke: int) -> tuple[int, int, int, int]:
    if box is None:
        raise SystemExit("a measured text drew nothing")
    half = -(-stroke // 2)
    return box[0] + half, box[1] + half, box[2] - half, box[3] - half


def _check(what: str, got: Fraction | int, want: Fraction | int) -> None:
    if abs(Fraction(got) - Fraction(want)) > TOLERANCE:
        raise SystemExit(f"{what}: measured {float(got):.0f} nm, the fit gives {float(want):.0f} nm")


def measure(cli_path: str | None) -> str:
    """The text of a fresh ``glyphs.toml``."""
    path = find_kicad_cli(cli_path)
    if path is None:
        raise SystemExit("kicad-cli not found: pass --kicad-cli or set FENOLITE_KICAD_CLI")
    cli = cli_for(path)
    singles = [_request(c) for c in GLYPHS]
    doubles = [_request(c + c) for c in GLYPHS]
    baselines = [_request("H", h=h, t=t) for h in (MM, 2 * MM) for t in (50_000, 100_000, 200_000)]
    margins = [
        _request("H", t=t, hj=hj) for t in (50_000, 100_000, 200_000) for hj in ("center", "left", "right")
    ]
    shifts = [_request("H", h=h, vj=vj) for h in (MM, 2 * MM) for vj in ("top", "bottom")]
    clamp = _request("H", w=MM // 2, h=MM // 2, t=300_000)
    boxes = measure_ink(cli, [*singles, *doubles, *baselines, *margins, *shifts, clamp])

    # the baseline: y_b(h, t) = B * h - G * t, fitted on (1 mm, 0.05 mm) and (2 mm, 0.2 mm)
    bottoms = {(r[2], r[3]): _skeleton(boxes[r], r[3])[3] for r in baselines}
    g = Fraction(bottoms[(MM, 50_000)] - bottoms[(MM, 200_000)], 150_000)
    b = Fraction(bottoms[(MM, 50_000)]) + g * 50_000
    for (h, t), bottom in bottoms.items():
        _check(f"baseline at h {h} t {t}", bottom, b * h / MM - g * t)

    rows: list[str] = []
    table: dict[str, list[int]] = {}
    for single, double in zip(singles, doubles, strict=True):
        x0, y0, x1, y1 = _skeleton(boxes[single], STROKE)
        dx0, _, dx1, _ = _skeleton(boxes[double], STROKE)
        advance = 2 * (dx1 - x1)
        left = Fraction(x0) + Fraction(advance, 2)
        _check(f"left of {single[0] * 2!r}", dx0, left - advance)
        y_base = b - g * STROKE
        top, bottom = Fraction(y0) - y_base, Fraction(y1) - y_base
        name = single[0].replace("\\", "\\\\").replace('"', '\\"')
        values = [advance, round(left), dx1, round(top), round(bottom)]
        table[single[0]] = values
        rows.append(f'"{name}" = [{", ".join(str(v) for v in values)}]')

    # the margin of a left or right justification: a(t) = alpha * t + beta beside half the advances
    half = Fraction(table["H"][0], 2)
    offsets: dict[int, Fraction] = {}
    for t in (50_000, 100_000, 200_000):
        centre = _skeleton(boxes[_request("H", t=t)], t)[0]
        left = _skeleton(boxes[_request("H", t=t, hj="left")], t)[0]
        right = _skeleton(boxes[_request("H", t=t, hj="right")], t)[0]
        _check(f"left and right justification at t {t}", left - centre, centre - right)
        offsets[t] = Fraction(left - centre) - half
    alpha = (offsets[200_000] - offsets[50_000]) / 150_000
    beta = offsets[50_000] - alpha * 50_000
    _check("justification margin at t 100000", offsets[100_000], alpha * 100_000 + beta)

    # the shift of a top or bottom justification, per mm of height
    shift = Fraction(0)
    for h in (MM, 2 * MM):
        centre = _skeleton(boxes[_request("H", h=h)], STROKE)[1]
        top = _skeleton(boxes[_request("H", h=h, vj="top")], STROKE)[1]
        bottom = _skeleton(boxes[_request("H", h=h, vj="bottom")], STROKE)[1]
        _check(f"top and bottom justification at h {h}", top - centre, centre - bottom)
        if h == MM:
            shift = Fraction(top - centre)
        else:
            _check("justification shift at h 2 mm", top - centre, 2 * shift)

    # the stroke clamp: a stroke above a quarter of the size is drawn at a quarter
    box = boxes[clamp]
    if box is None:
        raise SystemExit("the clamp text drew nothing")
    x0, _, x1, _ = box
    _check(
        "the clamped stroke of H at 0.5 mm", (x1 - x0) - Fraction(table["H"][2] - table["H"][1], 2), MM // 8
    )

    lines = [
        "# SPDX-License-Identifier: Apache-2.0",
        "# Copyright (c) 2026 Fenolite contributors",
        "# Glyph metrics of KiCad's stroke font, measured by tools/measure_glyphs.py from the ink",
        "# that `kicad-cli pcb export svg` draws (S-0020; docs/formats/kicad/text.md). Boxes only,",
        "# no glyph shape. Each glyph: [advance, left, right, top, bottom] in nm at a width and height",
        "# of 1 mm; left and right from the start of its cell, top and bottom from the baseline",
        "# (negative is up).",
        "",
        "[meta]",
        f'tool = "kicad-cli {cli.version()}"',
        f'measured = "{date.today().isoformat()}"',
        "",
        "[layout]",
        f"baseline = {round(b)}",
        f"baseline_stroke = {round(g * 1_000_000)}",
        f"justify_margin = {round(beta)}",
        f"justify_margin_stroke = {round(alpha * 1_000_000)}",
        f"v_shift = {round(shift)}",
        "",
        "[glyphs]",
        *rows,
        "",
    ]
    return "\n".join(lines)


def _body(text: str) -> list[str]:
    """The lines that a fresh measurement must repeat: everything but the tool and the date."""
    return [line for line in text.splitlines() if not line.startswith(("tool =", "measured ="))]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 when a fresh measurement differs")
    parser.add_argument("--kicad-cli", dest="kicad_cli", help="kicad-cli binary or docker:<image>")
    args = parser.parse_args(argv)
    fresh = measure(args.kicad_cli)
    if args.check:
        held = TABLE.read_text(encoding="utf-8") if TABLE.is_file() else ""
        if _body(held) != _body(fresh):
            print(f"{TABLE.relative_to(ROOT)} differs from a fresh measurement", file=sys.stderr)
            return 1
        return 0
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text(fresh, encoding="utf-8", newline="\n")
    print(f"wrote {TABLE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
