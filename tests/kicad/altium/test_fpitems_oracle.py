# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's importer on the footprint lines and arcs of a rewritten PCB document (capability
altium-verification, "Footprint graphics in the Altium round trips", scenario "KiCad reads the footprint
lines of a rewrite"; change c0126; ``H-A-PCBX-FPGFX-KICAD``).

A document is read by Fenolite and its model is written as a new PCB document (``_rta3oracle.rewritten``:
``lower.write_design(..., allow_lossy=True, rewrite=True)``), which now holds the lines and arcs of its
footprints. ``kicad-cli pcb import`` reads that rewrite, and KiCad's reader keeps the drawing children of a
board footprint as opaque slots; ``backends.kicad.fpitems.with_footprint_items`` projects them (change
c0126, group 3b). For each footprint, by the reference of its component, and each layer class, the number
of lines and the number of arcs (a full circle counts as an arc) of KiCad's read must equal those of
Fenolite's read of the same rewrite.

The layer class is ``silkscreen`` for an overlay and ``drawing`` for every other layer that is not copper:
KiCad names the mechanical layers of an import by its own mapping, which this test does not assume, so the
mechanical, paste and solder-mask layers are counted together. Copper is left out: a rewrite writes no
graphic of a footprint on copper (``footprint-copper``).

The probe ``altium-fpitems-kicad`` is ``_fpitemsoracle.outcome()`` on the own documents, in
``tests/kicad/_probes.py`` for major 10 since its result was recorded on 10.0.6 (task 7.3 of c0126);
``test_probe_outcome`` runs it here too.
"""

from __future__ import annotations

import pytest
from _corpus import manifest_items, require
from _fpitemsoracle import OWN, both_counts, outcome
from _rta3oracle import SAMPLES

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
ROWS = [item for item in manifest_items("rta") if "-pcbdoc-" in item.id and not item.heavy]
IDS = [item.id for item in ROWS]


@pytest.mark.parametrize("name", OWN)
def test_own_rewrite_keeps_its_footprint_lines(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    mine, theirs = both_counts(SAMPLES / name)
    with capsys.disabled():
        print(f"\nrewrite of {name}: {sum(mine.values())} lines and arcs, KiCad {sum(theirs.values())}")
    assert sum(mine.values()) == 27
    assert theirs == mine


def test_probe_outcome() -> None:
    assert outcome() == "equal"


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", IDS)
def test_corpus_rewrite_keeps_its_footprint_lines(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    item = next(i for i in ROWS if i.id == row)
    mine, theirs = both_counts(require(item), row)
    with capsys.disabled():
        print(f"\nrewrite of {row}: {sum(mine.values())} lines and arcs, KiCad {sum(theirs.values())}")
    assert mine and theirs == mine, sorted((mine - theirs) + (theirs - mine))[:10]
