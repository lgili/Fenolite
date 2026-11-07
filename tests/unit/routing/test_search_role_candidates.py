# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0366 final judges, measured facts and reviewed-input invalidation."""

from dataclasses import replace
from pathlib import Path

import pytest
from _rolefieldbench import field_bench
from _search_project import SEARCH, cli, project

from fenolite.cli import _propose
from fenolite.cli._search_fields import compile_fields
from fenolite.model.rules import NetRole, RoleSet
from fenolite.roles.store import document_path, dumps_document
from fenolite.routing.octilinear import OctilinearRouter

OPTIONS = {
    "search": "only",
    "search-grid": "0.5mm",
    "search-max-states": "40000",
    "search-max-vias": "0",
    "max-length": "30mm",
}


def prepared():
    job, _, roles = field_bench()
    fields = compile_fields(job.design, (), roles).fields
    return replace(
        job,
        options=OPTIONS,
        extra={
            **job.extra,
            "search_fields": fields,
            "copper_check": lambda design: [],
            "role_check": lambda design: [],
        },
    )


def test_fallback_filters_patterns_before_search_and_never_merges() -> None:
    job = prepared()
    result = OctilinearRouter().route(replace(job, options={**OPTIONS, "search": "fallback"}))
    assert result.candidates and not result.refusals
    assert not (result.tracks or result.vias)
    assert all(t.net_id == "net_sig" for c in result.candidates for t in c.tracks)
    # Every retained family is subjected to the same hard field, including pattern shapes.
    from fenolite.routing.search_fields import Evaluator

    evaluation = Evaluator(job.extra["search_fields"])
    assert all(
        evaluation.allows("SIG", t.layer, (t.start, t.end), t.width)
        for c in result.candidates
        for t in c.tracks
    )


@pytest.mark.parametrize("judge", ["copper_check", "role_check"])
def test_missing_final_judge_fails_closed(judge: str) -> None:
    job = prepared()
    extra = dict(job.extra)
    del extra[judge]
    result = OctilinearRouter().route(replace(job, extra=extra))
    assert not result.candidates and result.refusals[0][1] == "search-role-refused"


def test_new_copper_finding_refuses_candidate_without_mutation() -> None:
    job = prepared()
    original = job.design

    def judge(design):
        return [] if design == original else [("clearance", "F.Cu", ("new",), 1)]

    result = OctilinearRouter().route(replace(job, extra={**job.extra, "copper_check": judge}))
    assert not result.candidates and result.refusals[0][1] == "search-role-refused"
    assert job.design == original and len(original.board.tracks) == 1


@pytest.mark.parametrize("confirmed", [False, True])
def test_only_confirmed_group_findings_are_binding(confirmed: bool) -> None:
    job = prepared()
    fields = replace(job.extra["search_fields"], confirmed_groups=("gate",) if confirmed else ())

    def judge(design):
        return [("roles.gate-length", "gate", "warning", 1 if design == job.design else 2)]

    result = OctilinearRouter().route(
        replace(
            job,
            extra={
                **job.extra,
                "search_fields": fields,
                "role_check": judge,
            },
        )
    )
    assert bool(result.candidates) is not confirmed
    if confirmed:
        assert result.refusals[0][1] == "search-role-refused"


def test_missing_limits_and_changed_board_are_explicit_refusals() -> None:
    job = prepared()
    fields = job.extra["search_fields"]
    missing = replace(fields, missing=(("SIG", "roles.limit-missing:SIG~BUS"),))
    result = OctilinearRouter().route(replace(job, extra={**job.extra, "search_fields": missing}))
    assert result.refusals[0][1] == "search-role-limit" and not result.candidates
    changed = replace(job, design=replace(job.design, board=replace(job.design.board, tracks=())))
    assert OctilinearRouter().route(changed).refusals[0][1] == "search-role-stale"


def role_project(tmp_path: Path):
    built = project(tmp_path, 2)
    document_path(built.board).write_bytes(
        dumps_document(
            RoleSet(
                nets=(
                    NetRole("SIG", "signal", "declared", sensitive=True),
                    NetRole("FENCE", "switch_node", "declared"),
                )
            )
        )
    )
    requirements = tmp_path / "requirements.toml"
    requirements.write_text(
        'schema = "fenolite.requirements.v0"\n[[distance]]\n'
        'a = { net = "SIG" }\nb = { net = "FENCE" }\nclearance_nm = 1000000\n'
    )
    return built, requirements


def test_public_facts_have_provenance_unknowns_and_no_score(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    built, requirements = role_project(tmp_path)
    before = built.board.read_bytes()
    code, reply, err = cli(
        "route",
        str(built.board),
        "--router",
        "octilinear",
        "--propose",
        "--nets",
        "SIG",
        "--requirements",
        str(requirements),
        *SEARCH,
    )
    assert code == 0, err
    context = reply["result"]["role_fields"]
    assert context["limits"] and context["provenance"]["profile"]
    assert "H-G-SEARCH-ROLE-FIELDS" in reply["evidence"]["hypotheses"]
    candidate = reply["result"]["proposals"][0]["candidates"][0]
    facts = candidate["facts"]["role_fields"]
    assert facts["input_fingerprint"] == context["fingerprint"]
    assert facts["confirmed_reference_length_lower_bound_nm"] == 0
    assert facts["unconfirmed_reference_length_nm"] == candidate["facts"]["length"]
    assert facts["switching_exposure_upper_bound_nm"] == 0
    assert "score" not in facts and built.board.read_bytes() == before


@pytest.mark.parametrize("dependency", ["requirements", "roles", "project", "rules", "profile", "model"])
def test_reviewed_acceptance_refuses_changed_field_inputs(
    tmp_path: Path, monkeypatch, dependency: str
) -> None:
    monkeypatch.chdir(tmp_path)
    built, requirements = role_project(tmp_path)
    # Exercise the real plan dependency tracker while keeping the source tree immutable.
    profile_copy = tmp_path / "profile.py"
    profile_copy.write_bytes(Path(_propose.profile.__file__).read_bytes())
    monkeypatch.setattr(_propose.profile, "__file__", str(profile_copy))
    words = ("route", str(built.board), "--router", "octilinear", "--requirements", str(requirements))
    code, reply, err = cli(*words, "--propose", "--nets", "SIG", *SEARCH)
    assert code == 0, err
    ident = reply["result"]["proposals"][0]["candidates"][0]["id"]
    code, planned, err = cli(*words, "--accept", ident, *SEARCH, "--dry-run")
    assert code == 0, err
    target = {
        "requirements": requirements,
        "roles": document_path(built.board),
        "project": built.board.with_suffix(".kicad_pro"),
        "rules": built.board.with_suffix(".kicad_dru"),
        "profile": profile_copy,
        "model": built.board.parent / ".fenolite" / "rules.json",
    }[dependency]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((target.read_bytes() if target.exists() else b"") + b"\n")
    before = built.board.read_bytes()
    code, _, err = cli(
        *words, "--accept", ident, *SEARCH, "--confirm", "--plan", planned["result"]["plan_id"]
    )
    assert code == 4 and "FEN-4002" in err
    assert built.board.read_bytes() == before


@pytest.mark.parametrize("args", [(), ("--propose",)])
def test_requirements_without_opt_in_search_are_usage_errors(tmp_path: Path, args) -> None:
    code, _, err = cli(
        "route",
        str(tmp_path / "missing.kicad_pcb"),
        "--router",
        "octilinear",
        "--requirements",
        "missing.toml",
        *args,
    )
    assert code == 2 and "FEN-2001" in err


def test_joint_acceptance_rechecks_new_switching_copper() -> None:
    from types import SimpleNamespace

    from _searchbench import MM, point

    from fenolite.model.board import Track
    from fenolite.routing.merge import apply
    from fenolite.routing.protocol import Candidate, RoutingResult

    job = prepared()
    _, _, roles = field_bench()
    sig = Track(
        id="trk_signal", start=point(2, 2), end=point(10, 2), width=100_000, layer="F.Cu", net_id="net_sig"
    )
    sw = replace(sig, id="trk_new_switch", start=point(6, 3), end=point(8, 3), net_id="net_wall")
    a = Candidate("signal", "sig", "search", (), (sig,), (), (), 8 * MM, ("F.Cu",))
    b = replace(a, id="switch", subject="sw", tracks=(sw,), length=2 * MM)
    board = SimpleNamespace(
        design=job.design,
        search_active=True,
        pads=(),
        requirements=None,
        layers=job.layers,
        checks={"copper_check": lambda design: []},
        judge=SimpleNamespace(
            judged=lambda design: SimpleNamespace(resolved=SimpleNamespace(roles=roles)),
            findings=lambda design: [],
        ),
    )
    alone = apply(job.design, RoutingResult(tracks=(sig,)))
    assert _propose._field_acceptance(board, alone, (a,)) == ""
    joint = apply(job.design, RoutingResult(tracks=(sig, sw)))
    assert _propose._field_acceptance(board, joint, (a, b)) == "search-role-refused"
