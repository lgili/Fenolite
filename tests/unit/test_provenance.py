# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Provenance rules (docs/provenance.md): PROVENANCE.md per backend, sources on format pages,
and a clean-room session row for every week of format work."""

from __future__ import annotations

import re
import subprocess
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_HEADER = ["fact-or-area", "public source", "licence of source", "date", "how used"]
SOURCE_REF = re.compile(r"\bS-\d{4}\b|https?://")
FORMAT_PATHS = ("src/fenolite/backends/", "docs/formats/")


PROVENANCE_PACKAGES = ("templates",)  # packages outside backends/ that ship sourced figures


def _provenance_problems(prov: Path, rel: str) -> list[str]:
    if not prov.is_file():
        return [f"{rel}: missing PROVENANCE.md"]
    headers = [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in prov.read_text(encoding="utf-8").splitlines()
        if line.startswith("| fact-or-area")
    ]
    if headers != [PROVENANCE_HEADER]:
        return [f"{rel}: PROVENANCE.md must have exactly one table with columns {PROVENANCE_HEADER}"]
    return []


def missing_provenance(root: Path) -> list[str]:
    backends = root / "src" / "fenolite" / "backends"
    problems: list[str] = []
    if not backends.is_dir():
        return problems
    for package in sorted(p for p in backends.iterdir() if p.is_dir() and not p.name.startswith("_")):
        if not (package / "__init__.py").exists():
            continue
        rel = package.relative_to(root / "src" / "fenolite").as_posix()
        problems += _provenance_problems(package / "PROVENANCE.md", rel)
    return problems


def missing_package_provenance(root: Path) -> list[str]:
    """The packages of ``PROVENANCE_PACKAGES`` that exist must carry a PROVENANCE.md as backends do."""
    problems: list[str] = []
    for name in PROVENANCE_PACKAGES:
        package = root / "src" / "fenolite" / name
        if package.is_dir():
            problems += _provenance_problems(package / "PROVENANCE.md", name)
    return problems


def pages_without_sources(root: Path) -> list[str]:
    formats = root / "docs" / "formats"
    if not formats.is_dir():
        return []
    return [
        page.relative_to(root).as_posix()
        for page in sorted(formats.rglob("*.md"))
        if page.name != "README.md" and not SOURCE_REF.search(page.read_text(encoding="utf-8"))
    ]


def _annex_weeks(root: Path) -> set[tuple[int, int]]:
    weeks: set[tuple[int, int]] = set()
    for line in (root / "LEGAL-ANNEX.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|", line)
        if match:
            iso = date.fromisoformat(match.group(1)).isocalendar()
            weeks.add((iso[0], iso[1]))
    return weeks


def _format_work_weeks(root: Path) -> set[tuple[int, int]]:
    proc = subprocess.run(
        ["git", "log", "--name-only", "--format=@@%cI"], cwd=root, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:  # no git, or no commits yet
        return set()
    weeks: set[tuple[int, int]] = set()
    current: datetime | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("@@"):
            current = datetime.fromisoformat(line[2:])
        elif current and line.startswith(FORMAT_PATHS) and not line.endswith("README.md"):
            iso = current.isocalendar()
            weeks.add((iso[0], iso[1]))
    return weeks


def test_every_backend_has_provenance() -> None:
    problems = missing_provenance(ROOT)
    assert not problems, "\n".join(problems)


def test_packages_with_figures_have_provenance() -> None:
    problems = missing_package_provenance(ROOT)
    assert not problems, "\n".join(problems)


def test_detects_package_without_provenance(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "fenolite" / "templates"
    pkg.mkdir(parents=True)
    assert missing_package_provenance(tmp_path) == ["templates: missing PROVENANCE.md"]
    (pkg / "PROVENANCE.md").write_text("| " + " | ".join(PROVENANCE_HEADER) + " |\n")
    assert missing_package_provenance(tmp_path) == []


def test_format_pages_cite_sources() -> None:
    pages = pages_without_sources(ROOT)
    assert not pages, "format pages without a source id or URL:\n" + "\n".join(pages)


def test_session_log_covers_every_week_of_format_work() -> None:
    missing = sorted(_format_work_weeks(ROOT) - _annex_weeks(ROOT))
    assert not missing, "LEGAL-ANNEX.md has no session row for ISO weeks: " + ", ".join(
        f"{y}-W{w:02d}" for y, w in missing
    )


def test_detects_backend_without_provenance(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "fenolite" / "backends" / "foo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    assert missing_provenance(tmp_path) == ["backends/foo: missing PROVENANCE.md"]
    (pkg / "PROVENANCE.md").write_text(
        "| fact-or-area | public source | licence of source | date | how used |\n"
    )
    assert missing_provenance(tmp_path) == []


def test_detects_page_without_source(tmp_path: Path) -> None:
    page = tmp_path / "docs" / "formats" / "x.md"
    page.parent.mkdir(parents=True)
    page.write_text("# x\nno source here\n")
    assert pages_without_sources(tmp_path) == ["docs/formats/x.md"]
    page.write_text("# x\nsee S-0001\n")
    assert pages_without_sources(tmp_path) == []


@pytest.mark.parametrize("row", ["| 2026-10-05 | backends/kicad | pcb.py | S-0001 | a |"])
def test_annex_week_parsing(tmp_path: Path, row: str) -> None:
    header = "| date | area | files touched | public sources consulted | author |\n|---|---|---|---|---|\n"
    (tmp_path / "LEGAL-ANNEX.md").write_text(header + row + "\n")
    assert _annex_weeks(tmp_path) == {(2026, 41)}
