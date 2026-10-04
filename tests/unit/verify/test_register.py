# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reading the hypothesis register and its reserved families (capability verification-evidence)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.core.evidence import Level
from fenolite.verify import load_families, load_register

ROOT = Path(__file__).resolve().parents[3]
LIVE = ROOT / "docs" / "hypotheses.md"
HEADER = (
    "| id | backend | statement | level | test or kit request | criterion | result | date |\n"
    "|---|---|---|---|---|---|---|---|\n"
)
FAMILIES = "| family | backend | rows for | owner |\n|---|---|---|---|\n"


def _row(ident: str = "H-K-UNIT", level: str = "INFERRED", result: str = "pending") -> str:
    return f"| {ident} | kicad | a claim | {level} | a test | a criterion | {result} | 2026-10-01 |\n"


def _write(tmp_path: Path, text: str, name: str = "reg.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_live_register_loads() -> None:
    rows = load_register(LIVE)
    expected = sum(1 for line in LIVE.read_text(encoding="utf-8").splitlines() if line.startswith("| H-"))
    assert len(rows) == expected and all(isinstance(r.level, Level) for r in rows)


def test_level_text_is_kept(tmp_path: Path) -> None:
    (row,) = load_register(_write(tmp_path, HEADER + _row(level="KICAD-VERIFIED (10.0.x)")))
    assert row.level is Level.KICAD_VERIFIED and row.level_text == "KICAD-VERIFIED (10.0.x)"
    assert (row.id, row.backend, row.date) == ("H-K-UNIT", "kicad", "2026-10-01")


def test_seven_cells_are_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, HEADER + "| H-K-UNIT | kicad | a | INFERRED | b | c | d |\n")
    with pytest.raises(ValueError, match=r"reg\.md:3.*8 cells"):
        load_register(path)


def test_unknown_level_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r":3: .*MAYBE"):
        load_register(_write(tmp_path, HEADER + _row(level="MAYBE")))


def test_bad_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r":3: 'H-K-unit'"):
        load_register(_write(tmp_path, HEADER + _row(ident="H-K-unit")))


def test_escaped_pipe_stays_in_its_cell(tmp_path: Path) -> None:
    (row,) = load_register(_write(tmp_path, HEADER + _row(result=r"pending \| later")))
    assert row.result == "pending | later"


def test_register_table_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reg.md: expected one register table, found 0"):
        load_register(_write(tmp_path, "no table\n"))
    with pytest.raises(ValueError, match="found 2"):
        load_register(_write(tmp_path, HEADER + _row() + "\n" + HEADER + _row()))


def test_successor_is_parsed() -> None:
    row = next(r for r in load_register(LIVE) if r.id == "H-K-TOK-FUTURE")
    assert row.refuted is True and row.successor == "H-K-TOK-FUTURE-2"


def test_partial_refutation_is_not_a_refutation() -> None:
    row = next(r for r in load_register(LIVE) if r.id == "H-K-FMT-MIXED")
    assert row.result.startswith("partly refuted") and row.refuted is False and row.successor is None


def test_settling_tests_are_named() -> None:
    rows = {r.id: r for r in load_register(LIVE)}
    assert (
        "test_flip_oracle.py::test_lib_drc" in rows["H-K-LIB-DRC"].test
        and "c0017" in rows["H-K-LIB-DRC"].test
    )
    shapely = rows["H-G-SHAPELY-GC"].test
    assert "test_boolean_shapely.py::test_line_parts_dropped" in shapely and "v0.3" in shapely


def test_families_of_the_live_register() -> None:
    families = load_families(LIVE)
    assert {"H-A-WRITE-*", "H-A-PH-*", "H-G-DSN-*"} <= set(families)
    assert "H-K-KRT-*" not in families


def test_family_cell_without_a_wildcard_is_rejected(tmp_path: Path) -> None:
    text = HEADER + _row() + "\n" + FAMILIES + "| `H-K-UNIT` | kicad | routing | later |\n"
    with pytest.raises(ValueError, match=r"reg\.md:7"):
        load_families(_write(tmp_path, text))


def test_register_without_a_families_table(tmp_path: Path) -> None:
    assert load_families(_write(tmp_path, HEADER + _row())) == ()


def test_two_families_tables_are_rejected(tmp_path: Path) -> None:
    table = FAMILIES + "| `H-K-KRT-*` | kicad | routing | later |\n"
    with pytest.raises(ValueError, match="reg.md"):
        load_families(_write(tmp_path, table + "\n" + table))


def test_family_rows_are_not_register_rows() -> None:
    lines = LIVE.read_text(encoding="utf-8").splitlines()
    assert sum(1 for line in lines if line.startswith("| `H-")) == len(load_families(LIVE))
    assert sum(1 for line in lines if line.startswith("| H-")) == len(load_register(LIVE))
