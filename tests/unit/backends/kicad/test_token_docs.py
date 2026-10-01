# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generated token page (capability kicad-token-inventory, requirement "Generated token page")."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[4]


def _tool() -> ModuleType:
    name = "fenolite_gen_token_docs"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "gen_token_docs.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_committed_page_is_current() -> None:
    assert _tool().main(["--check"]) == 0


def test_drift_detected(tmp_path: Path) -> None:
    page = tmp_path / "tokens.md"
    page.write_text((ROOT / "docs/formats/kicad/tokens.md").read_text(encoding="utf-8") + "| extra | row |\n")
    assert _tool().main(["--check", "--page", str(page)]) == 1


def test_page_lists_every_row_and_note() -> None:
    from fenolite.backends.kicad.versions import load_inventory

    text = (ROOT / "docs/formats/kicad/tokens.md").read_text(encoding="utf-8")
    inventory = load_inventory()
    assert all(f"| {row.id} |" in text for row in (*inventory.tokens, *inventory.forms))
    assert all(f"| {note.version} |" in text for note in inventory.notes)
