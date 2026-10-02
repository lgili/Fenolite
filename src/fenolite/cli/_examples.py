# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Example inputs of the read-only commands (change c0013 Decision 19): absolute, so the consistency suite
runs their ``example_args`` from any working directory of a source checkout."""

from __future__ import annotations

from pathlib import Path

import fenolite

EXAMPLE_BOARD = str(
    Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/board/two_layer.kicad_pcb"
)
"""The authored two-layer board of the test data."""

__all__ = ["EXAMPLE_BOARD"]
