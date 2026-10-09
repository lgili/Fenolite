# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper locks in an Altium build (change c0108; capability altium-build, "Copper locks in an Altium
build"): ``result.copper.locked``, and the warning for a record kind whose lock is not written."""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest
from _altium_copper import NAME, routed_board_text, routed_build, routed_design, routed_model

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RawPrimitive
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.errors import Issue
from fenolite.dsl import to_model
from fenolite.lens import altium_copper
from fenolite.lens.altium import CopperSource
from fenolite.lens.build import BuildOutput
from fenolite.model.design import Design

DOCUMENT = f"{NAME}.PcbDoc"
BOARD = "routed.kicad_pcb"
SAMPLE = Path(__file__).resolve().parents[2] / "data" / "altium" / "routed" / DOCUMENT


def lock(design: Design, *, tracks: int = 0, arcs: int = 0, vias: int = 0) -> Design:
    """``design`` with its first ``tracks`` tracks, ``arcs`` arcs and ``vias`` vias locked."""
    board = design.board
    assert board is not None

    def first(items: tuple, count: int) -> tuple:  # type: ignore[type-arg]
        assert len(items) >= count
        return (*(dataclasses.replace(item, locked=True) for item in items[:count]), *items[count:])

    return dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            tracks=first(board.tracks, tracks),
            arcs=first(board.arcs, arcs),
            vias=first(board.vias, vias),
        ),
    )


def from_board(root: Path, edit: Callable[[Design], Design]) -> BuildOutput:
    """The build whose copper is read from the sample's routed ``.kicad_pcb`` text, as ``--copper-from``
    does."""
    text = routed_board_text(edit)
    board = read_board(text, file=BOARD, issues=[])
    return routed_build(root, to_model(routed_design()), copper_source=CopperSource(board, "board", BOARD))


def lock_warnings(output: BuildOutput) -> list[Issue]:
    return [
        found
        for found in output.issues
        if found.code == "altium.not-lowered" and found.where == altium_copper.LOCK_WHERE
    ]


def locked_tracks(data: bytes) -> int:
    doc = read_pcbdoc(data)
    typed = [item for item in doc.tracks if not isinstance(item, RawPrimitive)]
    return sum(1 for item in typed if item.prefix.locked and item.prefix.component is None)


def test_copper_lock_counts_are_zero_without_locked_copper(tmp_path: Path) -> None:
    """A build whose design holds no locked copper gives what it gave, but for the key ``locked``."""
    output = routed_build(tmp_path)
    assert output.summary["copper"]["locked"] == {"tracks": 0, "arcs": 0, "vias": 0}  # type: ignore[index]
    assert lock_warnings(output) == []


def test_bytes_of_a_design_without_locks(tmp_path: Path) -> None:
    """Scenario "A design without locks keeps its bytes": the routed sample's document is the committed
    one."""
    built = routed_build(tmp_path).files[DOCUMENT]
    assert hashlib.sha256(built).hexdigest() == hashlib.sha256(SAMPLE.read_bytes()).hexdigest()


def test_locked_track_from_a_routed_board(tmp_path: Path) -> None:
    """Scenario "A locked track from a routed board": a segment of the routed board written with
    ``(locked yes)`` is a locked track of the document."""
    text = routed_board_text(lambda design: lock(design, tracks=1))
    # one more lock than the board without it, which holds the lock of a placed part
    assert text.count("(locked yes)") == routed_board_text().count("(locked yes)") + 1
    output = from_board(tmp_path, lambda design: lock(design, tracks=1))
    assert not [found for found in output.issues if found.severity == "error"]
    assert output.summary["copper"]["locked"] == {"tracks": 1, "arcs": 0, "vias": 0}  # type: ignore[index]
    assert lock_warnings(output) == []
    assert locked_tracks(output.files[DOCUMENT]) == 1


def test_locked_items_of_the_model_are_counted(tmp_path: Path) -> None:
    output = routed_build(tmp_path, lock(routed_model(), tracks=2, arcs=1, vias=1))
    assert output.summary["copper"]["locked"] == {"tracks": 2, "arcs": 1, "vias": 1}  # type: ignore[index]
    assert lock_warnings(output) == [] and locked_tracks(output.files[DOCUMENT]) == 2


@pytest.mark.parametrize("kind", ["track", "arc", "via"])
def test_locked_kind_whose_fact_is_not_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Scenario "A kind whose fact is not recorded", for the three kinds: the item is written unlocked,
    one warning names the kind and the count, and the count of locked items written is 0."""
    monkeypatch.setattr(pcbrecords, "LOCK_WRITTEN", pcbrecords.LOCK_WRITTEN - {kind})
    output = routed_build(tmp_path, lock(routed_model(), tracks=1, arcs=1, vias=1))
    (warning,) = lock_warnings(output)
    assert warning.severity == "warning" and f"1 locked {kind}" in warning.message
    assert "unlocked" in warning.message and "Altium" in warning.hint
    counts = output.summary["copper"]["locked"]  # type: ignore[index]
    assert counts[f"{kind}s"] == 0 and sum(counts.values()) == 2
    assert locked_tracks(output.files[DOCUMENT]) == (0 if kind == "track" else 1)


def test_locked_copper_with_an_empty_set_is_never_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no fact row at all, every locked kind is named and nothing is written locked."""
    monkeypatch.setattr(pcbrecords, "LOCK_WRITTEN", frozenset())
    output = routed_build(tmp_path, lock(routed_model(), tracks=1, arcs=1, vias=1))
    assert len(lock_warnings(output)) == 3
    assert output.summary["copper"]["locked"] == {"tracks": 0, "arcs": 0, "vias": 0}  # type: ignore[index]
    free = routed_build(tmp_path).files[DOCUMENT]
    assert output.files[DOCUMENT] == free
