# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawing-sheet and paper probes, one test per hypothesis of c0012 (capability kicad-oracle, "Drawing
sheet and paper semantics are probed"). They run before the model code that relies on them, and each
asserts on ``run(<probe id>)``; ``tests/kicad/test_probe_results.py`` pins the outcomes per version.

A sheet is judged by what ``kicad-cli`` draws against same-session controls, never by its exit code.
"""

from __future__ import annotations

import _expected
import pytest
from _probes import run
from _sheetcases import VALUE_ATOMS

pytestmark = pytest.mark.needs_kicad


def test_controls() -> None:
    assert run("wks-default") == "present"
    assert run("wks-control") == "load"


def test_svg_shape() -> None:  # H-K-WKS-SVG
    assert run("wks-svg-shape") == "present"


def test_fallback() -> None:  # H-K-WKS-FALLBACK
    assert run("wks-missing-file") == "absent"
    assert run("wks-pro-missing") == "absent"
    assert run("wks-broken") == "reject"


def test_corners() -> None:  # H-K-WKS-CORNER
    assert run("wks-corners") == "equal"


def test_repeat() -> None:  # H-K-WKS-REPEAT
    assert run("wks-repeat") == "equal"


def test_page1() -> None:  # H-K-WKS-PAGE1
    assert run("wks-page1only") == "present"
    assert run("wks-notonpage1") == "absent"


def test_tokens() -> None:  # H-K-WKS-VARS
    assert run("wks-tokens") == "equal"
    assert run("wks-undefined-var") == "present"


def test_project_keys() -> None:  # H-K-PRO-WKS
    assert run("wks-pro-relative") == "present"
    assert run("wks-pro-kiprjmod") == "present"


@pytest.mark.parametrize("atom", VALUE_ATOMS)
def test_values(atom: str) -> None:  # H-K-WKS-VALUES
    assert run(f"wks-value-{atom}") == "load"


def test_unknown_value() -> None:  # H-K-WKS-VALUES
    assert run("wks-value-unknown") == "reject"


def test_bitmap() -> None:  # H-K-WKS-BITMAP
    assert run("wks-bitmap-corrupt") == "present"
    assert run("wks-bitmap") == "load"
    assert run("wks-bitmap-clean") == "absent"


def test_resolution() -> None:  # H-K-WKS-RES (refuted), H-K-WKS-RES-2
    assert run("wks-resolution") == "different"
    assert run("wks-resolution-exact") == "equal"


def test_percent() -> None:  # H-K-WKS-PCT
    assert run("wks-percent") == "equal"


@pytest.mark.parametrize("name", [n for n in _expected.PAPERS if n != "custom"])
def test_paper(name: str) -> None:  # H-K-PCB-PAPER-2 (named sizes, and whole-mil User sizes exact)
    assert run(f"pcb-paper-{name}") == "equal"


def test_paper_custom_truncated_to_mils() -> None:  # H-K-PCB-PAPER (refuted), H-K-PCB-PAPER-2
    assert run("pcb-paper-custom") == "different"
    assert run("pcb-paper-custom-mil") == "equal"
    assert run("pcb-paper-custom-fraction") == "equal"
