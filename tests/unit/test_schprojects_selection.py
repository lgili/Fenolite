# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which demo projects a test may read sheet by sheet (``tests/_schprojects.readable``): decided from the
corpus manifest alone, so it needs no cached file and no ``kicad-cli``."""

from __future__ import annotations

import dataclasses
from pathlib import PurePosixPath

import _schcorpus
import _schprojects
import pytest

OLD_ON_9 = {f"kicad-demo-9-0-9-1-sch-{number}" for number in ("008", "012", "013", "014")}
"""The four projects of the 9.0.9 demo tree with a sheet of format 20230121, below the read floor."""


def test_projects_with_an_old_sheet_are_not_readable() -> None:
    roots = {row.id: row for row in _schprojects.roots(9)}
    assert OLD_ON_9 <= set(roots)
    assert not any(_schprojects.readable(roots[name], 9) for name in OLD_ON_9)
    kept = [row for row in roots.values() if _schprojects.readable(row, 9)]
    assert kept and all(_schprojects.OLD not in row.uses for row in kept)


@pytest.mark.parametrize("major", [9, 10])
def test_a_readable_project_has_no_old_sheet_in_its_folder(major: int) -> None:
    by_path = _schcorpus.at_tag(_schprojects.MAJOR_TAGS[major])
    for row in _schprojects.roots(major):
        folder = str(PurePosixPath(row.path).parent)
        sheets = [sheet for path, sheet in by_path.items() if str(PurePosixPath(path).parent) == folder]
        old = _schprojects.OLD in row.uses or any(_schprojects.OLD in sheet.uses for sheet in sheets)
        assert _schprojects.readable(row, major) is (not old), row.id


def test_the_root_row_alone_can_be_old(monkeypatch: pytest.MonkeyPatch) -> None:
    row = next(row for row in _schprojects.roots(10) if _schprojects.readable(row, 10))
    marked = dataclasses.replace(row, uses=(*row.uses, _schprojects.OLD))
    monkeypatch.setattr(_schcorpus, "at_tag", lambda tag, items=None: {})
    assert _schprojects.readable(row, 10) and not _schprojects.readable(marked, 10)
