# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The impedance table for the fabricator (capability manufacturing-exports, "Impedance table for the
fabricator"; change c0105)."""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

from _buildhelp import build
from _zdesign import zdesign

from fenolite.exports import impedance
from fenolite.model.design import Design

SOURCE = Path(impedance.__file__)


@cache
def bench() -> Design:
    layout = build(zdesign()).layout
    assert layout is not None
    return layout


def test_table_of_the_bench() -> None:
    se_front, se_back, usb = impedance.impedance_table(bench())
    assert (se_front.target, se_front.layer, se_front.structure) == ("SE50", "F.Cu", "microstrip")
    assert (se_back.target, se_back.layer, se_back.structure) == ("SE50", "B.Cu", "microstrip")
    assert se_front.heights == (200_000,) and se_front.epsilon_r == "4.3" and se_front.gap is None
    assert (se_front.ohms, se_front.kind, se_front.classes) == ("50", "single", ("SE50",))
    assert se_front.nets == ("LED_A", "LED_DRV")
    assert (usb.target, usb.kind, usb.width, usb.gap) == ("USB90", "differential", 200_000, 150_000)
    assert usb.nets == ("USB_N", "USB_P") and usb.tolerance_percent == "10"


def test_csv_header_and_lengths() -> None:
    lines = impedance.render_csv(impedance.impedance_table(bench())).decode("utf-8").splitlines()
    assert lines[0] == ",".join(impedance.COLUMNS)
    usb = lines[3].split(",")
    columns = list(impedance.COLUMNS)
    assert usb[columns.index("width_mm")] == "0.2" and usb[columns.index("gap_mm")] == "0.15"
    assert usb[columns.index("heights_mm")] == "0.2" and usb[columns.index("nets")] == "USB_N USB_P"


def test_csv_with_estimates() -> None:
    rows = impedance.impedance_table(bench())
    lines = impedance.render_csv(rows, [(50_763, 343_000), (50_700, None), (None, None)]).decode("utf-8")
    header, first, second, third = lines.splitlines()
    assert header.endswith(",estimate_ohms,suggested_width_mm")
    assert first.endswith(",50.763,0.343") and second.endswith(",50.7,") and third.endswith(",,")


def test_no_stackup_no_heights() -> None:
    layout = build(zdesign(usb90=False, stackup=None)).layout
    assert layout is not None
    rows = impedance.impedance_table(layout)
    assert [r.heights for r in rows] == [None, None] and [r.epsilon_r for r in rows] == ["", ""]


def test_issue_codes() -> None:
    assert dict(impedance.ISSUE_CODES) == {
        "impedance.none": "info",
        "impedance.no-stackup": "warning",
        "impedance.estimate-unsupported": "info",
        "impedance.mixed-dielectric": "info",
        "impedance.out-of-range": "warning",
        "impedance.off-target": "warning",
    }
    assert impedance.issue("impedance.none", "x").severity == "info"


def test_no_float_and_no_tool() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Constant) and isinstance(node.value, float))
        assert not (isinstance(node, ast.Name) and node.id == "float")
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith(("subprocess", "fenolite.analysis"))
