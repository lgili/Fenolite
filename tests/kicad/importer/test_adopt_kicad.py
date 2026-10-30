# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad loads an adopted board (``H-K-IMPORT-ADOPT``; capability layout-lens, scenario "KiCad loads the
adopted board"; change c0275): ``pcb drc`` gives the same violations and unconnected items on the adopted
board as on its source. The source is the authored board built for the running major, as another tool
would hold it."""

from __future__ import annotations

from pathlib import Path

import pytest
from _importcode import built_for, foreign, imported
from _probes import major, runner

pytestmark = pytest.mark.needs_kicad


def test_kicad_loads_the_adopted_board(tmp_path: Path) -> None:
    source = foreign(tmp_path, built_for(tmp_path / "authored", major()))
    reply = imported(tmp_path, source, "--adopt", "--confirm")
    assert reply.exit_code == 0, reply.error
    adopted = tmp_path / "out" / "adopted" / "foreign.kicad_pcb"
    tool = runner()
    before, after = tool.drc(source), tool.drc(adopted)
    assert before.report is not None and after.report is not None
    old, new = before.report.entries(), after.report.entries()
    assert [e for e in new if e[0] == "violations"] == [e for e in old if e[0] == "violations"]

    # an unconnected item names the nearest copper of its net; between items at equal distance the tool
    # picks by its own order, which the new uuids change, so the pads and the counts are compared
    def ends(
        entries: tuple[tuple[str, str, str, bool, tuple[tuple[str, int, int], ...]], ...],
    ) -> list[object]:
        return sorted((e[1], e[4][0]) for e in entries if e[0] == "unconnected_items")

    assert ends(new) == ends(old)
