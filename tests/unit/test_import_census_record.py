# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored census preflight covers every selected board without loading CAD payloads (c0311)."""

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_import_census_covers_every_selected_board_including_heavy() -> None:
    census = runpy.run_path(str(ROOT / "tests/corpus/test_import_corpus.py"))
    expected = {item.id.removeprefix(census["PREFIX"]) for item in census["ITEMS"]}
    rows = census["recorded"]()
    assert set(rows) == expected, {
        "missing": sorted(expected - rows.keys()),
        "extra": sorted(rows.keys() - expected),
    }
