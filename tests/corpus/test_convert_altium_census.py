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
    # change c0168: the regions with ISBOARDCUTOUT=TRUE on the Keep-Out layer (one in -03, four in -06) are
    # board cut-outs of the import, Edge.Cuts rings, no longer graphics of that layer
    "altium-third-party-pcbdoc-03": {"Mech.1": 12, "Mech.13": 216, "Mech.15": 225},
    # change c0411: the region of -04's component on the Keep-Out layer with KEEPOUTRESTRICTIONS is a rule
    # area of its footprint on every copper layer, no longer a graphic of that layer
    "altium-third-party-pcbdoc-04": {
        "Mech.1": 12,
        "Mech.15": 92,
        "Mech.16": 56,
        "Mech.2": 73,
        "Mech.7": 1,
    },
    "altium-third-party-pcbdoc-05": {"Mech.1": 4, "Mech.2": 92, "Mech.4": 92},
    # change c0407: the three regions of KIND=1 (polygon cut-outs) on the Multi-Layer layer of -06 are rule
    # areas against pours on every copper layer, no longer graphics of layer 74
    "altium-third-party-pcbdoc-06": {  # its 2 component cut-outs are Edge.Cuts since c0443
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
    "altium-third-party-pcbdoc-01": {},
    "altium-third-party-pcbdoc-02": {},
    "altium-third-party-pcbdoc-03": {"schematic": 1},
    "altium-third-party-pcbdoc-04": {},
    "altium-third-party-pcbdoc-05": {},
    "altium-third-party-pcbdoc-06": {},
    "altium-third-party-pcbdoc-07": {},
    "altium-third-party-pcbdoc-08": {},
}
"""The losses per kind, measured on 2026-10-15; on 2026-10-16 (change c0170) the slots of the pads of
``-07`` (8) and ``-08`` (4) are kept: the import holds a slot's axis in the pad's own frame, and none is
turned against its pad.

Change c0223 (2026-10-28) places each embedded model of a top-side part, not turned about X or Y, in the
derived library (a ``model`` change); every other embedded model is a ``model`` loss: of a bottom-side part
(118, 14, 3, 0, 0, 2, 3 and 41 in rows ``-01`` to ``-08``) or turned about X or Y (48, 4, 24, 2, 0, 17, 0
and 11). The bodies stay ``body`` losses, since the board's footprints carry no model. No row has a
``pad-margin`` loss: the only scoped expansion rules of the documents are of scope ``IsVia`` (rows ``-01``,
``-04``, ``-05``), which govern no pad.

Change c0372 (found on 2026-11-04) writes the generated schematic of ``-08`` on several pages: the
generator refused it as one page, and it is now a ``schematic`` change, not a loss.

Change c0407 (2026-11-05): the 12 lines and 8 arcs of the Keep-Out layer of ``-01`` are each the rule area of
the band their width covers (they were ``graphic`` losses, open outlines that enclosed no area), and the three
polygon cut-outs on the Multi-Layer layer of ``-06`` are rule areas of the import (they were ``graphic``
losses of layer 74).

Change c0423 (2026-11-05) places every embedded model, on either side and for any turn, and writes every
other body as a generated STEP model: no row has a ``body`` or ``model`` loss. Of the bodies of rows ``-01``
to ``-08``, 245, 42, 45, 3, 23, 27, 6 and 81 are carried by their embedded models and 2, 0, 5, 30, 0, 0, 18
and 1217 are generated; none falls back to the prism over its outline.

Change c0424 (2026-11-05) gives every rule record a fate: each is mapped, kept as written for an Altium
write-back, or a declared format limit of KiCad, so no row has a ``rule`` loss.

Change c0422 (2026-11-05): a footprint's own texts are written as ``fp_text user`` children (c0409 reported
them lost); ``FOOTPRINT_TEXTS`` holds the counts, each written and none lost.

Change c0428 (2026-11-05; rows ``-01`` to ``-07``, measured on ``origin/cac/lote-24`` 948b6a376 with c0428):
no ``rule`` is lost (each rule record has its own fate since c0424); the text of ``-02`` on the drill drawing
layer is written on a user row; ``-03`` still loses its schematic, now because several parts on its board
share a designator."""
FOOTPRINT_TEXTS = {
    "altium-third-party-pcbdoc-02": 4,
    "altium-third-party-pcbdoc-03": 46,
    "altium-third-party-pcbdoc-04": 3,
    "altium-third-party-pcbdoc-06": 25,
    "altium-third-party-pcbdoc-07": 12,
    "altium-third-party-pcbdoc-08": 554,
}
"""The texts of the components of a row that are neither its designator nor its comment, measured on
2026-11-05 (change c0422): the report's ``footprint-text`` row counts them and writes every one."""
ZONE_ARC_OUTLINES = {
    "altium-third-party-pcbdoc-02": 2,
    "altium-third-party-pcbdoc-07": 4,
    "altium-third-party-pcbdoc-08": 6,
}
"""Zones whose Altium outline holds an arc vertex: the import leaves them without an outline, and the
conversion writes the flattened outline of the source record (measured on 2026-10-15)."""


POLYGON_CUTOUTS = {"altium-third-party-pcbdoc-01": 2, "altium-third-party-pcbdoc-06": 13}
"""The free regions of ``KIND=1`` (polygon cut-outs) of a row, measured on 2026-11-05 (change c0407): two on
Top and Bottom in ``-01``; eight on Top, two on Bottom and three on the Multi-Layer layer in ``-06``. Each
was copper of its layer (or a graphic of layer 74) before c0407."""


@pytest.mark.parametrize("item", [i for i in ROWS if i.id in POLYGON_CUTOUTS], ids=lambda i: i.id)
def test_polygon_cutouts_keep_pours_off(item) -> None:
    """A polygon cut-out is a rule area that forbids pours alone, never copper (change c0407)."""
    design = AltiumBackend().read(require(item)).design
    assert design.board is not None
    pour_only = [
        k
        for k in design.board.keepouts
        if k.no_copper_pour and not (k.no_tracks or k.no_vias or k.no_pads or k.no_footprints)
    ]
    assert len(pour_only) == POLYGON_CUTOUTS[item.id]
    assert not [g for g in design.board.graphics if g.layer == "Altium.74"]


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
    rows = {row.kind: row for row in result.conversion.report.rows}
    texts = rows.get("footprint-text")
    counted = (texts.source, texts.written, texts.lost) if texts is not None else (0, 0, 0)
    expected = FOOTPRINT_TEXTS.get(item.id, 0)
    assert counted == (expected, expected, 0)
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
