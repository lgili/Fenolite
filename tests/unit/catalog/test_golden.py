# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The shipped catalog gives the bytes recorded before its move to data files (change c0259; capability
fenolite-component-catalog, "The move to data keeps every byte", scenario "Definitions equal the golden
digests"). The built files of the catalog examples are compared in the KiCad job
(``tests/kicad/build/test_catalog_golden.py``)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = json.loads((ROOT / "tests" / "data" / "catalog" / "golden.json").read_text(encoding="utf-8"))


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("golden", ROOT / "tools" / "catalog" / "golden.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_definitions_equal_the_golden_digests() -> None:
    found = _tool().definitions()
    assert set(found) == set(GOLDEN["definitions"])
    changed = sorted(lib_id for lib_id, digest in found.items() if GOLDEN["definitions"][lib_id] != digest)
    assert changed == []


def test_review_sheets_equal_the_golden_digests() -> None:
    assert _tool().renders() == GOLDEN["renders"]


def test_golden_records_the_catalog_examples() -> None:
    examples = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "examples").glob("catalog*/*.py"))
    assert sorted(GOLDEN["builds"]) == examples
    assert all(files and ".fenolite/meta.json" not in files for files in GOLDEN["builds"].values())
