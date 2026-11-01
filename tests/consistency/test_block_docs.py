# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pages of the shipped blocks are current (capability block-library, "Shipped block pages are
current"; change c0268)."""

from __future__ import annotations

import dataclasses
import importlib.util
import runpy
import shutil
from pathlib import Path

from fenolite.dsl import describe

ROOT = Path(__file__).resolve().parents[2]
TOOL = runpy.run_path(str(ROOT / "tools" / "gen_block_docs.py"))


def divider() -> object:
    spec = importlib.util.spec_from_file_location(
        "_c0268_docs_divider", ROOT / "tests" / "data" / "blocks" / "divider.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return describe(module.divider)


def test_block_docs_are_current() -> None:
    assert TOOL["main"](["--check"]) == 0


def test_block_docs_stale_page(tmp_path: Path) -> None:
    """Scenario "Stale page": a block whose summary changed and whose page was not regenerated."""
    record = divider()
    (tmp_path / "docs" / "evidence").mkdir(parents=True)
    shutil.copy(ROOT / "docs" / "evidence" / "sources.md", tmp_path / "docs" / "evidence" / "sources.md")
    titles = TOOL["source_titles"](tmp_path)
    for path, text in TOOL["pages"]([record], titles).items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text, encoding="utf-8")
    assert TOOL["differences"](TOOL["pages"]([record], titles), tmp_path) == []
    header = dataclasses.replace(record.header, summary="Another summary")  # type: ignore[arg-type]
    changed = dataclasses.replace(record, header=header)  # type: ignore[arg-type]
    problems = TOOL["differences"](TOOL["pages"]([changed], titles), tmp_path)
    assert any(p.startswith("docs/blocks/divider.md: stale") for p in problems), problems


def test_block_docs_source_titles() -> None:
    titles = TOOL["source_titles"]()
    assert titles["S-0001"].startswith("https://")
