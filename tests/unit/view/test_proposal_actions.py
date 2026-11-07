# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0369 structured regeneration controls and real reviewed viewer decisions."""

import copy
import json
from dataclasses import replace

import pytest

from fenolite.cli.main import invoke
from fenolite.view.actions import ActionRefused, ActionRequest, Context, plan
from fenolite.view.project import load_tree
from fenolite.view.proposal_controls import SCHEMA, ControlError, words
from tests.unit.cli.test_route_search import subject_bench
from tests.unit.cli.test_view_actions import _Served

CID = "c-" + "1" * 16


def controls():
    return {
        "schema": SCHEMA,
        "portable": True,
        "router_options": [
            "search=only",
            "search-grid=0.5mm",
            "search-max-states=10000",
            "search-max-vias=0",
        ],
        "external_routers": [],
        "nets": ["SIGNAL"],
        "kinds": ["connection"],
        "groups": [],
        "candidate_limit": 1,
        "timeout": 60,
        "requirements": None,
        "gate": None,
    }


def test_only_structured_regeneration_arguments_are_forwarded(tmp_path):
    data = controls()
    result = words(data, tmp_path)
    assert isinstance(result, tuple)
    assert "--router-option=search-grid=0.5mm" in result
    assert "--nets=SIGNAL" in result and "--candidates=1" in result
    assert not {"--confirm", "--dry-run", "--out", "--no-backup"} & set(result)
    assert data == controls()


@pytest.mark.parametrize(
    "update",
    [
        {"schema": "future"},
        {"portable": False},
        {"command": "rm"},
        {"words": ["--confirm"]},
        {"external_routers": ["cloud"]},
        {"candidate_limit": True},
        {"candidate_limit": 9},
        {"timeout": float("inf")},
        {"timeout": -1},
        {"router_options": ["--confirm"]},
        {"router_options": ["force-reroute=on"]},
        {"router_options": ["search-grid=1mm --confirm"]},
        {"kinds": ["unknown"]},
        {"nets": "SIGNAL"},
    ],
)
def test_unknown_or_unsafe_controls_refuse_the_complete_request(tmp_path, update):
    assert isinstance(words({**controls(), **update}, tmp_path), ControlError)


def test_requirements_are_confined_including_symlink_escape(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    inside = project / "requirements.toml"
    inside.write_text("# authored requirements\n")
    data = {**controls(), "requirements": str(inside)}
    assert "--requirements=requirements.toml" in words(data, project)
    outside = tmp_path / "outside.toml"
    outside.write_text("# authored outside\n")
    assert isinstance(words({**data, "requirements": "../outside.toml"}, project), ControlError)
    link = project / "linked.toml"
    link.symlink_to(outside)
    assert isinstance(words({**data, "requirements": "linked.toml"}, project), ControlError)


def test_stale_proposals_and_client_injected_controls_never_plan(tmp_path):
    built = subject_bench(tmp_path)
    tree = load_tree(built.board)
    context = Context(candidates=frozenset({CID}), proposal_stale=True, route_controls=controls())
    request = {"action": "route-accept", "doc": "doc1", "options": {"candidates": [CID]}}
    result = plan(request, tree, context)
    assert isinstance(result, ActionRefused) and "earlier board revision" in result.reason
    bad = copy.deepcopy(request)
    bad["options"]["controls"] = {"words": ["--confirm"]}
    assert isinstance(plan(bad, tree, replace(context, proposal_stale=False)), ActionRefused)


def test_scene_controls_preserve_selection_in_the_fixed_route_template(tmp_path):
    built = subject_bench(tmp_path)
    tree = load_tree(built.board)
    context = Context(candidates=frozenset({CID}), route_controls=controls())
    result = plan({"action": "route-accept", "doc": "doc1", "options": {"candidates": [CID]}}, tree, context)
    assert isinstance(result, ActionRequest)
    assert result.words[0] == "route"
    assert result.words.count("octilinear") == 1
    assert "--nets=SIGNAL" in result.words and "--candidates=1" in result.words
    assert "--confirm" not in result.words and result.words[-2] == "--"


def test_real_viewer_preview_keeps_files_and_changed_confirmation_is_refused(tmp_path, monkeypatch):
    (tmp_path / "source").mkdir()
    built = subject_bench(tmp_path / "source")
    code, envelope, error = invoke(
        [
            "route",
            built.board.name,
            "--router",
            "octilinear",
            "--propose",
            "--nets",
            "SIG",
            "--candidates",
            "1",
            "--json",
        ],
        cwd=built.out,
    )
    assert code == 0 and envelope is not None, error
    candidate = envelope["result"]["proposals"][0]["candidates"][0]["id"]
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(envelope))
    served = _Served(monkeypatch, tmp_path, built.board, ("--proposals", str(saved)))
    before = served.board.read_bytes()
    with served:
        reviewed = served.plan("route-accept", candidates=[candidate])
        assert reviewed["state"] == "done" and reviewed["plan"]["confirmable"], reviewed
        assert served.board.read_bytes() == before
        edited = before + b"\n"
        served.board.write_bytes(edited)
        done = served.confirm(reviewed)
    assert done["exit"] == 4 and done["error"]["code"] == "FEN-4002"
    assert done["review_again"] is True and served.board.read_bytes() == edited


def test_server_refuses_preview_after_the_source_board_changes(tmp_path, monkeypatch):
    (tmp_path / "source").mkdir()
    built = subject_bench(tmp_path / "source")
    code, envelope, error = invoke(
        ["route", built.board.name, "--router", "octilinear", "--propose", "--nets", "SIG", "--json"],
        cwd=built.out,
    )
    assert code == 0 and envelope is not None, error
    candidate = envelope["result"]["proposals"][0]["candidates"][0]["id"]
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(envelope))
    served = _Served(monkeypatch, tmp_path, built.board, ("--proposals", str(saved)))
    with served:
        served.board.write_bytes(served.board.read_bytes() + b"\n")
        edited = served.board.read_bytes()
        code, result = served.post(
            "/action/plan", {"action": "route-accept", "doc": "doc1", "options": {"candidates": [candidate]}}
        )
    assert code == 400 and "earlier board revision" in result["error"]
    assert served.board.read_bytes() == edited


def test_real_viewer_acceptance_confirms_the_reviewed_board_and_record(tmp_path, monkeypatch):
    (tmp_path / "source").mkdir()
    built = subject_bench(tmp_path / "source")
    code, envelope, error = invoke(
        [
            "route",
            built.board.name,
            "--router",
            "octilinear",
            "--propose",
            "--nets",
            "SIG",
            "--candidates",
            "1",
            "--json",
        ],
        cwd=built.out,
    )
    assert code == 0 and envelope is not None, error
    candidate = envelope["result"]["proposals"][0]["candidates"][0]["id"]
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(envelope))
    served = _Served(monkeypatch, tmp_path, built.board, ("--proposals", str(saved)))
    before = served.board.read_bytes()
    with served:
        reviewed = served.plan("route-accept", candidates=[candidate])
        assert reviewed["state"] == "done" and reviewed["plan"]["confirmable"], reviewed
        assert served.board.read_bytes() == before
        done = served.confirm(reviewed)
    assert done["exit"] == 0 and done["receipt"]["written"], done
    assert served.board.read_bytes() != before
    assert any(row["path"].endswith("route-decisions.json") for row in done["receipt"]["written"])


def test_rejection_stales_old_choices_even_without_board_changes_and_fresh_run_replaces_context(
    tmp_path, monkeypatch
):
    from tests.unit.view.test_server import _call

    (tmp_path / "source").mkdir()
    built = subject_bench(tmp_path / "source")
    code, envelope, error = invoke(
        [
            "route",
            built.board.name,
            "--router",
            "octilinear",
            "--propose",
            "--nets",
            "SIG",
            "--candidates",
            "1",
            "--json",
        ],
        cwd=built.out,
    )
    assert code == 0 and envelope is not None, error
    candidate = envelope["result"]["proposals"][0]["candidates"][0]["id"]
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(envelope))
    served = _Served(monkeypatch, tmp_path, built.board, ("--proposals", str(saved)))
    before = served.board.read_bytes()
    with served:
        reviewed = served.plan("route-reject", candidates=[candidate], reason="authored review")
        done = served.confirm(reviewed)
        assert done["exit"] == 0 and served.board.read_bytes() == before
        code, refused = served.post(
            "/action/plan", {"action": "route-accept", "doc": "doc1", "options": {"candidates": [candidate]}}
        )
        assert code == 400 and "stale" in refused["error"]
        assert served.get("/scene/doc1.json")["proposals"]["stale"] is True
        code, started = _call(
            served.port,
            "/run",
            {"command": "proposals", "doc": "doc1", "options": {}},
            {"Content-Type": "application/json", "X-Fenolite-Run": "1"},
        )
        assert code == 202, started
        ran = served.job(started["job"])
        assert ran["state"] == "done", ran
        assert not served.get("/scene/doc1.json")["proposals"].get("stale", False)
    assert served.board.read_bytes() == before
