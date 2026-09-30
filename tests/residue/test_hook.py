# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pre-commit hook refuses a commit with residue and accepts a clean one (in a throwaway repo)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import _scanmod
import pytest

REPO = _scanmod.REPO


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("FENOLITE_RESIDUE_TOKENS", "FENOLITE_RESIDUE_TOKENS_FILE", "FENOLITE_RESIDUE_BLOBS_FILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "repo"
    shutil.copytree(
        REPO / "tools" / "residue", root / "tools" / "residue", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(REPO / "tools" / "hooks", root / "tools" / "hooks")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    hook = root / ".git" / "hooks" / "pre-commit"
    shutil.copy2(root / "tools" / "hooks" / "pre-commit", hook)
    return root


def _commit(root: Path, message: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        "git",
        "-C",
        str(root),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_hook_blocks_and_allows(repo: Path) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "tools"], check=True)
    assert _commit(repo, "tooling").returncode == 0
    (repo / "notes.md").write_text("draft at " + "/" + "Users/dave/work/board\n")
    subprocess.run(["git", "-C", str(repo), "add", "notes.md"], check=True)
    blocked = _commit(repo, "leak")
    assert blocked.returncode != 0
    assert "notes.md:" in blocked.stdout + blocked.stderr
    (repo / "notes.md").write_text("draft\n")
    subprocess.run(["git", "-C", str(repo), "add", "notes.md"], check=True)
    assert _commit(repo, "clean").returncode == 0


def test_history_mode_finds_residue_in_old_commits(repo: Path) -> None:
    scan = _scanmod.load()
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    (repo / "old.md").write_text("draft at " + "/" + "Users/erin/x\n")
    subprocess.run([*git, "add", "old.md"], check=True)
    subprocess.run([*git, "commit", "-q", "--no-verify", "-m", "leak"], check=True)
    (repo / "old.md").write_text("clean\n")
    subprocess.run([*git, "commit", "-q", "--no-verify", "-am", "fix"], check=True)
    assert scan.scan(repo, scan.load_config())[0] == []  # the working tree is clean now
    hits, _ = scan.scan(repo, scan.load_config(), scan.history_files(repo))
    assert [h.path.split(":", 1)[1] for h in hits] == ["old.md"]
