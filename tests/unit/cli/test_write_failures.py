# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A command writes all its files or none, a failed write ends in one error object, and a command that
reports an error writes nothing (capability cli-contract, "All-or-nothing writes", "Error findings plan no
write" and "Typed errors on stderr"; change c0120). Hermetic."""

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from _checkcli import run
from _cliexamples import folder_snapshot

import fenolite.cli.main as cli_main
from fenolite.cli.errors import REGISTRY
from fenolite.core.state import state_dir

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
MonkeyPatch = pytest.MonkeyPatch
needs_modes = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="a read-only folder does not refuse a write on Windows or for the superuser",
)


@contextmanager
def read_only(folder: Path) -> Iterator[None]:
    before = stat.S_IMODE(folder.stat().st_mode)
    folder.chmod(0o555)
    try:
        yield
    finally:
        folder.chmod(before)


def tree(folder: Path) -> list[str]:
    """Every file and folder under ``folder``."""
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


def test_registry_holds_the_three_codes() -> None:
    assert (int(REGISTRY["FEN-1002"].exit_code), REGISTRY["FEN-1002"].retryable) == (1, True)
    assert (int(REGISTRY["FEN-1003"].exit_code), REGISTRY["FEN-1003"].retryable) == (1, True)
    assert (int(REGISTRY["FEN-4002"].exit_code), REGISTRY["FEN-4002"].retryable) == (4, False)
    assert REGISTRY["FEN-1002"].hint == "nothing was written; fix the cause and run the same command again"
    assert REGISTRY["FEN-1003"].message == "stopped by a signal; nothing was written"
    assert REGISTRY["FEN-1001"].retryable is False


def test_blocked_write_ends_in_an_error_object(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A blocked write ends in an error object" (measured 1 of the design: a traceback before)."""
    (tmp_path / "blocker").write_bytes(b"a file")
    monkeypatch.chdir(tmp_path)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["_echo", "--write", "ok.txt", "--write", "blocker/x.txt", "--confirm", "--json"])
    assert code == 1
    assert err.getvalue().count("\n") == 1, "stderr is one line"
    error = json.loads(err.getvalue())
    assert error["code"] == "FEN-1002" and error["retryable"] is True
    assert error["message"].startswith("blocker/x.txt: ") and error["where"] == "blocker/x.txt"
    assert error["hint"] == "nothing was written; fix the cause and run the same command again"
    for text in (err.getvalue(), out.getvalue()):
        assert "Traceback" not in text and str(tmp_path) not in text
    env = json.loads(out.getvalue())
    assert env["ok"] is False and env["receipt"] is None
    assert [row["path"] for row in env["result"]["plan"]] == ["ok.txt", "blocker/x.txt"]
    assert len(env["result"]["plan_id"]) == 16
    assert tree(tmp_path) == ["blocker"], "the first file was taken back"


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


@needs_modes
def test_build_that_fails_in_the_middle_changes_nothing(
    monkeypatch: MonkeyPatch, tmp_path: Path, no_kicad_libraries: None
) -> None:
    """Scenario "A build that fails in the middle changes nothing" (measured 2: 8 of 20 files before)."""
    script = _blink(tmp_path)
    work = script.parent
    args = ("build", "design.py", "--out", "proj", "--confirm")
    code, first, _, _ = run(monkeypatch, work, *args)
    assert code == 0, first
    text = script.read_text(encoding="utf-8")
    assert "blink" in text
    script.write_text(text + "\n# one more line, so the script is another input\n", encoding="utf-8")
    before = folder_snapshot(work / "proj")
    assert any(name.startswith(".fenolite/") for name in before) and any(n.startswith("lib/") for n in before)
    with read_only(work / "proj" / "lib"):
        code, env, err, raw = run(monkeypatch, work, *args)
    assert code == 1 and err["code"] == "FEN-1002" and err["retryable"] is True
    assert err["where"].startswith("proj/lib/") and "permission denied" in err["message"]
    assert str(tmp_path) not in json.dumps(err) and "Traceback" not in raw
    assert env["ok"] is False and env["receipt"] is None and env["result"]["plan"]
    assert folder_snapshot(work / "proj") == before, "every file holds what it held, .fenolite/ included"
    # a receipt returned by the earlier command still restores: no .bak was touched
    code, again, _, _ = run(monkeypatch, work, *args)
    assert code == 0 and again["receipt"]["written"]


@needs_modes
def test_first_build_into_a_blocked_folder_leaves_nothing(
    monkeypatch: MonkeyPatch, tmp_path: Path, no_kicad_libraries: None
) -> None:
    """Scenario "A first build into a blocked folder leaves nothing"."""
    script = _blink(tmp_path)
    work = script.parent
    (work / "proj").mkdir()
    with read_only(work / "proj"):
        code, env, err, _ = run(monkeypatch, work, "build", "design.py", "--out", "proj", "--confirm")
    assert code == 1 and err["code"] == "FEN-1002" and err["where"].startswith("proj/")
    assert env["receipt"] is None and tree(work / "proj") == []


@needs_modes
def test_the_plan_survives_the_failure(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The plan survives the failure": under ``--plan`` the stage stays for the retry."""
    (tmp_path / "ro").mkdir()
    args = ("_echo", "--write", "top.txt", "--write", "ro/x.txt")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    plan = env["result"]["plan_id"]
    assert code == 0
    with read_only(tmp_path / "ro"):
        code, env, err, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan)
    assert code == 1 and err["code"] == "FEN-1002" and err["where"] == "ro/x.txt"
    assert env["result"]["plan_id"] == plan and tree(tmp_path) == ["ro"]
    root = state_dir()
    assert root is not None and (root / "plans" / plan).is_dir()
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan)
    assert code == 0 and env["receipt"]["plan"] == plan
    assert (tmp_path / "ro" / "x.txt").read_bytes() == b"echo\n" and not (root / "plans" / plan).exists()


def test_failed_write_keeps_earlier_backups(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "blocker").write_bytes(b"a file")
    (tmp_path / "a.txt").write_bytes(b"one")
    code, first, _, raw = run(monkeypatch, tmp_path, "_echo", "--write", "a.txt", "--confirm")
    assert code == 0 and (tmp_path / "a.txt.bak").read_bytes() == b"one"
    args = ("_echo", "--write", "a.txt", "--write", "blocker/x.txt", "--content", "three\n", "--confirm")
    code, _, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 1 and err["code"] == "FEN-1002"
    assert (tmp_path / "a.txt").read_bytes() == b"echo\n" and (tmp_path / "a.txt.bak").read_bytes() == b"one"
    (tmp_path / "r.json").write_text(raw, encoding="utf-8")
    code, _, _, _ = run(monkeypatch, tmp_path, "restore", "r.json", "--confirm")
    assert code == 0 and (tmp_path / "a.txt").read_bytes() == b"one"


def test_unmapped_exception_gives_no_traceback(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    def boom() -> dict[str, object]:
        raise RuntimeError("outside every command")

    monkeypatch.setattr(cli_main, "discover", boom)
    code, env, err, _ = run(monkeypatch, tmp_path, "_echo")
    assert code == 1 and env == {} and err["code"] == "FEN-1001"
    assert "outside every command" in err["message"]


# --- error findings plan no write -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "protocol", [("--confirm",), ("--dry-run",), ()], ids=["confirm", "dry-run", "neither"]
)
def test_error_finding_plans_no_write(
    monkeypatch: MonkeyPatch, tmp_path: Path, protocol: tuple[str, ...]
) -> None:
    """Scenario "No write beside an error" (measured 3: the file was written before)."""
    code, env, err, _ = run(monkeypatch, tmp_path, "_echo", "--issue", "error", "--write", "x.txt", *protocol)
    assert code == 5 and err["code"] == "FEN-5001"
    assert list(tmp_path.iterdir()) == [] and env["receipt"] is None
    assert "plan" not in env["result"] and "plan_id" not in env["result"]
    root = state_dir()
    assert root is not None and not root.exists(), "nothing is staged"


def test_error_finding_warning_still_writes(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(
        monkeypatch, tmp_path, "_echo", "--issue", "warning", "--write", "x.txt", "--confirm"
    )
    assert code == 0 and env["receipt"]["written"][0]["path"] == "x.txt"
