# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sheet specification loader (capability sheet-templates, "Sheet specification files", "Template values
carry provenance", and the loader scenarios of "Frame, reference zones and title-block grid"; c0012)."""

from __future__ import annotations

import pytest
from _specs import BASE, TITLE, ZONES

from fenolite.templates import ISSUE_CODES, TemplateError, load_spec


def codes(error: TemplateError) -> list[tuple[str, str]]:
    return [(i.code, i.where) for i in error.issues]


def refused(text: str, **kwargs: bool) -> TemplateError:
    with pytest.raises(TemplateError) as info:
        load_spec(text, **kwargs)
    for issue in info.value.issues:
        assert ISSUE_CODES[issue.code] == issue.severity
    return info.value


def test_exact_millimetres() -> None:
    spec = load_spec(BASE.replace("right = 10\n", "right = 10.005\n"))
    assert spec.margins == (20_000_000, 10_005_000, 10_000_000, 10_000_000)
    assert all(type(v) is int for v in (*spec.margins, spec.text_size, spec.frame.line_width))
    assert spec.sizes == ("A4", "A3") and spec.portrait is False and spec.provenance == {}


def test_every_problem_reported_at_once() -> None:
    text = (
        "[frame]\nline_width = 0.7\ncolour = 1\n"
        + BASE.split("[frame]")[0].replace("left = 20", "left = 0.0005")
        + TITLE.replace('token = "title"', 'token = "owner"')
    )
    error = refused(text)
    assert error.locator == "frame.colour"
    assert codes(error) == [
        ("template.unknown-key", "frame.colour"),
        ("template.resolution", "margins.left"),
        ("template.unknown-token", "title_block.cell[0].token"),
    ]
    assert "frame.colour" in str(error) and "margins.left" in str(error)


def test_custom_size_needs_its_dimensions() -> None:
    text = BASE.replace('sizes = ["A4", "A3"]', 'sizes = ["custom"]\nwidth = 300')
    assert ("template.bad-value", "sheet.height") in codes(refused(text))
    ok = load_spec(BASE.replace('sizes = ["A4", "A3"]', 'sizes = ["custom"]\nwidth = 300\nheight = 200'))
    assert (ok.width, ok.height) == (300_000_000, 200_000_000)
    assert ("template.bad-value", "sheet.width") in codes(
        refused(BASE.replace("text_size", "width = 3\ntext_size"))
    )


@pytest.mark.parametrize(
    ("change", "code", "where"),
    [
        (('sizes = ["A4", "A3"]', 'sizes = ["A4", "B"]'), "template.bad-value", "sheet.sizes[1]"),
        (('sizes = ["A4", "A3"]', "sizes = []"), "template.bad-value", "sheet.sizes"),
        (("line_width = 0.7", "line_width = -1"), "template.bad-value", "frame.line_width"),
        (("[margins]", "orientation = 'diagonal'\n[margins]"), "template.bad-value", "sheet.orientation"),
        (('name = "test"\n', ""), "template.bad-value", "sheet.name"),
        (("[frame]\nline_width = 0.7\n", ""), "template.bad-value", "frame"),
        (("[margins]", "[extra]\nx = 1\n[margins]"), "template.unknown-key", "extra"),
    ],
)
def test_bad_values(change: tuple[str, str], code: str, where: str) -> None:
    assert (code, where) in codes(refused(BASE.replace(*change)))


def test_toml_syntax_error() -> None:
    error = refused("[sheet\nname = 1")
    assert codes(error) == [("template.bad-value", "")]
    assert "line" in str(error) and "column" in str(error)


def test_too_many_letter_rows() -> None:
    error = refused(ZONES.replace('sizes = ["A4", "A3"]', 'sizes = ["A2"]\norientation = "portrait"'))
    assert ("template.zone-letters", "frame.zone_pitch") in codes(error)
    load_spec(ZONES.replace('sizes = ["A4", "A3"]', 'sizes = ["A2", "A3"]'))  # A2 landscape passes


def test_zones_need_their_figures() -> None:
    error = refused(BASE.replace("line_width = 0.7", "line_width = 0.7\nzones = true"))
    assert {w for _, w in codes(error)} >= {"frame.zone_pitch", "frame.zone_band"}


def test_overlapping_and_outside_cells() -> None:
    cells = "\n[[title_block.cell]]\nrow = 0\ncol = 1\n"
    error = refused(BASE + TITLE.replace("col = 2\n", "col = 5\n") + cells)
    assert ("template.cell-outside", "title_block.cell[1]") in codes(error)
    assert ("template.cell-overlap", "title_block.cell[3]") in codes(error)


def test_title_block_loaded() -> None:
    spec = load_spec(BASE + TITLE)
    block = spec.title_block
    assert (
        block is not None and block.corner == "rb" and block.columns == (30_000_000, 60_000_000, 30_000_000)
    )
    assert [(c.row, c.col, c.span, c.token) for c in block.cells] == [(0, 0, 2, "title"), (0, 2, 1, "sheet"),
                                                                      (1, 0, 1, "param:LOT_NO")]  # fmt: skip
    assert block.cells[2].font_size == 2_500_000 and block.cells[1].justify == "center"


def test_bitmap_table_loaded_and_checked() -> None:
    spec = load_spec(BASE + '[bitmap]\npath = "logo.png"\ncorner = "lt"\nx = 5\ny = 5\nscale = 0.25\n')
    assert spec.bitmap is not None and spec.bitmap.scale_ppm == 250_000
    for bad, where in (('path = "../logo.png"', "bitmap.path"), ('path = "/logo.png"', "bitmap.path"),
                       ('path = "l.png"\nscale = 0.0000001', "bitmap.scale")):  # fmt: skip
        assert ("template.bad-value", where) in codes(refused(BASE + f"[bitmap]\n{bad}\n"))


PROVENANCE = """
[provenance]
sources = ["S-0077"]
licence = "CC0-1.0"

[provenance.values]
"sheet.text_size" = "fenolite-choice"
"sheet.line_width" = "fenolite-choice"
"sheet.text_line_width" = "fenolite-choice"
"margins.left" = "S-0077"
"margins.right" = "S-0077"
"margins.top" = "S-0077"
"margins.bottom" = "S-0077"
"frame.line_width" = "S-0077"
"frame.zone_pitch" = "S-0077"
"frame.zone_band" = "fenolite-choice"
"frame.zone_line_width" = "S-0077"
"frame.zone_text_size" = "S-0077"
"""


def test_provenance_accepted() -> None:
    spec = load_spec(PROVENANCE + ZONES, require_provenance=True)
    assert spec.provenance["margins.left"] == "S-0077" and spec.sources == ("S-0077",)
    assert spec.licence == "CC0-1.0"


def test_missing_number_refused() -> None:
    error = refused(
        PROVENANCE.replace('"frame.zone_pitch" = "S-0077"\n', "") + ZONES, require_provenance=True
    )
    assert codes(error) == [("template.unproven-value", "frame.zone_pitch")]


def test_unlisted_source_refused() -> None:
    text = PROVENANCE.replace('sources = ["S-0077"]', 'sources = ["S-0079"]') + ZONES
    error = refused(text, require_provenance=True)
    assert ("template.unproven-value", "margins.left") in codes(error)


def test_grid_indices_and_arrays() -> None:
    values = (
        PROVENANCE + '"title_block.columns" = "fenolite-choice"\n"title_block.rows" = "fenolite-choice"\n'
    )
    values += '"title_block.line_width" = "fenolite-choice"\n"title_block.label_size" = "fenolite-choice"\n'
    values += '"title_block.cell[2].font_size" = "fenolite-choice"\n'
    load_spec(values + ZONES + TITLE, require_provenance=True)  # row, col and span need no provenance
    without = values.replace('"title_block.cell[2].font_size" = "fenolite-choice"\n', "")
    error = refused(without + ZONES + TITLE, require_provenance=True)
    assert codes(error) == [("template.unproven-value", "title_block.cell[2].font_size")]


def test_licence_required() -> None:
    error = refused(PROVENANCE.replace('licence = "CC0-1.0"\n', "") + ZONES, require_provenance=True)
    assert ("template.unproven-value", "provenance.licence") in codes(error)


def test_user_specification_without_provenance() -> None:
    assert load_spec(BASE).provenance == {}
