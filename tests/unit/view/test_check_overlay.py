# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``check`` findings placed on a board or a sheet (capability check-overlay, scenario "Two findings";
change c0188). The replies are authored here."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fenolite.cli.cmd_view import scene_of
from fenolite.core.errors import FormatError
from fenolite.view.check_overlay import overlay, read_reply, summary

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _reply(*issues: dict[str, Any], stages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    full = [{"hint": "", "retryable": False, "where": ""} | issue for issue in issues]
    return {
        "command": "check",
        "result": {"stages": stages or []},
        "issues": full,
        "evidence": {"level": "INFERRED"},
    }


def test_two_findings() -> None:
    """Scenario "Two findings": one clearance error at a point, one finding without a position."""
    reply = _reply(
        {
            "code": "kicad.drc.clearance",
            "severity": "error",
            "message": "clearance: Clearance violation",
            "where": "@12.5,3.25, @13,-1",
        },
        {
            "code": "copper.clearance-unset",
            "severity": "info",
            "message": "1 item pair(s) judged for shorts only",
        },
        stages=[{"name": "drc.kicad", "evidence": {"level": "ORACLE-VERIFIED(kicad-cli)"}, "summary": {}}],
    )
    placed = overlay(read_reply(reply), {"prims": [], "pads": [], "comps": [], "nets": [], "meta": {}})
    first, second = placed["findings"]
    assert first["at"] == [12500.0, 3250.0] and first["box"] == [12500.0, -1000.0, 13000.0, 3250.0]
    assert first["stage"] == "drc.kicad" and first["evidence"] == "ORACLE-VERIFIED(kicad-cli)"
    assert second["at"] is None and second["evidence"] == "INFERRED"
    assert summary(placed) == {"error": 1, "warning": 0, "info": 1, "total": 2, "placed": 1}


def test_names_and_messages_on_a_board() -> None:
    scene = scene_of(BOARD)
    reply = _reply(
        {
            "code": "copper.short",
            "severity": "error",
            "message": "copper of A and B touches on F.Cu at (1.5, 2) mm",
        },
        {
            "code": "kicad.drc.unconnected_items",
            "severity": "error",
            "message": "x",
            "where": "R1-1, /kicad_pcb/segment[0]",
        },
        {
            "code": "model.single-pin-net",
            "severity": "warning",
            "message": "net connects a single pin",
            "where": "GND",
        },
        {"code": "kicad.erc.pin_not_connected", "severity": "error", "message": "x", "where": "/@10,20"},
        {"code": "kicad.erc.footprint-link-issues", "severity": "warning", "message": "x", "where": "R1"},
        {
            "code": "kicad.drc.starved-thermal",
            "severity": "error",
            "message": "x",
            "where": "/kicad_pcb/zone[0]",
        },
    )
    found = {f["code"]: f for f in overlay(reply, scene)["findings"]}
    assert found["copper.short"]["at"] == [1500.0, 2000.0] and found["copper.short"]["layer"] == "F.Cu"
    pad = next(p for p in scene["pads"] if p["label"] == "R1-1")
    unconnected = found["kicad.drc.unconnected_items"]
    assert unconnected["layer"] == "F.Cu" and unconnected["box"][0] <= pad["x"] <= unconnected["box"][2]
    assert found["model.single-pin-net"]["at"] is not None  # the net's own box
    assert found["kicad.erc.pin_not_connected"]["at"] is None  # a sheet's finding, listed only
    assert (
        found["kicad.erc.footprint-link-issues"]["at"] is None
    )  # an ERC finding names a symbol, not the part
    assert found["kicad.drc.starved-thermal"]["at"] is not None  # the zone, by its index among the zones


def test_sheet_findings() -> None:
    sheet = {
        "kind": "schematic",
        "meta": {"name": "power.kicad_sch", "backend": "kicad"},
        "comps": [],
        "objects": [],
    }
    reply = _reply(
        {"code": "kicad.erc.a", "severity": "error", "message": "x", "where": "/power/@10,20"},
        {"code": "kicad.erc.b", "severity": "error", "message": "x", "where": "/other/@1,2"},
    )
    a, b = overlay(reply, sheet)["findings"]
    assert a["at"] == [10000.0, 20000.0] and b["at"] is None


def test_not_a_check_reply() -> None:
    with pytest.raises(FormatError, match="analyze"):
        read_reply({"command": "analyze", "issues": []}, name="a.json")


def test_roles_findings_through_group_aliases() -> None:
    """Scenario "A Kelvin finding located" (c0305): ``roles.*`` codes belong to the stage ``roles.rules``, and
    a ``where`` that names a role group, or one pad of it, is placed through the groups given as aliases."""
    pads = [
        {"label": label, "x": x, "y": y}
        for label, x, y in (
            ("R12-1", 1000, 2000),
            ("R12-2", 3000, 2000),
            ("C1-1", 0, 0),
            ("Q1-3", 4000, 5000),
        )
    ]
    scene = {"prims": [], "pads": pads, "comps": [], "nets": [], "meta": {}}
    reply = _reply(
        {
            "code": "roles.kelvin-outer",
            "severity": "warning",
            "message": "outer half",
            "where": "kelvin_R12:R12-1",
        },
        {"code": "roles.loop-area", "severity": "warning", "message": "too large", "where": "hot_SW"},
        {"code": "roles.unconfirmed", "severity": "info", "message": "not confirmed", "where": "roles"},
    )
    groups = {"kelvin_R12": ["R12-1", "R12-2"], "hot_SW": ["C1-1", "Q1-3"]}
    placed = {f["code"]: f for f in overlay(reply, scene, aliases=groups)["findings"]}
    kelvin, loop = placed["roles.kelvin-outer"], placed["roles.loop-area"]
    assert {f["stage"] for f in placed.values()} == {"roles.rules"}
    assert kelvin["at"] == [1000, 2000] and kelvin["where"] == "kelvin_R12:R12-1"
    assert loop["box"] == [0, 0, 4000, 5000] and loop["at"] == [2000.0, 2500.0]
    assert placed["roles.unconfirmed"]["at"] is None
    bare = {f["code"]: f for f in overlay(reply, scene)["findings"]}
    assert bare["roles.kelvin-outer"]["at"] is None and bare["roles.loop-area"]["stage"] == "roles.rules"
