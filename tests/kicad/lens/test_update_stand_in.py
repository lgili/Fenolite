# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A rebuild over a board that the stand-in for KiCad's "Update PCB from Schematic" has touched is loaded
by ``kicad-cli`` and agrees with the schematic (capability layout-lens, "Boards updated from the schematic
keep their layout"; change c0061). What the real update writes is not measured here: no headless command
runs it, and ``H-K-SCH-UPDATE`` stays ``INFERRED``."""

from __future__ import annotations

import _erc
import _probes
import pytest
from _buildhelp import blink, build
from _layout_edit import EDIT_UUIDS, edit_blink, update_from_schematic
from _preserve_help import rebuild

pytestmark = pytest.mark.needs_kicad


def test_rebuild_after_the_stand_in_is_accepted() -> None:
    target = _probes.major()
    first = build(blink(), target)
    board, sheet = (first.files[name].decode("utf-8") for name in ("blink.kicad_pcb", "blink.kicad_sch"))
    updated = update_from_schematic(edit_blink(board), sheet)
    again = rebuild(blink(), updated, target)
    assert again.summary["preserved"]["kept"] == ["D1", "R1", "U1"]  # type: ignore[index]
    text = again.files["blink.kicad_pcb"].decode("utf-8")
    assert all(uuid in text for uuid in EDIT_UUIDS) and text.count('(sheetfile "blink.kicad_sch")') == 3
    files = {rel: data for rel, data in again.files.items() if not rel.startswith(".fenolite/")}
    report = _erc.run_parity(_probes.runner(), "blink.kicad_pcb", files)
    assert report.loaded, report.stderr
    found = _erc.parity(report)
    assert found == [], [(item["type"], item["description"]) for item in found]
    updated_files = {**files, "blink.kicad_pcb": updated.encode("utf-8")}
    before = _erc.run_parity(_probes.runner(), "blink.kicad_pcb", updated_files)
    assert before.loaded and _erc.parity(before) == []
    erc = _erc.run_erc(_probes.runner(), "blink.kicad_sch", files, exit_code=True)
    assert erc.returncode == 0 and _erc.violations(erc) == []
    print(f"rebuild after the update stand-in: loaded, parity 0, ERC 0 on kicad-cli {_probes.version()}")
