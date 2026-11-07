# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reviewed completion stages on an authored board, judged by the running ``kicad-cli`` (change c0370,
task 4; capability routing, scenario "Locked edits survive later passes").

Each writing stage is its own reviewed transaction (``--dry-run``, then ``--confirm --plan ID``): accept a
proposal, a tidy scoped to approved nets, a second routing pass. Manual copper (drawn in KiCad, without the
copper marker) and locked copper keep their items through every stage, a tidy scoped to ``SIG`` leaves the
manual bend that an unscoped chamfer would cut, and KiCad's DRC finds no new violation type and one open
connection fewer per accepted route. A stage stopped by a signal while it writes changes no file and its
reviewed plan writes on the next run; a search stopped by its bound writes nothing and reports ``unknown``.
"""

from __future__ import annotations

import os
import signal
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _completion_project import HAND_UUIDS, by_hand, project
from _probes import major, runner
from _search_project import cli

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.routing.decisions import loads

pytestmark = pytest.mark.needs_kicad
ROUTE = ("--router", "octilinear", "--router-option", "max-length=60mm")
SIG = "connection:SIG:R1-1~R2-1"
SECOND = "connection:SECOND:R3-1~R4-1"
PROTECTED = ("MANUAL", "BLOCK")


def protected(board: Path) -> dict[str, tuple[Any, ...]]:
    """The tracks of the manual and locked nets by KiCad uuid: ends, width, layer and lock."""
    design = read_board(board.read_text(encoding="utf-8"), file=board.name)
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    return {
        t.native_ids["kicad"]: (t.start, t.end, t.width, t.layer, t.locked)
        for t in design.board.tracks
        if names.get(t.net_id or "") in PROTECTED
    }


def drc(board: Path) -> tuple[Counter[str], int]:
    result = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert result.report is not None
    violations = Counter(v.type for v in result.report.violations if not v.excluded)
    return violations, sum(not v.excluded for v in result.report.unconnected_items)


def snapshot(folder: Path) -> dict[str, bytes]:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def plan(*words: str) -> str:
    code, env, err = cli(*words, "--dry-run")
    assert code == 0, (err, env.get("issues"))
    return env["result"]["plan_id"]


def confirm(*words: str, plan_id: str) -> dict[str, Any]:
    code, env, err = cli(*words, "--confirm", "--plan", plan_id)
    assert code == 0, err
    assert env["receipt"]["written"], env["receipt"]
    return env["result"]


def propose(board: Path, *more: str) -> dict[str, Any]:
    before = board.read_bytes()
    code, env, err = cli("route", str(board), *ROUTE, "--propose", *more)
    assert code == 0, err
    assert board.read_bytes() == before, "a proposal run writes nothing"
    return env["result"]


def first_clean(result: dict[str, Any], subject: str) -> str:
    (row,) = [p for p in result["proposals"] if p["subject"] == subject]
    chosen = next(
        c
        for c in row["candidates"]
        if c["facts"]["open"]["after"] < c["facts"]["open"]["before"]
        and not c["facts"]["copper_check"]["new"]
    )
    return chosen["id"]


def accept(board: Path, candidate: str) -> dict[str, Any]:
    words = ("route", str(board), *ROUTE, "--accept", candidate)
    return confirm(*words, plan_id=plan(*words))


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(runner().path))
    layers = getattr(request, "param", 2)
    made = project(tmp_path, layers=layers, major=major())
    by_hand(made.board)
    return made


@pytest.mark.parametrize("built", [2, 4], indirect=True, ids=["2-layer", "4-layer"])
def test_reviewed_stages_keep_manual_and_locked_copper(built) -> None:
    board = built.board
    kept = protected(board)
    assert set(HAND_UUIDS) <= set(kept) and len(kept) == 3
    violations, opens = drc(board)
    assert opens == 2, violations

    # An unscoped chamfer would cut the manual bend: scoping the tidy is what protects it.
    before = board.read_bytes()
    code, env, err = cli("tidy", str(board), "--chamfer", "--dry-run")
    assert code == 0, err
    assert env["result"]["changed"] and board.read_bytes() == before

    # Stage 1: proposals, then one reviewed acceptance.
    first = propose(board)
    assert first["completion"]["subjects"]["proposed"] == [SECOND, SIG]
    assert first["completion"]["open"] == 2 and first["completion"]["complete"] is False
    done = accept(board, first_clean(first, SIG))
    record = loads(Path(done["record"]).read_bytes())  # relative to the working folder
    assert [entry.subject for entry in record.locked] == [SIG]
    assert protected(board) == kept
    after_sig, open_sig = drc(board)
    assert open_sig == opens - 1
    assert all(after_sig[k] <= violations[k] for k in after_sig), (violations, after_sig)

    # Stage 2: a tidy scoped to the approved net; manual and locked copper keep every item.
    words = ("tidy", str(board), "--nets", "SIG", "--prune", "--straighten", "--chamfer")
    code, env, err = cli(*words, "--dry-run")
    assert code == 0, err
    if env["result"].get("plan_id"):
        confirm(*words, plan_id=env["result"]["plan_id"])
    assert protected(board) == kept

    # Stage 3: a second routing pass sees SIG closed and its accepted copper present.
    second = propose(board)
    assert second["completion"]["open"] == 1
    assert second["completion"]["subjects"]["proposed"] == [SECOND]
    assert [row["present"] for row in second["locked"]] == [True]
    accept(board, first_clean(second, SECOND))
    assert protected(board) == kept

    final, remaining = drc(board)
    assert remaining == 0, final
    assert all(final[k] <= violations[k] for k in final), (violations, final)
    closed = propose(board)["completion"]
    assert closed["state"] == "unchecked" and closed["open"] == 0 and closed["complete"] is False
    assert not any(closed["subjects"].values()) and closed["checks"] == "not-run"


def _interrupt_the_write(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Make the first replacement of a written file raise the signal of a stopped command."""
    real = os.replace
    hit: list[str] = []

    def replace(src: Any, dst: Any, **kwargs: Any) -> None:
        if Path(src).suffix == ".tmp" and not hit:
            hit.append(Path(dst).name)
            raise cli_main.Interrupted(signal.SIGINT)
        real(src, dst, **kwargs)

    monkeypatch.setattr(os, "replace", replace)
    return hit


@pytest.mark.parametrize("stage", ["accept", "tidy"])
def test_a_stage_stopped_while_it_writes_changes_nothing_and_its_plan_recovers(
    built, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    board = built.board
    kept = protected(board)
    if stage == "accept":
        words: tuple[str, ...] = ("route", str(board), *ROUTE, "--accept", first_clean(propose(board), SIG))
    else:  # the approved net is MANUAL: only its bend is chamfered, the locked bar stays
        words = ("tidy", str(board), "--nets", "MANUAL", "--chamfer")
    reviewed = plan(*words)
    folder = built.out.parent
    before = snapshot(folder)
    with monkeypatch.context() as patched:
        hit = _interrupt_the_write(patched)
        code, env, err = cli(*words, "--confirm", "--plan", reviewed)
    assert hit, "the write was reached"
    assert code == 1 and '"FEN-1003"' in err and env["receipt"] is None
    assert snapshot(folder) == before, "every file holds its previous bytes"

    confirm(*words, plan_id=reviewed)
    _violations, opens = drc(board)
    now = protected(board)
    if stage == "accept":
        assert now == kept and opens == 1
        assert propose(board)["completion"]["subjects"]["proposed"] == [SECOND]
    else:
        locked = {k: v for k, v in kept.items() if v[4]}
        assert {k: v for k, v in now.items() if v[4]} == locked
        assert now != kept, "the reviewed chamfer of the approved net was written"
        assert opens == 2


def test_a_search_stopped_by_its_bound_writes_nothing_and_is_unknown(built) -> None:
    folder = built.out.parent
    before = snapshot(folder)
    bound = (
        "--router-option",
        "search=only",
        "--router-option",
        "search-grid=0.5mm",
        "--router-option",
        "search-max-states=1",
        "--router-option",
        "search-max-vias=0",
    )
    done = propose(built.board, *bound)
    assert {p["reason"] for p in done["proposals"]} == {"state-limit"}
    assert done["completion"]["subjects"]["unknown"] == [SECOND, SIG]
    assert not done["completion"]["subjects"]["no-candidate"] and done["completion"]["state"] == "open"
    assert snapshot(folder) == before
