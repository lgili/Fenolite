# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every example builds the bytes recorded before change c0277 (design-dsl, "Coverage items keep existing
builds", scenario "Examples keep their bytes"; task 0.1 records the table, task 4.5 guards it).

The table ``tests/data/build_bytes.json`` was measured by ``tests/_buildbytes.py`` on the base commit of
change c0277 (8dab89d6, branch ``circuits-as-code``), before any product code of the change: one row per
example and target with the exit code of the dry-run build and the SHA-256 of each planned file. A digest
moves only with the change that changes the writer, never to make a test pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _buildbytes import TABLE, TARGETS, examples, measure

RECORDED: dict[str, dict[str, object]] = json.loads(TABLE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_table_covers_every_example() -> None:
    assert sorted(RECORDED) == sorted(f"{e}@{t}" for e in examples() for t in TARGETS)


@pytest.mark.parametrize("row", sorted(RECORDED))
def test_example_keeps_its_bytes(row: str, tmp_path: Path) -> None:
    example, target = row.split("@")
    found = measure(example, target, tmp_path / f"{example}-{target}")
    assert found == RECORDED[row]
