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
  measured with ``kicad-cli`` and recorded in ``geometry/data/glyphs.toml``
  (``geometry.strokefont`` since change c0492; advance, ink left and right, ink top and
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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fenolite.core.evidence import Level
from fenolite.core.units import Nm
from fenolite.geometry.strokefont import (
    ESTIMATE_EVIDENCE,
    ESTIMATE_HYPOTHESIS,
    ESTIMATE_MARGIN,
    FONT,
    LINE_PITCH,
    MEASURE_HYPOTHESIS,
    Glyph,
    GlyphTable,
    InkBox,
    TextKey,
    effective_stroke,
    estimate,
    glyph_table,
    read_table,
)
from fenolite.model.board import FieldJustifyH, FieldJustifyV

CACHE_VARIABLE = "FENOLITE_CACHE_DIR"


@dataclass(frozen=True, slots=True)
class Ink:
    """A box and how it was found: ``kicad-cli <version>`` (a render, ``KICAD-VERIFIED``), ``cache`` of
    such a render, or ``estimate`` (``INFERRED``). ``box`` is ``None`` for a text without ink."""

    box: InkBox | None
    level: Level
    source: str


Measure = Callable[[Sequence[TextKey]], Mapping[TextKey, InkBox | None]]
"""Renders texts and returns the box of each (``None`` for a text without ink)."""


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
    "ESTIMATE_MARGIN",
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
