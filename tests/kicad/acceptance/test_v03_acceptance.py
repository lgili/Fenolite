# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The independent acceptance run of c0092, kept outside the quick suite."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest
from _probes import runner

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10), pytest.mark.slow]
ROOT = Path(__file__).resolve().parents[3]


def test_v03_acceptance(tmp_path: Path) -> None:
    tool = runpy.run_path(str(ROOT / "tools/acceptance_v03.py"))
    report = tool["run"](tmp_path, kicad_cli=str(runner().path))
    assert report["passed"], report["steps"]
