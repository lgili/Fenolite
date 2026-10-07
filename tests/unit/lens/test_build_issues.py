# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build issue codes and evidence (capability design-dsl, "Build issue codes" and "Build evidence";
changes c0011, c0027, c0019 and c0036; preservation codes are build codes)."""

from __future__ import annotations

import re
from pathlib import Path

from _buildhelp import blink, build, codes

from fenolite.backends.kicad import embed
from fenolite.core.evidence import Level
from fenolite.lens.build import BUILD_EVIDENCE, BUILD_ISSUE_CODES, plane_issues
from fenolite.lens.preserve import PRESERVE_ISSUE_CODES

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / "tests" / "unit" / "lens"


def test_closed_set() -> None:
    table = {
        "build.unknown-pin": "error", "build.pin-on-two-nets": "error", "build.pin-without-pad": "error",
        "build.pin-pad-map-invalid": "error",
        "build.no-footprint": "error", "build.no-board": "error", "build.name-case-collision": "error",
        "build.layout-exists": "error", "build.pin-ambiguous": "warning",
        "build.unused-pin-without-pad": "warning",
        "build.library-too-new": "warning", "layout.unplaced": "warning", "build.pad-without-pin": "info",
        "build.global-library": "info", "build.interface-not-lowered": "info",
        "build.field-added": "info",  # c0077
        # c0027
        "build.property-reserved": "error", "build.property-invalid": "error",
        "build.property-conflict": "error", "build.vendor-unsafe-name": "error",
        "build.library-changed": "warning",
        "build.no-connect-on-net": "error",  # c0036
        "build.plane-not-lowered": "info",  # c0038
        "build.diff-pair-name": "warning", "build.i2c-pullup-missing": "warning",  # c0073
        # c0061: the build codes of the generated schematic
        "build.schematic-too-large": "error", "build.symbol-overlap": "warning",
        "build.symbol-short": "error", "build.symbol-placement-unknown": "warning",
        "build.symbol-placement-invalid": "error", "build.reserved-library": "error",
        "build.schematic-replaced": "warning",
        "build.schematic-netlist-differs": "error",  # c0063: the netlist guard
        "build.sheet-file-collision": "error",  # c0070: module sheets
        "build.sheet-stale": "warning",
        "build.pad-map-default": "warning",  # c0147: the catalog's default pin-to-pad map
        **PRESERVE_ISSUE_CODES,  # c0019
    }  # fmt: skip
    assert dict(BUILD_ISSUE_CODES) == table
    literals: set[str] = set()
    kicad = ROOT / "src" / "fenolite" / "backends" / "kicad"
    generator = [
        kicad / "schgen.py",
        kicad / "schlayout.py",
        ROOT / "src" / "fenolite" / "cli" / "cmd_build.py",
    ]
    for path in [*(ROOT / "src" / "fenolite" / "lens").glob("*.py"), *generator]:
        literals |= set(
            re.findall(r'"((?:build|layout|zone)\.[a-z0-9-]+)"', path.read_text(encoding="utf-8"))
        )
    assert literals == set(table)
    tested: set[str] = set()
    cli_tests = TESTS.parent / "cli" / "test_build_schematic_cmd.py"
    layout_tests = TESTS.parent / "backends" / "kicad" / "test_schlayout.py"
    for path in [*TESTS.glob("test_build_*.py"), *TESTS.glob("test_preserve_*.py"), cli_tests, layout_tests]:
        tested |= set(re.findall(r'"((?:build|layout|zone)\.[a-z0-9-]+)"', path.read_text(encoding="utf-8")))
    assert set(table) - set(PRESERVE_ISSUE_CODES) <= tested, set(table) - tested


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


def test_plane_issues() -> None:
    """``design-dsl`` "Planes in a build" (change c0038): one info per plane, naming the layer and the net."""
    assert plane_issues({}) == []
    first, second = plane_issues({"In1.Cu": "GND", "In2.Cu": "VIN"})
    assert (first.code, first.severity, first.where) == ("build.plane-not-lowered", "info", "In1.Cu")
    assert "In1.Cu" in first.message and "GND" in first.message
    assert "design.zone(" in first.hint and "GND" in first.hint and 'layers=("In1.Cu",)' in first.hint
    assert "KiCad" not in first.hint and 'layers=("In2.Cu",)' in second.hint
    assert second.where == "In2.Cu" and "VIN" in second.message
