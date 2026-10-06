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
    _without_plane_lines,  # pyright: ignore[reportPrivateUsage]
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

BOARDS = manifest_items("altium-pcbdoc")
SETS = project_sets()
COUNTS = ("pairs", "judged", "shorts", "clearance", "zone_overlaps", "unset_pairs", "approximated")


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

    # never against a value the document does not hold: a zone has no clearance of its own
    assert not [f for f in report.findings if f.source == ZONE_SOURCE], item.id
    held = [r for r in (rules.design.rules.rules if rules.design.rules else ()) if r.kind == "clearance"]
    if not held:
        assert summary["clearance"] == 0, item.id
    codes = Counter(found.code for found in stage.issues)
    opaque = rules.opaque_clearance_rules
    unjudged = bool(summary["unpoured"] or summary["zones_unjudged"] or opaque or rules.left_out)
    if unjudged or summary["unsupported"]:
        assert stage.evidence.level is Level.UNVERIFIED, item.id
        assert codes["copper.rules-incomplete"] + codes["copper.item-unsupported"] >= 1, item.id
    # copper at exactly its clearance in the document's unit is no finding: with the values as the
    # document writes them, the findings that the slack of the unit takes away are short by that slack
    # at most, and nothing else changes
    exact, _ = _without_plane_lines(_without_zone_clearance(design))
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
        "clearance_rules": len(held),
        "opaque_clearance_rules": opaque,
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
