# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A corpus board written for its own target 9 against ``kicad-cli`` (capability kicad-file-backend, "Net
form per target"; change c0163).

``RoyalBlue54L-Feather`` (``kicad-demo-10-0-6-pcb-13``, format ``20241229``) holds teardrops on nets stored
with ``{slash}``; ``write_board`` refused it for target 9 before c0163. Its target-9 text must load and give
the DRC report of the source, judged as RT2 judges a re-dump (``fenolite.checks.rt2.compare_runs``):
KiCad does not repeat its own report on this board (22 to 52 of about 1 100 entries differed between two
runs of one file in 9.0.9, all of them clearances), so each side runs three times and a key whose count
differs between the runs of one side is left out. Both sides use the same ``{}`` project. The proof runs
on 9.0.9; 10.0.6 reads the text too. Copies are made in ``tmp_path`` only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _corpus import CorpusItem
from _probes import runner
from _projects import STEM, demo_project

from fenolite.backends.base import DrcReport, Rt2Outcome
from fenolite.backends.kicad.pcb import write_board
from fenolite.checks.rt2 import compare_runs

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.slow]
ROYALBLUE = "kicad-demo-10-0-6-pcb-13"
RUNS = 3


def _reports(root: Path) -> tuple[DrcReport, ...]:
    files = {name: root / name for name in (f"{STEM}.kicad_pro", f"{STEM}.kicad_dru")}
    reports: list[DrcReport] = []
    for _ in range(RUNS):
        report = runner().drc(root / f"{STEM}.kicad_pcb", files=files).report
        assert report is not None, root.name
        reports.append(report)
    return tuple(reports)


@pytest.mark.parametrize("item", [i for i in READABLE_ITEMS if i.id == ROYALBLUE], ids=lambda i: i.id)
def test_written_for_target_9_keeps_the_drc_report(item: CorpusItem, tmp_path: Path) -> None:
    source = demo_project(tmp_path / "source", item)
    written = demo_project(tmp_path / "written", item)
    board = written / f"{STEM}.kicad_pcb"
    board.write_text(write_board(read(item.path)[0], target=9).text, encoding="utf-8")
    loaded = runner().load_board_svg(board, files={f"{STEM}.kicad_pro": written / f"{STEM}.kicad_pro"})
    assert loaded.ok and "out.svg" in loaded.outputs, item.id
    after = _reports(written)
    outcome = Rt2Outcome(_reports(source), after[0], False, runner().version(), repeats=after[1:])
    verdict = compare_runs(outcome)
    assert verdict is not None and verdict.holds, (item.id, verdict)
    print(f"{item.id}: DRC parity on {runner().version()}, {verdict.unstable} unstable key(s) left out")
