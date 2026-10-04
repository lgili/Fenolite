# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Required-resource mode (capability ci-baseline): FENOLITE_REQUIRE turns skips into failures."""

from __future__ import annotations

from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
MARKERS = """[pytest]
markers =
    needs_kicad: requires kicad-cli
    needs_corpus: requires the corpus
    needs_libs: requires the KiCad libraries
    needs_router: requires the KiCadRoutingTools checkout and interpreter
    needs_freerouting: requires the Freerouting jar
"""


def _project(pytester: pytest.Pytester) -> None:
    pytester.makeini(MARKERS)
    pytester.makeconftest((TESTS / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile(_resources=(TESTS / "_resources.py").read_text(encoding="utf-8"))
    pytester.makepyfile(
        test_needs="""
import pytest

@pytest.mark.needs_kicad
def test_kicad():
    pass

@pytest.mark.needs_corpus
def test_corpus():
    pass
"""
    )


def test_missing_kicad_cli_fails_when_required(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    _project(pytester)
    monkeypatch.setenv("FENOLITE_REQUIRE", "kicad")
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(pytester.path / "missing-kicad-cli"))
    monkeypatch.setenv("FENOLITE_CORPUS_CACHE", str(pytester.path / "no-cache"))
    result = pytester.runpytest("-p", "no:cacheprovider", "-rA")
    result.assert_outcomes(errors=1, skipped=1)  # a setup failure: the run fails
    result.stdout.fnmatch_lines(["*kicad-cli not found*"])
    assert result.ret != 0


def test_missing_corpus_fails_when_required(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    _project(pytester)
    monkeypatch.setenv("FENOLITE_REQUIRE", "kicad, corpus")
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(pytester.path / "missing-kicad-cli"))
    monkeypatch.setenv("FENOLITE_CORPUS_CACHE", str(pytester.path / "no-cache"))
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(errors=2)
    assert result.ret != 0


def test_default_remains_skip(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    _project(pytester)
    monkeypatch.delenv("FENOLITE_REQUIRE", raising=False)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(pytester.path / "missing-kicad-cli"))
    monkeypatch.setenv("FENOLITE_CORPUS_CACHE", str(pytester.path / "no-cache"))
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(skipped=2)
    assert result.ret == 0


def test_missing_router_fails_when_required(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    _project(pytester)
    pytester.makepyfile(
        test_router="""
import pytest

@pytest.mark.needs_router
def test_router():
    pass
"""
    )
    monkeypatch.setenv("FENOLITE_REQUIRE", "router")
    monkeypatch.setenv("FENOLITE_KRT", str(pytester.path / "missing-router"))
    monkeypatch.setenv("FENOLITE_KRT_PYTHON", str(pytester.path / "missing-python"))
    empty_path = pytester.path / "empty-path"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(pytester.path / "missing-kicad-cli"))
    result = pytester.runpytest("-p", "no:cacheprovider", "-p", "no:textual-snapshot", "-rA")
    result.assert_outcomes(errors=1, skipped=2)
    result.stdout.fnmatch_lines(["*KiCadRoutingTools not found*"])
    assert result.ret != 0


def _freerouting_project(pytester: pytest.Pytester) -> None:
    pytester.makeini(MARKERS)
    pytester.makeconftest((TESTS / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile(_resources=(TESTS / "_resources.py").read_text(encoding="utf-8"))
    pytester.makepyfile(
        test_needs="""
import pytest

@pytest.mark.needs_freerouting
def test_router():
    pass
"""
    )


def test_freerouting_skips_without_the_variable(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Capability ci-baseline, "Freerouting in the routing job": the skip names the variable."""
    _freerouting_project(pytester)
    monkeypatch.delenv("FENOLITE_REQUIRE", raising=False)
    monkeypatch.delenv("FENOLITE_FREEROUTING_JAR", raising=False)
    result = pytester.runpytest("-p", "no:cacheprovider", "-rs")
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*FENOLITE_FREEROUTING_JAR*"])
    assert result.ret == 0


def test_missing_freerouting_fails_when_required(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freerouting_project(pytester)
    monkeypatch.setenv("FENOLITE_REQUIRE", "freerouting")
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(pytester.path / "missing.jar"))
    result = pytester.runpytest("-p", "no:cacheprovider", "-rA")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*FENOLITE_FREEROUTING_JAR*"])
    assert result.ret != 0


def test_freerouting_runs_with_a_jar(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    _freerouting_project(pytester)
    jar = pytester.path / "freerouting.jar"
    jar.write_bytes(b"")
    monkeypatch.setenv("FENOLITE_REQUIRE", "freerouting")
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(jar))
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)
