# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""When KiCad applies a stored DRC exclusion (``H-K-DRC-EXCL``; capability kicad-oracle, "Exclusion facts
are probed"; change c0114), and what ``fenolite check`` then says about a stale one (verification-loop,
"Exclusions in the DRC stage").

The bench of ``_exclcases.py`` runs on the running ``kicad-cli``; every key is built from the report of a
first run. ``tests/kicad/test_probe_results.py`` pins every outcome per version.
"""

from __future__ import annotations

from pathlib import Path

import _exclcases as ex
import pytest
from _checkrun import check, stage
from _probes import run

from fenolite.backends.base import NIL_UUID

pytestmark = pytest.mark.needs_kicad


def test_exclusion_first_run_has_the_entries_to_exclude() -> None:
    found = ex.first()
    (via,) = ex.via_entries(found)
    (pair,) = ex.clearance_entries(found)
    assert not via.excluded and not pair.excluded and via.severity == "warning"
    assert len(via.items) == 1 and len(pair.items) == 2
    assert ex.via_key() == f"via_dangling|30123456|20654321|{via.items[0].uuid}|{NIL_UUID}"


@pytest.mark.parametrize("case", ex.CASES)
def test_exclusion_facts(case: str) -> None:
    """Scenario "Exclusion facts on both majors"."""
    (entry,) = ex.excluded(case)
    assert entry.excluded is (case in ("pair", "plain", "first-position")), case
    assert entry.comment == (ex.COMMENT if case == "pair" else "pair" if case == "first-position" else "")
    assert run(f"drc-excl-{case}") == "equal"


def test_exclusion_keeps_the_severity_and_gains_the_comment() -> None:
    (before,) = ex.via_entries(ex.first())
    (after,) = ex.excluded("pair")
    assert (after.type, after.severity, after.items) == (before.type, before.severity, before.items)
    assert after.excluded and after.comment == ex.COMMENT


def test_exclusion_project_file_is_not_written() -> None:
    assert run("drc-excl-project-unchanged") == "equal"


def test_exclusion_stage_reports_a_moved_exclusion(tmp_path: Path) -> None:
    """The stage run: an exclusion whose marker position is 1 nm off is ``moved``, a live one shows its
    comment, and an exclusion of a type that KiCad does not repeat is not judged."""
    dangling = [
        entry
        for entry in ex.first().of_type("track_dangling")
        if {item.uuid for item in entry.items} & set(ex.bench().uuids("close_a"))
    ]
    exclusions = [
        [ex.via_key(dx=1), ex.COMMENT],
        [ex.clearance_key(), "pair"],
        [ex.key(dangling[0]), "kept"],
    ]
    (tmp_path / ex.BOARD).write_text(ex._board_text("exclusion"), encoding="utf-8")  # pyright: ignore[reportPrivateUsage]
    (tmp_path / ex.PROJECT).write_text(ex.project_text(exclusions=exclusions), encoding="utf-8")
    before = (tmp_path / ex.PROJECT).read_bytes()
    _, env, _, stderr = check(tmp_path, "--stages", "drc.kicad")
    assert env, stderr
    (stale,) = [found for found in env["issues"] if found["code"] == "check.exclusion-stale"]
    assert stale["severity"] == "warning" and "(moved)" in stale["message"]
    assert "via_dangling" in stale["message"] and repr(ex.COMMENT) in stale["message"]
    assert stale["where"].startswith("/kicad_pcb/via[")
    summary = stage(env, "drc.kicad")["summary"]
    assert summary["exclusions"] == {"stored": 3, "live": 1, "stale": 1, "unjudged": 1}
    kept = [found for found in env["issues"] if found["message"].endswith("(excluded in the project: kept)")]
    assert kept and all(found["severity"] == "info" for found in kept)
    assert {found["code"] for found in kept} == {"kicad.drc.track-dangling"}
    assert (tmp_path / ex.PROJECT).read_bytes() == before
