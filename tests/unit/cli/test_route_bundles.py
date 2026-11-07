# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored CLI atomic decisions, lifecycle and transactional guard proofs (c0367)."""

from pathlib import Path

import pytest
from _negotiate_project import NEGOTIATE, project
from _search_project import cli

from fenolite.routing.decisions import loads


def proposed(tmp_path, monkeypatch, *, requirements=False, high=False):
    monkeypatch.chdir(tmp_path)
    built = project(tmp_path, high=high)
    words = ("route", str(built.board), "--router", "octilinear")
    if requirements:
        path = tmp_path / "limits.toml"
        text = 'schema = "fenolite.requirements.v0"\n'
        if high:
            text += '[[distance]]\na = { net = "*" }\nb = { net = "*" }\nclearance_nm = 200000\n'
        path.write_text(text)
        words += ("--requirements", str(path))
    code, reply, err = cli(*words, "--propose", "--nets", "SIG", "--nets", "SECOND", *NEGOTIATE)
    assert code == 0, err
    assert reply["result"]["bundles"], reply["result"]
    return built, words, reply["result"]["bundles"][0]


def test_decisions_accept_bundle_locks_all_members_and_refuses_a_member(tmp_path: Path, monkeypatch) -> None:
    built, words, bundle = proposed(tmp_path, monkeypatch)
    before = built.board.read_bytes()
    code, _, err = cli(*words, "--accept", bundle["members"][0], *NEGOTIATE, "--dry-run")
    assert code == 2 and "FEN-2001" in err and bundle["id"] in err
    assert built.board.read_bytes() == before
    code, plan, err = cli(*words, "--accept", bundle["id"], *NEGOTIATE, "--dry-run")
    assert code == 0, err
    assert built.board.read_bytes() == before
    code, reply, err = cli(
        *words, "--accept", bundle["id"], *NEGOTIATE, "--confirm", "--plan", plan["result"]["plan_id"]
    )
    assert code == 0, err
    record = loads((tmp_path / reply["result"]["record"]).read_bytes())
    assert set(record.bundles[0].members) == set(bundle["members"])
    assert {e.candidate for e in record.locked} == set(bundle["members"])
    assert built.board.read_bytes() != before


def test_decisions_reject_bundle_only_records_the_unit_and_can_show_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    built, words, bundle = proposed(tmp_path, monkeypatch)
    before = built.board.read_bytes()
    code, _, err = cli(*words, "--reject", bundle["members"][0], *NEGOTIATE, "--dry-run")
    assert code == 2 and bundle["id"] in err
    code, plan, err = cli(
        *words, "--reject", bundle["id"], "--reason", "authored review", *NEGOTIATE, "--dry-run"
    )
    assert code == 0, err
    code, reply, err = cli(
        *words,
        "--reject",
        bundle["id"],
        "--reason",
        "authored review",
        *NEGOTIATE,
        "--confirm",
        "--plan",
        plan["result"]["plan_id"],
    )
    assert code == 0, err
    record = loads((tmp_path / reply["result"]["record"]).read_bytes())
    assert not record.locked and record.rejected[0].id == bundle["id"] and len(record.bundles) == 1
    assert built.board.read_bytes() == before
    code, reply, err = cli(*words, "--propose", "--nets", "SIG", "--nets", "SECOND", *NEGOTIATE)
    assert code == 0, err
    assert not reply["result"]["bundles"] and not any(p["candidates"] for p in reply["result"]["proposals"])
    code, reply, err = cli(
        *words, "--propose", "--nets", "SIG", "--nets", "SECOND", "--show-rejected", *NEGOTIATE
    )
    assert code == 0, err
    assert reply["result"]["bundles"][0]["id"] == bundle["id"]


def accepted(tmp_path, monkeypatch, **options):
    built, words, bundle = proposed(tmp_path, monkeypatch, **options)
    code, plan, err = cli(*words, "--accept", bundle["id"], *NEGOTIATE, "--dry-run")
    assert code == 0, err
    code, reply, err = cli(
        *words, "--accept", bundle["id"], *NEGOTIATE, "--confirm", "--plan", plan["result"]["plan_id"]
    )
    assert code == 0, err
    return built, words, bundle, tmp_path / reply["result"]["record"]


def erase_tracks(built):
    from dataclasses import replace

    from fenolite.backends.kicad.pcb import read_board, write_board

    design = read_board(built.board.read_text())
    lost = {n.id for n in design.circuit.nets if n.name in ("SIG", "SECOND")}
    remaining = tuple(t for t in design.board.tracks if t.net_id not in lost)
    built.board.write_text(write_board(replace(design, board=replace(design.board, tracks=remaining))).text)


def test_lifecycle_forget_refuses_a_member_then_removes_the_whole_unit(tmp_path: Path, monkeypatch) -> None:
    built, words, bundle, record_path = accepted(tmp_path, monkeypatch)
    before, record_before = built.board.read_bytes(), record_path.read_bytes()
    code, _, err = cli(*words, "--forget", bundle["members"][0], "--dry-run")
    assert code == 2 and bundle["id"] in err
    assert (built.board.read_bytes(), record_path.read_bytes()) == (before, record_before)
    code, plan, err = cli(*words, "--forget", bundle["id"], "--dry-run")
    assert code == 0, err
    code, _, err = cli(*words, "--forget", bundle["id"], "--confirm", "--plan", plan["result"]["plan_id"])
    assert code == 0, err
    record = loads(record_path.read_bytes())
    assert not (record.bundles or record.locked)
    from fenolite.backends.kicad.pcb import read_board

    assert not read_board(built.board.read_text()).board.tracks


def test_lifecycle_replay_restores_all_members_and_preserves_legacy_flag_order(
    tmp_path: Path, monkeypatch
) -> None:
    built, words, bundle, record_path = accepted(tmp_path, monkeypatch)
    erase_tracks(built)
    before, record_before = built.board.read_bytes(), record_path.read_bytes()
    code, _, err = cli(*words, "--replay", bundle["members"][0], "--dry-run")
    assert code == 2 and bundle["id"] in err
    code, plan, err = cli(*words, "--replay", bundle["id"], "--dry-run")
    assert code == 0, err
    assert set(plan["result"]["replayed"]) == set(bundle["members"])
    assert built.board.read_bytes() == before
    code, _, err = cli(*words, "--replay", bundle["id"], "--confirm", "--plan", plan["result"]["plan_id"])
    assert code == 0, err
    assert record_path.read_bytes() == record_before and built.board.read_bytes() != before
    code, reply, err = cli("route", "--replay", str(built.board), "--router", "octilinear", "--dry-run")
    assert code == 0, err
    assert not reply["result"]["replayed"]


def test_lifecycle_one_stale_member_prevents_replay_of_every_member(tmp_path: Path, monkeypatch) -> None:
    from dataclasses import replace

    from fenolite.backends.kicad.pcb import read_board, write_board
    from fenolite.core.coords import Point

    built, words, bundle, record_path = accepted(tmp_path, monkeypatch)
    erase_tracks(built)
    design = read_board(built.board.read_text())
    r4 = next(c.id for c in design.circuit.components if c.ref == "R4")
    moved = tuple(
        replace(f, position=Point(f.position.x + 1_000_000, f.position.y)) if f.component_id == r4 else f
        for f in design.board.footprints
    )
    built.board.write_text(write_board(replace(design, board=replace(design.board, footprints=moved))).text)
    before, record_before = built.board.read_bytes(), record_path.read_bytes()
    code, reply, err = cli(*words, "--replay", bundle["id"], "--dry-run")
    assert code == 0, err
    assert not reply["result"]["replayed"] and len(reply["result"]["stale"]) == 2
    assert not reply["result"].get("plan_id")
    assert (built.board.read_bytes(), record_path.read_bytes()) == (before, record_before)


@pytest.mark.parametrize("dependency", ["requirements", "profile", "roles", "rules", "model", "record"])
def test_guard_changed_bundle_input_refuses_reviewed_bytes(
    tmp_path: Path, monkeypatch, dependency: str
) -> None:
    from fenolite.roles import profile
    from fenolite.roles.store import document_path

    profile_copy = tmp_path / "profile_copy.py"
    profile_copy.write_bytes(Path(profile.__file__).read_bytes())
    monkeypatch.setattr(profile, "__file__", str(profile_copy))
    built, words, bundle = proposed(tmp_path, monkeypatch, requirements=True)
    code, plan, err = cli(*words, "--accept", bundle["id"], *NEGOTIATE, "--dry-run")
    assert code == 0, err
    record_path = tmp_path / plan["result"]["record"]
    path = {
        "requirements": tmp_path / "limits.toml",
        "profile": profile_copy,
        "roles": document_path(built.board),
        "rules": built.board.with_suffix(".kicad_dru"),
        "model": built.board.parent / ".fenolite" / "rules.json",
        "record": record_path,
    }[dependency]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((path.read_bytes() if path.exists() else b"") + b"\n")
    before = built.board.read_bytes()
    code, _, err = cli(
        *words, "--accept", bundle["id"], *NEGOTIATE, "--confirm", "--plan", plan["result"]["plan_id"]
    )
    assert code == 4 and "FEN-4002" in err
    assert built.board.read_bytes() == before


def test_guard_bundle_write_failure_rolls_back_board_and_record_then_retries_without_search(
    tmp_path: Path, monkeypatch
) -> None:
    import os

    from fenolite.routing import negotiate

    built, words, bundle = proposed(tmp_path, monkeypatch)
    before = built.board.read_bytes()
    code, plan, err = cli(*words, "--accept", bundle["id"], *NEGOTIATE, "--dry-run")
    assert code == 0, err
    record = tmp_path / plan["result"]["record"]
    prior = record.read_bytes() if record.exists() else None
    real_replace = os.replace
    written = []
    triggered = []

    def fail_record(src, dst, *args, **kwargs):
        written.append(Path(dst))
        if Path(dst) == record and not triggered:
            triggered.append(True)
            raise PermissionError(13, "authored atomic bundle write fault")
        return real_replace(src, dst, *args, **kwargs)

    def must_not_negotiate(*args, **kwargs):
        raise AssertionError("confirmation uses reviewed bytes")

    monkeypatch.setattr(negotiate, "negotiate", must_not_negotiate)
    with monkeypatch.context() as fault:
        fault.setattr(os, "replace", fail_record)
        code, _, err = cli(
            *words, "--accept", bundle["id"], *NEGOTIATE, "--confirm", "--plan", plan["result"]["plan_id"]
        )
        assert code == 1 and "FEN-1002" in err
    assert triggered and built.board in written[: written.index(record)]
    assert built.board.read_bytes() == before
    assert (record.read_bytes() if record.exists() else None) == prior
    code, _, err = cli(
        *words, "--accept", bundle["id"], *NEGOTIATE, "--confirm", "--plan", plan["result"]["plan_id"]
    )
    assert code == 0, err
    assert {e.candidate for e in loads(record.read_bytes()).locked} == set(bundle["members"])


@pytest.mark.needs_kicad  # --gate drc resolves kicad-cli before the patched gate runs
def test_guard_final_gate_cannot_accept_a_partial_bundle(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from fenolite.cli import _propose
    from fenolite.core.evidence import Evidence

    built, words, bundle = proposed(tmp_path, monkeypatch)
    before = built.board.read_bytes()
    seen = []

    def partial_gate(path, original, after, **kwargs):
        assert len(kwargs["together"]) == 1
        seen.append(True)
        victim = after.board.tracks[0].id
        return SimpleNamespace(
            design=original, result=None, evidence=Evidence(), issues=(), dropped=frozenset((victim,))
        )

    monkeypatch.setattr(_propose._gate, "gate", partial_gate)
    code, reply, err = cli(*words, "--accept", bundle["id"], *NEGOTIATE, "--gate", "drc", "--dry-run")
    assert code == 5, err
    assert seen and not reply["result"].get("plan_id") and not reply["result"]["accepted"]
    assert built.board.read_bytes() == before


def test_lifecycle_forget_rejected_bundle_removes_only_metadata(tmp_path: Path, monkeypatch) -> None:
    built, words, bundle = proposed(tmp_path, monkeypatch)
    before = built.board.read_bytes()
    code, plan, err = cli(*words, "--reject", bundle["id"], *NEGOTIATE, "--dry-run")
    assert code == 0, err
    code, reply, err = cli(
        *words, "--reject", bundle["id"], *NEGOTIATE, "--confirm", "--plan", plan["result"]["plan_id"]
    )
    assert code == 0, err
    record_path = tmp_path / reply["result"]["record"]
    code, plan, err = cli(*words, "--forget", bundle["id"], "--dry-run")
    assert code == 0, err
    code, _, err = cli(*words, "--forget", bundle["id"], "--confirm", "--plan", plan["result"]["plan_id"])
    assert code == 0, err
    record = loads(record_path.read_bytes())
    assert not (record.bundles or record.locked or record.rejected) and built.board.read_bytes() == before


def test_decisions_subset_selection_can_be_repeated_for_atomic_acceptance(
    tmp_path: Path, monkeypatch
) -> None:
    import shlex

    monkeypatch.chdir(tmp_path)
    built = project(tmp_path, third=True)
    base = ("route", str(built.board), "--router", "octilinear")
    selectors = ("--nets", "SIG", "--nets", "SECOND", "--kind", "connection")
    code, reply, err = cli(*base, "--propose", *selectors, *NEGOTIATE)
    assert code == 0, err
    bundle = reply["result"]["bundles"][0]
    action = shlex.split(reply["result"]["next"][0])
    assert action.count("--nets") == 2 and "--kind" in action and bundle["id"] in action
    code, plan, err = cli(*base, "--accept", bundle["id"], *selectors, *NEGOTIATE, "--dry-run")
    assert code == 0, err
    code, reply, err = cli(
        *base,
        "--accept",
        bundle["id"],
        *selectors,
        *NEGOTIATE,
        "--confirm",
        "--plan",
        plan["result"]["plan_id"],
    )
    assert code == 0, err
    record = loads((tmp_path / reply["result"]["record"]).read_bytes())
    assert {e.net for e in record.locked} == {"SIG", "SECOND"}


@pytest.mark.parametrize(
    "prefix",
    [
        (),
        ("--json",),
        ("--fields", "route"),
        ("--limit", "2"),
        ("--cursor", "route"),
        ("--format", "concise"),
        ("--seed", "2"),
        ("--kicad-version", "9"),
    ],
)
def test_replay_argument_compatibility_preserves_global_prefix_and_legacy_path(prefix) -> None:
    from fenolite.cli.api import discover
    from fenolite.cli.main import _route_replay_arguments, build_parser

    words = (*prefix, "route", "--replay", "authored.kicad_pcb", "--router", "octilinear")
    args = build_parser(discover()).parse_args(_route_replay_arguments(words))
    assert args.path == "authored.kicad_pcb" and args.replay == "all"


def test_lifecycle_replay_requires_current_hv_limits_without_search_options(
    tmp_path: Path, monkeypatch
) -> None:
    built, words, bundle, record_path = accepted(tmp_path, monkeypatch, requirements=True, high=True)
    erase_tracks(built)
    before, record_before = built.board.read_bytes(), record_path.read_bytes()
    code, reply, err = cli(*words[:4], "--replay", bundle["id"], "--dry-run")
    assert code == 0, err
    assert not reply["result"]["replayed"] and len(reply["result"]["stale"]) == 2
    assert not reply["result"].get("plan_id") and built.board.read_bytes() == before
    code, reply, err = cli(*words, "--replay", bundle["id"], "--dry-run")
    assert code == 0, err
    assert set(reply["result"]["replayed"]) == set(bundle["members"])
    assert "H-G-ROUTE-NEGOTIATE" in reply["evidence"]["hypotheses"]
    assert (built.board.read_bytes(), record_path.read_bytes()) == (before, record_before)


def test_decisions_replacing_shared_historical_members_requires_explicit_forget(
    tmp_path: Path, monkeypatch
) -> None:
    built, words, old = proposed(tmp_path, monkeypatch)
    code, plan, err = cli(*words, "--reject", old["id"], *NEGOTIATE, "--dry-run")
    assert code == 0, err
    code, reply, err = cli(
        *words, "--reject", old["id"], *NEGOTIATE, "--confirm", "--plan", plan["result"]["plan_id"]
    )
    assert code == 0, err
    record_path = tmp_path / reply["result"]["record"]
    options = tuple("negotiate-max-rounds=6" if w == "negotiate-max-rounds=5" else w for w in NEGOTIATE)
    code, reply, err = cli(*words, "--propose", *options)
    assert code == 0, err
    new = reply["result"]["bundles"][0]
    assert new["id"] != old["id"] and set(new["members"]) == set(old["members"])
    assert all(p["candidates"] for p in reply["result"]["proposals"])
    before, stored = built.board.read_bytes(), record_path.read_bytes()
    code, reply, err = cli(*words, "--accept", new["id"], *options, "--dry-run")
    assert code == 5, err
    assert not reply["result"].get("plan_id")
    assert any(old["id"] in issue["hint"] for issue in reply["issues"])
    assert (built.board.read_bytes(), record_path.read_bytes()) == (before, stored)
