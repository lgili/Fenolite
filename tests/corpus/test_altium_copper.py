# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper check and the parity comparison on the public Altium files (capability altium-verification,
"Copper check on Altium boards" and "Parity on Altium projects"; change c0088; ``H-A-DRC-SAME``,
``H-A-DRC-PARITY``).

``test_copper`` runs the ``copper.clearance`` stage of a document check on every public PCB document and
records its counts. What it asserts is what the stage promises whatever the board holds: no clearance is
judged against a value the document does not hold (no finding has the source ``zone``, the model's default
of a zone), a board whose ``Clearance`` records all stay opaque has no clearance finding and says what it
left unjudged, and no finding is within the unit's slack of its clearance. Findings of a third-party board
are recorded, never asserted: such a board may hold real ones.

``test_parity`` lays out each public project set and compares its PCB document with its schematic
documents. A project of the corpus is no agreeing project by contract, so the assertion is the criterion
of ``H-A-DRC-PARITY``: every ``parity.net-conflict`` names a pad that ``netlist.assignment_compare`` also
flags, so that no net finding comes from a name alone.

The census holds counts and row ids only: no part name and no net name of a corpus file is printed or
written (``docs/evidence/altium-roundtrip.md``, "Light DRC over the corpus", is written from it).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _altium_sets import lay_out, project_sets
from _boards import census
from _corpus import CorpusItem, heavy_enabled, manifest_items, require

from fenolite.backends.altium.backend import (
    UNIT_SLACK_NM,
    AltiumBackend,
    _without_zone_clearance,  # pyright: ignore[reportPrivateUsage]
)
from fenolite.backends.base import PadNetList
from fenolite.checks import assignment_compare, parity
from fenolite.checks.clearance import ZONE_SOURCE
from fenolite.checks.copper import check_copper
from fenolite.checks.documents import document_copper, project_of
from fenolite.core.evidence import Level
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus

HEAVY_BOARD = "altium-third-party-pcbdoc-08"
BOARDS = [*manifest_items("altium-pcbdoc"), *(i for i in manifest_items("rta") if i.id == HEAVY_BOARD)]
"""The seven rows and the heavy PCB document, which ``FENOLITE_HEAVY=1`` includes."""
SETS = project_sets()
COUNTS = ("pairs", "judged", "shorts", "clearance", "zone_overlaps", "unset_pairs", "approximated")
CLEARANCE_RULES = {
    "altium-third-party-pcbdoc-01": (1, 0),
    "altium-third-party-pcbdoc-02": (0, 1),
    "altium-third-party-pcbdoc-03": (2, 0),
    "altium-third-party-pcbdoc-04": (1, 1),
    "altium-third-party-pcbdoc-05": (1, 0),
    "altium-third-party-pcbdoc-06": (0, 2),
    "altium-third-party-pcbdoc-07": (2, 1),
    "altium-third-party-pcbdoc-08": (2, 3),
}
"""Row → the clearance rules the check judges with and the Clearance records it could not read: facts
of the documents' rule records, not findings (census of 2026-10-06; change c0125 moved the third row
from ``(0, 3)``, and change c0130 the heavy row from ``(0, 4)``: one generic rule and one cell rule)."""
CELLS = {HEAVY_BOARD: {"judged": 1, "unjudged": 8}}
"""Row → the cells of its clearance matrices that the rules hold and do not hold, where it has any in an
enabled record (the matrices of rows 02 and 06 are counted under them too)."""


UNREAD_MATRICES = ("altium-third-party-pcbdoc-02", "altium-third-party-pcbdoc-06")


PLANE_CUTS = {"altium-third-party-pcbdoc-01": 74, "altium-third-party-pcbdoc-02": 43}
"""Row id → the free primitives on its internal planes, which the import leaves out (every other row
has no plane layer). They are tracks without a net on both rows."""


def _planes(design: Design) -> dict[str, int]:
    """Layer name → ``plane_cuts`` (0 without the pair), for the internal planes of an imported board."""
    assert design.board is not None
    found: dict[str, int] = {}
    for layer in design.board.layers:
        pairs = dict(layer.ext["altium"].payload) if "altium" in layer.ext else {}
        if 39 <= int(pairs.get("layer_id", 0)) <= 54:
            found[layer.name] = int(pairs.get("plane_cuts", 0))
    return found


PARITY = {
    "altium-set:01": (540, 544, 0, 0, 27, 8, 6, 22, 171, 10),
    "altium-set:02": (248, 260, 2, 2, 10, 21, 0, 3, 241, 129),
    "altium-set:03": (23, 27, 0, 0, 0, 0, 0, 0, 23, 0),
    "altium-set:04": (41, 41, 0, 0, 0, 2, 0, 2, 41, 0),
    "altium-set:05": (27, 27, 0, 0, 0, 0, 0, 0, 27, 0),
}
"""Per set, the counts of the parity table of ``docs/evidence/altium-roundtrip.md`` ("Light DRC over the
corpus"), measured on 2026-10-06 after the channel net names and the pin-to-pad map of c0083: components,
footprints, missing and extra footprints, value or footprint-name differences, net conflicts, pins without
a pad, pads without a pin, and the footprints and the pads that differ in spelling alone. Counts only."""


def test_boards_exist() -> None:
    assert len(BOARDS) >= 5


@pytest.mark.parametrize("item", BOARDS, ids=[item.id for item in BOARDS])
def test_copper(item: CorpusItem) -> None:
    if item.heavy and not heavy_enabled():
        pytest.skip(f"{item.id} is a heavy corpus item: set FENOLITE_HEAVY=1 to include it")
    path = require(item)
    backend = AltiumBackend()
    documents = backend.documents(path)
    read = backend.read_documents(documents)
    if read.pcb is None:
        pytest.skip(f"{item.id}: the reader refuses the document")
    design = read.pcb.design
    assert isinstance(design, Design)
    project = project_of(documents)
    assert project is not None
    stage = document_copper(design, project=project, validator=backend, evidence=read.pcb.evidence)
    summary = stage.summary
    rules = backend.design_rules(design, project)
    report = check_copper(rules.design, pads=backend.board_pads(rules.design))

    # the import makes no copper of what is drawn on an internal plane (change c0124): the board that
    # is checked is the board that was read, with every track and arc, and none of them lies on a plane
    assert design.board is not None and rules.design.board is not None
    assert rules.design.board.tracks == design.board.tracks, item.id
    assert rules.design.board.arcs == design.board.arcs, item.id
    plane_layers = {name: cuts for name, cuts in _planes(design).items()}
    on_planes = [t for t in (*design.board.tracks, *design.board.arcs) if t.layer in plane_layers]
    assert not on_planes, item.id
    plane_cuts = sum(plane_layers.values())
    assert plane_cuts == PLANE_CUTS.get(item.id, 0), item.id
    assert [count for kind, count, _ in rules.left_out] == ([len(plane_layers)] if plane_layers else [])

    # never against a value the document does not hold: a zone has no clearance of its own
    assert not [f for f in report.findings if f.source == ZONE_SOURCE], item.id
    held = [r for r in (rules.design.rules.rules if rules.design.rules else ()) if r.kind == "clearance"]
    if not held:
        assert summary["clearance"] == 0, item.id
    codes = Counter(found.code for found in stage.issues)
    opaque = rules.opaque_clearance_rules
    assert (len(held), opaque) == CLEARANCE_RULES[item.id], item.id
    cells = summary["clearance_cells"]
    assert cells == CELLS.get(item.id, {"judged": 0, "unjudged": cells["unjudged"]}), item.id  # type: ignore[index]
    assert (cells["unjudged"] > 0) == (item.id in (*CELLS, *UNREAD_MATRICES)), item.id  # type: ignore[index]
    unjudged = bool(summary["unpoured"] or summary["zones_unjudged"] or opaque or rules.left_out)
    if unjudged or summary["unsupported"]:
        assert stage.evidence.level is Level.UNVERIFIED, item.id
        assert codes["copper.rules-incomplete"] + codes["copper.item-unsupported"] >= 1, item.id
    # copper at exactly its clearance in the document's unit is no finding: with the values as the
    # document writes them, the findings that the slack of the unit takes away are short by that slack
    # at most, and nothing else changes
    exact = _without_zone_clearance(design)
    unslacked = check_copper(exact, pads=backend.board_pads(exact))
    kept = {frozenset(entry.entity_id for entry in f.items) for f in report.findings}
    rounding = [f for f in unslacked.findings if frozenset(e.entity_id for e in f.items) not in kept]
    assert all(
        f.code == "copper.clearance" and f.clearance is not None and f.clearance - f.gap <= UNIT_SLACK_NM
        for f in rounding
    ), item.id
    assert len(unslacked.findings) == len(report.findings) + len(rounding), item.id
    kinds = Counter(
        "-".join(sorted(entry.kind for entry in f.items))
        for f in report.findings
        if f.code != "copper.zone-overlap"
    )
    counts = {
        "items": dict(summary["items"]),  # type: ignore[call-overload]
        **{key: summary[key] for key in COUNTS},
        "unpoured": summary["unpoured"],
        "zones_unjudged": summary["zones_unjudged"],
        "planes": sum(count for kind, count, _ in rules.left_out if kind == "plane"),
        "plane_cuts": plane_cuts,
        "clearance_rules": len(held),
        "opaque_clearance_rules": opaque,
        "clearance_cells": dict(cells),  # type: ignore[call-overload]
        "level": stage.evidence.level.value,
        "status": stage.status,
        "finding_pairs": dict(sorted(kinds.items())),
        "unit_rounding": len(rounding),
    }
    print(item.id, counts)
    census("altium-copper", item.id, counts)


def _implied(schematic: Design, board: Design) -> set[str]:
    """The pads that the pad-net comparison of the two readings flags, as ``REF-PAD``."""
    listed = assignment_compare.model_netlist(schematic)
    placed, _ = assignment_compare.board_netlist(board)
    pair = assignment_compare.compare(
        PadNetList("schematic", listed.assignments, listed.uncovered),
        PadNetList("pcb", placed.assignments, placed.uncovered),
        min_pins=1,
    )
    return (
        {difference.element for difference in pair.differences}
        | {entry.element for entry in pair.only_a}
        | {entry.element for entry in pair.only_b}
    )


def test_sets_exist() -> None:
    assert len(SETS) >= 3


@pytest.mark.parametrize("name", list(SETS))
def test_parity(name: str, tmp_path: Path) -> None:
    items = SETS[name]
    if any(item.heavy for item in items) and not heavy_enabled():
        pytest.skip(f"{name} holds a heavy corpus item: set FENOLITE_HEAVY=1 to include it")
    folder = lay_out(items, tmp_path / "set")
    backend = AltiumBackend()
    read = backend.read_documents(backend.documents(folder))
    if read.schematic is None or read.pcb is None:
        pytest.skip(f"{name}: a side of the set cannot be read")
    schematic, board = read.schematic.design, read.pcb.design
    assert isinstance(schematic, Design) and isinstance(board, Design)
    outcome = backend.parity_side(schematic, board)
    assert outcome.side is not None
    report = parity.compare(outcome.side, board)
    flagged = _implied(schematic, board)
    conflicts = [f for f in report.findings if f.code == parity.NET_CONFLICT]
    alone = [f.key for f in conflicts if f.key not in flagged]
    assert not alone, f"{name}: {len(alone)} net finding(s) that the pad-net comparison does not imply"
    # without the board's spelling the same project gives findings of spelling alone: the reason for it
    from fenolite.backends.altium.adapter.parity import side_of

    raw = parity.compare(side_of(schematic), board)
    counts = {
        "components": len(schematic.circuit.components),
        "footprints": len(board.board.footprints) if board.board is not None else 0,
        **{key.removeprefix("parity."): report.summary[key] for key in parity.SUMMARY_KEYS},
        "net_conflicts_implied": len(conflicts) - len(alone),
        "spelling_only": {
            "footprint": raw.summary[parity.MISMATCH] - report.summary[parity.MISMATCH],
            "net": raw.summary[parity.NET_CONFLICT] - report.summary[parity.NET_CONFLICT],
        },
    }
    print(name, counts)
    census("altium-parity", name, counts)
    pinned = (
        counts["components"],
        counts["footprints"],
        counts["missing-footprint"],
        counts["extra-footprint"],
        counts["footprint-mismatch"],
        counts["net-conflict"],
        counts["pin-without-pad"],
        counts["pad-without-pin"],
        counts["spelling_only"]["footprint"],  # type: ignore[index]
        counts["spelling_only"]["net"],  # type: ignore[index]
    )
    assert pinned == PARITY[name], f"{name}: update PARITY and the table of docs/evidence/altium-roundtrip.md"


def test_known_false_findings_of_padless_vias_c0132() -> None:
    """KNOWN FALSE FINDINGS, pinned so that they are not taken for real and so that their repair is seen:
    the 28 shorts of the heavy document (and one clearance finding beside them) are a defect of the import,
    not of the board. The follow-up change c0132 is to remove them; when it lands, this test must fail and
    its counts go to zero.

    The class: a via against the pour of another net on an inner layer, where the pour stands at the
    generic clearance from the via's HOLE (its centre is the drill radius plus that clearance from the
    pour's copper, within the rounding of the pour's points). The via has no pad on that layer; the import
    gives it its one diameter on every layer, so the pad it invents meets the pour. Every such via has the
    long form of the via record, and no fact Fenolite holds says what that form adds
    (``docs/evidence/altium-roundtrip.md``, "Light DRC over the corpus")."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.checks.copper import _clean_ring  # pyright: ignore[reportPrivateUsage]
    from fenolite.geometry import Thick, thick_gap_floor

    (item,) = [row for row in BOARDS if row.id == HEAVY_BOARD]
    path = require(item)
    backend = AltiumBackend()
    documents = backend.documents(path)
    read = backend.read_documents(documents)
    assert read.pcb is not None and isinstance(read.pcb.design, Design)
    project = project_of(documents)
    assert project is not None
    rules = backend.design_rules(read.pcb.design, project)
    board = rules.design.board
    assert board is not None and rules.design.rules is not None
    (generic,) = [r.min for r in rules.design.rules.rules if r.kind == "clearance" and "/" not in r.name]
    assert generic is not None
    records = read_pcbdoc(path.read_bytes(), file=path.name).vias
    lengths = Counter(len(record.raw) for record in records)
    vias = {via.id: via for via in board.vias}
    zones = {zone.id: zone for zone in board.zones}
    report = check_copper(rules.design, pads=backend.board_pads(rules.design))
    shorts = [f for f in report.findings if f.code == "copper.short"]
    assert len(shorts) == 28 and sorted(lengths) == [326, 335]
    touched: set[str] = set()
    for found in shorts:
        assert sorted(entry.kind for entry in found.items) == ["fill", "via"], found.where
        assert found.layer not in ("F.Cu", "B.Cu")
        via = next(vias[e.entity_id] for e in found.items if e.entity_id in vias)
        zone = next(zones[e.entity_id] for e in found.items if e.entity_id in zones)
        assert via.provenance is not None
        assert len(records[int(via.provenance.locator.split("#")[1])].raw) == 335
        centre = Thick((via.position,), 2)
        reach = min(
            thick_gap_floor(centre, Thick(_clean_ring(fill.polygon), 0, filled=True))
            for fill in zone.fills
            if fill.layer == found.layer
        )
        # the generic rule of the check is lowered by the slack of the unit; the document's value is above
        assert abs(reach + 1 - (via.drill // 2 + generic)) <= 12, (found.where, reach)
        touched.add(via.id)
    assert len(touched) == 7
