# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone fills cross from a KiCad 10 copy to a board of its original major."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.base import WriteResult
from fenolite.backends.kicad import fill
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.versions import LegacyEditRefusedError
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Level
from fenolite.model.board import ZoneFill

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "kicad" / "fill"


def _texts() -> tuple[str, str, str]:
    return tuple(
        (FIXTURES / name).read_text(encoding="utf-8")
        for name in ("triad_t9.kicad_pcb", "triad_t9_refilled.kicad_pcb", "triad_t9_filled.kicad_pcb")
    )  # type: ignore[return-value]


def test_lift_keeps_original_inputs_and_takes_all_fills() -> None:
    original, refilled, _ = _texts()
    before, saved = read_board(original), read_board(refilled)
    assert before.board is not None and saved.board is not None
    first = before.board.zones[0]
    second = saved.board.zones[0]
    added = ZoneFill(second.fills[0].layer, (Point(1, 1), Point(2, 1), Point(2, 2)), True)
    modified = dataclasses.replace(second, priority=first.priority + 1, fills=(*second.fills, added))
    saved = dataclasses.replace(saved, board=dataclasses.replace(saved.board, zones=(modified,)))
    lifted = fill.lift_fills(before, saved)
    assert lifted.design.board is not None
    zone = lifted.design.board.zones[0]
    assert zone.priority == first.priority and zone.fills == modified.fills and zone.filled
    assert lifted.changed == (first.id,) and lifted.counts[first.id] == 2
    assert not lifted.unmatched and lifted.design.board.keepouts == before.board.keepouts
    assert fill.lift_fills(lifted.design, saved).changed == ()


def test_missing_zone_reports_an_error_without_text() -> None:
    original, refilled, _ = _texts()
    before = read_board(original)
    assert before.board is not None
    zone_id = before.board.zones[0].id
    # The copied board has no zones; the original's zone cannot be paired by uuid.
    from fenolite.backends.kicad.pcb import write_board

    saved = read_board(refilled)
    assert saved.board is not None
    saved = dataclasses.replace(saved, board=dataclasses.replace(saved.board, zones=()))
    result = fill.fill_board(original, write_board(saved, target=10).text)
    assert result.text is None and result.issues[0].code == "zone.fill-mismatch"
    assert zone_id in result.issues[0].message


def test_target_nine_and_idempotence() -> None:
    original, refilled, expected = _texts()
    result = fill.fill_board(original, refilled)
    assert result.text == expected and "(version 20241229)" in result.text
    assert result.changed and result.zones[0].filled
    again = fill.fill_board(expected, refilled)
    assert again.text == expected and again.changed == ()


def test_target_eight_is_refused() -> None:
    original, refilled, _ = _texts()
    legacy = original.replace("(version 20241229)", "(version 20240108)", 1)
    with pytest.raises(LegacyEditRefusedError) as exc:
        fill.fill_board(legacy, refilled)
    assert getattr(exc.value, "cli_code", "") == "FEN-7003"


def test_writer_loss_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    original, refilled, _ = _texts()
    monkeypatch.setattr(fill, "write_board", lambda design, target: WriteResult(original))
    with pytest.raises(FormatError, match="cannot express fill"):
        fill.fill_board(original, refilled)


def test_evidence_follows_hypotheses() -> None:
    table = (Path(__file__).resolve().parents[4] / "docs" / "hypotheses.md").read_text(encoding="utf-8")
    verified = all(
        f"| {key} |" in table
        and "KICAD-VERIFIED (10.0.x)"
        in next(row for row in table.splitlines() if row.startswith(f"| {key} |"))
        for key in ("H-K-FILL-SAVE", "H-K-FILL-LIFT", "H-K-FILL-REPEAT")
    )
    assert (fill.EVIDENCE.level is Level.KICAD_VERIFIED) == verified
