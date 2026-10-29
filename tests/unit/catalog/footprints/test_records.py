# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored package records of ``tests/data/packages`` (change c0260, task 1.3): each opens with the
authored-for-Fenolite line and cites sources registered in both evidence registers."""

from __future__ import annotations

from pathlib import Path

import pytest
from _package_records import PACKAGES, RECORDS, raw_record

ROOT = PACKAGES.parents[2]


def _source_ids() -> set[str]:
    text = (ROOT / "docs" / "evidence" / "sources.md").read_text(encoding="utf-8")
    return {line.split("|")[1].strip() for line in text.splitlines() if line.startswith("| S-")}


@pytest.mark.parametrize("stem", RECORDS)
def test_record_sources_are_registered(stem: str) -> None:
    path = PACKAGES / f"{stem}.toml"
    first = path.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("# Authored for Fenolite (CC0-1.0)."), path
    raw = raw_record(stem)
    sources = raw["sources"]
    assert sources and set(sources) <= _source_ids(), (stem, sources)
    catalog_map = (ROOT / "docs" / "catalog" / "sources.md").read_text(encoding="utf-8")
    row = next(line for line in catalog_map.splitlines() if line.startswith(f"| `{stem}.toml` |"))
    assert all(source in row for source in sources), row
    land = raw.get("land")
    if land is not None:
        assert land["source"].split()[0] in sources, (stem, land["source"])


def test_records_are_declared_in_the_manifest() -> None:
    manifest = Path(ROOT / "tests" / "data" / "MANIFEST.toml").read_text(encoding="utf-8")
    for stem in RECORDS:
        assert f'path = "tests/data/packages/{stem}.toml"' in manifest, stem
