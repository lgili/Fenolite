# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``tools/dco_check.py`` on temporary repositories (capability ci-baseline, "DCO job"; change c0025)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "dco_check.py"
SIGNED = "Signed-off-by: A Tester <tester@example.org>"
ENV = {
    "GIT_AUTHOR_NAME": "A Tester",
    "GIT_AUTHOR_EMAIL": "tester@example.org",
    "GIT_COMMITTER_NAME": "A Tester",
    "GIT_COMMITTER_EMAIL": "tester@example.org",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str) -> str:
    run = subprocess.run(
        ["git", *args], cwd=repo, env={**os.environ, **ENV}, capture_output=True, text=True, check=True
    )
    return run.stdout.strip()


def commit(repo: Path, subject: str, *, signed: bool) -> None:
    (repo / "file.txt").write_text(subject, encoding="utf-8")
    git(repo, "add", "file.txt")
    message = f"{subject}\n\nbody\n" + (f"\n{SIGNED}\n" if signed else "")
    git(repo, "commit", "-q", "--no-verify", "-m", message)


def check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=repo,
        env={**os.environ, **ENV},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


def test_signed_history_passes(repo: Path) -> None:
    commit(repo, "first", signed=True)
    commit(repo, "second", signed=True)
    run = check(repo)
    assert (run.returncode, run.stdout) == (0, "")


def test_unsigned_commit_is_named(repo: Path) -> None:
    """Scenario "Unsigned commit is named"."""
    commit(repo, "first", signed=True)
    commit(repo, "the unsigned one", signed=False)
    run = check(repo)
    short = git(repo, "rev-parse", "--short", "HEAD")
    assert run.returncode == 1 and run.stdout == f"{short} the unsigned one\n"


def test_range_limits_the_commits(repo: Path) -> None:
    commit(repo, "old and unsigned", signed=False)
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, "new and signed", signed=True)
    assert check(repo).returncode == 1
    assert check(repo, f"{base}..HEAD").returncode == 0


def test_merge_commit_is_skipped(repo: Path) -> None:
    """Scenario "Merge commit skipped"."""
    commit(repo, "base", signed=True)
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, "side", signed=True)
    git(repo, "checkout", "-q", "main")
    (repo / "other.txt").write_text("x", encoding="utf-8")
    git(repo, "add", "other.txt")
    git(repo, "commit", "-q", "--no-verify", "-m", f"main\n\n{SIGNED}\n")
    git(repo, "merge", "-q", "--no-ff", "--no-verify", "-m", "merge without a sign-off", "side")
    assert len(git(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()) == 3
    assert check(repo).returncode == 0


def test_a_trailer_needs_a_name_and_an_address(repo: Path) -> None:
    (repo / "file.txt").write_text("x", encoding="utf-8")
    git(repo, "add", "file.txt")
    git(repo, "commit", "-q", "--no-verify", "-m", "bad trailer\n\nSigned-off-by: nobody\n")
    assert check(repo).returncode == 1


def test_exceptions_file() -> None:
    """An exception is a full hash with a reason; this repository has one, for a GitHub squash merge."""
    sys.path.insert(0, str(TOOL.parent))
    try:
        import dco_check
    finally:
        sys.path.pop(0)
    listed = dco_check.exceptions()
    assert all(len(commit) == 40 for commit in listed) and len(listed) <= 1
    bad = TOOL.parent / "dco_exceptions.txt"
    lines = [line for line in bad.read_text(encoding="utf-8").splitlines() if line and line[0] != "#"]
    assert all(len(line.split(" ", 1)) == 2 and line.split(" ", 1)[1].strip() for line in lines)


def test_git_failure_exits_2(tmp_path: Path) -> None:
    run = check(tmp_path)
    assert run.returncode == 2 and "git failed" in run.stderr
    assert check(tmp_path, "a", "b").returncode == 2


def test_this_repository_passes() -> None:
    """Scenario "History passes" (skipped in a checkout without history)."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    if git(ROOT, "rev-parse", "--is-shallow-repository") == "true":
        # a shallow clone shows the runner's merge commit of a pull request without its parents
        pytest.skip("a shallow clone: the dco job checks the full history")
    run = check(ROOT)
    if run.returncode == 2:
        pytest.skip(f"git cannot read the history here: {run.stderr.strip()}")
    assert (run.returncode, run.stdout) == (0, "")
