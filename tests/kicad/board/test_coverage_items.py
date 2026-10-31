# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The coverage items of change c0277 on the running ``kicad-cli`` (capability kicad-oracle, "Coverage items
pass the oracle"; task 4.4): the board of ``examples/board_coverage`` is built for the running major, loaded
by ``pcb drc`` with no violation that names an item, and on 10.0 re-saved with every item kept."""

from __future__ import annotations

import os
import tempfile
from functools import cache
from pathlib import Path

import pytest

from fenolite.backends.kicad.sexpr import parse

pytestmark = pytest.mark.needs_kicad

ROOT = Path(__file__).resolve().parents[3]
HEADS = ("image", "group", "dimension", "target")
"""Root items of the coverage board that a re-save must keep."""


@cache
def built(target: int) -> tuple[str, Path]:
    from fenolite.api import run

    folder = Path(tempfile.mkdtemp(prefix="fenolite-coverage-"))
    os.environ["KICAD_CONFIG_HOME"] = str(folder / "kicad-config")
    reply = run(
        "build", str(ROOT / "examples" / "board_coverage" / "design.py"), "--out", str(folder / "out"),
        "--kicad-version", str(target), "--confirm", cwd=folder, timestamp="2026-10-30T00:00:00Z", seed=1,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    board = folder / "out" / "coverage.kicad_pcb"
    return board.read_text(encoding="utf-8"), board


def _counts(text: str) -> dict[str, int]:
    root = parse(text)
    found = {head: len(root.nodes(head)) for head in HEADS}
    found["teardrops"] = text.count("(teardrops")
    found["shaped"] = sum(text.count(f"({head}") for head in ("rect_delta", "chamfer_ratio", "primitives"))
    return found


@pytest.mark.parametrize("target", [pytest.param(10, marks=pytest.mark.kicad_min_major(10)), 9])
def test_items_load(target: int) -> None:
    """Scenarios "Items on KiCad 10" and "Items on KiCad 9": the board loads, and no violation names a
    coverage item (an image, a dimension, a group, a target or a shaped pad)."""
    from _probes import runner

    text, board = built(target)
    pro = board.with_suffix(".kicad_pro")
    drc = runner().drc(board, files={pro.name: pro})
    assert drc.report is not None
    words = ("image", "dimension", "group", "target", "Shaped_Pads", "teardrop")
    named = [v for v in drc.report.violations if any(w in str(v) for w in words)]
    assert named == [], named
    assert _counts(text)["shaped"] == 3  # the board pads keep the shapes of the vendored footprint's text


@pytest.mark.kicad_min_major(10)
def test_items_survive_a_resave() -> None:
    from _probes import runner

    text, board = built(10)
    pro = board.with_suffix(".kicad_pro")
    saved = runner().upgrade_board(board, files={pro.name: pro}).decode("utf-8")
    before, after = _counts(text), _counts(saved)
    for head in (*HEADS, "shaped"):
        assert after[head] == before[head], head
    assert after["teardrops"] >= 1
