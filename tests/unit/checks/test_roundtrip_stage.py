# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``roundtrip`` stage (capability verification-loop, "Round-trip stage"; change c0013)."""

from __future__ import annotations

from fakes import READ_EVIDENCE, validation

from fenolite.checks.roundtrip import roundtrip_stage
from fenolite.core.errors import Issue


def test_roundtrip_stage_passes() -> None:
    result = roundtrip_stage(validation())
    assert result.status == "ok" and result.issues == ()
    assert result.summary == {
        "level": "RT1",
        "tree_equal": True,
        "model_equal": True,
        "opaque_equal": True,
        "opaque_count": 2,
    }
    assert result.evidence == READ_EVIDENCE


def test_roundtrip_stage_failed_round_trip() -> None:
    result = roundtrip_stage(validation(passed=False, difference="/kicad_pcb/footprint[0]/pad[1]"))
    (found,) = result.issues
    assert (found.code, found.severity, found.where) == (
        "check.rt1-failed",
        "error",
        "/kicad_pcb/footprint[0]/pad[1]",
    )
    assert result.status == "errors"


def test_roundtrip_stage_keeps_reader_issues_only() -> None:
    issues = (Issue("kicad.board.kept-opaque", "info", "x"), Issue("model.duplicate-ref", "warning", "y"))
    result = roundtrip_stage(validation(issues=issues))
    assert [i.code for i in result.issues] == ["kicad.board.kept-opaque"]
