# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Converted code stays out of the tool repository (capability corpus-policy, "Converted code stays out of the
tool repository"; change c0275).

``fenolite import`` heads every emitted ``.py`` file with ``Converted from <URL>…``. A tracked ``.py`` file
holding that line is code converted from a third-party board, which belongs in the separate
``fenolite-library`` repository, unless the file also holds ``Authored for Fenolite`` (an example imported
from a board authored for Fenolite). Pages of the documentation that quote the header are not code.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest
from _importcode import PROJECT, imported

ROOT = Path(__file__).resolve().parents[2]
CONVERTED = re.compile(r"Converted from [a-z][a-z0-9+.-]*://\S+")
AUTHORED = "Authored for Fenolite"
SOURCE = "https://example.invalid/corpus.git"


def converted_reports(paths: Iterable[Path], root: Path) -> list[str]:
    """``<path>: <conversion line>`` for each file of ``paths`` that holds a conversion line and not the
    authored marker."""
    reports: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found = CONVERTED.search(text)
        if found is not None and AUTHORED not in text:
            reports.append(f"{path.relative_to(root).as_posix()}: {found.group(0)}")
    return reports


def _tracked() -> list[Path]:
    try:
        done = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git is not available")
    names = [name for name in done.stdout.decode("utf-8").split("\0") if name]
    return [ROOT / name for name in names if name.endswith(".py") and (ROOT / name).is_file()]


def test_no_converted_code_is_tracked() -> None:
    assert converted_reports(_tracked(), ROOT) == []


def test_converted_corpus_board_planted(tmp_path: Path) -> None:
    """Scenario "Converted corpus board planted": the emitted code of a board stated to come from a URL."""
    reply = imported(tmp_path, PROJECT, "--source", SOURCE, "--confirm")
    assert reply.exit_code == 0, reply.error
    scripts = sorted((tmp_path / "out").rglob("*.py"))
    reports = converted_reports(scripts, tmp_path)
    assert [line.split(":", 1)[0] for line in reports] == [
        p.relative_to(tmp_path).as_posix() for p in scripts
    ]
    assert all(line.endswith(f"Converted from {SOURCE}") for line in reports)


def test_authored_import_example_passes() -> None:
    """Scenario "Authored import example passes"."""
    folder = ROOT / "examples" / "import_python"
    scripts = sorted(folder.rglob("*.py"))
    assert scripts
    assert converted_reports(scripts, ROOT) == []
