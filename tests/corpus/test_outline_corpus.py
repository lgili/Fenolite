# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Does ``board_outline`` close a ring, or name its problem, for every readable demo board? (capability
kicad-file-backend, "Board outline as rings"; ``H-G-PLACE-OUTLINE``; change c0022).

A measurement over the readable non-heavy demo boards: it fails only when ``board_outline`` raises or
breaks its own contract, and records counts (never content) through ``census`` for
``docs/evidence/kicad-board-read.md``. Where a ``kicad-cli`` 10.0 is present, each verdict is compared with
``board.has_outline`` of KiCad's own ``pcb export stats``; the comparison is recorded, not asserted, because
KiCad also chains the edge items of footprints, which stay opaque here.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import cast

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import census
from _corpus import require
from _resources import kicad_cli

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.outline import PROBLEMS, board_outline
from fenolite.geometry import area2


def _has_outline(runner: KicadCli, path: Path) -> bool | None:
    """``board.has_outline`` of ``pcb export stats`` (``None`` when the tool gives no answer)."""
    try:
        stats = runner.export_stats(path)
    except Exception:
        return None
    board = stats.get("board")
    if not isinstance(board, dict):
        return None
    found = cast(dict[str, object], board).get("has_outline")
    return found if isinstance(found, bool) else None


@pytest.mark.needs_corpus
def test_outlines() -> None:
    items = [i for i in READABLE_ITEMS if i.path.is_file() and not i.heavy]
    if not items:
        require(READABLE_ITEMS[0])  # skips, or fails in required-resource mode
    tool = kicad_cli()
    runner = KicadCli(Path(tool), timeout=600) if tool is not None else None
    if runner is not None and runner.major() < 10:
        runner = None  # 9.0 has no ``pcb export stats``
    counts: Counter[str] = Counter()
    for item in items:
        design, _ = read(item.path)
        found = board_outline(design)  # must not raise
        counts["boards"] += 1
        if found.rings:
            assert found.problem == "" and found.source == "edge"
            assert all(len(ring) >= 3 and area2(ring) != 0 for ring in found.rings)
            assert all(abs(area2(found.rings[0])) >= abs(area2(ring)) for ring in found.rings)
            counts["source:edge"] += 1
            counts["rings"] += len(found.rings)
            counts["boards:approximated"] += not found.exact
        else:
            assert found.problem in PROBLEMS
            counts[f"problem:{found.problem}"] += 1
        if runner is not None:
            theirs = _has_outline(runner, item.path)
            ours = "ring" if found.rings else "no-ring"
            counts[
                f"kicad:{'unknown' if theirs is None else 'outline' if theirs else 'no-outline'}:{ours}"
            ] += 1
    census("outline-rings", "native", dict(sorted(counts.items())))
    assert counts["boards"] == len(items)
    assert counts["source:edge"] + sum(counts[f"problem:{p}"] for p in PROBLEMS) == len(items)
