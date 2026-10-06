# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The guide of the assembly tables, ``docs/assembly.md`` (capability assembly-outputs, "Assembly issue
codes and evidence", scenario "Guide present"; change c0064)."""

from __future__ import annotations

import re
from pathlib import Path

from _assembly import LED, QFP, R_0603, Part, design_of, rectangle

from fenolite.backends.kicad.outline import board_outline
from fenolite.exports import bom, placement
from fenolite.exports.assembly import read_template, render_csv

ROOT = Path(__file__).resolve().parents[3]
GUIDE = ROOT / "docs" / "assembly.md"


def test_guide_examples_are_valid_templates() -> None:
    """Every ``toml`` block of the guide reads as a template."""
    blocks = re.findall(r"```toml\n(.*?)```", GUIDE.read_text(encoding="utf-8"), flags=re.DOTALL)
    assert blocks
    for block in blocks:
        read_template(block, file="docs/assembly.md")


def test_guide_says_what_ships() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    assert "ships no template of any assembly service" in guide
    assert "made up" in guide and "--source model" in guide
    for key in ("sign", "offset", "match", "origin", "y_axis", "units", "group_by", "exclude_dnp"):
        assert f"`{key}`" in guide, key


def test_guide_is_linked() -> None:
    for page in ("README.md", "docs/exports.md"):
        assert "assembly.md" in (ROOT / page).read_text(encoding="utf-8"), page


def test_worked_example_gives_the_files_the_guide_shows() -> None:
    """The two files printed under "A worked example" are what the example template renders for the
    blink's parts (their positions as a build writes them, and the made-up property ``Bin`` on ``R1``)."""
    guide = GUIDE.read_text(encoding="utf-8")
    template = read_template(re.findall(r"```toml\n(.*?)```", guide, flags=re.DOTALL)[0])
    shown = {
        block.split(";", 1)[0]: block
        for block in re.findall(r"```text\n(.*?)```", guide, flags=re.DOTALL)
        if ";" in block.splitlines()[0]
    }
    design = design_of(
        Part("U1", "MCU", QFP, x=114, y=115),
        Part("R1", "330", R_0603, x=132, y=109, properties={"Bin": "A7"}),
        Part("D1", "LED", LED, x=138, y=120, side="bottom", attributes=("through_hole",)),
        outline=rectangle(100, 100, 50, 30),
    )
    lines = bom.group(bom.parts_from_model(design), template.bom)
    bill = render_csv([c.name for c in template.bom.columns], bom.table(lines, template.bom), template.csv)
    assert bill.decode("utf-8").replace("\r\n", "\n") == shown["Parts"]
    rows = placement.apply(
        placement.rows_from_model(design), template.placement, outline=board_outline(design)
    )
    table = placement.table(rows, template.placement)
    placed = render_csv([c.name for c in template.placement.columns], table, template.csv)
    assert placed.decode("utf-8").replace("\r\n", "\n") == shown["Part"]
    assert placed.endswith(b"\r\n")
