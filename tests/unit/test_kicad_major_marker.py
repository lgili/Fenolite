# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kicad_min_major marker (capability kicad-oracle): an older major skips, never fails."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
INI = """[pytest]
markers =
    needs_kicad: requires kicad-cli
    needs_corpus: requires the corpus
    needs_libs: requires the KiCad libraries
    kicad_min_major(n): minimum kicad-cli major
"""


def _fake_cli(directory: Path, version: str) -> Path:
    cli = directory / "kicad-cli"
    cli.write_text(f"#!/bin/sh\necho {version}\n")
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    return cli


def _project(pytester: pytest.Pytester) -> None:
    pytester.makeini(INI)
    pytester.makeconftest((TESTS / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile(_resources=(TESTS / "_resources.py").read_text(encoding="utf-8"))
    pytester.makepyfile(
        test_major="""
import pytest

@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
def test_upgrade():
    pass

@pytest.mark.needs_kicad
def test_any_major():
    pass
"""
    )


def test_older_major_skips_in_required_mode(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    _project(pytester)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(_fake_cli(pytester.path, "9.0.9")))
    monkeypatch.setenv("FENOLITE_REQUIRE", "kicad")
    result = pytester.runpytest("-p", "no:cacheprovider", "-rs")
    result.assert_outcomes(passed=1, skipped=1)
    result.stdout.fnmatch_lines(["*needs kicad-cli 10.x; running 9.x*"])
    assert result.ret == 0


def test_newer_major_runs(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    _project(pytester)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(_fake_cli(pytester.path, "10.0.6")))
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(passed=2)
