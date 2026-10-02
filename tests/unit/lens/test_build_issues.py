# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build issue codes and evidence (capability design-dsl, "Build issue codes" and "Build evidence";
change c0011)."""

from __future__ import annotations

import re
from pathlib import Path

from _buildhelp import blink, build, codes

from fenolite.backends.kicad import embed
from fenolite.core.evidence import Level
from fenolite.lens.build import BUILD_EVIDENCE, BUILD_ISSUE_CODES

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / "tests" / "unit" / "lens"


def test_closed_set() -> None:
    table = {
        "build.unknown-pin": "error", "build.pin-on-two-nets": "error", "build.pin-without-pad": "error",
        "build.no-footprint": "error", "build.no-board": "error", "build.name-case-collision": "error",
        "build.layout-exists": "error", "build.pin-ambiguous": "warning",
        "build.unused-pin-without-pad": "warning",
        "build.library-too-new": "warning", "layout.unplaced": "warning", "build.pad-without-pin": "info",
        "build.global-library": "info", "build.interface-not-lowered": "info",
    }  # fmt: skip
    assert dict(BUILD_ISSUE_CODES) == table
    literals: set[str] = set()
    for path in (ROOT / "src" / "fenolite" / "lens").glob("*.py"):
        literals |= set(re.findall(r'"((?:build|layout)\.[a-z0-9-]+)"', path.read_text(encoding="utf-8")))
    assert literals == set(table)
    tested: set[str] = set()
    for path in TESTS.glob("test_build_*.py"):
        tested |= set(re.findall(r'"((?:build|layout)\.[a-z0-9-]+)"', path.read_text(encoding="utf-8")))
    assert set(table) <= tested, set(table) - tested


def test_warnings_do_not_fail() -> None:
    d = blink()
    d.parts["R1"].request = None
    out = build(d)
    assert out.files and [i for i in out.issues if i.code == "layout.unplaced"][0].where == "R1"
    assert all(BUILD_ISSUE_CODES.get(i.code, i.severity) == i.severity for i in out.issues)
    assert "layout.unplaced" in codes(out)


def test_blink_evidence() -> None:
    out = build(blink())
    assert out.evidence.level is Level.INFERRED and BUILD_EVIDENCE.level is Level.INFERRED
    for h in ("H-K-BUILD-TRIAD", "H-K-LIB-READ", "H-K-PCB-WRITE"):
        assert h in out.evidence.hypotheses
    assert set(embed.EVIDENCE.hypotheses) <= set(out.evidence.hypotheses)


def test_bottom_parts_add_the_flip_rows() -> None:
    d = blink()
    d.parts["D1"].request = None
    d.parts["D1"].place("38mm", "20mm")
    out = build(d)
    assert not set(embed.EVIDENCE.hypotheses) & set(out.evidence.hypotheses)
