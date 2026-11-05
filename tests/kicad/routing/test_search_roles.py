# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0366 authored hard detours, missing limits and stale fills with native DRC."""

from collections import Counter
from pathlib import Path

import pytest
from _probes import major, runner
from _rolefieldproject import role_project
from _search_project import SEARCH, cli

pytestmark = pytest.mark.needs_kicad


def drc(board: Path):
    result = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert result.report is not None
    return Counter(v.type for v in result.report.violations if not v.excluded), sum(
        not v.excluded for v in result.report.unconnected_items
    )


@pytest.mark.parametrize("layers", [2, 4])
@pytest.mark.parametrize("state", ["valid", "stale", "missing-limit"])
def test_role_search_detour_or_explicit_unknown(tmp_path: Path, monkeypatch, layers: int, state: str) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(runner().path))
    built = role_project(tmp_path, layers, state=state, major=major())
    before = built.board.read_bytes()
    violations, opens = drc(built.board)
    words = ("route", str(built.board), "--router", "octilinear")
    code, reply, err = cli(*words, "--propose", "--nets", "SIG", *SEARCH)
    assert code == 0, err
    assert built.board.read_bytes() == before
    row = reply["result"]["proposals"][0]
    if state == "missing-limit":
        assert not row["candidates"] and row["reason"] == "search-role-limit"
        assert reply["result"]["role_fields"]["missing_limits"]
        assert drc(built.board) == (violations, opens)
        return
    candidate = row["candidates"][0]
    facts = candidate["facts"]["role_fields"]
    if state == "stale":
        assert facts["confirmed_reference_length_lower_bound_nm"] == 0
        assert any(s.startswith("ground:") for s in facts["unknowns"])
    else:
        assert facts["confirmed_reference_length_lower_bound_nm"] > 0
    assert facts["switching_exposure_upper_bound_nm"] == 0
    assert candidate["source"] == "search"
    code, planned, err = cli(*words, "--accept", candidate["id"], *SEARCH, "--gate", "drc", "--dry-run")
    assert code == 0, err
    assert built.board.read_bytes() == before
    code, _, err = cli(
        *words,
        "--accept",
        candidate["id"],
        *SEARCH,
        "--gate",
        "drc",
        "--confirm",
        "--plan",
        planned["result"]["plan_id"],
    )
    assert code == 0, err
    after, remaining = drc(built.board)
    assert remaining == opens - 1
    assert all(after[k] <= violations[k] for k in after), (violations, after)
