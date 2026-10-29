# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role profile and its overrides (change c0222; capability net-roles, "Role profile" and "Role limit
overrides"; ``docs/roles.md``, "Default limits")."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fenolite.core.evidence import Level
from fenolite.model.design import Design
from fenolite.model.rules import ROLE_LIMIT_UNITS, HotLoop, NetRole, RoleLimit, RoleSet
from fenolite.roles import checks, profile
from fenolite.roles.measure import Measure, Measured, RoleBoard

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "docs" / "roles.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
MM2 = profile.MM2


def _page_rows() -> dict[str, list[str]]:
    text = PAGE.read_text(encoding="utf-8")
    section = text.split("## Default limits", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0].startswith("`"):
            rows[cells[0].strip("`")] = cells
    return rows


def test_every_default_has_a_source() -> None:
    assert set(profile.DEFAULTS) == set(ROLE_LIMIT_UNITS)
    known = set(re.findall(r"^\| (S-\d{4}) \|", SOURCES.read_text(encoding="utf-8"), re.MULTILINE))
    labels = {level.value for level in Level}
    for key, default in profile.DEFAULTS.items():
        assert default.unit == ROLE_LIMIT_UNITS[key]
        if default.value is None:
            assert (default.source, default.label) == ("user", ""), key
            continue
        assert re.fullmatch(r"S-\d{4}|H-G-ROLE-[A-Z-]+", default.source), key
        assert default.label in labels, key
        if default.source.startswith("S-"):
            assert default.source in known, key
        cited = re.findall(r"S-\d{4}", default.meaning)
        assert set(cited) <= known, key


def test_the_page_lists_the_same_keys() -> None:
    rows = _page_rows()
    assert set(rows) == set(profile.DEFAULTS)
    for key, default in profile.DEFAULTS.items():
        _, value, _unit, source, label, _meaning = rows[key]
        if default.value is None:
            assert (value, source, label) == ("none", "user", "—"), key
        else:
            assert (value, source, label) == (str(default.value), default.source, f"`{default.label}`"), key


def test_no_distance_rise_thickness_or_current_ships() -> None:
    for key in profile.DEFAULTS:
        assert not re.search(r"creepage|clearance|thickness", key), key
    assert profile.DEFAULTS["temp_rise_mk"].value is None
    assert profile.DEFAULTS["high_voltage_mv"].value is None
    assert not [key for key in profile.DEFAULTS if key in ("milliamps", "current_ma")]
    assert any("creepage" in text for text in profile.NO_DEFAULTS)


def test_the_most_specific_limit_wins() -> None:
    limits = (
        RoleLimit("loop_ratio_max", 3000),
        RoleLimit("loop_ratio_max", 2500, kind="switch_node"),
        RoleLimit("loop_ratio_max", 1500, net="SW"),
    )
    assert profile.resolve("loop_ratio_max", limits, net="SW", kind="switch_node") == profile.Limit(
        "loop_ratio_max", 1500, "override", ""
    )
    assert profile.resolve("loop_ratio_max", limits, net="SW2", kind="switch_node").value == 2500
    assert profile.resolve("loop_ratio_max", limits, net="SW2", kind="gate").value == 3000
    found = profile.resolve("loop_ratio_max", ())
    assert (found.value, found.origin, found.source) == (2000, "profile", "H-G-ROLE-LOOP-RATIO")
    assert found.text() == "loop_ratio_max=2000 (profile, H-G-ROLE-LOOP-RATIO)"


def test_requirements_come_after_the_overrides() -> None:
    rise = profile.resolve("temp_rise_mk", (), requirements={"temp_rise_mk": 20_000})
    assert (rise.value, rise.origin) == (20_000, "requirements")
    mine = profile.resolve(
        "temp_rise_mk", (RoleLimit("temp_rise_mk", 10_000),), requirements={"temp_rise_mk": 1}
    )
    assert (mine.value, mine.origin) == (10_000, "override")
    with pytest.raises(KeyError):
        profile.resolve("no_such_key", ())


def _hot_loop(limits: tuple[RoleLimit, ...], area_mm2: int) -> list[str]:
    roles = RoleSet(
        nets=(NetRole("SW", "switch_node", "confirmed"),),
        loops=(HotLoop("hot_SW", ("C1-1", "Q1-1", "Q2-2", "C1-2"), origin="confirmed"),),
        limits=limits,
    )
    board = RoleBoard(Design.new("t", seed=1), (), roles, {})
    measure = Measure(
        "loop",
        "hot_SW",
        "loop_areas",
        ("tracks",),
        {
            "group": "hot",
            "pads": ["C1-1", "Q1-1", "Q2-2", "C1-2"],
            "area_nm2": area_mm2 * MM2,
            "bound_nm2": 100 * MM2,
            "ratio_permille": area_mm2 * 10,
            "legs": [],
            "open": [],
            "net": "SW",
        },
    )
    done = Measured(measures=[measure])
    found = checks.judge(board, done)
    assert {issue.code for issue in found} <= {"roles.loop-area", "roles.current-missing"}
    return [
        f"{issue.code}|{issue.severity}|{issue.message}" for issue in found if issue.code == "roles.loop-area"
    ]


def test_a_net_override_wins() -> None:
    limits = (RoleLimit("loop_max", 200 * MM2), RoleLimit("loop_max", 60 * MM2, net="SW"))
    (found,) = _hot_loop(limits, 150)
    code, level, message = found.split("|")
    assert code == "roles.loop-area" and level == "error"
    assert "above the 60.00 mm² of loop_max=60000000000000 (override)" in message
    assert "200.00" not in message


def test_the_design_limit_without_a_net_one() -> None:
    (found,) = _hot_loop((RoleLimit("loop_max", 200 * MM2),), 150 + 100)
    assert "above the 200.00 mm²" in found
    assert _hot_loop((RoleLimit("loop_max", 200 * MM2), RoleLimit("loop_ratio_max", 5000)), 150) == []
