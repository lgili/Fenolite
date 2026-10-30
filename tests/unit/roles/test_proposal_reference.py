# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Proposals on the reference boards, the acceptance gate of change c0280 (capability net-roles, "Leftover
opens of role copper are proposed", "Proposals on the reference boards" and "Proposals on both backends";
hypotheses ``H-G-PROP-LEFTOVERS``, ``-FACTS``, ``-COMPLETE``, ``-REPLAY`` and ``H-A-PROP-READBACK``;
``docs/roles.md``, "Proposals after the critical routes").

Each role-copper variant (``good_roles.py``, ``bad_roles.py``; phase 1 runs in its build) is built, its
inferred roles and groups confirmed (``roles --accept-all``, as the reference tests confirm them), and its
critical routes written (``route --roles critical``, phase 2). Then ``route --propose --candidates 2`` runs
as a user runs it. The test, not Fenolite, chooses (design decision 15): per proposal that holds an open
connection the first candidate in reply order whose facts show ``open.after < open.before``, no new
copper-check finding and no new role finding of warning or above; each ``group`` proposal (a group phase 2
left ``unrouted`` with its connections closed, task 0.1) is rejected whole. Both go in one reviewed plan.
Two candidates per subject keep the test's time; the default is four.
"""

from __future__ import annotations

import dataclasses
import shutil
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from _critical import cli, confirmed_copy, routed
from _proposals import copy_of, phase2
from _roleboards import EXAMPLES, Built, read
from _rolecheck import checked, inputs
from _rolecheck import findings as variant_findings
from _rolecopper import board as read_role_board
from _rolecopper import findings

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.connectivity import connectivity
from fenolite.analysis.pour import DEFAULT_GRID_NM, pour_copper
from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.backends.kicad.pcb import read_board
from fenolite.cli import cmd_route
from fenolite.core.coords import Point
from fenolite.model.design import Design
from fenolite.roles import copper
from fenolite.roles.judge import Judged, run
from fenolite.routing.decisions import loads
from fenolite.routing.octilinear import fresh

ROUTE = ("--router", "octilinear")
REJECT_REASON = "group proposals are recorded, not locked, by the reference gate"
LEFTOVERS: dict[tuple[str, str], list[str]] = {
    ("buck_shunt", "good"): ["fanout:GND:C3-2"],
    ("buck_shunt", "bad"): ["fanout:GND:C3-2", "join:VOUT:C3-1~role.power.VOUT.F.Cu"],
    ("half_bridge", "good"): ["join:SRC:Q2-2~role.power.SRC.F.Cu", "join:SW:Q1-2~role.switch_node.SW.F.Cu"],
    ("half_bridge", "bad"): ["join:SRC:Q2-2~role.power.SRC.F.Cu"],
    ("bms", "good"): ["role-net:FET_S:Q1-2~Q1-3", "role-net:FET_S:Q1-3~Q2-3"],
    ("bms", "bad"): ["role-net:FET_S:Q1-2~Q1-3", "role-net:FET_S:Q1-3~Q2-3"],
}
"""The subjects of the opens phase 1 leaves (task 0.1), per variant after phase 2."""
GROUPS: dict[tuple[str, str], list[str]] = {
    ("buck_shunt", "good"): ["group:gate_Q1"],
    ("buck_shunt", "bad"): ["group:gate_Q1", "group:kelvin_R12"],
    ("half_bridge", "good"): [],
    ("half_bridge", "bad"): ["group:gate_Q1"],
    ("bms", "good"): [],
    ("bms", "bad"): ["group:kelvin_R1"],
}
"""The groups phase 2 leaves ``unrouted`` on the variants (task 0.1), whose connections are closed."""
CASES = sorted(LEFTOVERS)
ROUTING_CODES = {"roles.kelvin-outer", "roles.kelvin-shared", "roles.gate-return-shared", "roles.gate-loop"}


def route(board: Path, *more: str) -> tuple[int, dict[str, Any], str]:
    return cli("route", str(board), *ROUTE, *more)


def planned(board: Path, *more: str) -> dict[str, Any]:
    code, env, err = route(board, *more, "--dry-run")
    assert code == 0, (err, [i for i in env.get("issues", []) if i["severity"] == "error"])
    plan = env["result"].get("plan_id")
    assert plan, env["result"]
    code, done, err = route(board, *more, "--confirm", "--plan", plan)
    assert code == 0, err
    return env


def clean(candidate: dict[str, Any]) -> bool:
    """The test's rule: the candidate lowers ``open`` and brings no new copper-check finding and no new role
    finding of warning or above."""
    facts = candidate["facts"]
    roles = facts.get("roles", {}).get("new", [])
    return (
        facts["open"]["after"] < facts["open"]["before"]
        and not facts["copper_check"]["new"]
        and not [row for row in roles if row["severity"] in ("warning", "error")]
    )


@dataclasses.dataclass
class Chain:
    """A variant through phases 1, 2 and 4: the board after phase 2 and after the accepted plan, the first
    proposal reply, the accepted candidates, the rejected proposals, the accept reply and the second
    proposal reply."""

    before: Built
    built: Built
    first: dict[str, Any]
    accepted: dict[str, dict[str, Any]]
    rejected: list[str]
    plan: dict[str, Any]
    again: dict[str, Any]


@pytest.fixture(scope="module")
def chain(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, str], Chain]:
    made: dict[tuple[str, str], Chain] = {}

    def get(board: str, variant: str) -> Chain:
        key = (board, variant)
        if key in made:
            return made[key]
        base = tmp_path_factory.mktemp(f"{board}_{variant}_chain")
        before = phase2(board, variant, base)
        built = copy_of(before, base / "accepted")
        code, first, err = route(built.board, "--propose", "--candidates", "2")
        assert code == 0, err
        accepted: dict[str, dict[str, Any]] = {}
        rejected: list[str] = []
        for proposal in first["result"]["proposals"]:
            if proposal["kind"] == "group":
                rejected.append(proposal["id"])
                continue
            chosen = next((c for c in proposal["candidates"] if clean(c)), None)
            assert chosen is not None, (proposal["subject"], proposal["candidates"], proposal["reason"])
            accepted[proposal["subject"]] = chosen
        args = [f"--accept={c['id']}" for c in accepted.values()]
        if rejected:
            args += [*(f"--reject={i}" for i in rejected), "--reason", REJECT_REASON]
        plan = planned(built.board, *args)
        code, again, err = route(built.board, "--propose", "--candidates", "2")
        assert code == 0, err
        made[key] = Chain(before, built, first, accepted, rejected, plan, again)
        return made[key]

    return get


def judged(built: Built, board: str) -> Judged:
    """The role findings of a board of the chain on its simulated pour, with the roles its model stores (the
    chain confirmed every inferred role and group) and the board's requirements file, as c0243's reference
    tests judge a role-copper board."""
    held = read_role_board(built)
    design = copper.with_simulated_fills(held.design, held.pads)
    return run(
        design,
        held.pads,
        circuit=held.circuit,  # type: ignore[arg-type]
        declared=held.declared,
        stored=held.stored,
        inputs=inputs(board),
    )


def _open(built: Built) -> int:
    design = read_board(built.board.read_text(encoding="utf-8"), file=built.board.name)
    _, pads = read(built)
    assert design.board is not None
    pour = pour_copper(design, pads=pads, boundary=board_boundary(design.board), grid=DEFAULT_GRID_NM)
    return connectivity(design, pads=pads, pour=pour).total


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_leftovers(chain: Callable[[str, str], Chain], board: str, variant: str) -> None:
    """Scenario "The leftovers of phase 1", ``H-G-PROP-LEFTOVERS``: the subjects of task 0.1, each with a
    candidate that closes it without a new finding of warning or above (the chain fails without one)."""
    done = chain(board, variant)
    subjects = [p["subject"] for p in done.first["result"]["proposals"]]
    assert [s for s in subjects if not s.startswith("group:")] == LEFTOVERS[board, variant]
    assert [s for s in subjects if s.startswith("group:")] == GROUPS[board, variant]
    assert sorted(done.accepted) == sorted(LEFTOVERS[board, variant])
    for proposal in done.first["result"]["proposals"]:
        if proposal["kind"] == "role-net":
            assert "confirm" in [a["kind"] for a in proposal["alternatives"]]


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_complete(
    chain: Callable[[str, str], Chain], reference: Callable[..., Built], board: str, variant: str
) -> None:
    """Scenario "Fully connected", ``H-G-PROP-COMPLETE``: no open connection after the accepted plan; on the
    simulated pour, no role finding of warning or above on ``good_roles``, exactly the designed routing
    findings on ``bad_roles``."""
    done = chain(board, variant)
    assert _open(done.built) == 0
    found = findings(judged(done.built, board))
    if variant == "good":
        assert found == set()
    else:
        designed = {f for f in variant_findings(checked(reference, board, "bad")) if f[0] in ROUTING_CODES}
        assert found == designed


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_facts_equal_the_measures(chain: Callable[[str, str], Chain], board: str, variant: str) -> None:
    """``H-G-PROP-FACTS``: each accepted candidate's ``open.after`` is one below ``open.before``, and the
    board after the write has as many open connections fewer as candidates were accepted; the copper check
    finds nothing new, and the role findings of warning or above gain nothing, as the facts said."""
    done = chain(board, variant)
    before_open = done.first["result"]["open"]["before"]
    for candidate in done.accepted.values():
        facts = candidate["facts"]
        assert facts["open"] == {"before": before_open, "after": before_open - 1}
    assert _open(done.before) == before_open
    assert _open(done.built) == before_open - len(done.accepted)
    design_before = _with_rules(done.before)
    design_after = _with_rules(done.built)
    rules = cmd_route._project_rules(design_after, done.built.board, [])  # pyright: ignore[reportPrivateUsage]
    check = cmd_route._job_checks(design_after, rules)["copper_check"]  # pyright: ignore[reportPrivateUsage]
    assert fresh(check(design_before), check(design_after)) == []  # type: ignore[operator]
    gained = findings(judged(done.built, board)) - findings(judged(done.before, board))
    assert gained == set()


def _with_rules(built: Built) -> Design:
    design = read_board(built.board.read_text(encoding="utf-8"), file=built.board.name)
    return cmd_route._project_rules(design, built.board, []).design  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_again_a_fixed_point(
    chain: Callable[[str, str], Chain], tmp_path_factory: pytest.TempPathFactory, board: str, variant: str
) -> None:
    """``H-G-PROP-REPLAY``: a second ``--propose`` proposes nothing (``route.proposal-none``), lists every
    decision present and the rejected group proposals apart; ``--replay`` on a fresh build of the same script
    restores the accepted board byte for byte, and a second replay plans no write."""
    done = chain(board, variant)
    result = done.again["result"]
    assert result["proposals"] == []
    codes = [i["code"] for i in done.again["issues"]]
    assert "route.proposal-none" in codes
    assert {row["candidate"] for row in result["locked"]} == {c["id"] for c in done.accepted.values()}
    assert all(row["present"] for row in result["locked"])
    assert sorted(row["id"] for row in result["rejected"]) == sorted(done.rejected)
    if done.rejected:
        assert "route.proposal-rejected" in codes
    record = loads((done.built.out / ".fenolite" / "route-decisions.json").read_bytes())
    assert sorted(e.candidate for e in record.locked) == sorted(c["id"] for c in done.accepted.values())
    fresh_build = copy_of(phase2(board, variant, tmp_path_factory.mktemp(f"{board}_{variant}_fresh")),
                          tmp_path_factory.mktemp(f"{board}_{variant}_replay"))  # fmt: skip
    shutil.copy(
        done.built.out / ".fenolite" / "route-decisions.json",
        fresh_build.out / ".fenolite" / "route-decisions.json",
    )
    replayed = planned(fresh_build.board, "--replay")
    assert sorted(replayed["result"]["replayed"]) == sorted(c["id"] for c in done.accepted.values())
    assert fresh_build.board.read_bytes() == done.built.board.read_bytes()
    code, env, err = route(fresh_build.board, "--replay", "--dry-run")
    assert code == 0, err
    assert not env["result"].get("plan_id") and env["result"]["replayed"] == []


@pytest.mark.parametrize("board", ["buck_shunt", "half_bridge", "bms"])
def test_good_variants_need_nothing(reference: Callable[..., Built], tmp_path: Path, board: str) -> None:
    """Scenario "Good variants need nothing": after phase 2 a ``good`` variant gets no proposal and one
    ``route.proposal-none``."""
    built = confirmed_copy(reference(board, "good"), tmp_path)
    routed(built.board)
    code, env, err = route(built.board, "--propose", "--candidates", "1")
    assert code == 0, err
    assert env["result"]["proposals"] == []
    assert [i["code"] for i in env["issues"] if i["code"].startswith("route.proposal")] == [
        "route.proposal-none"
    ]


def test_open_half_bridge_records_its_sense_pair(reference: Callable[..., Built], tmp_path: Path) -> None:
    """Decision 15.9: on the half-bridge's ``open`` variant after phase 2, the sense pair that ``SW_UNDER``
    blocks is a ``group`` subject whose candidates carry a relaxation, or whose reason is
    ``near-switching``; its open sense branches are not proposed again as plain connections."""
    built = confirmed_copy(reference("half_bridge", "open"), tmp_path)
    routed(built.board)
    code, env, err = route(built.board, "--propose", "--candidates", "2")
    assert code == 0, err
    proposals = {p["subject"]: p for p in env["result"]["proposals"]}
    pair = proposals["group:kelvin_R1"]
    assert pair["reason"] == "near-switching" or all(c["relaxed"] for c in pair["candidates"])
    assert not [s for s in proposals if s.startswith(("join:SRC:", "connection:SRC:", "join:GND:U3"))]


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_altium_readback(
    chain: Callable[[str, str], Chain], tmp_path: Path, board: str, variant: str
) -> None:
    """Scenario "Same accepted copper in Altium", ``H-A-PROP-READBACK``: the convert of each accepted variant
    reads back with every accepted track and via at its place (to 1 µm) and width, locked."""
    done = chain(board, variant)
    out = tmp_path / "altium"
    code, _, err = cli("convert", str(done.built.board), "--to", "altium", "--out", str(out), "--confirm")
    assert code == 0, err
    (document,) = sorted(out.glob("*.PcbDoc"))
    backend = registry.for_path(document)
    assert backend is not None and isinstance(backend, BoardFrame)
    altium = backend.read(document).content
    assert isinstance(altium, Design) and altium.board is not None
    kicad, pads_k = read(done.built)
    pads_a = {f"{p.ref}-{p.number}": p.position for p in backend.board_pads(altium, issues=[])}
    anchor = sorted(f"{p.ref}-{p.number}" for p in pads_k)[0]
    first = next(p.position for p in pads_k if f"{p.ref}-{p.number}" == anchor)
    dx, dy = pads_a[anchor].x - first.x, pads_a[anchor].y - first.y

    def at(point: Point, shift: bool) -> tuple[int, int]:
        x, y = (point.x + dx, point.y + dy) if shift else (point.x, point.y)
        return (round(x / 1_000), round(y / 1_000))

    accepted: Counter[tuple[object, ...]] = Counter()
    for candidate in done.accepted.values():
        for item in candidate["geometry"]:
            if item["kind"] == "track":
                points = [Point(*p) for p in item["points"]]
                for p, q in zip(points, points[1:], strict=False):
                    accepted[(item["layer"], *sorted((at(p, True), at(q, True))), item["width"])] += 1
            else:
                accepted[("via", at(Point(*item["at"]), True), item["diameter"])] += 1
    held: Counter[tuple[object, ...]] = Counter()
    for track in altium.board.tracks:
        if track.locked:
            held[(track.layer, *sorted((at(track.start, False), at(track.end, False))), track.width)] += 1
    for via in altium.board.vias:
        if via.locked:
            held[("via", at(via.position, False), via.diameter)] += 1
    assert accepted and not accepted - held, (accepted, held)
    assert kicad.board is not None and EXAMPLES.is_dir()
