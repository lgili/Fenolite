# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sheet templates: ``*.sheet.toml`` specifications built into neutral drawing sheets (change c0012).

``load_spec`` reads a specification, ``build_sheet`` builds a ``DrawingSheet`` of corner-anchored
items, and ``layout`` predicts what a backend draws for it on a page. The package imports only
``fenolite.model``, ``fenolite.core`` and the standard library; ``backends.kicad.wks`` writes the sheet.
Facts and provenance: ``docs/formats/sheets.md`` and ``PROVENANCE.md`` in this package.
"""

from __future__ import annotations

from pathlib import Path

from fenolite.templates.build import build_sheet
from fenolite.templates.layout import PlacedLine, PlacedText, SheetLayout, layout, resolve_text
from fenolite.templates.spec import (
    ISSUE_CODES,
    BitmapSpec,
    FrameSpec,
    SheetSpec,
    TemplateError,
    TitleBlockSpec,
    TitleCell,
    load_spec,
    page_size,
)

EXAMPLES: tuple[str, ...] = ("iso5457_generic", "letter_generic")
"""The shipped CC0 examples (``examples/<name>.sheet.toml``)."""
_EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"


def example_path(name: str) -> Path:
    """The path of the shipped example ``name``."""
    if name not in EXAMPLES:
        raise ValueError(f"unknown example {name!r} (examples: {', '.join(EXAMPLES)})")
    return _EXAMPLES_DIR / f"{name}.sheet.toml"


__all__ = [
    "EXAMPLES",
    "ISSUE_CODES",
    "BitmapSpec",
    "FrameSpec",
    "PlacedLine",
    "PlacedText",
    "SheetLayout",
    "SheetSpec",
    "TemplateError",
    "TitleBlockSpec",
    "TitleCell",
    "build_sheet",
    "example_path",
    "layout",
    "load_spec",
    "page_size",
    "resolve_text",
]
