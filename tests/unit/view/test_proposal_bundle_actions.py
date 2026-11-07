# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0369 complete bundle eligibility and real served atomic acceptance on authored boards."""

import copy
import json

import pytest
from _negotiate_project import NEGOTIATE, project
from _search_project import cli

from fenolite.view.proposals import bundle_units, ids_of
from tests.unit.cli.test_view_actions import _Served

BID = "b-" + "a" * 16
A, B = "c-" + "1" * 16, "c-" + "2" * 16
P, Q = "p-" + "3" * 16, "p-" + "4" * 16


def data():
    return {
        "schema": "fenolite.view_proposals.v0",
        "controls": {
            "schema": "fenolite.proposal_controls.v0",
            "portable": True,
            "router_options": ["negotiate=on"],
        },
        "proposals": [
            {"id": pid, "subject": subject, "candidates": [{"id": member, "source": "search", "bundle": BID}]}
            for pid, subject, member in ((P, "sA", A), (Q, "sB", B))
        ],
        "bundles": [{"id": BID, "fingerprint": "f" * 64, "members": [A, B], "subjects": ["sA", "sB"]}],
    }


def test_only_the_complete_unit_can_be_written_not_members_or_parent_proposals():
    scene = data()
    before = copy.deepcopy(scene)
    assert bundle_units(scene) == {BID: (A, B)}
    assert ids_of(scene) == (frozenset({BID}), frozenset())
    assert scene == before


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "fingerprint", "owner", "overlap", "subjects", "unknown", "controls"]
)
def test_invalid_bundle_is_inspectable_but_never_downgraded_to_member_decisions(fault):
    scene = data()
    if fault == "missing":
        scene["bundles"][0]["members"] = [A]
    elif fault == "duplicate":
        scene["bundles"][0]["members"] = [A, A]
    elif fault == "fingerprint":
        scene["bundles"][0]["fingerprint"] = "unknown"
    elif fault == "owner":
        scene["proposals"][1]["candidates"][0]["bundle"] = "b-" + "b" * 16
    elif fault == "overlap":
        scene["bundles"].append({**scene["bundles"][0], "id": "b-" + "b" * 16})
    elif fault == "subjects":
        scene["bundles"][0]["subjects"] = ["sA", "sA"]
    elif fault == "unknown":
        scene["proposals"][0]["candidates"][0]["source"] = "unknown"
    else:
        scene.pop("controls")
    assert bundle_units(scene) == {}
    assert ids_of(scene) == (frozenset(), frozenset())
    assert scene["proposals"], "inspection data is retained"


def test_legacy_independent_candidates_remain_independent():
    scene = data()
    scene.pop("bundles")
    for row in scene["proposals"]:
        row["candidates"][0].pop("bundle")
    assert ids_of(scene) == (frozenset({A, B}), frozenset({P, Q}))


def test_real_served_bundle_acceptance_refuses_members_then_writes_every_member(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.chdir(source)
    built = project(source)
    code, reply, error = cli(
        "route",
        str(built.board),
        "--router",
        "octilinear",
        "--propose",
        "--nets",
        "SIG",
        "--nets",
        "SECOND",
        *NEGOTIATE,
    )
    assert code == 0 and reply["result"]["bundles"], (error, reply)
    bundle = reply["result"]["bundles"][0]
    saved = tmp_path / "proposals.json"
    saved.write_text(json.dumps(reply))
    served = _Served(monkeypatch, tmp_path, built.board, ("--proposals", str(saved)))
    before = served.board.read_bytes()
    with served:
        for ident in (bundle["members"][0], reply["result"]["proposals"][0]["id"]):
            code, refused = served.post(
                "/action/plan", {"action": "route-accept", "doc": "doc1", "options": {"candidates": [ident]}}
            )
            assert code == 400, refused
        reviewed = served.plan("route-accept", candidates=[bundle["id"]])
        assert reviewed["plan"]["confirmable"] and served.board.read_bytes() == before, reviewed
        done = served.confirm(reviewed)
    assert done["exit"] == 0, done
    record = json.loads((served.folder / ".fenolite" / "route-decisions.json").read_text())
    assert record["bundles"][0]["id"] == bundle["id"]
    assert set(record["bundles"][0]["members"]) == set(bundle["members"])
    assert {row["candidate"] for row in record["locked"]} >= set(bundle["members"])
    assert served.board.read_bytes() != before
