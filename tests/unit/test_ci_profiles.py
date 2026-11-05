# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""CI policy cannot downgrade a merge or accept missing dependencies."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ci_profiles", ROOT / "tools/ci_profiles.py")
assert SPEC and SPEC.loader
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Callable[..., str], str]:
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "isolated-gitconfig"
    config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    def git(*args: str) -> str:
        return subprocess.check_output(
            [
                "git", "-c", "user.name=Fenolite test", "-c", "user.email=test@example.invalid",
                "-c", "commit.gpgsign=false", *args,
            ], text=True,
        ).strip()  # fmt: skip

    git("init", "-q", "--template=")
    git("config", "diff.renames", "true")
    (tmp_path / "README.md").write_text("authored base\n")
    (tmp_path / "Makefile").write_text("authored CI control\n")
    git("add", ".")
    git("commit", "-qm", "authored base")
    base = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/dev", base)
    (tmp_path / "README.md").write_text("authored working change\n")
    git("commit", "-qam", "authored working change")
    return git, base


def test_real_git_diff_supports_working_push_new_branch_and_manual(
    checkout: tuple[Callable[..., str], str],
) -> None:
    _, before = checkout
    for event, payload in (
        ("push", {"before": before}),
        ("push", {"before": "0" * 40}),
        ("workflow_dispatch", {"inputs": {"profile": "fast"}}),
    ):
        changed = policy.changed_paths(event, payload)
        assert changed == ["README.md"]
        assert policy.profile(event, "refs/heads/codex/example", payload, changed)[0] == "fast"


@pytest.mark.parametrize("before", [None, "", "0", "0" * 41, "bad", 3, "f" * 40])
def test_missing_malformed_or_unavailable_before_is_not_a_new_branch(
    checkout: tuple[Callable[..., str], str], before: object
) -> None:
    payload = {} if before is None else {"before": before}
    assert policy.changed_paths("push", payload) is None


def test_renamed_away_ci_control_forces_full(checkout: tuple[Callable[..., str], str]) -> None:
    git, _ = checkout
    before = git("rev-parse", "HEAD")
    git("mv", "Makefile", "former-make.txt")
    git("commit", "-qm", "authored renamed control")
    assert git("diff", "--name-status", before, "HEAD").startswith("R100\t")
    changed = policy.changed_paths("push", {"before": before})
    assert changed == ["Makefile", "former-make.txt"]
    assert policy.profile("push", "refs/heads/codex/example", {}, changed)[0] == "full"


@pytest.mark.parametrize("event", ["pull_request", "merge_group", "unknown", "pull_request_target"])
def test_merge_events_always_full(event: str) -> None:
    assert policy.profile(event, "refs/heads/codex/example", {}, ["README.md"])[0] == "full"


@pytest.mark.parametrize(
    "ref",
    [
        "refs/heads/dev",
        "refs/heads/main",
        "refs/heads/master",
        "refs/heads/release/v1",
        "refs/heads/cac/lote-12",
        "refs/heads/cac/lote-13",
        "refs/heads/unclassified",
        "refs/tags/v1",
        "",
    ],
)
def test_manual_cannot_downgrade_integration_or_unknown_ref(ref: str) -> None:
    assert policy.profile("push", ref, {}, ["README.md"])[0] == "full"
    assert (
        policy.profile("workflow_dispatch", ref, {"inputs": {"profile": "fast"}}, ["README.md"])[0] == "full"
    )


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/ci.yml",
        "tools/ci_tests.py",
        "tests/conftest.py",
        "tests/_resources.py",
        "tests/_drawn_census_reuse.py",
        "tests/_drawn_context.py",
        "tests/_drawn_corpus.py",
        "tests/kicad/schematic/test_drawn_corpus.py",
        "tests/unit/test_ci_profiles.py",
        "pyproject.toml",
        "uv.lock",
        "Makefile",
        "AGENTS.md",
        "docs/ci.md",
        "tests/unit/roles/test_proposal_reference.py",
        "tests/unit/test_new_file.py",
        "conftest.py",
        "tests/UNIT/CONFTEST.PY",
        "pytest.toml",
        ".pytest.toml",
        "pytest.ini",
        ".pytest.ini",
        "tests/kicad/pytest.ini",
        "tox.ini",
        "setup.cfg",
        "setup.py",
        "GNUmakefile",
        "makefile",
        "uv.toml",
        ".python-version",
    ],
)
def test_control_changes_force_full(path: str) -> None:
    assert policy.profile("push", "refs/heads/codex/example", {}, [path])[0] == "full"
    assert (
        policy.profile(
            "workflow_dispatch", "refs/heads/codex/example", {"inputs": {"profile": "fast"}}, [path]
        )[0]
        == "full"
    )


def test_unknown_diff_and_deleted_ref_fail_closed() -> None:
    assert policy.profile("push", "refs/heads/cac/example", {}, None)[0] == "full"
    assert policy.profile("push", "refs/heads/cac/example", {"deleted": True}, [])[0] == "full"


@pytest.mark.parametrize(
    "branch", ["codex/example", "cac/example", "feature/example", "fix/example", "router-next"]
)
def test_working_push_can_run_fast(branch: str) -> None:
    assert policy.profile("push", f"refs/heads/{branch}", {}, ["src/fenolite/core/coords.py"])[0] == "fast"
    assert policy.profile("workflow_dispatch", f"refs/heads/{branch}", {}, ["README.md"])[0] == "full"
    assert (
        policy.profile(
            "workflow_dispatch", f"refs/heads/{branch}", {"inputs": {"profile": "fast"}}, ["README.md"]
        )[0]
        == "fast"
    )


@pytest.mark.parametrize("state", ["skipped", "failure", "cancelled", "timed_out", "missing"])
def test_full_gate_refuses_each_missing_or_unsuccessful_job(state: str) -> None:
    for omitted in policy.FULL_JOBS:
        needs = {name: {"result": "success"} for name in policy.FULL_JOBS}
        if state == "missing":
            needs.pop(omitted)
        else:
            needs[omitted] = {"result": state}
        assert policy.gate("full", "full", needs)
    assert policy.gate("full", "fast", {name: {"result": "success"} for name in policy.FULL_JOBS})


def test_full_gate_accepts_complete_result() -> None:
    assert policy.gate("full", "full", {name: {"result": "success"} for name in policy.FULL_JOBS}) == []


def test_malformed_event_cannot_select_fast(tmp_path: Path) -> None:
    payload, output = tmp_path / "event.json", tmp_path / "output"
    payload.write_text("invalid", encoding="utf-8")
    env = {
        **os.environ,
        "GITHUB_EVENT_PATH": str(payload),
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/codex/example",
        "GITHUB_OUTPUT": str(output),
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/ci_profiles.py"), "plan"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["profile"] == "full"
    assert output.read_text(encoding="utf-8") == "profile=full\n"


def test_missing_profile_cannot_pass_complete_gate() -> None:
    assert policy.gate("full", "", {name: {"result": "success"} for name in policy.FULL_JOBS})


def test_ci_collections_and_wrapper_contract() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    jobs = set(re.findall(r"^  ([a-zA-Z0-9_-]+):$", text.split("jobs:\n", 1)[1], re.MULTILINE))
    assert jobs - {"fast", "fast-audit", "fast-result", "complete"} == set(policy.FULL_JOBS)
    complete = text.split("  complete:\n", 1)[1].split("  fast-result:", 1)[0]
    assert "if: always() && needs.plan.outputs.profile != 'fast'" in complete
    assert "'fast' && 'ci-complete-not-requested' || 'ci-complete'" in complete
    assert "CI_NEEDS: ${{ toJSON(needs) }}" in complete
    assert "ci_profiles.py gate --kind full" in complete
    for job in policy.FULL_JOBS:
        assert job in complete.split("needs: [", 1)[1].split("]", 1)[0].split(", ")
    assert "shard: [0, 1, 2, 3]" in text
    assert "--suite kicad-10 --shard ${{ matrix.shard }} --shards 4" in text
    assert "FENOLITE_REQUIRE: kicad,corpus,libs" in text
    assert "ci_tests.py audit ci-receipts --commit" in text
    assert "pattern: ci-tests-*" in text
    for serial_suite in ("viewer", "mcp", "routing-${{ matrix.target }}"):
        assert f"--suite {serial_suite} --workers 0 --out" in text
    assert text.count("run: make lint format types residue") == 1
    assert (
        "--dist loadfile" in (ROOT / "tools/ci_tests.py").read_text()
        or '"loadfile"' in (ROOT / "tools/ci_tests.py").read_text()
    )


def test_deleted_branch_cannot_publish_a_successful_plan(tmp_path: Path) -> None:
    payload, output = tmp_path / "deleted.json", tmp_path / "output"
    payload.write_text(json.dumps({"deleted": True}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/ci_profiles.py"), "plan"],
        env={
            **os.environ,
            "GITHUB_EVENT_PATH": str(payload),
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/codex/deleted",
            "GITHUB_OUTPUT": str(output),
        },
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert json.loads(result.stdout)["profile"] == "full"


def test_native_platform_typing_is_retained() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    unit = text.split("  unit:\n", 1)[1].split("  viewer:", 1)[0]
    assert "- name: Native platform types\n        if: matrix.os != 'ubuntu-latest'" in unit
    assert "run: uv run pyright src" in unit
