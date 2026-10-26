# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad imports a large document and a full-stack pad (capability altium-pcb-writer, "DIFAT sectors in a
written compound file" scenario "KiCad imports a large document", and "Full-stack pad records"; change
c0160; hypotheses ``H-A-CONV-DIFAT`` and ``H-A-CONV-PADSTACK``).

``vme-wren``, the demo board whose written PCB document needs 181 FAT sectors and so DIFAT sectors, and the
committed board ``padstack.kicad_pcb``, whose one pad has a per-layer stack written with stack mode 1, are
converted to Altium and imported back with ``kicad-cli pcb import`` 10.0.6, and compared with the design
that was written at level 4 under the importer's profile ``kicad-import``. The probes ``convert-difat`` and
``convert-padstack`` record the outcome per version.
"""

from __future__ import annotations

import _convcases
import _probes
import pytest
from _corpus import manifest_items, require

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def _difat_board():
    row = next(item for item in manifest_items("rt0") if item.id == _convcases.DIFAT_ROW)
    return require(row)


def test_difat() -> None:
    """The scenario "KiCad imports a large document": the DIFAT document of ``vme-wren`` imports and
    equals the source at level 4."""
    found = _convcases.triangle(_difat_board(), level=4, ignore_refs=("",))
    print(f"vme-wren: level {found.report.levels[-1].level}, {len(found.report.excluded)} excluded")
    assert found.unexplained == ()
    assert found.report.levels[-1].level >= 4


def test_padstack() -> None:
    """A pad whose per-layer stack is written with stack mode 1 imports and equals the source at level 4."""
    found = _convcases.triangle(_convcases.PADSTACK, level=4, ignore_refs=("",))
    print(f"padstack: level {found.report.levels[-1].level}, {len(found.report.excluded)} excluded")
    assert found.unexplained == ()
    assert found.report.levels[-1].level >= 4


@pytest.mark.parametrize("probe", ["convert-difat", "convert-padstack"])
def test_probe(probe: str) -> None:
    """The two probes of the hypothesis rows: each is ``equal`` on the pinned 10.0.6 image. The DIFAT probe
    needs the heavy board: without it the test skips, or fails when the corpus is required."""
    if probe == "convert-difat":
        _difat_board()
    outcome = _probes.run(probe)
    print(f"{probe}: {outcome} on kicad-cli {_probes.version()}")
    assert outcome == "equal"
