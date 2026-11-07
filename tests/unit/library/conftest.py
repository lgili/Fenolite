# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fixtures of the library-repository tests (change c0279): a copy of the authored demo library."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[2] / "data" / "library_repo" / "demo"


@pytest.fixture
def demo(tmp_path: Path) -> Path:
    """A writable copy of ``tests/data/library_repo/demo``."""
    target = tmp_path / "demo"
    shutil.copytree(DEMO, target)
    return target
