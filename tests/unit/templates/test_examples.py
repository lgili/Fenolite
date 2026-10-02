# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The shipped sheet examples (capability sheet-templates, "Shipped sheet examples", "Cell texts inside
their cells" and "Sheets built from templates are deterministic"; change c0012)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from fenolite.backends.kicad.wks import read_drawing_sheet, write_drawing_sheet
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.templates import EXAMPLES, build_sheet, example_path, layout, load_spec, page_size

MM = 1_000_000


def test_example_names() -> None:
    assert EXAMPLES == ("iso5457_generic", "letter_generic")
    for name in EXAMPLES:
        path = example_path(name)
        assert path.is_file() and path.read_text(encoding="utf-8").startswith(
            "# SPDX-License-Identifier: CC0-1.0\n"
        )
    with pytest.raises(ValueError):
        example_path("unknown")


@pytest.mark.parametrize("name", EXAMPLES)
def test_examples_load_with_provenance(name: str) -> None:
    issues: list[Issue] = []
    spec = load_spec(example_path(name), require_provenance=True)
    build_sheet(spec, issues=issues)
    assert issues == []


def test_example_sizes() -> None:
    iso = load_spec(example_path("iso5457_generic"))
    letter = load_spec(example_path("letter_generic"))
    assert iso.sizes == ("A4", "A3") and not iso.portrait and iso.frame.zones
    assert letter.sizes == ("Letter", "Tabloid") and not letter.portrait and not letter.frame.zones
    assert letter.margins == (12_700_000,) * 4
    assert sum(iso.title_block.columns) == 180 * MM  # type: ignore[union-attr]


def test_cell_texts_inside_their_cells() -> None:
    spec = load_spec(example_path("iso5457_generic"))
    block = spec.title_block
    assert block is not None
    width, height = page_size(spec, "A4")
    lay = layout(build_sheet(spec), width=width, height=height)
    # the grid's right-bottom corner sits at the inner frame corner: margin box minus the zone band
    right = width - spec.margins[1] - spec.frame.zone_band
    bottom = height - spec.margins[3] - spec.frame.zone_band
    left, top = right - sum(block.columns), bottom - sum(block.rows)
    xs = [left + sum(block.columns[:j]) for j in range(len(block.columns) + 1)]
    ys = [top + sum(block.rows[:i]) for i in range(len(block.rows) + 1)]
    cell_texts = [t for t in lay.texts if left <= t.x <= right and top <= t.y <= bottom]
    assert len(cell_texts) == 2 * len(block.cells)
    for cell in block.cells:
        x0, x1 = xs[cell.col], xs[cell.col + cell.span]
        y0, y1 = ys[cell.row], ys[cell.row + 1]
        mine = [t for t in cell_texts if t.text in (cell.label, f"{{{cell.token}}}")]
        assert len(mine) == 2, cell
        for text in mine:
            half = text.size[1] // 2
            assert x0 <= text.x <= x1 and y0 <= text.y - half and text.y + half <= y1, (cell, text)


SCRIPT = """
import hashlib
from fenolite.backends.kicad.wks import write_drawing_sheet
from fenolite.templates import build_sheet, example_path, load_spec
sheet = build_sheet(load_spec(example_path("iso5457_generic"), require_provenance=True))
print(sheet.id, hashlib.sha256(write_drawing_sheet(sheet).text.encode()).hexdigest())
"""


def test_same_specification_same_bytes() -> None:
    runs = {subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True, check=True).stdout
            for _ in range(2)}  # fmt: skip
    assert len(runs) == 1
    (line,) = runs
    assert line.split()[0] == derived_id("wks", "template", "iso5457_generic")


def test_built_sheet_survives_a_round_trip() -> None:
    sheet = build_sheet(load_spec(example_path("letter_generic")))
    back = read_drawing_sheet(write_drawing_sheet(sheet, target=10).text)
    assert (back.setup, back.items) == (sheet.setup, sheet.items)
