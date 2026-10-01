# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored S-expression fixtures: parse outcomes and the mirror rule, without KiCad."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends.kicad import load
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "sexpr"
CLASSES = {"mirror", "unmirrored", "semantic"}


def expectations() -> list[dict[str, Any]]:
    return list(tomllib.loads((ROOT / "EXPECT.toml").read_text(encoding="utf-8"))["fixture"])


def parse_outcome(path: Path) -> str:
    try:
        load(path)
    except FormatError as error:
        return error.message
    return "accept"


def row_problems(rows: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for row in rows:
        name = str(row.get("file"))
        if row.get("class") not in CLASSES:
            problems.append(f"{name}: class must be one of {sorted(CLASSES)}")
        if not str(row.get("hypothesis", "")).startswith("H-K-"):
            problems.append(f"{name}: no hypothesis id")
        if row.get("class") == "mirror":
            for key in ("expect_kicad_10", "expect_kicad_9"):
                if key in row and (row["expect_parse"] != "accept") != (row[key] == 3):
                    problems.append(f"{name}: mirror row must reject exactly when {key} is 3")
        if row.get("class") == "semantic" and row.get("expect_parse") != "accept":
            problems.append(f"{name}: semantic fixtures must parse")
    return problems


def test_every_fixture_has_one_row() -> None:
    files = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.kicad_pcb"))
    listed = sorted(str(r["file"]) for r in expectations())
    assert files == listed


def test_rows_are_consistent() -> None:
    problems = row_problems(expectations())
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("row", expectations(), ids=lambda r: str(r["file"]))
def test_parse_outcome(row: dict[str, Any]) -> None:
    outcome = parse_outcome(ROOT / str(row["file"]))
    expected = str(row["expect_parse"])
    if expected == "accept":
        assert outcome == "accept"
    else:
        assert expected in outcome, outcome


def test_inconsistent_mirror_row_is_reported() -> None:
    row = {"file": "mirror/x.kicad_pcb", "class": "mirror", "expect_parse": "accept", "expect_kicad_10": 3,
           "hypothesis": "H-K-SEXPR-LEX-10"}  # fmt: skip
    assert row_problems([row]) == [
        "mirror/x.kicad_pcb: mirror row must reject exactly when expect_kicad_10 is 3"
    ]
