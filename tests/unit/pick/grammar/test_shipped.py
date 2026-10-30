# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Illustrative grammars only in the core (change c0263, "Illustrative grammars only in the core",
scenario "No real series in the package")."""

from __future__ import annotations

import re
from pathlib import Path

from _grammars import authored_files

from fenolite.pick.grammar.lint import lint_family
from fenolite.pick.grammar.schema import read_family
from fenolite.pick.rows import is_grammar

ROOT = Path(__file__).resolve().parents[4]
URL = re.compile(r"https?://([^/\s\"]+)")


def test_no_real_series_in_the_package() -> None:
    package = ROOT / "src" / "fenolite"
    shipped = [
        path.relative_to(ROOT).as_posix()
        for path in sorted(package.rglob("*"))
        if path.suffix in (".toml", ".json", ".txt") and is_grammar(path.read_text(encoding="utf-8"))
    ]
    assert shipped == []


def test_the_authored_grammars_are_illustrative() -> None:
    files = authored_files()
    assert len(files) >= 4
    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert lines[0] == "# SPDX-License-Identifier: CC0-1.0", path
        assert lines[1].startswith("# Authored for Fenolite as ") and "not a real product line" in lines[1], (
            path
        )
        family = read_family(path)
        assert family.manufacturer == "Example Passive" and family.id.startswith("Example:"), path
        assert set(URL.findall(text)) == {"example.invalid"}, path
        assert family.licence == "CC0-1.0" and "(illustrative)" in family.summary, path
        # every numeric attribute names a source (family.source-missing is an error)
        assert not [item for item in lint_family(family) if item.code == "family.source-missing"], path
