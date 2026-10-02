# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reader for the SVG that ``kicad-cli pcb export svg --mode-single`` writes (c0012 Decision 17;
``H-K-WKS-SVG``), standard library only.

KiCad writes the page size in millimetres as the SVG ``width`` and ``height``, every drawn worksheet
text a second time as a hidden searchable ``<text>`` (``opacity="0"``) holding the resolved string, and
worksheet lines and rectangles as ``<path>`` elements. The strokes of text glyphs sit inside
``<g class="stroked-text">`` groups and are not read as lines.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal

SVG_NS = "{http://www.w3.org/2000/svg}"
_TOKEN = re.compile(r"[A-DF-Za-df-z]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


@dataclass(frozen=True)
class SvgText:
    """A hidden searchable text: its string, anchor point (page mm) and ``text-anchor``."""

    text: str
    x: Decimal
    y: Decimal
    anchor: str
    font_size: Decimal


@dataclass(frozen=True)
class Segment:
    x1: Decimal
    y1: Decimal
    x2: Decimal
    y2: Decimal


@dataclass(frozen=True)
class SheetSvg:
    width_mm: Decimal
    height_mm: Decimal
    texts: tuple[SvgText, ...]
    paths: tuple[Segment, ...]

    def strings(self) -> list[str]:
        """The hidden text strings, sorted (a multiset)."""
        return sorted(t.text for t in self.texts)


def _mm(value: str | None, what: str) -> Decimal:
    if value is None or not value.endswith("mm"):
        raise ValueError(f"SVG {what} is not in millimetres: {value!r}")
    return Decimal(value[:-2])


def _segments(d: str) -> list[Segment]:
    """Straight segments of a path: ``M``, ``L``, ``H``, ``V`` and ``Z``, absolute and relative."""
    found: list[Segment] = []
    tokens = _TOKEN.findall(d)
    i = 0
    command = ""
    x = y = start_x = start_y = Decimal(0)
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            command = token
            i += 1
            if command in "Zz":
                if (x, y) != (start_x, start_y):
                    found.append(Segment(x, y, start_x, start_y))
                x, y = start_x, start_y
            continue
        relative = command.islower()
        kind = command.upper()
        if kind in "ML":
            nx, ny = Decimal(tokens[i]), Decimal(tokens[i + 1])
            i += 2
            if relative:
                nx, ny = x + nx, y + ny
            if kind == "M":
                start_x, start_y = nx, ny
                command = "l" if relative else "L"  # further pairs after M are line-tos
            else:
                found.append(Segment(x, y, nx, ny))
            x, y = nx, ny
        elif kind in "HV":
            value = Decimal(tokens[i])
            i += 1
            nx, ny = x, y
            if kind == "H":
                nx = x + value if relative else value
            else:
                ny = y + value if relative else value
            found.append(Segment(x, y, nx, ny))
            x, y = nx, ny
        else:
            raise ValueError(f"unsupported path command {command!r} in {d!r}")
    return found


def _walk(node: ET.Element, inside_glyphs: bool, texts: list[SvgText], paths: list[Segment]) -> None:
    for child in node:
        tag = child.tag.removeprefix(SVG_NS)
        if tag == "g":
            glyphs = inside_glyphs or "stroked-text" in (child.get("class") or "").split()
            _walk(child, glyphs, texts, paths)
        elif tag == "text" and child.get("opacity") == "0":
            texts.append(
                SvgText(
                    text=child.text or "",
                    x=Decimal(child.get("x", "0")),
                    y=Decimal(child.get("y", "0")),
                    anchor=child.get("text-anchor", "start"),
                    font_size=Decimal(child.get("font-size", "0")),
                )
            )
        elif tag == "path" and not inside_glyphs:
            paths.extend(_segments(child.get("d", "")))
        else:
            _walk(child, inside_glyphs, texts, paths)


def read_sheet_svg(text: str) -> SheetSvg:
    """The page size, hidden texts and straight path segments of an SVG written by ``kicad-cli``."""
    # The DOCTYPE names an external DTD; ElementTree does not fetch it.
    root = ET.fromstring(text)
    texts: list[SvgText] = []
    paths: list[Segment] = []
    _walk(root, False, texts, paths)
    return SheetSvg(
        width_mm=_mm(root.get("width"), "width"),
        height_mm=_mm(root.get("height"), "height"),
        texts=tuple(texts),
        paths=tuple(paths),
    )


__all__ = ["Segment", "SheetSvg", "SvgText", "read_sheet_svg"]
