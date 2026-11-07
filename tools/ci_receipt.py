# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Opt-in pytest inventory/outcome instrumentation for tools/ci_tests.py (c0380)."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

RESOURCE_MARKERS = ("needs_kicad", "needs_corpus", "needs_libs")
EARLY_FILES = (
    "tests/unit/roles/test_proposal_reference.py",
    "tests/unit/cli/test_route_propose.py",
    "tests/unit/backends/altium/test_lower_build_spec.py",
)
"""Authored Fenolite whole-file cost evidence in docs/ci.md; never an inclusion/exclusion list."""


def write(path: str, value: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class Receipt:
    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.mode = os.environ["CI_RECEIPT_MODE"]
        self.collection: list[dict] = []
        self.outcomes: dict[str, str] = {}
        self.plan = json.loads(Path(os.environ["CI_RECEIPT_PLAN"]).read_text(encoding="utf-8"))

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        if self.mode == "collect" and os.environ.get("CI_RECEIPT_SUITE") == "kicad-10":
            # Keep whole resource-bearing unit files: selecting marked cases alone could omit
            # an earlier unmarked case that establishes state allowed by the loadfile contract.
            resource_files = {
                item.path for item in items if any(item.get_closest_marker(m) for m in RESOURCE_MARKERS)
            }
            kept, omitted = [], []
            for item in items:
                file = item.path.relative_to(self.config.rootpath).as_posix()
                native = file.startswith(("tests/kicad/", "tests/corpus/"))
                unit_resource = file.startswith("tests/unit/") and item.path in resource_files
                (kept if native or unit_resource else omitted).append(item)
            items[:] = kept
            self.config.hook.pytest_deselected(items=omitted)
        self.collection = [
            {
                "id": item.nodeid,
                "file": item.path.relative_to(self.config.rootpath).as_posix(),
                "resources": [m for m in RESOURCE_MARKERS if item.get_closest_marker(m)],
            }
            for item in items
        ]
        if self.mode == "run":
            actual: dict[str, list[str]] = defaultdict(list)
            expected: dict[str, list[str]] = defaultdict(list)
            for item in self.collection:
                actual[item["file"]].append(item["id"])
            for item in self.plan["selected"]:
                expected[item["file"]].append(item["id"])
            if actual != expected:
                raise pytest.UsageError("CI execution collection differs from its planned file inventory")
            if hasattr(self.config, "workerinput"):
                # Locked xdist loadfile inherits loadscope's ordering option; the live one-worker
                # regression protects this behavior. Serial jobs retain the original collection.
                groups: dict[str, list[pytest.Item]] = defaultdict(list)
                for item in items:
                    groups[item.path.relative_to(self.config.rootpath).as_posix()].append(item)
                rank = {file: n for n, file in enumerate(EARLY_FILES)}
                ordered = sorted(groups, key=lambda f: (rank.get(f, len(rank)), -len(groups[f])))
                items[:] = [item for file in ordered for item in groups[file]]

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # The controller receives xdist reports too. Setup skips/errors are terminal without a call.
        if report.failed:
            self.outcomes[report.nodeid] = "failed"
        elif report.skipped and self.outcomes.get(report.nodeid) != "failed":
            self.outcomes[report.nodeid] = "skipped"
        elif report.when == "call" and report.passed and report.nodeid not in self.outcomes:
            self.outcomes[report.nodeid] = "passed"

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if hasattr(self.config, "workerinput"):
            return  # Workers never share a report writer; the controller observes all terminal outcomes.
        if self.mode == "collect":
            write(os.environ["CI_RECEIPT_OUT"], {"items": self.collection, "exit_code": int(exitstatus)})
        else:
            expected = {item["id"] for item in self.plan["selected"]}
            valid = set(self.outcomes) == expected and all(v != "failed" for v in self.outcomes.values())
            if not valid and exitstatus == 0:
                session.exitstatus = pytest.ExitCode.TESTS_FAILED
            write(
                os.environ["CI_RECEIPT_OUT"],
                {
                    **self.plan,
                    "outcomes": self.outcomes,
                    "exit_code": int(session.exitstatus),
                },
            )


def pytest_configure(config: pytest.Config) -> None:
    if os.environ.get("CI_RECEIPT_MODE") in {"collect", "run"}:
        config.pluginmanager.register(Receipt(config), "fenolite-ci-receipt")
