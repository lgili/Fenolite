# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Invariants of pyproject.toml that keep the core stdlib-only and the extras closed."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path
from typing import Any

import fenolite

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_EXTRAS = {"geo", "kicad-ipc", "mcp", "dev", "oracles"}


REPOSITORY = "https://github.com/lgili/Fenolite"
URLS = {
    "Homepage": REPOSITORY,
    "Source": REPOSITORY,
    "Issues": f"{REPOSITORY}/issues",
    "Changelog": f"{REPOSITORY}/blob/main/CHANGELOG.md",
}
STATUS = "Development Status :: 3 - Alpha"


def _pyproject() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _project() -> dict[str, Any]:
    return _pyproject()["project"]


def metadata_problems(project: dict[str, Any]) -> list[str]:
    """One message per problem of ``[project.urls]`` and of the status classifier (repo-layout,
    "Package metadata")."""
    problems: list[str] = []
    urls: dict[str, str] = project.get("urls", {})
    for key, wanted in URLS.items():
        if key not in urls:
            problems.append(f"[project.urls] has no {key}")
        elif urls[key] != wanted:
            problems.append(f"[project.urls] {key} is {urls[key]!r}, expected {wanted!r}")
    problems += [f"[project.urls] has the unknown key {key}" for key in sorted(set(urls) - set(URLS))]
    status = [c for c in project.get("classifiers", []) if c.startswith("Development Status ::")]
    if status != [STATUS]:
        problems.append(f"the status classifiers are {status}, expected [{STATUS!r}]")
    return problems


SDIST_INCLUDE = [
    "/src",
    "/tests",
    "/docs",
    "/examples",
    "/schemas",
    "/tools",
    "/README.md",
    "/CHANGELOG.md",
    "/CONTRIBUTING.md",
    "/LEGAL.md",
    "/LEGAL-ANNEX.md",
    "/LICENSE",
    "/NOTICE",
]


def sdist_problems(table: dict[str, Any]) -> list[str]:
    """One message per problem of ``[tool.hatch.build.targets.sdist]`` (repo-layout, "Source distribution
    contents"): the table is an allowlist with exactly the entries of ``SDIST_INCLUDE``."""
    problems: list[str] = []
    if "exclude" in table:
        problems.append("the sdist table has an exclude list; it must be an allowlist only")
    include: list[str] = table.get("include", [])
    problems += [f"the sdist allowlist holds {entry}" for entry in include if entry not in SDIST_INCLUDE]
    problems += [f"the sdist allowlist lacks {entry}" for entry in SDIST_INCLUDE if entry not in include]
    return problems


def _sdist() -> dict[str, Any]:
    return _pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]


def test_core_has_no_runtime_dependencies() -> None:
    deps = _project().get("dependencies")
    assert deps == [], f"runtime dependencies are forbidden in the core, found: {deps}"


def test_extras_are_the_closed_list() -> None:
    extras = set(_project().get("optional-dependencies", {}))
    unknown = extras - ALLOWED_EXTRAS
    missing = ALLOWED_EXTRAS - extras
    assert not unknown, f"unknown extras: {sorted(unknown)}"
    assert not missing, f"missing extras: {sorted(missing)}"


def test_python_floor_and_entry_point() -> None:
    project = _project()
    assert project["requires-python"] == ">=3.11"
    assert project["scripts"] == {"fenolite": "fenolite.cli.main:main"}


def test_licence_metadata() -> None:
    project = _project()
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE", "NOTICE"]


def test_version_is_single_sourced() -> None:
    assert "version" in _project()["dynamic"]
    assert importlib.metadata.version("fenolite") == fenolite.__version__


def test_alias_distribution_tracks_fenolite() -> None:
    alias_dir = ROOT / "packaging" / "phenolite"
    with (alias_dir / "pyproject.toml").open("rb") as fh:
        alias = tomllib.load(fh)["project"]
    assert alias["name"] == "phenolite"
    assert alias["version"] == fenolite.__version__, "bump packaging/phenolite with fenolite"
    assert alias["dependencies"] == [f"fenolite=={fenolite.__version__}"]
    assert (alias_dir / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()


def test_urls_and_classifier() -> None:
    assert metadata_problems(_project()) == []


def test_urls_problems_are_named() -> None:
    project = _project()
    missing = {**project, "urls": {k: v for k, v in URLS.items() if k != "Issues"}}
    assert metadata_problems(missing) == ["[project.urls] has no Issues"]
    elsewhere = {**project, "urls": {**URLS, "Source": "https://example.org/fenolite"}}
    assert len(metadata_problems(elsewhere)) == 1 and "Source" in metadata_problems(elsewhere)[0]
    extra = {**project, "urls": {**URLS, "Docs": REPOSITORY}}
    assert metadata_problems(extra) == ["[project.urls] has the unknown key Docs"]
    assert len(metadata_problems({**project, "urls": {}})) == len(URLS)


def test_classifier_problems_are_named() -> None:
    project = _project()
    others = [c for c in project["classifiers"] if not c.startswith("Development Status ::")]
    old = {**project, "classifiers": ["Development Status :: 2 - Pre-Alpha", *others]}
    assert len(metadata_problems(old)) == 1 and "2 - Pre-Alpha" in metadata_problems(old)[0]
    assert len(metadata_problems({**project, "classifiers": others})) == 1
    assert len(metadata_problems({**project, "classifiers": [STATUS, STATUS, *others]})) == 1


def test_sdist_is_the_allowlist() -> None:
    assert sdist_problems(_sdist()) == []
    assert all((ROOT / entry.lstrip("/")).exists() for entry in SDIST_INCLUDE)


def test_sdist_problems_are_named() -> None:
    table = _sdist()
    assert len(sdist_problems({**table, "exclude": ["/private"]})) == 1
    widened = sdist_problems({**table, "include": [*SDIST_INCLUDE, "/openspec"]})
    assert widened == ["the sdist allowlist holds /openspec"]
    assert sdist_problems({"include": SDIST_INCLUDE[1:]}) == ["the sdist allowlist lacks /src"]
    assert len(sdist_problems({})) == len(SDIST_INCLUDE)
