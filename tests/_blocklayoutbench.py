# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored versioned layout assets in isolated build folders (c0271)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _relbench import Bench

from fenolite.model import canonical
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/data/blocks/bench/divider.py"
LAYOUT = ROOT / "tests/data/blocks/lib/layouts/divider.toml"
MM = 1_000_000


def make_bench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    layout: bool = True,
    copper: bool = True,
    bottom: bool = False,
) -> Bench:
    text = SOURCE.read_text(encoding="utf-8")
    if layout:
        text = text.replace("    top.place(mm(0), mm(0), rot=90)\n", "").replace(
            '    bot.place(mm(0), mm("2.5"), rot=90)\n', ""
        )
        text += f'\ndut.layout(reuse="divider.toml", copper={copper})\n'
    if bottom:
        text = text.replace("dut.place(mm(10), mm(8))", 'dut.place(mm(10), mm(8), side="bottom")')
    bench = Bench(tmp_path, monkeypatch, text, "divider_bench")
    (bench.folder / "divider.toml").write_bytes(LAYOUT.read_bytes())
    return bench


def built_model(bench: Bench) -> Design:
    return canonical.load_dir(bench.out / ".fenolite")
