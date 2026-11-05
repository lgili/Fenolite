# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Planted omissions, duplicate shards and real serial/xdist receipt execution."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ci_tests", ROOT / "tools/ci_tests.py")
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def baseline() -> list[dict]:
    return [
        {"id": f"tests/test_file_{file}.py::test_case[{case}]", "file": f"tests/test_file_{file}.py"}
        for file in range(20)
        for case in range(3)
    ]


def receipts() -> list[dict]:
    items = baseline()
    return [
        {
            "schema": runner.SCHEMA,
            "suite": "sample",
            "shard": shard,
            "shards": 4,
            "commit": "authored",
            "baseline": items,
            "selected": chosen,
            "outcomes": {item["id"]: "passed" for item in chosen},
            "exit_code": 0,
        }
        for shard in range(4)
        for chosen in [runner.partition(items, shard, 4)]
    ]


def test_partition_is_exhaustive_preserves_files_order_and_assigns_new_tests() -> None:
    items = baseline()
    groups = [runner.partition(items, i, 4) for i in range(4)]
    assert sorted(x["id"] for group in groups for x in group) == sorted(x["id"] for x in items)
    for file in {item["file"] for item in items}:
        assert sum(any(item["file"] == file for item in group) for group in groups) == 1
        assert [x for x in groups[runner.slot(file, 4)] if x["file"] == file] == [
            x for x in items if x["file"] == file
        ]
    extra = {"id": "tests/test_new.py::test_added", "file": "tests/test_new.py"}
    assert sum(extra in runner.partition([*items, extra], i, 4) for i in range(4)) == 1
    assert runner.audit(receipts(), {"sample": 4}, "authored") == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-shard",
        "duplicate-shard",
        "missing-node",
        "missing-outcome",
        "extra-outcome",
        "failed",
        "wrong-commit",
        "wrong-count",
        "drift",
        "wrong-slot",
        "unknown-outcome",
        "empty-baseline",
    ],
)
def test_audit_rejects_planted_coverage_holes(mutation: str) -> None:
    rows = copy.deepcopy(receipts())
    report = next(r for r in rows if r["selected"])
    if mutation == "missing-shard":
        rows.pop()
    elif mutation == "duplicate-shard":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "missing-node":
        report["selected"].pop()
    elif mutation == "missing-outcome":
        report["outcomes"].pop(next(iter(report["outcomes"])))
    elif mutation == "extra-outcome":
        report["outcomes"]["unplanned"] = "passed"
    elif mutation == "failed":
        report["exit_code"] = 1
    elif mutation == "wrong-commit":
        report["commit"] = "other"
    elif mutation == "wrong-count":
        report["shards"] = 8
    elif mutation == "drift":
        report["baseline"].pop()
    elif mutation == "wrong-slot":
        report["shard"] = 9
    elif mutation == "unknown-outcome":
        report["outcomes"][next(iter(report["outcomes"]))] = "pending"
    elif mutation == "empty-baseline":
        for r in rows:
            r.update(baseline=[], selected=[], outcomes={})
    assert runner.audit(rows, {"sample": 4}, "authored")


def prepare(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = pytester.path / "isolated-gitconfig"
    config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    tools = pytester.path / "tools"
    tools.mkdir()
    for file in ("ci_receipt.py", "ci_tests.py"):
        shutil.copyfile(ROOT / "tools" / file, tools / file)
    subprocess.run(["git", "init", "-q", "--template="], cwd=pytester.path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fenolite test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "authored fixture",
        ],
        cwd=pytester.path,
        check=True,
    )
    monkeypatch.setattr(runner, "ROOT", pytester.path)
    return pytester.path


@pytest.mark.parametrize("workers", ["0", "2"])
def test_real_collection_and_outcomes_with_serial_and_xdist(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, workers: str
) -> None:
    root = prepare(pytester, monkeypatch)
    pytester.makepyfile(
        test_small="""
        import pytest
        STATE = []
        def test_first():
            STATE.append('first')
        def test_second():
            assert STATE == ['first']
        @pytest.mark.skip(reason='authored skip')
        def test_skip(): pass
    """
    )
    out = root / "evidence"
    assert runner.run("unit-ubuntu-latest-py3.12", 0, 1, out, workers) == 0
    receipt = json.loads((out / "receipt.json").read_text())
    assert runner.audit([receipt], {receipt["suite"]: 1}, receipt["commit"]) == []
    assert sorted(receipt["outcomes"].values()) == ["passed", "passed", "skipped"]
    assert (out / "junit.xml").is_file()


def test_mark_deselection_is_in_baseline_not_reported_as_omission(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = prepare(pytester, monkeypatch)
    (root / "tests/unit").mkdir(parents=True)
    for name in ("residue", "consistency", "fidelity"):
        (root / "tests" / name).mkdir()
    (root / "pytest.ini").write_text("[pytest]\nmarkers =\n needs_kicad\n needs_corpus\n needs_libs\n")
    (root / "tests/unit/test_marks.py").write_text(
        "import pytest\ndef test_kept(): pass\n@pytest.mark.needs_kicad\ndef test_native(): pass\n"
    )
    out = root / "evidence"
    assert runner.run("fast", 0, 1, out, "0") == 0
    receipt = json.loads((out / "receipt.json").read_text())
    assert len(receipt["baseline"]) == 1
    assert list(receipt["outcomes"]) == ["tests/unit/test_marks.py::test_kept"]


@pytest.mark.parametrize("host_config", ["", "[safe]\n\tdirectory = *\n"], ids=["normal", "wildcard"])
def test_container_owner_guard_retains_actual_head_without_global_git_changes(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, host_config: str
) -> None:
    host = pytester.path / "supplied-host-gitconfig"
    host.write_text(host_config)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(host))
    root = prepare(pytester, monkeypatch)
    pytester.makepyfile(test_small="def test_kept(): pass")
    expected = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
    monkeypatch.setenv("GITHUB_SHA", "unverified-environment-sha")
    blocked = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True)
    assert blocked.returncode != 0  # Git diagnostics may be localized on a maintainer's machine.
    out = root / "evidence"
    assert runner.run("unit-ubuntu-latest-py3.12", 0, 1, out, "0") == 0
    receipt = json.loads((out / "receipt.json").read_text())
    assert receipt["commit"] == expected
    assert runner.audit([receipt], {receipt["suite"]: 1}, expected) == []
    # The trust exception is scoped to that subprocess, not persisted for later Git calls.
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True).returncode != 0
    assert (root / "isolated-gitconfig").read_text() == ""
    assert host.read_text() == host_config


def test_collection_drift_refuses_execution_and_clears_old_receipt(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = prepare(pytester, monkeypatch)
    pytester.makepyfile(test_small="def test_kept(): pass\ndef test_removed(): pass")
    pytester.makeconftest("""
        import os
        def pytest_collection_modifyitems(items):
            if os.environ.get('CI_RECEIPT_MODE') == 'run':
                items.pop()
    """)
    out = root / "evidence"
    out.mkdir()
    (out / "receipt.json").write_text('{"old_success": true}')
    assert runner.run("unit-ubuntu-latest-py3.12", 0, 1, out, "0") != 0
    if (out / "receipt.json").exists():
        assert "old_success" not in json.loads((out / "receipt.json").read_text())


def test_collection_failure_does_not_preserve_a_success_receipt(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = prepare(pytester, monkeypatch)
    pytester.makepyfile(test_broken="raise RuntimeError('authored collection failure')")
    out = root / "evidence"
    out.mkdir()
    (out / "receipt.json").write_text('{"old_success": true}')
    (out / "junit.xml").write_text("stale success")
    assert runner.run("unit-ubuntu-latest-py3.12", 0, 1, out, "0") != 0
    assert not (out / "receipt.json").exists()
    assert not (out / "junit.xml").exists()


def test_real_four_shards_include_empty_receipts_and_every_new_file(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = prepare(pytester, monkeypatch)
    (root / "tests/kicad").mkdir(parents=True)
    (root / "tests/corpus").mkdir()
    names = [
        f"tests/kicad/test_file_{i}.py"
        for i in range(100)
        if runner.slot(f"tests/kicad/test_file_{i}.py", 4) == 0
    ][:2]
    for name in names:
        (root / name).write_text("def test_new(): pass\n")
    rows = []
    for shard in range(4):
        out = root / f"evidence-{shard}"
        assert runner.run("kicad-10", shard, 4, out, "0") == 0
        rows.append(json.loads((out / "receipt.json").read_text()))
    assert runner.audit(rows, {"kicad-10": 4}, rows[0]["commit"]) == []
    assert sum(bool(row["selected"]) for row in rows) == 1
    assert sum(len(row["outcomes"]) for row in rows) == 2


def test_full_suite_scopes_retain_the_prepartition_baselines() -> None:
    # These are the previously required workflow selections, not an affected-path allowlist.
    assert runner.selection("kicad-10") == []  # Native plus whole resource-bearing unit files.
    assert runner.selection("kicad-9") == ["tests/kicad"]
    assert runner.selection("mcp") == ["tests/unit/mcp", "tests/unit/cli/test_mcp_cmd.py"]
    assert runner.selection("viewer") == ["tests/visual"]
    for major in (9, 10):
        assert runner.selection(f"routing-{major}") == [
            "tests/routing",
            "tests/kicad/routing/test_external_candidates.py",  # c0368 pinned external candidates.
        ]
    units = [name for name in runner.FULL if name.startswith("unit-")]
    assert len(units) == 5
    assert all(runner.selection(name) == [] for name in units)


def test_implicit_last_failed_or_keyword_filter_cannot_shrink_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for value in ("--lf", "-k test_kept", "--ignore tests/corpus"):
        monkeypatch.setenv("PYTEST_ADDOPTS", value)
        (tmp_path / "receipt.json").write_text('{"old_success": true}')
        (tmp_path / "junit.xml").write_text("stale success")
        with pytest.raises(ValueError, match="PYTEST_ADDOPTS"):
            runner.run("kicad-10", 0, 4, tmp_path, "0")
        assert not (tmp_path / "receipt.json").exists()
        assert not (tmp_path / "junit.xml").exists()
    assert not (tmp_path / "receipt.json").exists()


def resource_reports(omit: str = "") -> list[dict]:
    suite = "unit-ubuntu-latest-py3.12"
    items = [
        {"id": "tests/kicad/test_core.py::test_core", "file": "tests/kicad/test_core.py", "resources": []},
        {"id": "tests/unit/test_extra.py::test_prepare", "file": "tests/unit/test_extra.py", "resources": []},
        {
            "id": "tests/unit/test_extra.py::test_required",
            "file": "tests/unit/test_extra.py",
            "resources": ["needs_corpus"],
        },
    ]
    native = [
        i
        for i in items
        if not (omit == "file" and i["file"].startswith("tests/unit/"))
        and not (omit == "neighbor" and i["id"].endswith("test_prepare"))
    ]
    rows = [
        {
            "schema": runner.SCHEMA,
            "suite": suite,
            "shard": 0,
            "shards": 1,
            "commit": "authored",
            "baseline": items,
            "selected": items,
            "outcomes": {i["id"]: "skipped" if i["resources"] else "passed" for i in items},
            "exit_code": 0,
        }
    ]
    for shard in range(4):
        chosen = runner.partition(native, shard, 4)
        rows.append(
            {
                "schema": runner.SCHEMA,
                "suite": "kicad-10",
                "shard": shard,
                "shards": 4,
                "commit": "authored",
                "baseline": native,
                "selected": chosen,
                "outcomes": {i["id"]: "passed" for i in chosen},
                "exit_code": 0,
            }
        )
    return rows


@pytest.mark.parametrize("omitted", ["", "file", "neighbor", "native-skip", "metadata"])
def test_unit_inventory_independently_requires_native_resource_coverage(omitted: str) -> None:
    rows = resource_reports(omitted)
    if omitted == "native-skip":
        for row in rows[1:]:
            for node in row["outcomes"]:
                if node.endswith("test_required"):
                    row["outcomes"][node] = "skipped"
    if omitted == "metadata":
        # Keep all unit/native node ids and outcomes intact; only erase the independent metadata.
        rows[0] = copy.deepcopy(rows[0])
        for item in rows[0]["baseline"]:
            item.pop("resources")
    problems = runner.audit(rows, {"unit-ubuntu-latest-py3.12": 1, "kicad-10": 4}, "authored")
    assert bool(problems) == bool(omitted)
    if omitted:
        assert any("resource" in problem for problem in problems)


def test_real_native_shards_cover_resource_unit_files_and_preserve_unmarked_state(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = prepare(pytester, monkeypatch)
    pytester.makeini(
        "[pytest]\ntestpaths = tests\naddopts = --import-mode=importlib\n"
        "markers =\n needs_kicad\n needs_corpus\n needs_libs\n"
    )
    for name in ("kicad", "corpus", "unit"):
        (root / "tests" / name).mkdir(parents=True)
    for name in ("kicad", "corpus"):
        (root / "tests" / name / "test_kept.py").write_text("def test_native(): pass\n")
    (root / "tests/unit/test_plain.py").write_text(
        "import os\ndef test_plain():\n assert os.environ.get('CI_RECEIPT_SUITE') != 'kicad-10'\n"
    )
    (root / "tests/unit/test_new_resource.py").write_text(
        "import pytest\nSTATE = []\ndef test_prepare(): STATE.append('ready')\n"
        + "\n".join(
            f"@pytest.mark.{marker}\ndef test_{marker}(): assert STATE == ['ready']\n"
            for marker in ("needs_kicad", "needs_corpus", "needs_libs")
        )
    )
    rows = []
    for suite, count in (("unit-ubuntu-latest-py3.12", 1), ("kicad-10", 4)):
        for shard in range(count):
            out = root / f"evidence-{suite}-{shard}"
            assert runner.run(suite, shard, count, out, "2") == 0
            rows.append(json.loads((out / "receipt.json").read_text()))
    native = next(row for row in rows if row["suite"] == "kicad-10")
    assert len(native["baseline"]) == 6  # Two native cases and the entire four-case unit file.
    assert {m for i in native["baseline"] for m in i["resources"]} == {
        "needs_kicad",
        "needs_corpus",
        "needs_libs",
    }
    assert runner.audit(rows, {"unit-ubuntu-latest-py3.12": 1, "kicad-10": 4}, rows[0]["commit"]) == []


@pytest.mark.parametrize(("workers", "priority_enabled"), [("1", True), ("1", False), ("0", True)])
def test_locked_loadfile_priority_is_effective_and_preserves_case_order(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, workers: str, priority_enabled: bool
) -> None:
    root = prepare(pytester, monkeypatch)
    pytester.makeini("[pytest]\ntestpaths = tests\naddopts = --import-mode=importlib\n")
    early = "tests/unit/roles/test_proposal_reference.py"
    (root / early).parent.mkdir(parents=True)
    (root / early).write_text(
        "STATE = []\ndef test_prepare(): STATE.append('ready')\ndef test_case(): assert STATE == ['ready']\n"
    )
    wide = "tests/unit/a/test_wide.py"
    (root / wide).parent.mkdir(parents=True)
    (root / wide).write_text(
        "import pytest\n@pytest.mark.parametrize('n', range(6))\ndef test_wide(n): assert n >= 0\n"
    )
    if not priority_enabled:
        call = runner.subprocess.call

        def original_count_order(command: list[str], **kwargs: Any) -> int:
            return call([arg for arg in command if arg != "--no-loadscope-reorder"], **kwargs)

        monkeypatch.setattr(runner.subprocess, "call", original_count_order)
    out = root / "evidence"
    assert runner.run("unit-ubuntu-latest-py3.12", 0, 1, out, workers) == 0
    receipt = json.loads((out / "receipt.json").read_text())
    first = next(iter(receipt["outcomes"]))
    assert first.startswith(early if priority_enabled and workers != "0" else wide)
    if workers == "0":
        assert list(receipt["outcomes"]) == [item["id"] for item in receipt["baseline"]]
    assert len(receipt["outcomes"]) == 8
    assert runner.audit([receipt], {receipt["suite"]: 1}, receipt["commit"]) == []
