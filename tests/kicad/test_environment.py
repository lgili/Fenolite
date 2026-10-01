# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Environment facts per kicad-cli major (hypotheses H-K-00, H-K-01, H-K-02)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from _kicad import loads, major, run_raw, supported_version

pytestmark = pytest.mark.needs_kicad
SKELETON = Path(__file__).resolve().parents[1] / "data" / "kicad" / "tokens" / "skeleton.kicad_pcb"


def test_import_command_only_in_10() -> None:
    """H-K-00: `pcb import` exists in 10.0 and not in 9.0."""
    listed = re.search(r"^\s+import\b", _help("pcb"), re.MULTILINE)
    assert bool(listed) == (major() == 10), f"H-K-00 must be updated: kicad-cli {supported_version()}"


def _help(*command: str) -> str:
    result = run_raw(*command, "--help")
    return result.stdout + result.stderr


def test_refill_options_only_in_10() -> None:
    """H-K-01: `pcb drc --refill-zones` and `--save-board` exist in 10.0 only."""
    text = _help("pcb", "drc")
    present = ("--refill-zones" in text, "--save-board" in text)
    expected = (major() == 10, major() == 10)
    assert present == expected, (
        f"H-K-01 must be updated and the zone-fill approach revisited: kicad-cli {supported_version()} "
        f"lists --refill-zones={present[0]}, --save-board={present[1]}"
    )


def test_version_parses_and_baseline_exports(tmp_path: Path) -> None:
    """H-K-02: a parseable version (printed for the record) and the board positive baseline loads."""
    version = supported_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", version)
    board = tmp_path / "skeleton.kicad_pcb"
    shutil.copy(SKELETON, board)
    assert loads(board)
