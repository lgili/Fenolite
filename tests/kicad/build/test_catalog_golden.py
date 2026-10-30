# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog examples build to the bytes recorded before the catalog's move to data files (change c0259;
capability fenolite-component-catalog, scenario "Built files are byte-identical"; hypothesis
H-K-CATALOG-DATA). Run in the KiCad job, beside the oracle tests of the same builds."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = json.loads((ROOT / "tests" / "data" / "catalog" / "golden.json").read_text(encoding="utf-8"))
pytestmark = pytest.mark.needs_kicad


def test_built_files_are_byte_identical(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    spec = importlib.util.spec_from_file_location("golden", ROOT / "tools" / "catalog" / "golden.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    built = tool.builds()
    base = "fenolite-base.json"  # the base record of the three-way merge (c0250), written after the golden
    for example, files in GOLDEN["builds"].items():
        built[example].pop(base, None)
        assert set(built[example]) == set(files), example
        changed = sorted(path for path, digest in files.items() if built[example][path] != digest)
        print(f"{example}: {len(files)} files, changed {changed}")
        assert changed == [], example
