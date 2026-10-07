# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Staged plans: the id of a plan, the store, and ``--confirm --plan ID`` (capability cli-contract,
"Staged plans" and "Mutation protocol"; change c0120). Hermetic."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run
from _fakecli import EXPORT_FILES, calls, fake_kicad_cli
from _projects import authored_project

from fenolite.cli import cmd__echo, cmd_export, plans
from fenolite.cli.api import Context, Result
from fenolite.core.state import STATE_ENV, state_dir

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
HEX16 = re.compile(r"^[0-9a-f]{16}$")
MonkeyPatch = pytest.MonkeyPatch


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store() -> Path:
    root = state_dir()
    assert root is not None
    return root / "plans"


def staged() -> list[str]:
    return sorted(p.name for p in store().iterdir()) if store().is_dir() else []


def dry(monkeypatch: MonkeyPatch, cwd: Path, *args: str) -> tuple[str, dict[str, Any]]:
    """The plan id and the envelope of a dry run."""
    code, env, _, _ = run(monkeypatch, cwd, *args, "--dry-run")
    assert code == 0, env
    return env["result"]["plan_id"], env


# --- the id ----------------------------------------------------------------------------------------


def test_refusal_names_the_plan(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "_echo", "--write", "out.txt")
    plan = env["result"]["plan_id"]
    assert code == 4 and HEX16.fullmatch(plan)
    assert err["code"] == "FEN-4001" and f"--confirm --plan {plan}" in err["hint"]
    assert list(tmp_path.iterdir()) == [] and staged() == [plan]
    # the id reaches the caller through stderr also when --fields dropped it
    code, env, err, _ = run(monkeypatch, tmp_path, "_echo", "--write", "out.txt", "--fields", "echo")
    assert code == 4 and "plan_id" not in env["result"] and f"--confirm --plan {plan}" in err["hint"]


def test_no_plan_no_id(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "_echo", "--dry-run")
    assert code == 0 and "plan" not in env["result"] and "plan_id" not in env["result"]
    assert staged() == []


def test_plan_needs_a_confirmation(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    args = ("_echo", "--write", "out.txt", "--plan", "0123456789abcdef")
    for extra in ((), ("--dry-run",)):
        code, env, err, _ = run(monkeypatch, tmp_path, *args, *extra)
        assert code == 2 and err["code"] == "FEN-2001" and err["where"] == "--plan"
        assert env == {} and list(tmp_path.iterdir()) == []
    code, _, err, _ = run(monkeypatch, tmp_path, "capabilities", "--plan", "0123456789abcdef")
    assert code == 2 and err["code"] == "FEN-2001", "only a mutating command takes --plan"


def test_digest_of_the_inputs_only(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The id is a digest of the inputs": no clock, seed or state folder takes part."""
    work = tmp_path / "work"
    work.mkdir()
    first, _ = dry(monkeypatch, work, "_echo", "--write", "out.txt", "--seed", "1")
    monkeypatch.setenv(STATE_ENV, str(tmp_path / "another-state"))
    stamp = ("--seed", "2", "--timestamp", "2026-01-02T03:04:05Z", "--no-backup", "--fields", "plan_id")
    second, _ = dry(monkeypatch, work, "_echo", "--write", "out.txt", *stamp)
    assert first == second and HEX16.fullmatch(first)
    other, _ = dry(monkeypatch, work, "_echo", "--write", "out.txt", "--content", "other\n")
    assert other != first


def test_digest_binds_every_part() -> None:
    row = {"path": "a.txt", "kind": "text", "bytes": 1, "sha256": "aa", "replaces": None}
    base = plans.plan_id("_echo", {"write": ["a.txt"]}, "/work", [("in.txt", "11")], [row])
    assert HEX16.fullmatch(base)
    assert base == plans.plan_id("_echo", {"write": ["a.txt"]}, "/work", [("in.txt", "11")], [dict(row)])
    others = [
        plans.plan_id("build", {"write": ["a.txt"]}, "/work", [("in.txt", "11")], [row]),
        plans.plan_id("_echo", {"write": ["b.txt"]}, "/work", [("in.txt", "11")], [row]),
        plans.plan_id("_echo", {"write": ["a.txt"]}, "/other", [("in.txt", "11")], [row]),
        plans.plan_id("_echo", {"write": ["a.txt"]}, "/work", [("in.txt", "22")], [row]),
        plans.plan_id("_echo", {"write": ["a.txt"]}, "/work", [("in.txt", None)], [row]),
        *(
            plans.plan_id("_echo", {"write": ["a.txt"]}, "/work", [("in.txt", "11")], [row | {key: value}])
            for key, value in (
                ("path", "b"),
                ("kind", "k"),
                ("bytes", 2),
                ("sha256", "bb"),
                ("replaces", "cc"),
            )
        ),
    ]
    assert base not in others and len(set(others)) == len(others)


def test_run_flags_take_no_part() -> None:
    assert plans.RUN_FLAGS == (
        "--dry-run", "--confirm", "--plan", "--json", "--text", "--fields", "--limit", "--cursor", "--format",
        "--progress", "--seed", "--timestamp", "--no-backup", "--timeout", "--kicad-cli",
    )  # fmt: skip
    namespace = {
        "command": "export", "dry_run": True, "confirm": False, "plan": None, "json": True, "text": False,
        "fields": "a", "limit": 3, "cursor": "0.aa", "format": "concise", "progress": True, "seed": 1,
        "timestamp": "x", "no_backup": True, "timeout": 5.0, "kicad_cli": "/bin/k",
        "out": "fab", "all": True, "kicad_version": 10, "path": Path("board"),
    }  # fmt: skip
    assert plans.arguments(namespace) == {"all": True, "kicad_version": 10, "out": "fab", "path": "board"}


# --- the store -------------------------------------------------------------------------------------


def _stage(root: Path, plan: str, data: bytes = b"x") -> None:
    row = {"path": "a.txt", "kind": "text", "bytes": len(data), "sha256": sha(data), "replaces": None}
    plans.stage(root, plan, command="_echo", args={}, cwd="/work", depends=[], writes=[row], payloads=[data],
                reply={"result": {}, "issues": [], "evidence": {}, "input": None})  # fmt: skip


def test_prune_keeps_sixteen(tmp_path: Path) -> None:
    """Scenario "The store is bounded"."""
    assert (plans.PLAN_KEEP, plans.PLAN_BYTES, plans.PLAN_DAYS) == (16, 512 * 1024 * 1024, 7)
    root = tmp_path / "state"
    names = [f"{n:016x}" for n in range(17)]
    now = 1_800_000_000
    for age, name in enumerate(names[:16]):
        _stage(root, name)
        os.utime(root / "plans" / name, (now - 1000 + age, now - 1000 + age))
    assert len(list((root / "plans").iterdir())) == 16
    _stage(root, names[16])
    kept = sorted(p.name for p in (root / "plans").iterdir())
    assert len(kept) == 16 and names[0] not in kept and names[16] in kept and names[1] in kept
    assert plans.load(root, names[0]) is None
    found = plans.load(root, names[16])
    assert found is not None and found.data(found.writes[0]) == b"x"
    assert not [p for p in (root / "plans").iterdir() if p.name.startswith(".")], "no temporary folder"


def test_prune_by_age_and_bytes(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    root = tmp_path / "state"
    old, new = "a" * 16, "b" * 16
    _stage(root, old)
    stamp = 1_800_000_000
    os.utime(root / "plans" / old, (stamp, stamp))
    assert plans.prune(root, now=stamp + 6 * 86400) == []
    assert plans.prune(root, now=stamp + 8 * 86400) == [old]
    monkeypatch.setattr(plans, "PLAN_BYTES", 100)
    _stage(root, old, b"o" * 60)
    os.utime(root / "plans" / old, (stamp, stamp))
    _stage(root, new, b"n" * 60)
    assert sorted(p.name for p in (root / "plans").iterdir()) == [new], "the oldest goes first"
    with pytest.raises(plans.StageError, match="larger than the store"):
        _stage(root, "c" * 16, b"c" * 101)


def test_stage_reasons_hold_no_path(tmp_path: Path) -> None:
    with pytest.raises(plans.StageError, match="off"):
        _stage(None, "a" * 16)  # type: ignore[arg-type]
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"a file")
    with pytest.raises(plans.StageError) as caught:
        _stage(blocker, "a" * 16)
    assert str(tmp_path) not in str(caught.value) and "not writable" in str(caught.value)
    assert plans.load(tmp_path, "../escape") is None and plans.load(None, "a" * 16) is None


def test_state_folder_rule(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(STATE_ENV, str(tmp_path / "s"))
    assert state_dir() == tmp_path / "s"
    for off in ("off", "OFF"):
        monkeypatch.setenv(STATE_ENV, off)
        assert state_dir() is None
    for default in ("", "relative/folder"):
        monkeypatch.setenv(STATE_ENV, default)
        assert state_dir() == Path.home() / ".cache" / "fenolite" / "state"
    monkeypatch.delenv(STATE_ENV)
    assert state_dir() == Path.home() / ".cache" / "fenolite" / "state"


# --- the replay ------------------------------------------------------------------------------------


def test_replay_writes_the_reviewed_bytes(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The reviewed bytes are written without a second run": the fake stamps each run."""
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10)
    stamped = {kind: {name: text + "; run {run}\n" for name, text in files.items()}
               for kind, files in EXPORT_FILES.items()}  # fmt: skip
    fake = fake_kicad_cli(tmp_path / "bin", export_files=stamped)
    work = tmp_path / "work"
    work.mkdir()
    args = ("export", str(root), "--out", "fab", "--all", "--manifest", "--kicad-cli", str(fake))
    plan, env = dry(monkeypatch, work, *args)
    rows = {row["path"]: row["sha256"] for row in env["result"]["plan"]}
    runs = len(calls(fake))
    assert runs >= 5 and staged() == [plan] and list(work.iterdir()) == []

    code, done, err, _ = run(monkeypatch, work, *args, "--confirm", "--plan", plan)
    assert code == 0, (done, err)
    assert len(calls(fake)) == runs, "the tool did not run again"
    assert done["receipt"]["plan"] == plan
    assert {w["path"]: w["sha256"] for w in done["receipt"]["written"]} == rows
    for path, digest in rows.items():
        assert sha((work / path).read_bytes()) == digest
    assert staged() == [], "a written plan is removed"
    assert "plan" not in done["result"] and "plan_id" not in done["result"]
    for key in ("kinds", "artifacts", "tool_version", "board"):
        assert done["result"][key] == env["result"][key]
    assert done["issues"] == env["issues"] and done["evidence"] == env["evidence"]
    assert done["input"] == env["input"]

    # a second run would have given other bytes: this is what --plan saves
    code, again, _, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 0 and len(calls(fake)) > runs
    assert {w["path"]: w["sha256"] for w in again["receipt"]["written"]} != rows
    assert again["receipt"]["plan"] is None


def test_replay_does_not_call_the_command(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    plan, _ = dry(monkeypatch, tmp_path, "_echo", "--write", "out.txt", "--issue", "warning")

    def boom(_args: object, _ctx: Context) -> Result:
        raise AssertionError("the command ran")

    monkeypatch.setattr(cmd__echo, "COMMAND", dataclasses.replace(cmd__echo.COMMAND, run=boom))
    args = ("_echo", "--write", "out.txt", "--issue", "warning", "--confirm", "--plan", plan)
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--fields", "echo.write", "--format", "concise")
    assert code == 0, env
    assert env["result"] == {"echo": {"write": "out.txt"}}, "the run flags shape the reply of a replay too"
    assert [i["code"] for i in env["issues"]] == ["echo.warning"]
    assert (tmp_path / "out.txt").read_bytes() == b"echo\n" and env["receipt"]["plan"] == plan


def test_target_changed_after_the_review(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_bytes(b"one\n")
    plan, _ = dry(monkeypatch, tmp_path, "_echo", "--write", "out.txt")
    target.write_bytes(b"edited by hand\n")
    code, env, err, _ = run(monkeypatch, tmp_path, "_echo", "--write", "out.txt", "--confirm", "--plan", plan)
    assert code == 4 and err["code"] == "FEN-4002" and err["retryable"] is False
    assert "out.txt" in err["message"] and err["where"] == "out.txt" and str(tmp_path) not in err["message"]
    assert env["ok"] is False and env["receipt"] is None
    assert target.read_bytes() == b"edited by hand\n" and not (tmp_path / "out.txt.bak").exists()
    assert staged() == [plan], "the stage stays"


def test_target_that_did_not_exist_must_not_exist(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    plan, _ = dry(monkeypatch, tmp_path, "_echo", "--write", "out.txt")
    (tmp_path / "out.txt").write_bytes(b"made meanwhile\n")
    code, _, err, _ = run(monkeypatch, tmp_path, "_echo", "--write", "out.txt", "--confirm", "--plan", plan)
    assert code == 4 and err["code"] == "FEN-4002" and "exists now" in err["message"]
    assert (tmp_path / "out.txt").read_bytes() == b"made meanwhile\n"


def test_another_command_line(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    plan, _ = dry(monkeypatch, tmp_path, "_echo", "--write", "a.txt")
    code, _, err, _ = run(monkeypatch, tmp_path, "_echo", "--write", "b.txt", "--confirm", "--plan", plan)
    assert code == 4 and err["code"] == "FEN-4002" and "another command line" in err["message"]
    assert list(tmp_path.iterdir()) == []
    other = tmp_path / "other"
    other.mkdir()
    code, _, err, _ = run(monkeypatch, other, "_echo", "--write", "a.txt", "--confirm", "--plan", plan)
    assert code == 4 and "another working folder" in err["message"] and str(tmp_path) not in err["message"]
    assert list(other.iterdir()) == [] and staged() == [plan]


def test_replayed_plan_can_be_undone(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "out.txt").write_bytes(b"one")
    plan, _ = dry(monkeypatch, tmp_path, "_echo", "--write", "out.txt")
    code, env, _, raw = run(monkeypatch, tmp_path, "_echo", "--write", "out.txt", "--confirm", "--plan", plan)
    assert code == 0 and env["receipt"]["plan"] == plan and env["receipt"]["undo"]
    assert (tmp_path / "out.txt").read_bytes() == b"echo\n"
    (tmp_path / "r.json").write_text(raw, encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "restore", "r.json", "--confirm")
    assert code == 0, env
    assert (tmp_path / "out.txt").read_bytes() == b"one"


def test_receipt_id_ignores_the_plan(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
    plan, _ = dry(monkeypatch, tmp_path / "a", "_echo", "--write", "out.txt")
    _, replayed, _, _ = run(
        monkeypatch, tmp_path / "a", "_echo", "--write", "out.txt", "--confirm", "--plan", plan
    )
    _, direct, _, _ = run(monkeypatch, tmp_path / "b", "_echo", "--write", "out.txt", "--confirm")
    assert replayed["receipt"]["id"] == direct["receipt"]["id"]
    assert (replayed["receipt"]["plan"], direct["receipt"]["plan"]) == (plan, None)


def test_damaged_stage_is_removed(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    args = ("_echo", "--write", "out.txt")
    plan, _ = dry(monkeypatch, tmp_path, *args)
    (store() / plan / "files" / "0000").write_bytes(b"other bytes\n")
    code, _, err, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan)
    assert code == 4 and err["code"] == "FEN-4002" and "damaged" in err["message"]
    assert staged() == [] and list(tmp_path.iterdir()) == []
    plan, _ = dry(monkeypatch, tmp_path, *args)
    (store() / plan / "plan.json").write_text("{", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan)
    assert code == 4 and err["code"] == "FEN-4002" and staged() == []
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan)
    assert code == 0 and env["receipt"]["plan"] == plan, "planned again, and the id still binds"


# --- declared inputs ---------------------------------------------------------------------------------


def _blink(tmp_path: Path) -> Path:
    target = tmp_path / "repo" / "examples" / "blink_2layer"
    shutil.copytree(BLINK_DIR, target)
    shutil.copytree(ROOT / "tests" / "data" / "libs", tmp_path / "repo" / "tests" / "data" / "libs")
    return target / "design.py"


@pytest.fixture
def no_kicad_libraries(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_input_changed_after_the_review(
    monkeypatch: MonkeyPatch, tmp_path: Path, no_kicad_libraries: None
) -> None:
    """Scenario "An input changed after the review"."""
    script = _blink(tmp_path)
    work = script.parent
    args = ("build", "design.py", "--out", "proj")
    plan, env = dry(monkeypatch, work, *args)
    assert not (work / "proj").exists() and env["result"]["plan"]
    script.write_text(script.read_text(encoding="utf-8") + "\n# edited after the review\n", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, work, *args, "--confirm", "--plan", plan)
    assert code == 4 and err["code"] == "FEN-4002"
    assert "design.py" in err["message"] and err["where"] == "design.py"
    assert not (work / "proj").exists() and staged() == [plan]


def test_build_plan_replays(monkeypatch: MonkeyPatch, tmp_path: Path, no_kicad_libraries: None) -> None:
    script = _blink(tmp_path)
    work = script.parent
    args = ("build", "design.py", "--out", "proj")
    plan, env = dry(monkeypatch, work, *args)
    code, done, err, _ = run(monkeypatch, work, *args, "--confirm", "--plan", plan)
    assert code == 0, (done, err)
    for row in env["result"]["plan"]:
        assert sha((work / row["path"]).read_bytes()) == row["sha256"]
    assert done["receipt"]["plan"] == plan and staged() == []


def test_altium_plan_replays_and_guards_the_document(
    monkeypatch: MonkeyPatch, tmp_path: Path, no_kicad_libraries: None
) -> None:
    """An Altium build's plan replays, and a PCB document edited after the review is a target with another
    digest: ``FEN-4002`` (design, Decision 2 and 13)."""
    work = tmp_path / "work"
    work.mkdir()
    args = ("build", str(BLINK_DIR / "design.py"), "--out", "B", "--target", "altium")
    plan, env = dry(monkeypatch, work, *args)
    code, done, err, _ = run(monkeypatch, work, *args, "--confirm", "--plan", plan)
    assert code == 0, (done, err)
    rows = {row["path"]: row for row in env["result"]["plan"]}
    for path, row in rows.items():
        assert sha((work / path).read_bytes()) == row["sha256"]
    document = next(path for path, row in rows.items() if path.endswith(".PcbDoc"))

    plan, env = dry(monkeypatch, work, *args)  # the second build replaces the documents of the first
    assert env["result"]["plan"]
    before = (work / document).read_bytes()
    (work / document).write_bytes(before + b"\x00edited in the tool")
    code, _, err, _ = run(monkeypatch, work, *args, "--confirm", "--plan", plan)
    assert code == 4 and err["code"] == "FEN-4002" and err["where"] == document
    assert (work / document).read_bytes() == before + b"\x00edited in the tool"


# --- a plan that is not staged ---------------------------------------------------------------------------


def test_not_staged_is_planned_again(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A plan that was not staged is planned again"."""
    monkeypatch.setenv(STATE_ENV, "off")
    plan, env = dry(monkeypatch, tmp_path, "_echo", "--write", "out.txt")
    (warning,) = [i for i in env["issues"] if i["code"] == "plan.not-staged"]
    assert warning["severity"] == "warning" and "off" in warning["message"] and plan in warning["message"]
    assert env["ok"] is True and list(tmp_path.iterdir()) == []
    code, done, _, _ = run(monkeypatch, tmp_path, "_echo", "--write", "out.txt", "--confirm", "--plan", plan)
    assert code == 0 and done["receipt"]["plan"] == plan
    assert (tmp_path / "out.txt").read_bytes() == b"echo\n"
    assert [i["code"] for i in done["issues"]] == [], "a confirmed write stages nothing and warns of nothing"
    (tmp_path / "out.txt").unlink()
    wrong = "0000000000000000"
    code, env, err, _ = run(
        monkeypatch, tmp_path, "_echo", "--write", "out.txt", "--confirm", "--plan", wrong
    )
    assert code == 4 and err["code"] == "FEN-4002" and wrong in err["message"] and plan in err["message"]
    assert env["receipt"] is None and list(tmp_path.iterdir()) == []


def test_not_staged_and_nothing_planned_now(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "_echo", "--confirm", "--plan", "0123456789abcdef")
    assert code == 4 and err["code"] == "FEN-4002" and "plans no write" in err["message"]
    code, _, err, _ = run(monkeypatch, tmp_path, "_echo", "--write", "x.txt", "--confirm", "--plan", "../x")
    assert code == 4 and err["code"] == "FEN-4002" and list(tmp_path.iterdir()) == []


def test_unwritable_store_warns_and_goes_on(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"a file")
    monkeypatch.setenv(STATE_ENV, str(blocker))
    work = tmp_path / "work"
    work.mkdir()
    plan, env = dry(monkeypatch, work, "_echo", "--write", "out.txt")
    (warning,) = env["issues"]
    assert warning["code"] == "plan.not-staged" and str(tmp_path) not in warning["message"]
    assert HEX16.fullmatch(plan) and list(work.iterdir()) == []


def test_deferred_write_is_planned_again(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """A deferred write (c0078) has no bytes before ``--confirm``: its plan is not staged, and
    ``--confirm --plan`` plans it again and resolves the source once, when the id is the same."""
    monkeypatch.setattr(cmd__echo, "DEFER_CALLS", [])
    plan, env = dry(monkeypatch, tmp_path, "_echo", "--defer", "d.bin", "--write", "w.txt")
    assert env["issues"] == [] and staged() == [] and cmd__echo.DEFER_CALLS == []
    args = ("_echo", "--defer", "d.bin", "--write", "w.txt", "--confirm", "--plan")
    code, _, err, _ = run(monkeypatch, tmp_path, *args, "0000000000000000")
    assert code == 4 and err["code"] == "FEN-4002" and cmd__echo.DEFER_CALLS == []
    assert list(tmp_path.iterdir()) == []
    code, done, _, _ = run(monkeypatch, tmp_path, *args, plan)
    assert code == 0 and done["receipt"]["plan"] == plan and cmd__echo.DEFER_CALLS == ["d.bin"]
    assert (tmp_path / "d.bin").read_bytes() == cmd__echo.DEFERRED
    assert [w["path"] for w in done["receipt"]["written"]] == ["w.txt", "d.bin"]


def test_staged_reply_survives_json(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """The reviewed ``input`` and ``evidence`` come back from the stage as they were."""
    hide_kicad(monkeypatch, tmp_path)
    args = tuple(cmd_export.COMMAND.mutation_example_args or ())
    fake = fake_kicad_cli(tmp_path / "bin")
    plan, env = dry(monkeypatch, tmp_path, "export", *args, "--kicad-cli", str(fake))
    stage = json.loads((store() / plan / "plan.json").read_text(encoding="utf-8"))
    assert stage["reply"]["input"] == env["input"] and stage["reply"]["evidence"] == env["evidence"]
    assert sorted(p.name for p in (store() / plan).iterdir()) == ["files", "plan.json"]
    assert len(list((store() / plan / "files").iterdir())) == len(env["result"]["plan"])
