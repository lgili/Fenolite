# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Light feedback excludes whole integration files; complete collection keeps prerequisites."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("light_runner", ROOT / "tools/ci_tests.py")
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_light_and_full_collection_keep_file_prerequisites(pytester):
    pytester.makeini("[pytest]\nmarkers =\n long_flow: complete board flow\n")
    pytester.makepyfile(
        test_light="def test_model(): assert True",
        test_flow="""import pytest
pytestmark = pytest.mark.long_flow
seen = []
def test_prepare(): seen.append(1)
def test_consume(): assert seen == [1]
""",
    )
    expression = runner.selection("fast")[-1]
    light = pytester.runpytest("--collect-only", "-q", "-m", expression)
    assert light.ret == 0
    light.stdout.fnmatch_lines(["*test_light.py::test_model*", "*1/3 tests collected*"])
    assert "test_flow.py::" not in light.stdout.str()
    full = pytester.runpytest("-q")
    full.assert_outcomes(passed=3)
    assert runner.selection("unit-ubuntu-latest-py3.12") == []


def test_light_audit_requires_three_exact_commit_partitions():
    items = [{"id": f"test_{i}.py::test_model", "file": f"test_{i}.py"} for i in range(20)]
    reports = [
        {
            "schema": runner.SCHEMA,
            "suite": "fast",
            "shard": shard,
            "shards": 3,
            "commit": "authored",
            "baseline": items,
            "selected": chosen,
            "outcomes": {item["id"]: "passed" for item in chosen},
            "exit_code": 0,
        }
        for shard in range(3)
        for chosen in [runner.partition(items, shard, 3)]
    ]
    assert runner.audit(reports, {"fast": 3}, "authored") == []
    assert runner.audit(reports[:1], {"fast": 3}, "authored")
    assert runner.audit([*reports, reports[0]], {"fast": 3}, "authored")
    assert runner.audit(reports, {"fast": 3}, "different")
    reports[0]["exit_code"] = 1
    assert runner.audit(reports, {"fast": 3}, "authored")


def test_light_workflow_requires_partition_audit_and_gate():
    import importlib.util

    policy_spec = importlib.util.spec_from_file_location("light_policy", ROOT / "tools/ci_profiles.py")
    assert policy_spec and policy_spec.loader
    policy = importlib.util.module_from_spec(policy_spec)
    policy_spec.loader.exec_module(policy)
    jobs = ("plan", "quality", "dco", "fast", "fast-audit")
    needs = {job: {"result": "success"} for job in jobs}
    assert policy.gate("fast", "fast", needs) == []
    for job in jobs:
        assert policy.gate("fast", "fast", {key: val for key, val in needs.items() if key != job})
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    fast = text.split("  fast:\n")[1].split("  unit:\n")[0]
    assert "shard: [0, 1, 2]" in fast
    assert "needs: [plan]" in fast
    assert "needs: [plan, quality]" not in fast
    assert "--suite fast --shard ${{ matrix.shard }} --shards 3" in fast
    assert "pattern: ci-fast-tests-*" in fast
    assert 'audit ci-fast-receipts --fast --commit "$GITHUB_SHA"' in fast
    assert "needs: [plan, quality, dco, fast, fast-audit]" in text
