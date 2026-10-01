# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``needs_libs`` skip rule (capability corpus-policy, modified requirement "Skip markers")."""

from __future__ import annotations

from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
MARKERS = """[pytest]
markers =
    needs_kicad: requires kicad-cli
    needs_corpus: requires the corpus
    needs_libs: requires the KiCad libraries
"""
LIB_VARIABLES = (
    "KICAD10_FOOTPRINT_DIR",
    "KICAD10_SYMBOL_DIR",
    "KICAD10_3DMODEL_DIR",
    "KICAD9_FOOTPRINT_DIR",
    "KICAD9_SYMBOL_DIR",
    "KICAD9_3DMODEL_DIR",
)


@pytest.fixture
def project(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    """A pytester project with Fenolite's conftest, one ``needs_libs`` test and no library source."""
    pytester.makeini(MARKERS)
    pytester.makeconftest((TESTS / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile(_resources=(TESTS / "_resources.py").read_text(encoding="utf-8"))
    pytester.makepyfile(
        test_libs="""
import pytest

@pytest.mark.needs_libs
def test_libs():
    pass
"""
    )
    for name in LIB_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("FENOLITE_REQUIRE", raising=False)
    monkeypatch.setenv("FENOLITE_KICAD_INSTALL_DIR", str(pytester.path / "no-install"))
    return pytester


def test_no_library_source_skips(project: pytest.Pytester) -> None:
    result = project.runpytest("-p", "no:cacheprovider", "-rs")
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*KICAD10_FOOTPRINT_DIR and KICAD10_SYMBOL_DIR*install KiCad*"])
    assert result.ret == 0


def test_required_libraries_missing_fail(project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_REQUIRE", "libs")
    result = project.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*KICAD10_FOOTPRINT_DIR and KICAD10_SYMBOL_DIR*install KiCad*"])
    assert result.ret != 0


@pytest.mark.parametrize("variable", ["KICAD10_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"])
def test_variables_select_the_source(
    project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    folder = project.mkdir("libs")
    monkeypatch.setenv(variable, str(folder))
    project.runpytest("-p", "no:cacheprovider").assert_outcomes(passed=1)


def test_variable_naming_a_missing_folder_is_no_source(
    project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KICAD10_FOOTPRINT_DIR", str(project.path / "absent"))
    project.runpytest("-p", "no:cacheprovider").assert_outcomes(skipped=1)


def test_install_dir_override(project: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    install = project.mkdir("install")
    (install / "symbols").mkdir()
    monkeypatch.setenv("FENOLITE_KICAD_INSTALL_DIR", str(install))
    project.runpytest("-p", "no:cacheprovider").assert_outcomes(passed=1)
