# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parallel test runs (capability ci-baseline: "Parallel test runs", "Local parity", "Fast local check",
"Working rule for parallel worktrees"): the make targets, the write-mode guard and the outcome comparison."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
MAKEFILE = ROOT / "Makefile"
WRITE_VARIABLES = (
    "FENOLITE_PROBES_WRITE",
    "FENOLITE_GOLDEN_WRITE",
    "FENOLITE_CENSUS_OUT",
    "FENOLITE_CHECK_EVIDENCE",
)
FAST_MARKERS = '-m "not needs_kicad and not needs_corpus and not needs_libs"'


def _target(name: str) -> tuple[str, str]:
    """The prerequisites and the recipe of one Makefile target."""
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(name)}:(.*)\n((?:\t.*\n)*)", text, re.MULTILINE)
    assert match, f"Makefile: target {name!r} missing"
    return match.group(1).strip(), match.group(2)


def _variable(name: str) -> str:
    match = re.search(rf"^{name} \?= (.*)$", MAKEFILE.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"Makefile: variable {name} missing"
    return match.group(1).strip()


def test_check_runs_every_gate_in_parallel() -> None:
    needs, _ = _target("check")
    assert needs.split() == ["lint", "format", "types", "residue", "test"]
    _, recipe = _target("test")
    assert recipe.strip() == "uv run pytest -q $(PYTEST_PARALLEL)"


def test_check_fast_needs_no_external_resource() -> None:
    needs, _ = _target("check-fast")
    assert needs.split() == ["lint", "format", "types", "residue", "test-fast"]
    _, recipe = _target("test-fast")
    assert recipe.strip() == (
        f"uv run pytest tests/unit tests/residue tests/consistency -q $(PYTEST_PARALLEL) {FAST_MARKERS}"
    )


def test_worker_count_is_capped() -> None:
    assert _variable("PYTEST_WORKERS") == "auto"
    assert 2 <= int(_variable("PYTEST_MAX_WORKERS")) <= 16
    parallel = _variable("PYTEST_PARALLEL")
    assert parallel == "-n $(PYTEST_WORKERS) --maxprocesses $(PYTEST_MAX_WORKERS) --dist loadfile"


def test_plain_pytest_stays_serial() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (addopts,) = re.findall(r"^addopts = (.*)$", text, re.MULTILINE)
    assert "-n" not in addopts.split() and "--dist" not in addopts and "numprocesses" not in addopts


def test_documents_state_the_working_rule() -> None:
    for name in ("AGENTS.md", "CONTRIBUTING.md"):
        text = " ".join((ROOT / name).read_text(encoding="utf-8").split())
        assert "make check-fast" in text and "make check" in text.replace("make check-fast", ""), name
        assert "several full suites" in text, name
    assert "## Parallel worktrees" in (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")


@pytest.fixture
def project(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    """A pytester project with Fenolite's conftest and two passing tests; no write mode is on."""
    pytester.makeini("[pytest]\nmarkers =\n    needs_kicad: x\n    needs_corpus: x\n    needs_libs: x\n")
    pytester.makeconftest((TESTS / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile(_resources=(TESTS / "_resources.py").read_text(encoding="utf-8"))
    pytester.makepyfile(test_two="def test_one():\n    pass\n\n\ndef test_two():\n    pass\n")
    for name in WRITE_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    return pytester


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("FENOLITE_PROBES_WRITE", "1"),
        ("FENOLITE_GOLDEN_WRITE", "1"),
        ("FENOLITE_CENSUS_OUT", "census.json"),
        ("FENOLITE_CHECK_EVIDENCE", "evidence.jsonl"),
    ],
)
def test_write_mode_refused_in_a_parallel_run(
    project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    result = project.runpytest_subprocess("-p", "no:cacheprovider", "-n", "2")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines([f"*{name} writes shared files and needs a serial run: drop -n*"])
    serial = project.runpytest_subprocess("-p", "no:cacheprovider")
    serial.assert_outcomes(passed=2)


def test_parallel_run_without_a_write_mode(project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_PROBES_WRITE", "0")  # only "1" turns the mode on
    result = project.runpytest_subprocess("-p", "no:cacheprovider", "-n", "2", "--dist", "loadfile")
    result.assert_outcomes(passed=2)
    assert result.ret == 0


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("test_outcomes", ROOT / "tools" / "test_outcomes.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _junit(path: Path, cases: dict[str, str]) -> Path:
    body = ""
    for name, outcome in cases.items():
        child = "" if outcome == "passed" else f'<{outcome} message="m"/>'
        body += f'<testcase classname="tests.unit.test_x" name="{name}" time="0.1">{child}</testcase>'
    path.write_text(f'<testsuites><testsuite name="pytest">{body}</testsuite></testsuites>', encoding="utf-8")
    return path


def test_equal_runs_compare_equal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cases = {"test_a": "passed", "test_b": "skipped", "test_c[1]": "passed"}
    first = _junit(tmp_path / "serial.xml", cases)
    second = _junit(tmp_path / "parallel.xml", dict(reversed(cases.items())))  # the order never matters
    assert _tool().main([str(first), str(second)]) == 0
    out = capsys.readouterr().out
    assert "serial.xml: 3 tests: 2 passed, 1 skipped" in out and "differences: 0" in out


def test_differences_are_named(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    first = _junit(tmp_path / "serial.xml", {"test_a": "passed", "test_b": "skipped", "test_c": "passed"})
    second = _junit(tmp_path / "parallel.xml", {"test_a": "failure", "test_b": "skipped"})
    assert _tool().main([str(first), str(second)]) == 1
    out = capsys.readouterr().out
    assert "tests.unit.test_x::test_a: passed -> failure" in out
    assert "tests.unit.test_x::test_c: passed -> absent" in out and "differences: 2" in out


def test_unreadable_file_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = _junit(tmp_path / "serial.xml", {"test_a": "passed"})
    assert _tool().main([str(good), str(tmp_path / "missing.xml")]) == 2
    assert "cannot read" in capsys.readouterr().err
