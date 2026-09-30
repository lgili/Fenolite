# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""No file of the official KiCad libraries is committed (they are CC-BY-SA as a collection)."""

from __future__ import annotations

import shutil
from pathlib import Path

import _scanmod
import pytest
from _resources import kicad_library_dirs

scan = _scanmod.load()
LIB_SUFFIXES = (".kicad_mod", ".kicad_sym", ".step", ".stp", ".wrl")


def identical_library_files(files: list[Path], library_dirs: list[Path]) -> list[str]:
    hits = []
    for path in files:
        for lib in library_dirs:
            for candidate in lib.rglob(path.name):
                if candidate.is_file() and candidate.read_bytes() == path.read_bytes():
                    hits.append(f"{path} == {candidate}")
                    break
    return hits


@pytest.mark.needs_libs
def test_no_official_library_file_is_committed() -> None:
    files = [scan.REPO / p for p in scan.tree_files(scan.REPO) if p.endswith(LIB_SUFFIXES)]
    hits = identical_library_files(files, kicad_library_dirs())
    assert not hits, "official KiCad library files must be fetched, not committed:\n" + "\n".join(hits)


@pytest.mark.needs_libs
def test_detector_finds_a_copied_footprint(tmp_path: Path) -> None:
    libs = kicad_library_dirs()
    sample = next(p for lib in libs for p in lib.rglob("*.kicad_mod"))
    copy = tmp_path / sample.name
    shutil.copyfile(sample, copy)
    assert identical_library_files([copy], libs)
