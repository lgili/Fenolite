# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The repository keeps a fixed, documented directory layout."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

DIRECTORIES = [
    "src/fenolite",
    "tests/unit",
    "docs/adr",
    "docs/evidence",
    "docs/formats",
    "tools",
    "schemas",
    "examples",
    "openspec",
    "verify_results",
]
MARKERS = ("README.md", ".gitkeep", "__init__.py")


@pytest.mark.parametrize("rel", DIRECTORIES)
def test_directory_exists_and_is_documented(rel: str) -> None:
    path = ROOT / rel
    assert path.is_dir(), f"missing directory {rel}"
    assert any((path / m).is_file() for m in MARKERS), f"{rel} has no README.md, .gitkeep or __init__.py"


@pytest.mark.parametrize("rel", ["private/notes.md", ".fenolite/board.json", "x.PcbDoc.bak"])
def test_private_and_derived_paths_are_ignored(rel: str) -> None:
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", rel], cwd=ROOT, check=False, capture_output=True
    )
    assert result.returncode == 0, f"{rel} is not ignored by .gitignore"
