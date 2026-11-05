# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The router families of c0365-c0369 together on an authored board, judged by the running ``kicad-cli``
(change c0370, task 5; capability routing, "Reviewed completion acceptance").

One run on two and four layers: the bounded search (c0365) with the role fields of a sensitive net over a
saved ground reference (c0366) negotiates the crossing ``SIG``/``SECOND`` pair into one atomic bundle (c0367);
an external candidate tool that is not installed refuses the whole run and writes nothing (c0368; the pinned
tools themselves are judged by ``test_external_candidates.py`` in the router CI job); the viewer accepts the
bundle as one reviewed unit (c0369); a second, ordinary search pass closes ``EXTRA``. KiCad's DRC finds one
open connection per subject fewer at each stage and no violation type growing, and ``result.completion``
stays truthful throughout.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _families_project import project
from _negotiate_project import NEGOTIATE
from _probes import major, runner
from _search_project import SEARCH, cli

from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from tests.unit.cli.test_view_actions import _Served

pytestmark = pytest.mark.needs_kicad
ROUTE = ("--router", "octilinear")
SIG = "connection:SIG:R1-1~R2-1"
SECOND = "connection:SECOND:R3-1~R4-1"
EXTRA = "connection:EXTRA:R5-1~R6-1"
PAIR = ("--nets", "SIG", "--nets", "SECOND")


def drc(board: Path) -> tuple[Counter[str], int]:
    result = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert result.report is not None
    violations = Counter(v.type for v in result.report.violations if not v.excluded)
    return violations, sum(not v.excluded for v in result.report.unconnected_items)


def no_growth(before: Counter[str], after: Counter[str]) -> bool:
    return all(after[kind] <= before[kind] for kind in after)


def propose(board: Path, *more: str) -> dict[str, Any]:
    unchanged = board.read_bytes()
    code, env, err = cli("route", str(board), *ROUTE, "--propose", *more)
    assert code == 0, err
    assert board.read_bytes() == unchanged, "a proposal run writes nothing"
    return env


@pytest.mark.parametrize("layers", [2, 4])
def test_router_families_close_the_board_through_reviewed_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layers: int
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.chdir(source)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(runner().path))
    built = project(source, layers=layers, major=major())
    violations, opens = drc(built.board)
    assert opens == 3, violations

    # c0368: a tool that is not installed refuses the run before anything is proposed or written.
    if not KicadRoutingToolsRouter().available().available:
        before = built.board.read_bytes()
        words = ("route", str(built.board), *ROUTE, "--propose", *PAIR, *SEARCH)
        code, _env, err = cli(*words, "--propose-with", "kicadroutingtools")
        assert code == 6 and json.loads(err)["code"] == "FEN-6001", err
        assert built.board.read_bytes() == before

    # c0365-c0367: role-aware search negotiates the crossing pair into one atomic bundle.
    envelope = propose(built.board, *PAIR, *NEGOTIATE)
    result = envelope["result"]
    (bundle,) = result["bundles"]
    assert set(bundle["subjects"]) == {SIG, SECOND} and len(bundle["members"]) == 2
    sources = {c["source"] for p in result["proposals"] for c in p["candidates"]}
    assert sources == {"search"}
    assert result["role_fields"]["fingerprint"] and result["role_fields"]["provenance"]["fill"]
    done = result["completion"]
    assert done["subjects"]["proposed"] == [SECOND, SIG] and done["subjects"]["not-attempted"] == [EXTRA]
    assert done["open"] == 3 and done["complete"] is False

    # c0369: the viewer refuses a lone member and accepts the bundle as one reviewed unit.
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(envelope), encoding="utf-8")
    served = _Served(monkeypatch, tmp_path, built.board, ("--proposals", str(saved)))
    before = served.board.read_bytes()
    with served:
        code, refused = served.post(
            "/action/plan",
            {"action": "route-accept", "doc": "doc1", "options": {"candidates": [bundle["members"][0]]}},
        )
        assert code == 400, refused
        reviewed = served.plan("route-accept", candidates=[bundle["id"]])
        assert reviewed["plan"]["confirmable"] and served.board.read_bytes() == before, reviewed
        accepted = served.confirm(reviewed)
    assert accepted["exit"] == 0, accepted
    board = served.board
    record = json.loads((served.folder / ".fenolite" / "route-decisions.json").read_text(encoding="utf-8"))
    assert record["bundles"][0]["id"] == bundle["id"]
    after_bundle, open_bundle = drc(board)
    assert open_bundle == opens - 2 and no_growth(violations, after_bundle), (violations, after_bundle)

    # A second, ordinary search pass: the bundle's copper is present and only EXTRA is left.
    second = propose(board, "--nets", "EXTRA", *SEARCH)["result"]
    assert second["completion"]["open"] == 1 and second["completion"]["subjects"]["proposed"] == [EXTRA]
    assert [row["present"] for row in second["locked"]] == [True, True]
    (row,) = second["proposals"]
    words = ("route", str(board), *ROUTE, "--accept", row["candidates"][0]["id"], *SEARCH)
    code, planned, err = cli(*words, "--dry-run")
    assert code == 0, err
    code, _env, err = cli(*words, "--confirm", "--plan", planned["result"]["plan_id"])
    assert code == 0, err

    final, remaining = drc(board)
    assert remaining == 0 and no_growth(violations, final), (violations, final)
    closed = propose(board)["result"]
    assert closed["completion"]["state"] == "unchecked" and closed["completion"]["open"] == 0
    assert not any(closed["completion"]["subjects"].values()) and closed["completion"]["complete"] is False
    assert all(row["present"] for row in closed["locked"]) and len(closed["locked"]) == 3
