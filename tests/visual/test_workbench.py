# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The workbench of the viewer page (change c0245): frame budgets, and later the shell, layouts, keymaps,
selection, linked messages and provenance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _budget import SCRIPT, summary
from _visual import job, run

pytestmark = pytest.mark.needs_browser


def test_budget_baseline(stress_page: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Task 0.2: the page's frame, cursor and open times on the stress board, printed for the record."""
    (reply,) = run([job("budget", stress_page, tmp_path, script=SCRIPT, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["prims"] > 20_000
    assert result["frame_p95_ms"] > 0 and result["open_ms"] > 0
    (tmp_path / "budget.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with capsys.disabled():
        print(f"\nc0245 budget baseline: {summary(result)}")
