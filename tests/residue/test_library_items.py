# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library items stay out of the tool repository (capability corpus-policy, "Library items in the corpus";
change c0279). Third-party material lives only in fenolite-library: no vendored ``fenolite_library/`` folder
and no ``PROVENANCE.json`` of a converted or seeded item is tracked under ``tests/``, ``examples/`` or
``src/``, unless ``tests/data/MANIFEST.toml`` declares the file authored for Fenolite (the demo library
fixture)."""

from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Iterable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOPS = ("tests/", "examples/", "src/")
VENDORED = "fenolite_library"
SCHEMA = "fenolite.provenance.v0"


def library_reports(paths: Iterable[str], root: Path, authored: set[str]) -> list[str]:
    """``<path>: <why>`` for each tracked path (POSIX, relative to ``root``) that is a library item."""
    reports: list[str] = []
    for rel in sorted(paths):
        if not rel.startswith(TOPS) or rel in authored:
            continue
        if VENDORED in rel.split("/")[:-1]:
            reports.append(f"{rel}: a vendored {VENDORED}/ folder is committed")
            continue
        if Path(rel).name != "PROVENANCE.json":
            continue
        try:
            data = json.loads((root / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            isinstance(data, dict)
            and data.get("schema") == SCHEMA
            and data.get("origin") in ("converted", "seeded")
        ):
            reports.append(f"{rel}: the provenance of a {data['origin']} library item is committed")
    return reports


def _authored(root: Path) -> set[str]:
    data = tomllib.loads((root / "tests" / "data" / "MANIFEST.toml").read_text(encoding="utf-8"))
    return {str(row["path"]) for row in data.get("file", []) if row.get("origin") == "authored"}


def test_no_library_item_is_tracked() -> None:
    try:
        done = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git is not available")
    names = [name for name in done.stdout.decode("utf-8").split("\0") if name]
    assert library_reports(names, ROOT, _authored(ROOT)) == []


def test_vendored_item_committed(tmp_path: Path) -> None:
    """Scenario "Vendored item committed"."""
    rel = "examples/x/fenolite_library/devices/Demo/EXB/PROVENANCE.json"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema": SCHEMA, "origin": "converted"}), encoding="utf-8")
    reports = library_reports([rel], tmp_path, set())
    assert reports and reports[0].startswith(rel)
    loose = "tests/data/x/PROVENANCE.json"
    (tmp_path / loose).parent.mkdir(parents=True)
    (tmp_path / loose).write_text(json.dumps({"schema": SCHEMA, "origin": "seeded"}), encoding="utf-8")
    assert library_reports([loose], tmp_path, set()) and library_reports([loose], tmp_path, {loose}) == []
