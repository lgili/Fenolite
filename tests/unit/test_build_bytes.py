# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every example builds the bytes recorded before change c0277 (design-dsl, "Coverage items keep existing
builds", scenario "Examples keep their bytes"; task 0.1 records the table, task 4.5 guards it).

The active table was remeasured from the clean integration base ``7c2f1df2`` before merging c0277.
All 72 pre-existing example/target rows were independently compared with the merged implementation.
The six families/picks circuit.json digests use root checkpoint 51c877b8: the complete planned-file maps
match that clean base independently, and only those six canonical circuit digests differ from 7c2f1df2.
Every native output and all other recorded digests remain unchanged. Only the three ``board_coverage``
rows come from c0277's new example. The original
``8dab89d6`` snapshot remains in Git history; concurrent catalog, lock and library changes explain its
differences from this integration base. A digest moves only with a documented writer change.

c0276 preserves hidden power pins in drawn schematics instead of making them visible as generated
schematics do. Only drawn@9 and drawn@10 were remeasured for that writer change; all other157 focused
example and generated-design guards passed unchanged before the two rows were refreshed.
The authored import_python snapshot now also carries the source drawing and native symbols; only its
three example rows were remeasured for that explicit source change (c0276 task 4.6).
The native drawn Altium writer moves only drawn@altium and import_python@altium: the project/root
schematic, their new native child sheets and removal of the generated-layout cache. Both examples
retain their exact Altium PCB and library digests (c0276 task 6.1).
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
    found = measure(example, target, tmp_path / f"{example}-{target}", expected=RECORDED[row])
    assert found == RECORDED[row]
