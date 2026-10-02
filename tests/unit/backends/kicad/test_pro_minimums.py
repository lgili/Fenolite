# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-setup minimums written into project files (capability kicad-file-backend, "Project files carry
the board-setup minimums"; change c0026)."""

from __future__ import annotations

import dataclasses
import itertools
from typing import Any, cast

import _netclass_bench as nb
import pytest
from _prodesigns import design, project, text

from fenolite.backends.kicad import _json, lowering
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.pro import (
    MINIMUM_POINTER,
    apply_project,
    project_minimums,
    read_project,
    read_project_text,
    synthesize_project,
    template,
    update_project,
)
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

_COUNTER = itertools.count(1)
FAB_TEXT = {
    "min_clearance": "0.1",
    "min_track_width": "0.127",
    "min_via_diameter": "0.45",
    "min_through_hole_diameter": "0.2",
    "min_copper_edge_clearance": "0.3",
}


def rule(kind: str, minimum: int | None, a: Selector | None = None, **fields: object) -> Rule:
    n = next(_COUNTER)
    values: dict[str, object] = {"name": f"m{n}", "min": minimum} | fields
    return Rule(
        id=derived_id("rul", "test", f"m{n}"),
        kind=kind,  # type: ignore[arg-type]
        selector_a=a or Selector("all"),
        **values,  # type: ignore[arg-type]
    )


def with_rules(base: Design, *items: Rule) -> Design:
    return dataclasses.replace(base, rules=RuleSet(id=derived_id("rst", "test", "m"), rules=items))


def fab(base: Design) -> Design:
    return with_rules(
        base,
        rule("clearance", 100_000),
        rule("track_width", 127_000),
        rule("via_diameter", 450_000),
        rule("hole_size", 200_000),
        rule("edge_clearance", 300_000),
    )


def rules_of(project_text: str) -> JsonObject:
    return cast(JsonObject, _json.get(read_project_text(project_text), MINIMUM_POINTER))


def codes(found: list[Issue]) -> list[str]:
    return [i.code for i in found]


def test_synthesis_writes_the_fab_minimums() -> None:
    found: list[Issue] = []
    written = rules_of(synthesize_project(fab(design({}, {})), target=10, board_name="b", issues=found))
    original = cast(JsonObject, _json.get(template(10), MINIMUM_POINTER))
    assert list(written) == list(original)
    for key, value in written.items():
        expected = JsonNumber(FAB_TEXT[key]) if key in FAB_TEXT else original[key]
        assert value == expected and (
            key in FAB_TEXT or _json.dumps({key: value}) == _json.dumps({key: original[key]})
        ), key
    assert "kicad.project.minimum-replaced" not in codes(found)


def test_synthesis_for_target_9() -> None:
    written = rules_of(synthesize_project(fab(design({}, {})), target=9, board_name="b"))
    assert {k: written[k] for k in FAB_TEXT} == {k: JsonNumber(v) for k, v in FAB_TEXT.items()}


def test_classes_compare_with_written_minimums() -> None:
    hv = with_rules(design({"HV": 200_000}, {"+3V3": "HV"}), rule("clearance", 300_000))
    found: list[Issue] = []
    synthesize_project(hv, target=10, board_name="b", issues=found)
    floor = [i for i in found if i.code == "kicad.project.below-floor"]
    assert len(floor) == 1
    assert all(part in floor[0].message for part in ("HV", "0.2", "min_clearance", "0.3"))


def test_class_conflicts_use_written_classes(monkeypatch: pytest.MonkeyPatch) -> None:
    hv = with_rules(design({"HV": 2_000_000}, {"+3V3": "HV"}), rule("clearance", 100_000))
    found: list[Issue] = []
    synthesize_project(hv, target=10, board_name="b", issues=found)
    assert "kicad.project.class-shadowed" in codes(found)
    assert "kicad.project.default-over-rule" not in codes(found)
    assert any("HV" in i.message for i in found if i.code == "kicad.project.class-shadowed")
    monkeypatch.setattr(lowering, "RULES_OVER_CLASSES", frozenset())
    found = []
    synthesize_project(hv, target=10, board_name="b", issues=found)
    assert "kicad.project.class-shadowed" not in codes(found)
    over = [i for i in found if i.code == "kicad.project.default-over-rule"]
    assert len(over) == 1 and "0.2" in over[0].message


def test_no_board_wide_rule_no_change() -> None:
    bench = nb.bench_design(target=10)
    synthesized = synthesize_project(bench, target=10, board_name="b")
    assert rules_of(synthesized) == _json.get(template(10), MINIMUM_POINTER)
    assert synthesized == synthesize_project(
        dataclasses.replace(bench, rules=None), target=10, board_name="b"
    )
    data = project(10)
    cast(JsonObject, _json.get(data, MINIMUM_POINTER))["min_track_width"] = JsonNumber("0.25")
    found: list[Issue] = []
    updated = update_project(text(data), bench, target=10, issues=found)
    assert rules_of(updated)["min_track_width"].text == "0.25"
    assert "kicad.project.minimum-replaced" not in codes(found)
    assert updated == update_project(text(data), dataclasses.replace(bench, rules=None), target=10)


def test_update_keeps_spelling_replaces_and_appends() -> None:
    data = project(10)
    table = cast(JsonObject, _json.get(data, MINIMUM_POINTER))
    table["min_track_width"] = JsonNumber("0.127000")
    table["min_through_hole_diameter"] = JsonNumber("0.3")
    del table["min_copper_edge_clearance"]
    before = dict(table)
    target = with_rules(
        design({}, {}),
        rule("track_width", 127_000),
        rule("hole_size", 250_000),
        rule("edge_clearance", 300_000),
    )
    found: list[Issue] = []
    written = rules_of(update_project(text(data), target, target=10, issues=found))
    assert written["min_track_width"].text == "0.127000"
    assert written["min_through_hole_diameter"].text == "0.25"
    assert (
        list(written)[-1] == "min_copper_edge_clearance"
        and written["min_copper_edge_clearance"].text == "0.3"
    )
    assert {k: v for k, v in written.items() if k not in FAB_TEXT} == {
        k: v for k, v in before.items() if k not in FAB_TEXT
    }
    replaced = [i for i in found if i.code == "kicad.project.minimum-replaced"]
    assert sorted(i.where.rsplit("/", 1)[1] for i in replaced) == [
        "min_copper_edge_clearance",
        "min_through_hole_diameter",
    ]
    absent = next(i for i in replaced if i.where.endswith("min_copper_edge_clearance"))
    assert "absent" in absent.message and "0.3" in absent.message


def test_missing_parents_are_appended() -> None:
    data = project(10)
    del data["board"]
    written = read_project_text(update_project(text(data), fab(design({}, {})), target=10))
    assert list(written)[-1] == "board"
    assert {k: v.text for k, v in rules_of(_json.dumps(written)).items()} == FAB_TEXT


def test_rules_member_that_is_not_an_object() -> None:
    data = project(10)
    cast(JsonObject, data["board"])["design_settings"]["rules"] = []
    with pytest.raises(FormatError) as caught:
        update_project(text(data), with_rules(design({}, {}), rule("track_width", 127_000)), target=10)
    assert caught.value.locator == "/board/design_settings/rules"


def test_project_minimums_reader() -> None:
    data = project(10)
    table = cast(JsonObject, _json.get(data, MINIMUM_POINTER))
    table["min_track_width"] = JsonNumber("0.0000001")
    table["min_via_diameter"] = "0.5"
    found: list[Issue] = []
    values = project_minimums(data, issues=found)
    assert "min_track_width" not in values and "min_via_diameter" not in values
    assert values["min_through_hole_diameter"] == 300_000
    assert codes(found) == ["kicad.project.inexact-value"]
    assert project_minimums({}) == {}


def test_minimums_stay_out_of_the_models_rules() -> None:
    original = fab(nb.bench_design(target=10))
    files = write_triad(original, name="b", target=10)
    board = read_board(files["b.kicad_pcb"])
    info = read_project(files["b.kicad_pro"])
    applied = apply_project(board, info)
    assert applied.rules == board.rules
    assert {k: v for k, v in project_minimums(info.data).items()} == {
        k: int(round(float(v) * 1_000_000)) for k, v in FAB_TEXT.items()
    }
    found: list[Issue] = []
    again = write_triad(original, name="b", target=10, existing_project=files["b.kicad_pro"], issues=found)
    assert {k: rules_of(again["b.kicad_pro"])[k].text for k in FAB_TEXT} == FAB_TEXT
    assert "kicad.project.minimum-replaced" not in codes(found)


def test_written_values_are_not_floats() -> None:
    written = rules_of(synthesize_project(fab(design({}, {})), target=10, board_name="b"))
    assert all(isinstance(cast(Any, written[k]), JsonNumber) for k in FAB_TEXT)
