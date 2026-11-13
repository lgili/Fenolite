# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Part J kit board, built once per run, and a fresh copy of it per test (change c0241)."""

from __future__ import annotations

import shutil
from collections.abc import Callable
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


@pytest.fixture(scope="session")
def board_ops(kit_board: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, bytes]:
    """The test boards of change c0497 (``board_ops``), by name."""
    from tests.unit.backends.altium.edit import board_ops as boards

    data = (kit_board / "edit.PcbDoc").read_bytes()
    folder = tmp_path_factory.mktemp("c0497")
    return {"drawn": boards.drawn(data), "vias": boards.vias(data), "texts": boards.texts(data, folder)}


@pytest.fixture
def ops_board(board_ops: dict[str, bytes], tmp_path: Path) -> Callable[[str], Path]:
    """Write the c0497 board ``name`` to ``tmp_path/<name>.PcbDoc``; its path."""

    def write(name: str) -> Path:
        path = tmp_path / f"{name}.PcbDoc"
        path.write_bytes(board_ops[name])
        return path

    return write
