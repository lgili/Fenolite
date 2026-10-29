# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored input of the import tests stays a fresh build of its script (change c0275)."""

from __future__ import annotations

import shutil
from pathlib import Path

from _importcode import DATA, STAMP, TWO_SHEET

from fenolite.api import run
from fenolite.lens.edits import BASE_FILE


def test_two_sheet_is_a_fresh_build(tmp_path: Path) -> None:
    work = tmp_path / "data" / "src"
    shutil.copytree(DATA / "src", work)
    shutil.copytree(DATA.parent / "libs", tmp_path / "libs")
    reply = run("build", "two_sheet.py", "--out", "../two_sheet", "--confirm", cwd=work, timestamp=STAMP)
    assert reply.exit_code == 0, reply.error
    made = tmp_path / "data" / "two_sheet"
    committed = sorted(p.relative_to(TWO_SHEET).as_posix() for p in TWO_SHEET.rglob("*") if p.is_file())
    fresh = sorted(
        p.relative_to(made).as_posix()
        for p in made.rglob("*")
        if p.is_file() and ".fenolite" not in p.parts and p.name != BASE_FILE  # the build's own record (c0250)
    )
    assert committed == fresh
    for name in committed:
        assert (made / name).read_bytes() == (TWO_SHEET / name).read_bytes(), name
