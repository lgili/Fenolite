# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The panel script of the guide page ``fabrication`` runs (change c0173; ``AGENTS.md``, "Teach what you
add"): written beside the fixture board, ``fenolite panel --dry-run`` plans it with no error."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _panels import committed_board, run

from fenolite.agent import guide


def _sample() -> str:
    page = guide.page("fabrication")
    text = page.text[page.text.index("## Panels") :]
    block = next(
        b for b in guide.blocks(guide.Page(page.topic, page.title, page.summary, text)) if b.tag == "text"
    )
    return "\n".join(block.lines) + "\n"


def test_the_guide_panel_sample_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "build").mkdir()
    shutil.copyfile(committed_board(10), tmp_path / "build" / "blink.kicad_pcb")
    (tmp_path / "blink_panel.py").write_text(_sample(), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    code, envelope, err = run("panel", "blink_panel.py", "--out", "panel", "--target", "10", "--dry-run")
    assert code == 0, (err, envelope.get("issues"))
    result = envelope["result"]
    assert isinstance(result, dict) and result["panel"]["copies"] == 8
