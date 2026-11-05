# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Truthful completion facts of ``fenolite route --propose`` (change c0370, task 3).

A proposal, a rejection, a timeout or an unknown check is never a connection: ``result.completion`` keeps
the physical open count, sorts every subject into one state and never reports the board complete.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROLES_TESTS = Path(__file__).resolve().parents[1] / "roles"
if str(ROLES_TESTS) not in sys.path:
    sys.path.insert(0, str(ROLES_TESTS))

from _critical import cli  # noqa: E402
from _proposals import subject_bench, wall_bench  # noqa: E402
from _roleboards import Built  # noqa: E402

from fenolite.cli._propose import _budget_cut  # pyright: ignore[reportPrivateUsage]  # noqa: E402
from fenolite.routing.completion import STATES, STOPPED, SubjectFacts, completion, state_of  # noqa: E402

ROUTE = ("--router", "octilinear")
SIG = "connection:SIG:R1-1~R2-1"


def route(board: Path, *more: str) -> tuple[int, dict[str, Any], str]:
    return cli("route", str(board), *ROUTE, *more)


def propose(board: Path, *more: str) -> dict[str, Any]:
    code, env, err = route(board, "--propose", *more)
    assert code == 0, err
    return env["result"]


def planned(board: Path, *more: str) -> None:
    code, env, err = route(board, *more, "--dry-run")
    assert code == 0, (err, env.get("issues"))
    code, _done, err = route(board, *more, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, err


# --- the pure classification --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("facts", "state"),
    [
        (SubjectFacts("a", selected=False, rejected=True, live=2, measured=2), "not-attempted"),
        (SubjectFacts("a", rejected=True, live=0), "rejected"),
        (SubjectFacts("a", live=0), "no-candidate"),
        (SubjectFacts("a", live=0, stopped=True), "unknown"),
        (SubjectFacts("a", rejected=True, stopped=True), "rejected"),
        (SubjectFacts("a", live=3, measured=0), "unknown"),
        (SubjectFacts("a", live=3, measured=1), "proposed"),
    ],
)
def test_each_subject_has_exactly_one_state_by_precedence(facts: SubjectFacts, state: str) -> None:
    assert state_of(facts) == state


def test_the_board_is_never_complete_and_opens_stay_visible() -> None:
    rows = [SubjectFacts("z", rejected=True), SubjectFacts("b", rejected=True), SubjectFacts("m", live=0)]
    done = completion(open_before=3, fill="simulated", subjects=rows)
    assert done == {
        "state": "open",
        "open": 3,
        "fill": "simulated",
        "subjects": {
            "proposed": [],
            "unknown": [],
            "no-candidate": ["m"],
            "rejected": ["b", "z"],
            "not-attempted": [],
        },
        "checks": "not-run",
        "complete": False,
    }
    assert list(done["subjects"]) == list(STATES)
    clear = completion(open_before=0, fill="saved", subjects=())
    assert clear["state"] == "unchecked" and clear["complete"] is False and clear["checks"] == "not-run"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"open_before": -1, "fill": "saved", "subjects": ()},
        {"open_before": 0, "fill": "guessed", "subjects": ()},
        {"open_before": 1, "fill": "saved", "subjects": (SubjectFacts("a"), SubjectFacts("a"))},
        {"open_before": 1, "fill": "saved", "subjects": (SubjectFacts("a", live=1, measured=2),)},
    ],
)
def test_inconsistent_inputs_are_refused(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        completion(**kwargs)


def test_stopping_reasons_are_known_proposal_reasons() -> None:
    from fenolite.cli._propose import REASONS

    assert STOPPED <= set(REASONS) and "no-room" not in STOPPED


def test_budget_cut_is_an_unmeasured_candidate() -> None:
    assert _budget_cut({"not_evaluated": [{"fact": "closes", "why": "budget"}]})
    assert not _budget_cut({"not_evaluated": [{"fact": "drc", "why": "no-gate"}]})
    assert not _budget_cut({})


# --- the reply of a proposal run ----------------------------------------------------------------------------


@pytest.fixture
def bench(tmp_path: Path) -> Built:
    return subject_bench(tmp_path)


def test_selected_subject_is_proposed_and_the_rest_not_attempted(bench: Built) -> None:
    result = propose(bench.board, "--nets", "SIG")
    done = result["completion"]
    assert done["open"] == result["open"]["before"] > 1
    assert done["state"] == "open" and done["complete"] is False
    assert done["subjects"]["proposed"] == [SIG]
    others = done["subjects"]["not-attempted"]
    assert others and SIG not in others
    total = sum(len(keys) for keys in done["subjects"].values())
    assert total == len({key for keys in done["subjects"].values() for key in keys})


def test_all_rejected_with_opens_left_is_reported_incomplete(bench: Built) -> None:
    """Scenario "Truthful completion contract": every candidate rejected, the physical opens remain."""
    first = propose(bench.board, "--nets", "SIG")
    (row,) = first["proposals"]
    for candidate in row["candidates"]:
        planned(bench.board, "--reject", candidate["id"], "--reason", "authored refusal")
    again = propose(bench.board, "--nets", "SIG")
    done = again["completion"]
    assert done["subjects"]["rejected"] == [SIG] and not done["subjects"]["proposed"]
    assert done["open"] == first["completion"]["open"] and done["state"] == "open"
    assert done["complete"] is False
    # Rejecting the proposal itself gives the same truthful state.
    planned(bench.board, "--reject", row["id"])
    assert propose(bench.board, "--nets", "SIG")["completion"]["subjects"]["rejected"] == [SIG]


def test_subject_without_room_is_no_candidate(tmp_path: Path) -> None:
    built = wall_bench(tmp_path)
    done = propose(built.board, "--nets", "WALLED")["completion"]
    assert [key for key in done["subjects"]["no-candidate"] if ":WALLED:" in key]
    assert done["state"] == "open" and done["complete"] is False


def test_completion_facts_have_tested_agent_instructions() -> None:
    from fenolite.agent import guide

    text = guide.page("board-completion").text
    for word in ("result.completion", "`open`", "`unchecked`", "`fill`", *(f"`{state}`" for state in STATES)):
        assert word in text, word
    assert "`checks` is `not-run`" in text and "`complete` is\nalways `false`" in text
