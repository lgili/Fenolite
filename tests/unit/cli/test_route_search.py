# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0365 option preflight and read-only/reviewed CLI search on authored boards."""

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

from fenolite.cli.main import main

ROLES_TESTS = Path(__file__).resolve().parents[1] / "roles"
if str(ROLES_TESTS) not in sys.path:
    sys.path.insert(0, str(ROLES_TESTS))
from _critical import bench  # noqa: E402
from _proposals import SUBJECTS, subject_bench  # noqa: E402

SEARCH = (
    "--router-option",
    "search=only",
    "--router-option",
    "search-grid=0.5mm",
    "--router-option",
    "search-max-states=50000",
    "--router-option",
    "search-max-vias=1",
)


def cli(*words: str):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main([*words, "--json"])
    return code, json.loads(out.getvalue() or "{}"), err.getvalue()


@pytest.mark.parametrize(
    "args",
    [
        ("--router", "octilinear"),
        ("--router", "freerouting", "--propose"),
        ("--router", "octilinear", "--roles", "critical"),
    ],
)
def test_wrong_mode_or_router_is_usage_error_before_reading_board(tmp_path: Path, args) -> None:
    code, _, err = cli("route", str(tmp_path / "missing.kicad_pcb"), *args, *SEARCH)
    assert code == 2 and "FEN-2001" in err


@pytest.mark.parametrize("option", ["search=other", "search=only", "search-grid=0mm"])
def test_bad_or_incomplete_bounds_are_usage_errors(tmp_path: Path, option: str) -> None:
    code, _, err = cli(
        "route",
        str(tmp_path / "missing.kicad_pcb"),
        "--router",
        "octilinear",
        "--propose",
        "--router-option",
        option,
    )
    assert code == 2 and "FEN-2001" in err


def test_search_proposals_and_reviewed_acceptance_preserve_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    built = subject_bench(tmp_path)
    before = built.board.read_bytes()
    words = ("route", str(built.board), "--router", "octilinear", "--nets", "SIG")
    code, reply, err = cli(*words, "--propose", *SEARCH)
    assert code == 0, err
    assert built.board.read_bytes() == before
    rows = reply["result"]["proposals"]
    assert len(rows) == 1 and rows[0]["candidates"]
    candidate = rows[0]["candidates"][0]
    assert candidate["source"] == "search"
    assert not {"score", "cost", "rank", "recommended"} & candidate["facts"].keys()
    code, planned, err = cli(*words[:4], "--accept", candidate["id"], *SEARCH, "--dry-run")
    assert code == 0, err
    assert built.board.read_bytes() == before
    plan = planned["result"]["plan_id"]

    def must_not_search(*args, **kwargs):
        raise AssertionError("confirmation must use reviewed bytes")

    monkeypatch.setattr("fenolite.routing.propose.maze_search", must_not_search)
    code, _, err = cli(*words[:4], "--accept", candidate["id"], *SEARCH, "--confirm", "--plan", plan)
    assert code == 0, err
    assert built.board.read_bytes() != before


def test_search_confirmation_refuses_a_changed_board(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    built = subject_bench(tmp_path)
    words = ("route", str(built.board), "--router", "octilinear")
    code, reply, err = cli(*words, "--propose", "--nets", "SIG", *SEARCH)
    assert code == 0, err
    ident = reply["result"]["proposals"][0]["candidates"][0]["id"]
    code, planned, err = cli(*words, "--accept", ident, *SEARCH, "--dry-run")
    assert code == 0, err
    edited = built.board.read_bytes() + b"\n"
    built.board.write_bytes(edited)
    code, _, err = cli(
        *words, "--accept", ident, *SEARCH, "--confirm", "--plan", planned["result"]["plan_id"]
    )
    assert code == 4 and "FEN-4002" in err
    assert built.board.read_bytes() == edited


@pytest.mark.parametrize("mode", ["fallback", "only"])
def test_named_pair_half_selection_has_no_independent_candidate(
    tmp_path: Path, monkeypatch, mode: str
) -> None:
    monkeypatch.chdir(tmp_path)
    body = SUBJECTS.format(name="named_pair", extra="").replace('Net("SIG")', 'Net("DP")')
    body = body.replace('Net("VS")', 'Net("DN")').replace('design.net_role(vs, "power")', "")
    built = bench(tmp_path, "named_pair", body)
    before = built.board.read_bytes()
    options = tuple(f"search={mode}" if word == "search=only" else word for word in SEARCH)
    code, reply, err = cli(
        "route", str(built.board), "--router", "octilinear", "--propose", "--nets", "DP", *options
    )
    assert code == 0, err
    row = reply["result"]["proposals"][0]
    assert row["net"] == "DP" and not row["candidates"]
    assert row["reason"] == "search-unsupported"
    assert built.board.read_bytes() == before
