# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stack-up presets of fenolite.dsl.stack (capability design-dsl, "Stack-up presets"; change c0101)."""

from __future__ import annotations

import re
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from fenolite.dsl import Design, DslError, mm, stack, to_model
from fenolite.dsl.units import as_nm

ROOT = Path(__file__).resolve().parents[3]
PRESET_FOLDER = ROOT / "src" / "fenolite" / "dsl" / "stackups"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
DSL_PAGE = ROOT / "docs" / "dsl.md"


def table(name: str) -> dict[str, Any]:
    return tomllib.loads((PRESET_FOLDER / f"{name}.toml").read_text(encoding="utf-8"))


def source_rows() -> dict[str, str]:
    """The URL cell of every row of the sources page, by id."""
    rows: dict[str, str] = {}
    for line in SOURCES.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"S-\d{4}", cells[0]):
            rows[cells[0]] = cells[1]
    return rows


def test_presets_are_the_files_in_code_point_order() -> None:
    files = sorted(p.stem for p in PRESET_FOLDER.glob("*.toml"))
    assert stack.PRESETS == tuple(files)
    assert list(stack.PRESETS) == sorted(stack.PRESETS)
    assert 1 <= len(stack.PRESETS) <= 3  # at most three ship with change c0101


def test_names_are_neutral() -> None:
    """No fabricator name in a file name: the name says the copper count and the board thickness."""
    for name in stack.PRESETS:
        assert re.fullmatch(r"(two|four|six)-layer-\d+(\.\d+)?mm", name), name


@pytest.mark.parametrize("name", stack.PRESETS)
def test_every_preset_is_sourced_and_valid(name: str) -> None:
    found = table(name)
    assert set(found) <= {"source", "url", "retrieved", "copper", "finish", "entry"}
    rows = source_rows()
    assert found["source"] in rows, f"{found['source']} is not a row of docs/evidence/sources.md"
    assert rows[found["source"]] == found["url"]
    assert found["url"].startswith("https://")
    date.fromisoformat(found["retrieved"])
    design = Design("preset")
    design.board(mm(50), mm(30), copper=found["copper"])
    design.stackup(*stack.preset(name))
    model = to_model(design)
    assert model.board is not None and model.board.stackup is not None
    coppers = [e for e in found["entry"] if e["kind"] == "copper"]
    assert len(coppers) == found["copper"]


@pytest.mark.parametrize("name", stack.PRESETS)
def test_entries_hold_the_values_of_the_file(name: str) -> None:
    """Every value of the file reaches the entry; nothing else is filled in, and a silkscreen keeps no
    thickness."""
    rows = table(name)["entry"]
    entries = stack.preset(name)
    assert len(entries) == len(rows)
    for row, entry in zip(rows, entries, strict=True):
        assert set(row) <= {"kind", "thickness", "material", "epsilon_r", "loss_tangent"}
        assert entry.kind == row["kind"]
        stated = 0 if row["kind"] == "silkscreen" else as_nm(row["thickness"], name="thickness")
        assert entry.thickness == stated
        assert entry.material == row.get("material", "")
        assert entry.epsilon_r == row.get("epsilon_r", "")
        assert entry.loss_tangent == row.get("loss_tangent", "")
        assert entry.color == ""


def test_four_layer_preset_values() -> None:
    """One preset read value by value against its page (S-0721): 1 oz outer, 0.5 oz inner copper, two
    2113 prepregs and one core."""
    entries = stack.preset("four-layer-1.6mm")
    kinds = [e.kind for e in entries]
    assert kinds == ["silkscreen", "mask", "copper", "prepreg", "copper", "core", "copper", "prepreg",
                     "copper", "mask", "silkscreen"]  # fmt: skip
    assert [e.thickness for e in entries if e.kind == "copper"] == [43_200, 17_500, 17_500, 43_200]
    assert [(e.thickness, e.material, e.epsilon_r) for e in entries if e.kind in ("core", "prepreg")] == [
        (199_900, "FR408HR 2113", "3.61"),
        (990_600, "FR408HR", "3.61"),
        (199_900, "FR408HR 2113", "3.61"),
    ]


def test_preset_on_a_board_of_another_count_is_refused() -> None:
    design = Design("preset")
    design.board(mm(50), mm(30), copper=2)
    with pytest.raises(DslError, match="out of place"):
        design.stackup(*stack.preset("four-layer-1.6mm"))


def test_unknown_preset() -> None:
    with pytest.raises(DslError) as raised:
        stack.preset("nope")
    for name in stack.PRESETS:
        assert name in str(raised.value)


def test_docs_list_each_preset_with_its_url_and_date() -> None:
    page = DSL_PAGE.read_text(encoding="utf-8")
    section = page.split("\n## Stack-up presets\n", 1)[1].split("\n## ", 1)[0]
    for name in stack.PRESETS:
        found = table(name)
        line = next((ln for ln in section.splitlines() if f"`{name}`" in ln), "")
        assert found["url"] in line and found["retrieved"] in line and found["source"] in line, name
