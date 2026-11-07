# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Part J kit board, built once per run, and a fresh copy of it per test (change c0241)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from fenolite.backends.altium import edit
from tests.unit.backends.altium.test_part_j import build_board

OPEN = dict.fromkeys(edit.OPERATIONS, True)
"""Every gate open: the tests exercise the operations, the gates stay off in ``edit.GATES``."""


def mm(value: float) -> int:
    """``value`` millimetres in nanometres."""
    return round(value * 1_000_000)


@pytest.fixture(scope="session")
def kit_board(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("part-j") / "board"
    build_board(folder)
    return folder


@pytest.fixture
def board(kit_board: Path, tmp_path: Path) -> Path:
    """A copy of the kit project in ``tmp_path``; its ``edit.PcbDoc``."""
    target = tmp_path / "board"
    shutil.copytree(kit_board, target)
    return target / "edit.PcbDoc"
