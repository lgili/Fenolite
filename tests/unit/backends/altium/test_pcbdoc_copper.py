# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Locked copper in the Altium PCB document (change c0108; capability altium-pcb-writer, "Locked copper
records"; ``H-A-PCB-CU-LOCK``): the document of the routed sample with a locked track, arc and via, read
back with Fenolite's own reader."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
from _altium_copper import NAME, routed_build, routed_model

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RawPrimitive
from fenolite.model.design import Design

DOCUMENT = f"{NAME}.PcbDoc"
SAMPLE = Path(__file__).resolve().parents[3] / "data" / "altium" / "routed" / DOCUMENT


def locked_model() -> Design:
    """The routed sample with its first track, its arc and its first via locked."""
    model = routed_model()
    board = model.board
    assert board is not None and board.tracks and board.arcs and board.vias
    return dataclasses.replace(
        model,
        board=dataclasses.replace(
            board,
            tracks=(dataclasses.replace(board.tracks[0], locked=True), *board.tracks[1:]),
            arcs=(dataclasses.replace(board.arcs[0], locked=True), *board.arcs[1:]),
            vias=(dataclasses.replace(board.vias[0], locked=True), *board.vias[1:]),
        ),
    )


def document(root: Path, model: Design | None = None) -> bytes:
    output = routed_build(root, model)
    assert not [found for found in output.issues if found.severity == "error"]
    return output.files[DOCUMENT]


def locked_free(doc: PcbDocument) -> dict[str, int]:
    """The locked free primitives per kind: those of no component with ``Prefix.locked``."""
    counts: dict[str, int] = {}
    for kind, items in (("track", doc.tracks), ("arc", doc.arcs), ("via", doc.vias)):
        typed = [item for item in items if not isinstance(item, RawPrimitive)]
        counts[kind] = sum(1 for item in typed if item.prefix.locked and item.prefix.component is None)
    return counts


def test_three_locked_items_in_a_document(tmp_path: Path) -> None:
    """Scenario "Three locked items in a document"."""
    assert frozenset({"track", "arc", "via"}) == pcbrecords.LOCK_WRITTEN
    free = document(tmp_path)
    locked = document(tmp_path, locked_model())
    assert locked_free(read_pcbdoc(free)) == {"track": 0, "arc": 0, "via": 0}
    assert locked_free(read_pcbdoc(locked)) == {"track": 1, "arc": 1, "via": 1}
    assert len(free) == len(locked)
    differing = [index for index, (a, b) in enumerate(zip(free, locked, strict=True)) if a != b]
    assert len(differing) == 3
    assert all((free[index], locked[index]) == (0x0C, 0x08) for index in differing)


def test_locked_does_not_change_the_order_of_the_records(tmp_path: Path) -> None:
    """The order in ``Tracks6``, ``Arcs6`` and ``Vias6`` does not depend on ``locked``."""
    free, locked = read_pcbdoc(document(tmp_path)), read_pcbdoc(document(tmp_path, locked_model()))

    def geometry(doc: PcbDocument) -> list[tuple[object, ...]]:
        tracks = [(t.x1, t.y1, t.x2, t.y2, t.width) for t in doc.tracks if not isinstance(t, RawPrimitive)]
        vias = [(v.x, v.y, v.diameter, v.hole) for v in doc.vias if not isinstance(v, RawPrimitive)]
        return [*tracks, *vias]

    assert geometry(free) == geometry(locked)


def test_locked_kind_outside_the_set_is_written_unlocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pcbrecords, "LOCK_WRITTEN", frozenset({"track", "arc"}))
    assert locked_free(read_pcbdoc(document(tmp_path, locked_model()))) == {"track": 1, "arc": 1, "via": 0}


def test_document_without_locked_copper_keeps_its_bytes(tmp_path: Path) -> None:
    """A design without locked copper gives the committed sample, byte for byte."""
    built = document(tmp_path)
    assert hashlib.sha256(built).hexdigest() == hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
