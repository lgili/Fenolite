# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored atomic corridor routes and protected/pair negatives with native KiCad (c0367)."""

from collections import Counter
from pathlib import Path

import pytest
from _negotiate_project import NEGOTIATE, project
from _probes import major, runner
from _search_project import cli

from fenolite.routing.decisions import loads

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
def test_joint_corridor_bundle_closes_both_connections_without_new_drc(
    tmp_path: Path, monkeypatch, layers: int
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(runner().path))
    built = project(tmp_path, layers=layers, major=major())
    before = built.board.read_bytes()
    violations, opens = drc(built.board)
    words = ("route", str(built.board), "--router", "octilinear")
    code, reply, err = cli(*words, "--propose", *NEGOTIATE)
    assert code == 0, err
    assert len(reply["result"]["bundles"]) == 1
    bundle = reply["result"]["bundles"][0]
    assert len(bundle["members"]) == 2 and built.board.read_bytes() == before
    code, plan, err = cli(*words, "--accept", bundle["id"], *NEGOTIATE, "--gate", "drc", "--dry-run")
    assert code == 0, err
    assert built.board.read_bytes() == before
    code, reply, err = cli(
        *words,
        "--accept",
        bundle["id"],
        *NEGOTIATE,
        "--gate",
        "drc",
        "--confirm",
        "--plan",
        plan["result"]["plan_id"],
    )
    assert code == 0, err
    record = loads((tmp_path / reply["result"]["record"]).read_bytes())
    assert len(record.locked) == 2 and record.bundles[0].id == bundle["id"]
    following, remaining = drc(built.board)
    assert remaining == opens - 2
    assert all(following[k] <= violations[k] for k in following), (violations, following)


@pytest.mark.parametrize("case", ["locked", "pair"])
def test_protected_originals_and_coupled_legs_never_escape_as_partial_copper(
    tmp_path: Path, monkeypatch, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(runner().path))
    built = project(tmp_path, major=major(), locked=case == "locked", pair=case == "pair")
    before = built.board.read_bytes()
    prior = drc(built.board)
    code, reply, err = cli("route", str(built.board), "--router", "octilinear", "--propose", *NEGOTIATE)
    assert code == 0, err
    assert not reply["result"]["bundles"]
    assert len(reply["result"]["proposals"]) == 2
    assert not any(p["candidates"] for p in reply["result"]["proposals"])
    assert built.board.read_bytes() == before and drc(built.board) == prior
    if case == "pair":
        assert all(p["reason"] == "negotiate-unsupported" for p in reply["result"]["proposals"])
