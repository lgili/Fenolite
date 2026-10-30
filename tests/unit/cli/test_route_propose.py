# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite route --propose``, ``--accept``, ``--reject``, ``--replay`` and ``--forget`` (change c0280;
capability cli-contract, "Route proposal mode" and the requirements after it; ``docs/cli-contract.md``,
"route"), on the authored benches of ``tests/unit/roles/_proposals.py`` and the buck role-copper variant
after phase 2."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

ROLES_TESTS = Path(__file__).resolve().parents[1] / "roles"
if str(ROLES_TESTS) not in sys.path:
    sys.path.insert(0, str(ROLES_TESTS))

from _critical import cli  # noqa: E402
from _proposals import copy_of, family_bench, phase2, subject_bench, wall_bench  # noqa: E402
from _roleboards import Built  # noqa: E402

from fenolite.backends.kicad.pcb import read_board  # noqa: E402
from fenolite.cli import _gate  # noqa: E402
from fenolite.cli._propose import CANDIDATE_KEYS, PROPOSAL_KEYS  # noqa: E402
from fenolite.routing.decisions import loads  # noqa: E402
from fenolite.routing.protocol import SUBJECT_KINDS  # noqa: E402

ROUTE = ("--router", "octilinear")
FORBIDDEN = {"score", "rank", "best", "recommended", "cost"}


def route(board: Path, *more: str) -> tuple[int, dict[str, Any], str]:
    return cli("route", str(board), *ROUTE, *more)


def propose(board: Path, *more: str) -> dict[str, Any]:
    code, env, err = route(board, "--propose", *more)
    assert code == 0, err
    return env


def planned(board: Path, *more: str) -> dict[str, Any]:
    """``route`` through the reviewed plan: the dry run, then ``--confirm --plan``; the confirm's envelope."""
    code, env, err = route(board, *more, "--dry-run")
    assert code == 0, (err, env.get("issues"))
    plan = env["result"]["plan_id"]
    code, done, err = route(board, *more, "--confirm", "--plan", plan)
    assert code == 0, err
    return done


def codes(env: dict[str, Any], prefix: str = "route.proposal") -> list[str]:
    return sorted(i["code"] for i in env["issues"] if i["code"].startswith(prefix))


def by_subject(env: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["subject"]: p for p in env["result"]["proposals"]}


def digests(folder: Path) -> dict[str, str]:
    return {
        str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def keys_in(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():  # type: ignore[union-attr]
            yield str(key)
            yield from keys_in(item)
    elif isinstance(value, list):
        for item in value:  # type: ignore[union-attr]
            yield from keys_in(item)


@pytest.fixture(scope="module")
def p2(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, str], Built]:
    base = tmp_path_factory.mktemp("phase2")
    return lambda board, variant: phase2(board, variant, base)


@pytest.fixture(scope="module")
def bench_board(tmp_path_factory: pytest.TempPathFactory) -> Built:
    return subject_bench(tmp_path_factory.mktemp("subjects"))


# --- task 3.1 -----------------------------------------------------------------------------------------------


def test_wrong_router(bench_board: Built) -> None:
    """Scenario "Wrong router": a router without the feature ``propose`` is ``FEN-2001`` naming
    ``octilinear``."""
    code, _, err = cli("route", str(bench_board.board), "--router", "direct", "--propose")
    assert code == 2
    error = json.loads(err.strip().splitlines()[-1])
    assert error["code"] == "FEN-2001" and "octilinear" in error["hint"]


@pytest.mark.parametrize(
    "more",
    [
        ("--propose", "--replay"),
        ("--propose", "--roles", "critical"),
        ("--propose", "--rip"),
        ("--accept", "c-0000000000000000", "--require-complete"),
        ("--kind", "join"),
        ("--reason", "x"),
        ("--propose", "--candidates", "9"),
        ("--replay", "--nets", "GND"),
    ],
)
def test_router_options_of_the_modes(bench_board: Built, more: tuple[str, ...]) -> None:
    """The modes exclude each other (``--accept`` and ``--reject`` excepted) and the options of other
    modes."""
    code, _, err = route(bench_board.board, *more)
    assert code == 2 and "FEN-2001" in err


def test_proposing_writes_nothing(p2: Callable[[str, str], Built], tmp_path: Path) -> None:
    """Scenario "Proposing writes nothing": exit 0, proposals, no ``plan_id``, every file unchanged."""
    built = copy_of(p2("buck_shunt", "bad"), tmp_path)
    before = digests(built.out)
    env = propose(built.board)
    assert env["result"]["proposals"] and "plan_id" not in env["result"] and not env.get("receipt")
    assert digests(built.out) == before
    assert env["evidence"]["level"] == "UNVERIFIED"


@pytest.mark.parametrize("board", ["buck_shunt", "half_bridge", "bms"])
def test_closed_keys(p2: Callable[[str, str], Built], board: str) -> None:
    """Scenario "Closed keys": every proposal and candidate has exactly the listed keys, no score anywhere,
    proposals sorted by kind then subject (the three ``bad_roles`` variants, one candidate per subject)."""
    env = propose(p2(board, "bad").board, "--candidates", "1")
    result = env["result"]
    assert set(result) >= {"mode", "order", "open", "proposals", "rejected", "locked", "next"}
    assert (result["mode"], result["order"]) == ("propose", "generation")
    proposals = result["proposals"]
    assert proposals
    for proposal in proposals:
        assert tuple(proposal) == PROPOSAL_KEYS
        for candidate in proposal["candidates"]:
            assert tuple(candidate) == CANDIDATE_KEYS
    order = [(SUBJECT_KINDS.index(p["kind"]), p["subject"]) for p in proposals]
    assert order == sorted(order)
    assert not FORBIDDEN & set(keys_in(result))


def test_fanout_facts(p2: Callable[[str, str], Built]) -> None:
    """Scenario "Facts of a fan-out": ``fanout:GND:C3-2`` has a candidate with one via, ``open.after`` one
    below ``open.before``, no new copper-check finding, and ``drc`` not evaluated for want of a gate."""
    env = propose(p2("buck_shunt", "bad").board)
    proposal = by_subject(env)["fanout:GND:C3-2"]
    assert proposal["kind"] == "fanout" and proposal["region"].startswith("fenolite render ")
    good = [
        c
        for c in proposal["candidates"]
        if c["facts"]["vias"] == 1
        and c["facts"]["open"]["after"] == c["facts"]["open"]["before"] - 1
        and c["facts"]["copper_check"]["new"] == []
    ]
    assert good
    facts = good[0]["facts"]
    assert {"fact": "drc", "why": "no-gate"} in facts["not_evaluated"]
    assert facts["closes"] == ["GND:C3-2"] and facts["fill"] in ("saved", "simulated", "stale")
    assert set(facts) >= {"closes", "open", "copper_check", "vias", "length", "layers", "bends", "conflicts"}


def test_blocked_connection(tmp_path: Path) -> None:
    """Scenario "A blocked connection": no candidate, reason ``no-room``, ``free-corridor`` naming the wall, a
    ``render --region`` command, one ``route.proposal-open``."""
    built = wall_bench(tmp_path)
    env = propose(built.board)
    (proposal,) = env["result"]["proposals"]
    assert proposal["candidates"] == [] and proposal["reason"] == "no-room"
    first = proposal["alternatives"][0]
    assert first["kind"] == "free-corridor" and "FENCE" in first["text"]
    assert " --region " in first["command"] and first["region"].startswith("fenolite render ")
    assert codes(env) == ["route.proposal-open"]


# --- task 3.2 -----------------------------------------------------------------------------------------------


def test_drc_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Batches of candidates": the gate runs once per batch, three batches for two subjects of three
    candidates; only the candidate whose items the stand-in gate names gets ``drc.new``."""
    built = family_bench(tmp_path)
    calls: list[list[frozenset[str]]] = []
    marked: dict[str, str] = {}

    def gate(board: Path, before: object, after: object, **kwargs: Any) -> _gate.Gated:
        together = [frozenset(unit) for unit in kwargs.get("together", ())]
        calls.append(together)
        dropped = []
        if len(calls) == 1 and together:
            first = sorted(together[0])[0]
            marked["id"] = first
            dropped = [{"id": first, "findings": [{"type": "clearance", "description": "stand-in"}]}]
        result = dict(_gate.untouched(), tool_version="10.0.7", dropped=dropped)
        return _gate.Gated(after, frozenset(d["id"] for d in dropped), result, (), None)  # type: ignore[arg-type]

    monkeypatch.setattr(_gate, "preflight", lambda *args, **kwargs: None)
    monkeypatch.setattr(_gate, "gate", gate)
    env = propose(built.board, "--candidates", "3", "--gate", "drc")
    proposals = env["result"]["proposals"]
    counts = [len(p["candidates"]) for p in proposals]
    assert counts == [3, 3] and len(calls) == 3
    flagged = [c for p in proposals for c in p["candidates"] if c["facts"]["drc"]["new"]]
    assert len(flagged) == 1 and flagged[0]["facts"]["drc"]["new"][0]["type"] == "clearance"
    assert all(
        c["facts"]["drc"]["evidence"].startswith("KICAD-VERIFIED") for p in proposals for c in p["candidates"]
    )
    assert not [
        r
        for p in proposals
        for c in p["candidates"]
        for r in c["facts"]["not_evaluated"]
        if r["fact"] == "drc"
    ]


# --- task 3.3 -----------------------------------------------------------------------------------------------


def _fanout_id(env: dict[str, Any]) -> str:
    candidates = by_subject(env)["fanout:GND:C3-2"]["candidates"]
    return next(c["id"] for c in candidates if c["source"] == "fanout")


def test_accept_then_confirm(p2: Callable[[str, str], Built], tmp_path: Path) -> None:
    """Scenario "Accept, then confirm": the dry run writes nothing; the confirm writes the board with a locked
    track and via and the record holding the candidate, both in the receipt."""
    built = copy_of(p2("buck_shunt", "bad"), tmp_path)
    chosen = _fanout_id(propose(built.board))
    before = digests(built.out)
    code, dry, err = route(built.board, "--accept", chosen, "--dry-run")
    assert code == 0, err
    assert dry["result"]["plan_id"] and digests(built.out) == before
    assert [row["candidate"] for row in dry["result"]["accepted"]] == [chosen]
    done = planned(built.board, "--accept", chosen)
    written = sorted(Path(row["path"]).name for row in done["receipt"]["written"])
    assert written == sorted([built.board.name, "route-decisions.json"])
    design = read_board(built.board.read_text(encoding="utf-8"), file=built.board.name)
    assert design.board is not None
    locked_tracks = [t for t in design.board.tracks if t.locked and t.id.startswith("trk_")]
    locked_vias = [v for v in design.board.vias if v.locked]
    assert locked_vias and locked_tracks
    record = loads((built.out / ".fenolite" / "route-decisions.json").read_bytes())
    assert [e.candidate for e in record.locked] == [chosen] and record.locked[0].subject == "fanout:GND:C3-2"
    again = propose(built.board)
    assert "fanout:GND:C3-2" not in by_subject(again)
    assert again["result"]["locked"] == [{"candidate": chosen, "subject": "fanout:GND:C3-2", "present": True}]


def test_unknown_and_conflicting_ids(p2: Callable[[str, str], Built], tmp_path: Path) -> None:
    """Scenario "Unknown and conflicting ids": both exit 5 with ``FEN-5001``, naming the code, and nothing is
    planned."""
    built = copy_of(p2("buck_shunt", "bad"), tmp_path)
    code, env, err = route(built.board, "--accept", "c-0000000000000000", "--dry-run")
    assert code == 5 and "FEN-5001" in err
    assert codes(env) == ["route.proposal-unknown"] and "c-0000000000000000" in env["issues"][-1]["where"]
    assert not env["result"].get("plan_id")
    candidates = by_subject(propose(built.board))["fanout:GND:C3-2"]["candidates"]
    assert len(candidates) >= 2
    code, env, err = route(
        built.board, "--accept", candidates[0]["id"], "--accept", candidates[1]["id"], "--dry-run"
    )
    assert code == 5 and "FEN-5001" in err
    assert "route.proposal-conflict" in codes(env) and not env["result"].get("plan_id")


def test_a_rejected_candidate_stays_out(bench_board: Built, tmp_path: Path) -> None:
    """Scenario "A rejected candidate stays out": ``--reject R --reason`` plans the record only; ``--propose``
    lists no R and one ``route.proposal-rejected``; ``--show-rejected`` lists R with ``rejected`` true."""
    built = copy_of(bench_board, tmp_path)
    env = propose(built.board)
    rejected = by_subject(env)["connection:SIG:R1-1~R2-1"]["candidates"][0]["id"]
    done = planned(built.board, "--reject", rejected, "--reason", "crosses the gate loop")
    assert [Path(row["path"]).name for row in done["receipt"]["written"]] == ["route-decisions.json"]
    record = loads((built.out / ".fenolite" / "route-decisions.json").read_bytes())
    assert [(e.id, e.reason) for e in record.rejected] == [(rejected, "crosses the gate loop")]
    again = propose(built.board)
    ids = [c["id"] for p in again["result"]["proposals"] for c in p["candidates"]]
    assert rejected not in ids and codes(again).count("route.proposal-rejected") == 1
    shown = propose(built.board, "--show-rejected")
    rows = [c for p in shown["result"]["proposals"] for c in p["candidates"] if c["id"] == rejected]
    assert [row["rejected"] for row in rows] == [True]
    proposal_id = by_subject(again)["role-net:VS:R6-1~R7-1"]["id"]
    planned(built.board, "--reject", proposal_id)
    after = propose(built.board)
    assert "role-net:VS:R6-1~R7-1" not in by_subject(after)
    assert [r["id"] for r in after["result"]["rejected"]] == [proposal_id]


def test_a_malformed_record_is_refused(bench_board: Built, tmp_path: Path) -> None:
    built = copy_of(bench_board, tmp_path)
    (built.out / ".fenolite" / "route-decisions.json").write_text('{"schema": "x"}', encoding="utf-8")
    code, _, err = route(built.board, "--propose")
    assert code == 3 and "FEN-3004" in err


# --- task 3.4 -----------------------------------------------------------------------------------------------


def test_replay_on_a_fresh_build(
    p2: Callable[[str, str], Built], tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Scenario "Replay on a fresh build": the record of the accepted buck beside a fresh build of the same
    script in another folder; ``--replay --confirm`` writes the accepted items with their ids, the board
    equals the accepted one byte for byte, and a second replay plans no write."""
    accepted = copy_of(p2("buck_shunt", "bad"), tmp_path / "accepted")
    chosen = _fanout_id(propose(accepted.board))
    planned(accepted.board, "--accept", chosen)
    fresh = copy_of(phase2("buck_shunt", "bad", tmp_path_factory.mktemp("fresh")), tmp_path / "fresh")
    shutil.copy(
        accepted.out / ".fenolite" / "route-decisions.json", fresh.out / ".fenolite" / "route-decisions.json"
    )
    done = planned(fresh.board, "--replay")
    assert done["result"]["replayed"] == [chosen] and done["result"]["stale"] == []
    assert fresh.board.read_bytes() == accepted.board.read_bytes()
    code, env, err = route(fresh.board, "--replay", "--dry-run")
    assert code == 0, err
    assert not env["result"].get("plan_id") and env["result"]["replayed"] == []


def test_forget(p2: Callable[[str, str], Built], tmp_path: Path) -> None:
    """``--forget ID`` plans removing the entry and its items; an unknown id is ``route.proposal-unknown``."""
    built = copy_of(p2("buck_shunt", "bad"), tmp_path)
    before = built.board.read_bytes()
    chosen = _fanout_id(propose(built.board))
    planned(built.board, "--accept", chosen)
    assert built.board.read_bytes() != before
    done = planned(built.board, "--forget", chosen)
    assert done["result"]["removed"] == 2
    assert built.board.read_bytes() == before
    record = loads((built.out / ".fenolite" / "route-decisions.json").read_bytes())
    assert record.locked == ()
    code, env, _ = route(built.board, "--forget", chosen, "--dry-run")
    assert code == 5 and codes(env) == ["route.proposal-unknown"]
