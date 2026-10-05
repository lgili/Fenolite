# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout issue codes (capability layout-lens, "Layout issue codes"; changes c0019 and c0069)."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.lens.preserve import PRESERVE_ISSUE_CODES

ROOT = Path(__file__).resolve().parents[3]
CODE = re.compile(r'"((?:layout|zone)\.[a-z0-9-]+)"')
C0011 = {"layout.unplaced"}
C0069_TESTS = (
    "test_moved.py",
    "test_alias_keep.py",
    "test_net_alias.py",
    "test_placements_file.py",
    "test_placement_source.py",
)


def test_closed_set() -> None:
    assert dict(PRESERVE_ISSUE_CODES) == {
        "layout.copper-mismatch": "error",
        "layout.source-invalid": "error",
        "layout.orphan": "warning",
        "layout.alias-unused": "warning",
        "layout.net-alias-unused": "warning",
        "layout.source-unknown": "warning",
        "layout.place-forced": "warning",
        "layout.footprint-replaced": "warning",
        "layout.net-removed": "warning",
        "layout.outline-kept": "warning",
        "zone.fill-stale": "warning",
        "layout.place-overridden": "info",
        "layout.alias-used": "info",
        "layout.net-alias-used": "info",
        "layout.source-stale": "info",
        "layout.board-only": "info",
    }
    source = (ROOT / "src" / "fenolite" / "lens" / "preserve.py").read_text(encoding="utf-8")
    # c0069: the alias resolution and the placements file report with codes of this table
    for module in ("moved.py", "placements.py"):
        source += (ROOT / "src" / "fenolite" / "lens" / module).read_text(encoding="utf-8")
    assert set(CODE.findall(source)) == set(PRESERVE_ISSUE_CODES)
    lens = ROOT / "tests" / "unit" / "lens"
    tests = [
        *lens.glob("test_preserve_*.py"),
        *(lens / name for name in C0069_TESTS),
        ROOT / "tests" / "unit" / "cli" / "test_build_preserve_command.py",
    ]
    produced: set[str] = set()
    for path in tests:
        produced |= set(CODE.findall(path.read_text(encoding="utf-8")))
    assert produced - C0011 <= set(PRESERVE_ISSUE_CODES)
    assert set(PRESERVE_ISSUE_CODES) <= produced, set(PRESERVE_ISSUE_CODES) - produced


def test_codes_pass_into_the_build_table() -> None:
    from fenolite.lens.build import BUILD_ISSUE_CODES

    assert {k: BUILD_ISSUE_CODES[k] for k in PRESERVE_ISSUE_CODES} == dict(PRESERVE_ISSUE_CODES)
