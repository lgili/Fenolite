# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Public Altium baseline and conversion census (c0161 task 1.1)."""

from __future__ import annotations

from collections import Counter

import pytest
from _corpus import manifest_items, require

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.pcb import _emit_layers

pytestmark = pytest.mark.needs_corpus
ROWS = [i for i in manifest_items("rta") if "-pcbdoc-" in i.id]
BASELINE = {
    "altium-third-party-pcbdoc-01": {
        "Altium.KeepOut": 20,
        "Mech.1": 69,
        "Mech.13": 159,
        "Mech.15": 324,
        "Mech.16": 23,
        "Mech.2": 888,
        "Mech.3": 592,
    },
    "altium-third-party-pcbdoc-02": {
        "Altium.DrillDrawing": 1,
        "Mech.1": 16,
        "Mech.10": 4,
        "Mech.12": 4,
        "Mech.13": 42,
        "Mech.14": 28,
        "Mech.15": 118,
    },
    "altium-third-party-pcbdoc-03": {"Altium.KeepOut": 1, "Mech.1": 12, "Mech.13": 216, "Mech.15": 225},
    "altium-third-party-pcbdoc-04": {
        "Altium.KeepOut": 1,
        "Mech.1": 12,
        "Mech.15": 92,
        "Mech.16": 56,
        "Mech.2": 73,
        "Mech.7": 1,
    },
    "altium-third-party-pcbdoc-05": {"Mech.1": 4, "Mech.2": 92, "Mech.4": 92},
    "altium-third-party-pcbdoc-06": {
        "Altium.74": 3,
        "Altium.KeepOut": 6,
        "Mech.1": 18,
        "Mech.11": 105,
        "Mech.13": 217,
        "Mech.15": 482,
        "Mech.16": 49,
        "Mech.2": 1,
        "Mech.6": 1,
    },
    "altium-third-party-pcbdoc-07": {
        "In1.Cu": 5,
        "In2.Cu": 3,
        "Mech.1": 12,
        "Mech.13": 8,
        "Mech.14": 1,
        "Mech.15": 36,
        "Mech.16": 116,
        "Mech.2": 21,
        "Mech.3": 41,
    },
}


@pytest.mark.parametrize("item", ROWS, ids=lambda i: i.id)
def test_baseline_layers(item) -> None:
    design = AltiumBackend().read(require(item)).design
    assert design.board is not None
    # Foreign models still have no KiCad bag: conversion must supply it, not change the import.
    with pytest.raises(KeyError, match="number"):
        _emit_layers(design.board.layers)
    if item.id not in BASELINE:
        return  # heavy row is measured by the conversion gate in CI
    known = {
        "F.Cu",
        "B.Cu",
        "F.SilkS",
        "B.SilkS",
        "F.Paste",
        "B.Paste",
        "F.Mask",
        "B.Mask",
        "F.CrtYd",
        "B.CrtYd",
        "F.Fab",
        "B.Fab",
        "Edge.Cuts",
        "Margin",
        "Dwgs.User",
        "Cmts.User",
        "Eco1.User",
        "Eco2.User",
    }
    counts = Counter()
    for field in ("graphics", "texts", "tracks", "arcs", "dimensions"):
        for entity in getattr(design.board, field):
            if entity.layer not in known:
                counts[entity.layer] += 1
    for fp in design.board.footprints:
        for entity in (*fp.graphics, *fp.texts, *fp.fields):
            if entity.layer not in known:
                counts[entity.layer] += 1
    assert dict(counts) == BASELINE[item.id]


CONVERTED_LOSSES = {
    "altium-third-party-pcbdoc-01": {"body": 247, "rule": 1, "graphic": 20},
    "altium-third-party-pcbdoc-02": {"body": 42, "rule": 1, "text": 1},
    "altium-third-party-pcbdoc-03": {"body": 50, "rule": 2, "schematic": 1},
    "altium-third-party-pcbdoc-04": {"body": 33, "rule": 1},
    "altium-third-party-pcbdoc-05": {"body": 23, "rule": 1},
    "altium-third-party-pcbdoc-06": {"body": 27, "rule": 1, "graphic": 3},
    "altium-third-party-pcbdoc-07": {"pad": 8, "body": 24},
    "altium-third-party-pcbdoc-08": {"pad": 4, "body": 1298, "text": 298, "graphic": 1000, "schematic": 1},
}
ZONE_ARC_OUTLINES = {
    "altium-third-party-pcbdoc-02": 2,
    "altium-third-party-pcbdoc-07": 4,
    "altium-third-party-pcbdoc-08": 6,
}
"""Zones whose Altium outline holds an arc vertex: the import leaves them without an outline, and the
conversion writes the flattened outline of the source record (measured on 2026-10-15)."""


@pytest.mark.parametrize("item", ROWS, ids=lambda i: i.id)
def test_converted_reports(item) -> None:
    from fenolite.api import convert

    result = convert(require(item), to="kicad", allow_lossy=True)
    assert not result.unexplained, result.unexplained
    assert any(key.endswith(".kicad_pcb") for key in result.conversion.files)
    if item.id in CONVERTED_LOSSES:
        losses = {
            row.kind: sum(
                reason.count
                for reason in row.reasons
                if reason.outcome == "lost" and not reason.reason.startswith("unmapped imported rule group:")
            )
            for row in result.conversion.report.rows
            if row.lost
        }
        assert {kind: count for kind, count in losses.items() if count} == CONVERTED_LOSSES[item.id]
    flattened = sum(
        reason.count
        for row in result.conversion.report.rows
        if row.kind == "zone"
        for reason in row.reasons
        if reason.outcome != "lost" and "arc vertices" in reason.reason
    )
    assert flattened == ZONE_ARC_OUTLINES.get(item.id, 0)


@pytest.mark.parametrize("name", ("altium-set:02", "altium-set:03", "altium-set:04", "altium-set:05"))
def test_light_project_sets(name, tmp_path) -> None:
    from _altium_sets import SETS, lay_out

    from fenolite.api import convert

    folder = lay_out(SETS[name], tmp_path / name)
    project = next(folder.rglob("*.PrjPcb"))
    result = convert(project, to="kicad", allow_lossy=True)
    assert not result.unexplained, result.unexplained
