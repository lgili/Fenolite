# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ink of a KiCad stroke text: measured by a render, cached, or estimated (capability
silkscreen-layout, "Text ink extents"; change c0212; facts: ``docs/formats/kicad/text.md``).

An ``InkBox`` is the box of the ink of one text in its own reading frame (X along the text, Y down),
relative to its anchor, for the text's own justification, half the stroke included on each side.

- **Measured.** A ``Measure`` callable renders texts with ``kicad-cli`` and returns their boxes; the CLI
  passes ``backends.kicad.textink.measure_ink``. The result is ``KICAD-VERIFIED`` and is cached per tool
  version, string, size, stroke and justification (``InkCache``), so a second call runs nothing.
- **Estimated.** Without a render, ``estimate`` adds up glyph metrics that ``tools/measure_glyphs.py``
  measured with ``kicad-cli`` and recorded in ``data/glyphs.toml`` (advance, ink left and right, ink top and
  bottom of each glyph at a 1 mm size). The result is ``INFERRED`` (``H-K-SILK-ESTIMATE``). A glyph that
  the table lacks takes the widest and tallest metrics of the table, so the box only grows. A text of
  several lines is boxed by its widest line, grown up and down by ``LINE_PITCH`` per further line.

No KiCad code or font data is read: the table holds only measured extents of rendered ink.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from math import ceil, floor
from pathlib import Path
from typing import cast

from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.model.board import FieldJustifyH, FieldJustifyV

MM = 1_000_000
PPM = 1_000_000
ESTIMATE_HYPOTHESIS = "H-K-SILK-ESTIMATE"
MEASURE_HYPOTHESIS = "H-K-SILK-INK"
ESTIMATE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=(ESTIMATE_HYPOTHESIS,))
"""The evidence of an estimated box: glyph metrics measured once, added up by a model of the layout."""
FONT = "kicad-stroke"
"""The only font measured: KiCad's built-in stroke font (a text with a TrueType face is not modelled)."""
LINE_PITCH = Fraction(161, 100)
"""Two lines of a text are 1.61 x its height apart (``docs/formats/kicad/board.md``, ``H-K-DRAW-TEXT``)."""
CACHE_VARIABLE = "FENOLITE_CACHE_DIR"
ESTIMATE_MARGIN: Nm = 1_000
"""What an estimate adds on every side: 1 µm, five times the largest miss of the table's own strings."""


@dataclass(frozen=True, slots=True, order=True)
class TextKey:
    """What decides the ink of a stroke text: the string, the glyph width and height, the stroke and the
    justification. The anchor, the angle and the mirror only move the box."""

    text: str
    width: Nm
    height: Nm
    stroke: Nm
    h_justify: FieldJustifyH = "center"
    v_justify: FieldJustifyV = "center"

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0 or self.stroke < 0:
            raise ValueError(f"a text needs a size above 0 and a stroke of at least 0: {self}")


@dataclass(frozen=True, slots=True)
class InkBox:
    """The ink of a text in its reading frame, relative to its anchor (Y down), half the stroke included."""

    x0: Nm
    y0: Nm
    x1: Nm
    y1: Nm

    @property
    def width(self) -> Nm:
        return self.x1 - self.x0

    @property
    def height(self) -> Nm:
        return self.y1 - self.y0


@dataclass(frozen=True, slots=True)
class Ink:
    """A box and how it was found: ``kicad-cli <version>`` (a render, ``KICAD-VERIFIED``), ``cache`` of
    such a render, or ``estimate`` (``INFERRED``). ``box`` is ``None`` for a text without ink."""

    box: InkBox | None
    level: Level
    source: str


Measure = Callable[[Sequence[TextKey]], Mapping[TextKey, InkBox | None]]
"""Renders texts and returns the box of each (``None`` for a text without ink)."""


def effective_stroke(key: TextKey) -> Nm:
    """The stroke KiCad draws: the given one, at most a quarter of the smaller of width and height
    (``H-K-SILK-INK``)."""
    return min(key.stroke, min(key.width, key.height) // 4)


# --- the glyph table ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Glyph:
    """Metrics of one glyph at a width and height of 1 mm, in nm: its advance, the left and right of its
    skeleton from the start of its cell, and the top and bottom of its skeleton from the baseline."""

    advance: int
    left: int
    right: int
    top: int
    bottom: int


@dataclass(frozen=True, slots=True)
class GlyphTable:
    """The measured metrics (``data/glyphs.toml``): per glyph, and the layout constants.

    ``baseline`` is the distance from a centred anchor down to the baseline per mm of height, less
    ``baseline_stroke`` per mm of stroke; ``justify_margin`` and ``justify_margin_stroke`` give the margin
    that a left or right justification adds beside the advances (nm, plus ppm of the stroke);
    ``v_shift`` is how far a top or bottom justification moves the ink, per mm of height."""

    tool: str
    measured: str
    glyphs: Mapping[str, Glyph]
    baseline: int
    baseline_stroke: int
    justify_margin: int
    justify_margin_stroke: int
    v_shift: int

    @property
    def widest(self) -> Glyph:
        """A stand-in for a glyph the table lacks: the widest and tallest metrics of the table."""
        values = list(self.glyphs.values())
        return Glyph(
            max(g.advance for g in values),
            min(g.left for g in values),
            max(g.right for g in values),
            min(g.top for g in values),
            max(g.bottom for g in values),
        )


TABLE_PATH = Path(__file__).with_name("data") / "glyphs.toml"


@cache
def glyph_table() -> GlyphTable:
    """The table shipped with Fenolite (read once)."""
    return read_table(TABLE_PATH.read_text(encoding="utf-8"))


def read_table(text: str) -> GlyphTable:
    """A glyph table from the text of a ``glyphs.toml``."""
    data = tomllib.loads(text)
    meta = cast(dict[str, object], data["meta"])
    layout = cast(dict[str, int], data["layout"])
    rows = cast(dict[str, list[int]], data["glyphs"])
    glyphs = {name: Glyph(*(int(v) for v in values)) for name, values in rows.items()}
    return GlyphTable(
        tool=str(meta["tool"]),
        measured=str(meta["measured"]),
        glyphs=glyphs,
        baseline=layout["baseline"],
        baseline_stroke=layout["baseline_stroke"],
        justify_margin=layout["justify_margin"],
        justify_margin_stroke=layout["justify_margin_stroke"],
        v_shift=layout["v_shift"],
    )


def _line_box(line: str, table: GlyphTable) -> tuple[Fraction, Fraction, int, int, Fraction]:
    """``(x0, x1, top, bottom, advances)`` of the skeleton of one centred line at 1 mm: x from the anchor,
    top and bottom from the baseline (nm)."""
    if not line:
        return Fraction(0), Fraction(0), 0, 0, Fraction(0)
    spare = table.widest
    glyphs = [table.glyphs.get(char, spare) for char in line]
    total = Fraction(sum(g.advance for g in glyphs))
    start = Fraction(0)
    x0: Fraction | None = None
    x1: Fraction | None = None
    for glyph in glyphs:
        left, right = start + glyph.left, start + glyph.right
        x0 = left if x0 is None else min(x0, left)
        x1 = right if x1 is None else max(x1, right)
        start += glyph.advance
    assert x0 is not None and x1 is not None
    half = total / 2
    return x0 - half, x1 - half, min(g.top for g in glyphs), max(g.bottom for g in glyphs), total


def estimate(key: TextKey, table: GlyphTable | None = None) -> InkBox | None:
    """The estimated ink of ``key`` from the glyph table (``INFERRED``, ``H-K-SILK-ESTIMATE``); ``None``
    for a text without a visible glyph. The box is rounded outward to whole nanometres."""
    table = glyph_table() if table is None else table
    lines = key.text.split("\n")
    if not key.text.strip():
        return None
    w, h = Fraction(key.width, MM), Fraction(key.height, MM)
    stroke = effective_stroke(key)
    boxes = [_line_box(line, table) for line in lines if line]
    x0 = min(box[0] for box in boxes) * w
    x1 = max(box[1] for box in boxes) * w
    advances = max(box[4] for box in boxes) * w
    top = min(box[2] for box in boxes) * h
    bottom = max(box[3] for box in boxes) * h
    baseline = Fraction(table.baseline) * h - Fraction(table.baseline_stroke * stroke, PPM)
    y0, y1 = baseline + top, baseline + bottom
    if len(lines) > 1:  # where KiCad puts the block is not measured: grow both ways by all the lines
        spread = (len(lines) - 1) * LINE_PITCH * key.height
        y0, y1 = y0 - spread, y1 + spread
    unknown = sum(1 for char in key.text if char != "\n" and char not in table.glyphs)
    if unknown:  # an unknown glyph's advance lies between the table's least and largest: allow for both
        least = min(g.advance for g in table.glyphs.values())
        slack = unknown * (table.widest.advance - least) * w / 2
        x0, x1 = x0 - slack, x1 + slack
    margin = Fraction(table.justify_margin) + Fraction(table.justify_margin_stroke * stroke, PPM)
    if key.h_justify != "center":
        shift = advances / 2 + margin
        x0, x1 = (x0 + shift, x1 + shift) if key.h_justify == "left" else (x0 - shift, x1 - shift)
    if key.v_justify != "center":
        shift = Fraction(table.v_shift) * h
        y0, y1 = (y0 + shift, y1 + shift) if key.v_justify == "top" else (y0 - shift, y1 - shift)
    grow = Fraction(stroke, 2) + ESTIMATE_MARGIN
    return InkBox(floor(x0 - grow), floor(y0 - grow), ceil(x1 + grow), ceil(y1 + grow))


# --- the cache ------------------------------------------------------------------------------------


def cache_folder(env: Mapping[str, str] | None = None) -> Path:
    """``$FENOLITE_CACHE_DIR/silk``, else ``$XDG_CACHE_HOME`` (or ``%LOCALAPPDATA%``, or ``~/.cache``)
    ``/fenolite/silk``: the folder of the measured boxes."""
    variables = os.environ if env is None else env
    given = variables.get(CACHE_VARIABLE)
    if given:
        return Path(given) / "silk"
    base = variables.get("XDG_CACHE_HOME") or variables.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".cache") / "fenolite" / "silk"


def _digest(tool: str, key: TextKey) -> str:
    fields = [FONT, tool, key.text, key.width, key.height, key.stroke, key.h_justify, key.v_justify]
    return hashlib.sha256(json.dumps(fields).encode("utf-8")).hexdigest()


class InkCache:
    """Measured boxes on disk, one JSON file per tool version and text; ``folder`` ``None`` keeps nothing.
    A file that cannot be read is a miss. ``hits`` and ``misses`` count the lookups of this object."""

    def __init__(self, folder: Path | None) -> None:
        self.folder = folder
        self.hits = 0
        self.misses = 0

    def get(self, tool: str, key: TextKey) -> tuple[bool, InkBox | None]:
        """``(found, box)``."""
        if self.folder is None:
            self.misses += 1
            return False, None
        path = self.folder / f"{_digest(tool, key)}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            box = data["box"]
            found = None if box is None else InkBox(*(int(v) for v in box))
        except (OSError, ValueError, KeyError, TypeError):
            self.misses += 1
            return False, None
        self.hits += 1
        return True, found

    def put(self, tool: str, key: TextKey, box: InkBox | None) -> None:
        if self.folder is None:
            return
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            payload = {
                "font": FONT,
                "tool": tool,
                "text": key.text,
                "size": [key.width, key.height],
                "stroke": key.stroke,
                "justify": [key.h_justify, key.v_justify],
                "box": None if box is None else [box.x0, box.y0, box.x1, box.y1],
            }
            handle, name = tempfile.mkstemp(dir=self.folder, suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream)
            os.replace(name, self.folder / f"{_digest(tool, key)}.json")
        except OSError:
            return  # a cache that cannot be written only costs a later render


# --- the boxes ------------------------------------------------------------------------------------


def ink_boxes(
    keys: Iterable[TextKey],
    *,
    measure: Measure | None = None,
    tool: str = "",
    cache: InkCache | None = None,
) -> dict[TextKey, Ink]:
    """The ink of every key: from ``cache``, else from one call of ``measure`` for all the missing ones
    (``tool`` names the renderer, ``kicad-cli <version>``), else estimated. Without ``measure`` every box
    is estimated."""
    wanted = sorted(set(keys))
    found: dict[TextKey, Ink] = {}
    if measure is None:
        for key in wanted:
            found[key] = Ink(estimate(key), Level.INFERRED, "estimate")
        return found
    store = cache if cache is not None else InkCache(None)
    missing: list[TextKey] = []
    for key in wanted:
        hit, box = store.get(tool, key)
        if hit:
            found[key] = Ink(box, Level.KICAD_VERIFIED, "cache")
        else:
            missing.append(key)
    if missing:
        measured = measure(missing)
        for key in missing:
            box = measured.get(key)
            store.put(tool, key, box)
            found[key] = Ink(box, Level.KICAD_VERIFIED, tool)
    return found


def ink_box(
    text: str,
    *,
    size: tuple[Nm, Nm],
    stroke: Nm,
    font: str | None = None,
    justify: tuple[FieldJustifyH, FieldJustifyV] = ("center", "center"),
    measure: Measure | None = None,
    tool: str = "",
    cache: InkCache | None = None,
) -> Ink:
    """The ink of one text of glyph ``size`` ``(width, height)``; see ``ink_boxes``. ``font`` must be
    ``None`` or ``FONT``: a TrueType face is not modelled."""
    if font not in (None, FONT):
        raise ValueError(f"only the stroke font is modelled, not {font!r}")
    key = TextKey(text, size[0], size[1], stroke, *justify)
    return ink_boxes([key], measure=measure, tool=tool, cache=cache)[key]


__all__ = [
    "CACHE_VARIABLE",
    "ESTIMATE_EVIDENCE",
    "ESTIMATE_HYPOTHESIS",
    "FONT",
    "LINE_PITCH",
    "MEASURE_HYPOTHESIS",
    "Glyph",
    "GlyphTable",
    "Ink",
    "InkBox",
    "InkCache",
    "Measure",
    "TextKey",
    "cache_folder",
    "effective_stroke",
    "estimate",
    "glyph_table",
    "ink_box",
    "ink_boxes",
    "read_table",
]
