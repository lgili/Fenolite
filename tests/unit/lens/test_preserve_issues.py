# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout issue codes (capability layout-lens, "Layout issue codes"; change c0019)."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.lens.preserve import PRESERVE_ISSUE_CODES

ROOT = Path(__file__).resolve().parents[3]
CODE = re.compile(r'"((?:layout|zone)\.[a-z0-9-]+)"')
C0011 = {"layout.unplaced"}


def test_closed_set() -> None:
    assert dict(PRESERVE_ISSUE_CODES) == {
        "layout.copper-mismatch": "error",
        "layout.orphan": "warning",
        "layout.alias-unused": "warning",
        "layout.place-forced": "warning",
        "layout.footprint-replaced": "warning",
        "layout.net-removed": "warning",
        "layout.outline-kept": "warning",
        "zone.fill-stale": "warning",
        "layout.place-overridden": "info",
        "layout.alias-used": "info",
        "layout.board-only": "info",
    }
    source = (ROOT / "src" / "fenolite" / "lens" / "preserve.py").read_text(encoding="utf-8")
    assert set(CODE.findall(source)) == set(PRESERVE_ISSUE_CODES)
    tests = [
        *(ROOT / "tests" / "unit" / "lens").glob("test_preserve_*.py"),
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
