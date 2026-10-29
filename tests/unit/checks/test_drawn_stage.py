# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stage ``schematic.drawn`` on an injected netlist (capability verification-loop, "Drawn schematic stage"
and "Drawn schematic stage issue codes"; change c0276)."""

from __future__ import annotations

import dataclasses

import _drawn

from fenolite.checks.codes import ISSUE_CODES
from fenolite.checks.drawn import NAME, drawn_stage
from fenolite.model.drawn import DrawnSchematic
from fenolite.model.drawn_connect import ISSUE_CODES as DRAWN_CODES


def test_a_faithful_drawing_is_ok() -> None:
    result = drawn_stage(_drawn.netlist("example"), _drawn.circuit("example"))
    assert result.name == NAME == "schematic.drawn" and result.status == "ok" and result.issues == ()
    assert result.evidence.level.value == "INFERRED"
    assert dict(result.summary)["nets"] == 5


def test_an_error_fails_the_stage_and_a_warning_does_not() -> None:
    value = _drawn.drawn("example")
    labels = tuple(
        dataclasses.replace(label, text="I2C_SDA") if label.text == "SDA" else label
        for label in value.sheets[0].labels
    )
    renamed = DrawnSchematic(
        value.root, (dataclasses.replace(value.sheets[0], labels=labels), value.sheets[1])
    )
    result = drawn_stage(_drawn.netlist("example", renamed), _drawn.circuit("example"))
    assert result.status == "ok" and [i.code for i in result.issues] == ["drawn.net-name-differs"]
    child = dataclasses.replace(value.sheets[1], labels=value.sheets[1].labels[1:])
    broken = DrawnSchematic(value.root, (value.sheets[0], child))
    netlist = _drawn.netlist("example", broken)
    result = drawn_stage(netlist, _drawn.circuit("example"), issues=netlist.issues)
    assert result.status == "errors"
    assert {"drawn.netlist-differs", "drawn.sheet-pin-unmatched"} <= {i.code for i in result.issues}


def test_the_check_table_holds_the_codes() -> None:
    """Scenario: ``checks.codes.ISSUE_CODES`` gains the drawn codes with their severities."""
    for code, severity in DRAWN_CODES.items():
        assert ISSUE_CODES[code] == (severity,)
