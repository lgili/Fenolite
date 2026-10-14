# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Graduation is earned by every condition, including current committed tool evidence (c0092)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.backends import matrix
from fenolite.backends.base import (
    RELEASE_LEVELS,
    GraduationHypothesis,
    GraduationRun,
    MatrixRow,
    graduated,
    graduation_context,
)
from fenolite.core.evidence import Evidence, Level
from fenolite.verify.evidence import RELEASE_VERIFIED

ROOT = Path(__file__).resolve().parents[3]


def inputs():
    # Injected identifiers are fixture keys, not claims in the public hypothesis register.
    row = MatrixRow(
        "altium",
        "authored",
        write=Evidence(Level.INFERRED, hypotheses=("fixture-a", "fixture-b")),
        readback="tests/unit/backends/test_graduation.py",
        model_roundtrip="fixture-roundtrip",
    )
    support = {
        "fixture-a": GraduationHypothesis("fixture-a", Level.ALTIUM_VERIFIED_KIT, run_id="run"),
        "fixture-b": GraduationHypothesis("fixture-b", Level.CORPUS_VERIFIED),
        "fixture-roundtrip": GraduationHypothesis("fixture-roundtrip", Level.CORPUS_VERIFIED),
    }
    runs = (GraduationRun("run", ("fixture-a",), committed=True),)
    return row, support, runs


def test_all_conditions_hold() -> None:
    assert graduated(*inputs()) == (True, ())
    assert RELEASE_LEVELS == RELEASE_VERIFIED


@pytest.mark.parametrize(
    "level", (Level.INFERRED, Level.UNKNOWN, Level.UNVERIFIED, Level.ALTIUM_VERIFIED_AUTHOR_REPORT)
)
def test_one_weak_hypothesis_refuses(level: Level) -> None:
    row, support, runs = inputs()
    support["fixture-b"] = replace(support["fixture-b"], level=level)
    ok, missing = graduated(row, support, runs)
    assert not ok and any("fixture-b" in item for item in missing)


@pytest.mark.parametrize(
    "change", ({"stale": ("fixture-a",)}, {"synthetic": True}, {"committed": False}, {"hypotheses": ()})
)
def test_unsound_or_stale_run_undoes_graduation(change) -> None:
    row, support, runs = inputs()
    ok, missing = graduated(row, support, (replace(runs[0], **change),))
    assert not ok and any("run" in item for item in missing)


def test_missing_and_refuted_support() -> None:
    row, support, runs = inputs()
    del support["fixture-b"]
    support["fixture-roundtrip"] = replace(support["fixture-roundtrip"], refuted=True)
    ok, missing = graduated(replace(row, readback=""), support, runs)
    assert not ok
    assert "fixture-b: not registered" in missing and "fixture-roundtrip: refuted" in missing
    assert "own-readback suite is not named" in missing


def test_kicad_uses_its_own_tool_evidence() -> None:
    row = MatrixRow(
        "kicad",
        "authored",
        write=Evidence(Level.KICAD_VERIFIED, hypotheses=("fixture-kicad",)),
        readback="suite",
    )
    support = {"fixture-kicad": GraduationHypothesis("fixture-kicad", Level.KICAD_VERIFIED)}
    assert graduated(row, support, ()) == (True, ())
    support["fixture-kicad"] = replace(support["fixture-kicad"], level=Level.CORPUS_VERIFIED)
    assert not graduated(row, support, ())[0]


def test_matrix_enforces_both_directions_and_names_suites() -> None:
    support, runs = graduation_context()
    for row in matrix.rows():
        if row.write is None:
            continue
        assert (ROOT / row.readback).is_file(), (row.backend, row.kind, row.readback)
        assert "def test_" in (ROOT / row.readback).read_text()
        ok, missing = graduated(row, support, runs)
        assert ("write" not in row.experimental) == ok, (row.kind, missing)
        if row.backend == "altium" and not any(run.committed and not run.synthetic for run in runs):
            assert not ok  # No actual committed kit is present on this tree.


def test_resource_matches_public_register_and_record_snapshot() -> None:
    import runpy

    from fenolite.verify.hypotheses import load_register

    snapshot = runpy.run_path(str(ROOT / "tools/_graduation.py"))["snapshot"]

    path = ROOT / "src/fenolite/backends/graduation.json"
    assert path.read_text() == snapshot(ROOT, load_register(ROOT / "docs/hypotheses.md"))
