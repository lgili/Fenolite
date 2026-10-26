# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The footprint lines and arcs of a rewritten PCB document, by Fenolite and by KiCad's importer, and
the probe ``altium-fpitems-kicad`` (change c0126; ``H-A-PCBX-FPGFX-KICAD``).
``tests/kicad/altium/test_fpitems_oracle.py`` says what is compared; ``_probes.PROBES`` runs ``outcome``
on major 10.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from _rta3oracle import SAMPLES, rewrite_sides

from fenolite.backends.kicad import fpitems
from fenolite.model.design import Design

OWN = ("blink/blink.PcbDoc", "routed/routed.PcbDoc", "board6/board6.PcbDoc")
"""Fenolite's own PCB documents: each holds 27 lines and arcs of footprints (change c0126)."""
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
