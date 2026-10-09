# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule areas, board items and area rules in an Altium build (capability altium-build; change c0103): what
the PCB document has a record for is written, and the rest is reported item by item."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _altium_drc import build_altium, coded, plant
from _routed import Routed

from fenolite.backends.altium import lower
from fenolite.backends.altium import rulemap as altium_rulemap
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.lens import altium_copper
from fenolite.model.board import Board, Dimension
from fenolite.model.rules import Rule, Selector

ANT = "[(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(4)), (mm(40), mm(4))]"
CORNER = "[(mm(1), mm(1)), (mm(5), mm(1)), (mm(5), mm(5)), (mm(1), mm(5))]"
AREA = f'design.rule_area("ANT", {ANT}, forbid=("tracks", "vias"))\n'
LABEL = 'design.text("rev", "REV A", (mm(2), mm(2)))\n'
DIMENSION = 'design.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))\n'
HV = f'design.rule_area("HV", {CORNER})\n'
SELECT = "from fenolite.dsl import select\n"


def new_items(env: dict[str, Any]) -> list[dict[str, Any]]:
    """The ``altium.not-lowered`` issues that name a rule area, a text or a dimension."""
    prefixes = ("keepout/", "text/", "dimension/")
    return [i for i in coded(env, "altium.not-lowered") if i["where"].startswith(prefixes)]


def test_script_items_in_an_altium_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Script items in an Altium build"."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, before, _ = build_altium(routed, "--dry-run")
    assert code == 0 and new_items(before) == []
    assert before["result"]["pcb"]["written"]["dimension"] == 0
    assert "dimension" not in before["result"]["pcb"]["not_lowered"]
    plant(routed, AREA, LABEL, DIMENSION)
    code, env, err = build_altium(routed, "--dry-run")
    assert code == 0, (env.get("issues"), err)
    pcb = env["result"]["pcb"]
    assert pcb["written"]["keep-out"] == before["result"]["pcb"]["written"]["keep-out"] + 1
    assert pcb["written"]["text"] == before["result"]["pcb"]["written"]["text"] + 1
    assert pcb["not_lowered"].get("dimension") == 1 and "keep-out" not in pcb["not_lowered"]
    found = new_items(env)
    wheres = sorted(i["where"] for i in found)
    assert wheres == [
        f"dimension/{derived_id('dim', 'dsl', 'dimension:width')}",
        f"keepout/{derived_id('kpo', 'dsl', 'area:ANT')}",
    ]
    assert all(i["severity"] == "info" for i in found)
    (named,) = [i for i in found if i["where"].startswith("keepout/")]
    assert "'ANT'" in named["message"] and "name" in named["message"]


def test_a_rules_only_area_and_a_justified_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A rules-only area and a justified text"."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    plant(routed, HV, 'design.text("rev", "REV A", (mm(2), mm(2)), justify="left bottom")\n')
    code, env, err = build_altium(routed, "--dry-run")
    assert code == 0, (env.get("issues"), err)
    pcb = env["result"]["pcb"]
    assert (pcb["not_lowered"].get("keep-out"), pcb["not_lowered"].get("text")) == (1, 1)
    found = {i["where"].split("/")[0]: i for i in new_items(env)}
    assert sorted(found) == ["keepout", "text"] and len(new_items(env)) == 2
    assert "left bottom" in found["text"]["message"] and "justification" in found["text"]["message"]
    assert "'HV'" in found["keepout"]["message"]


def test_an_area_rule_is_not_lowered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "An area rule is not lowered"."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, before, _ = build_altium(routed, "--dry-run")
    assert code == 0
    rule = 'design.rules.rule("hv", "clearance", where=select.area("HV"), min=mm(2))\n'
    plant(routed, SELECT, HV, rule)
    code, env, err = build_altium(routed, "--dry-run")
    assert code == 0, (env.get("issues"), err)
    (found,) = [i for i in coded(env, "altium.not-lowered") if i["where"] == "design-rules/clearance"]
    assert found["severity"] == "warning" and "hv" in found["message"]
    assert "scope-unsupported" in found["message"]
    rules = env["result"]["rules"]
    (row,) = [r for r in rules["not_lowered"] if r["reason"] == "scope-unsupported"]
    assert row["kind"] == "clearance" and "area" in row["selector"] and "HV" in row["selector"]
    assert rules["written"] == before["result"]["rules"]["written"]


def test_area_leaf_has_no_scope_in_the_rule_records() -> None:
    """``backends.altium.rulemap.lower`` answers ``scope-unsupported`` for a rule with an ``area`` leaf, on
    either side and inside a compound, and for that rule only; the table gains no row."""
    area = Selector("area", "HV")

    def rule(name: str, a: Selector, b: Selector | None = None) -> Rule:
        return Rule(id=derived_id("rul", "dsl", f"rule:named:{name}"), name=name, kind="clearance",
                    selector_a=a, selector_b=b, min=2_000_000)  # fmt: skip

    made = (
        rule("one", area),
        rule("two", Selector("net", "A"), area),
        rule("three", Selector("and", items=(Selector("net", "A"), area))),
        rule("plain", Selector("net", "A")),
    )
    lowered = altium_rulemap.lower(made)
    assert sorted((item.rule.name, item.reason) for item in lowered.not_lowered) == [
        ("one", "scope-unsupported"), ("three", "scope-unsupported"), ("two", "scope-unsupported"),
    ]  # fmt: skip
    assert [rule.name for record in lowered.records for rule in record.rules] == ["plain"]
    assert all("area" not in row.scopes and row.neutral != "area" for row in altium_rulemap.TABLE)


def test_dimensions_without_a_document() -> None:
    """Scenario "Dimensions without a document": one info for the kind, naming the count."""
    dimension = Dimension(
        id=derived_id("dim", "dsl", "dimension:width"), kind="aligned", layer="Dwgs.User",
        start=Point(0, 0), end=Point(40_000_000, 0), offset=-3_000_000,
    )  # fmt: skip
    board = Board(id=derived_id("brd", "dsl", "board"), dimensions=(dimension,))
    (found,) = altium_copper.board_not_lowered(board)
    assert (found.code, found.severity, found.where) == ("altium.not-lowered", "info", "dimensions")
    assert found.message.startswith("1 dimensions")
    assert ("dimensions", "dimensions") in altium_copper.BOARD_KINDS
    assert "dimension" in altium_copper.KINDS and altium_copper.KINDS == lower.KINDS


def test_lower_items_accounts_for_dimensions_and_names() -> None:
    from fenolite.core.errors import Issue

    dimension = Dimension(
        id="dim_x", kind="aligned", layer="Dwgs.User", start=Point(0, 0), end=Point(40_000_000, 0),
        offset=-3_000_000,
    )  # fmt: skip
    issues: list[Issue] = []
    found = altium_copper.lower_items(
        Board(id="brd_x", dimensions=(dimension, dimension)), ("F.Cu", "B.Cu"), issues
    )
    assert found.counts["dimension"] == (0, 2)
    assert [i.where for i in issues] == ["dimension/dim_x", "dimension/dim_x"]
    assert altium_copper.lower_items(Board(id="brd_x"), ("F.Cu", "B.Cu"), []).counts["dimension"] == (0, 0)
