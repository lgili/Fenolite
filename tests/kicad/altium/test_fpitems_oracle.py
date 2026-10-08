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

The probe ``altium-fpitems-kicad`` is ``outcome()`` on the own documents. It is not yet in
``tests/kicad/_probes.py``: its result must first be recorded with kicad-cli 10.0.6
(``FENOLITE_PROBES_WRITE=1``), which change c0126 owes (task 7.3); ``test_probe_outcome`` runs it here.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _corpus import manifest_items, require
from _rta3oracle import SAMPLES, rewrite_sides

from fenolite.backends.kicad import fpitems
from fenolite.model.design import Design

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
OWN = ("blink/blink.PcbDoc", "routed/routed.PcbDoc", "board6/board6.PcbDoc")
"""Fenolite's own PCB documents: each holds 27 lines and arcs of footprints (change c0126)."""
ROWS = [item for item in manifest_items("rta") if "-pcbdoc-" in item.id and not item.heavy]
IDS = [item.id for item in ROWS]
Counts = Counter[tuple[str, str, str]]


def layer_class(layer: str) -> str | None:
    """``silkscreen``, ``drawing``, or ``None`` for a copper layer (left out)."""
    if layer.endswith(".Cu") or layer == "*.Cu":
        return None
    return "silkscreen" if layer.endswith("SilkS") or layer.endswith("Silkscreen") else "drawing"


def counts(design: Design) -> Counts:
    """(reference, layer class, ``line`` or ``arc``) → the number of graphics of the footprints."""
    refs = {component.id: component.ref for component in design.circuit.components}
    found: Counts = Counter()
    if design.board is None:
        return found
    for footprint in design.board.footprints:
        ref = refs.get(footprint.component_id, "")
        for graphic in footprint.graphics:
            kind = {"line": "line", "arc": "arc", "circle": "arc"}.get(graphic.kind)
            group = layer_class(graphic.layer)
            if kind is not None and group is not None and ref:
                found[(ref, group, kind)] += 1
    return found


def both_counts(source: Path, row: str = "") -> tuple[Counts, Counts]:
    """The counts of Fenolite's read of the rewrite of ``source`` and of KiCad's projected import."""
    sides = rewrite_sides(source, row)
    return counts(sides.a), counts(fpitems.with_footprint_items(sides.b).design)


def outcome() -> str:
    """The probe ``altium-fpitems-kicad``: ``equal`` when, for each document of ``OWN``, KiCad's import of
    the rewrite holds as many lines and arcs per footprint and layer class as Fenolite's read and both hold
    some; ``different`` otherwise."""
    for name in OWN:
        mine, theirs = both_counts(SAMPLES / name)
        if not mine or mine != theirs:
            return "different"
    return "equal"


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
