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
ALLOWED_EXTRAS = {"geo", "kicad-ipc", "route", "mcp", "dev", "oracles"}


def _project() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]


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
