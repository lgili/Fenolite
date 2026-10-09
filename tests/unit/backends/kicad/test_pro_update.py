# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""In-place project updates and target gating (capability kicad-file-backend, "Project files are
synthesised and preserved" and "Project files are gated by target"; change c0010)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _prodesigns import design, project, text

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.pro import read_project_text, update_project
from fenolite.backends.kicad.versions import (
    DowngradeRefusedError,
    FileKind,
    FutureFormatError,
    LossyWriteError,
    UnsupportedFormatError,
)
from fenolite.core.errors import Issue
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
BOARD_9 = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
HV3 = design({"HV": 3_000_000}, {"+3V3": "HV"})


def on_board(source: Design, board_text: str) -> Design:
    """``source``'s circuit on a board read from ``board_text`` (for the board's source major)."""
    board = read_board(board_text)
    return dataclasses.replace(board, circuit=source.circuit)


def board_10() -> str:
    return BOARD_9.read_text(encoding="utf-8").replace("(version 20241229)", "(version 20260206)", 1)


def test_unknown_keys_and_tuning_profiles_kept() -> None:
    data = project(10, x_unknown={"k": JsonNumber("1.000")})
    data["tuning_profiles"] = {"meta": {"version": JsonNumber("0")}}
    out = read_project_text(update_project(text(data), HV3, target=10))
    assert _json.structural_equal(out["x_unknown"], {"k": JsonNumber("1.000")})
    assert _json.structural_equal(out["tuning_profiles"], data["tuning_profiles"])
    assert out["net_settings"]["classes"][1]["clearance"] == JsonNumber("3")
    out["net_settings"]["classes"][1]["clearance"] = JsonNumber("2")
    out["net_settings"]["netclass_patterns"] = []
    assert _json.structural_equal(out, data)


def test_equal_value_keeps_its_spelling() -> None:
    data = project(10)
    data["net_settings"]["classes"][1]["clearance"] = JsonNumber("2.000")
    out = read_project_text(update_project(text(data), design({"HV": 2_000_000}, {}), target=10))
    assert out["net_settings"]["classes"][1]["clearance"] == JsonNumber("2.000")


def test_classes_appended_never_deleted() -> None:
    data = project(10)
    out = read_project_text(
        update_project(text(data), design({"Z": 1_000_000, "A": 2_000_000}, {}), target=10)
    )
    assert [c["name"] for c in out["net_settings"]["classes"]] == ["Default", "HV", "A", "Z"]


def test_patterns_regenerated_first_others_kept() -> None:
    data = project(10)
    data["net_settings"]["netclass_patterns"] = [
        {"netclass": "HV", "pattern": "OLD*"},
        {"netclass": "HV", "pattern": "+3V3"},
    ]
    out = read_project_text(update_project(text(data), HV3, target=10))
    assert out["net_settings"]["netclass_patterns"] == [
        {"netclass": "HV", "pattern": "+3V3"},
        {"netclass": "HV", "pattern": "OLD*"},
    ]


def test_wildcard_pattern_conflicts_with_the_model() -> None:
    data = project(10)
    lv = dict(data["net_settings"]["classes"][1])
    lv["name"] = "LV"
    data["net_settings"]["classes"].append(lv)
    data["net_settings"]["netclass_patterns"] = [{"netclass": "LV", "pattern": "+3*"}]
    found: list[Issue] = []
    out = read_project_text(
        update_project(text(data), design({"HV": 2_000_000}, {"+3V3": "HV"}), target=10, issues=found)
    )
    assert out["net_settings"]["netclass_patterns"][-1] == {"netclass": "LV", "pattern": "+3*"}
    conflicts = [i for i in found if i.code == "kicad.project.pattern-conflict"]
    assert len(conflicts) == 1 and all(s in conflicts[0].message for s in ("+3V3", "HV", "LV"))


def test_meta_and_boards_kept() -> None:
    data = project(10)
    data["meta"]["filename"] = "other.kicad_pro"
    out = read_project_text(update_project(text(data), HV3, target=10))
    assert out["meta"]["filename"] == "other.kicad_pro" and out["boards"] == []


# -- versions


def test_future_project_is_read_only() -> None:
    with pytest.raises(FutureFormatError) as caught:
        update_project('{"meta": {"version": 4}}', HV3, target=10)
    assert caught.value.cli_code == "FEN-3002"


@pytest.mark.parametrize("source", ["{}", '{"meta": {"version": 2}}', '{"meta": {"version": 3}}'])
def test_older_project_not_editable(source: str) -> None:
    with pytest.raises(UnsupportedFormatError) as caught:
        update_project(source, HV3, target=10)
    assert "KiCad 9 or 10" in caught.value.hint and caught.value.cli_code == "FEN-3003"


def test_pair_kept_on_update() -> None:
    out = read_project_text(update_project(text(project(9)), HV3, target=10))
    assert out["net_settings"]["meta"]["version"] == JsonNumber("4")


# -- target gating


def ten_project() -> str:
    return text(project(10))


def test_ten_project_for_a_nine_board() -> None:
    nine = on_board(HV3, BOARD_9.read_text(encoding="utf-8"))
    with pytest.raises(LossyWriteError) as caught:
        update_project(ten_project(), nine, target=9)
    wheres = [i.where for i in caught.value.issues]
    assert "/tuning_profiles" in wheres and "/net_settings/meta/version" in wheres
    assert {i.code for i in caught.value.issues} == {"kicad.project.too-new-key"} and caught.value.droppable


def test_lossy_update_for_target_9() -> None:
    nine = on_board(HV3, BOARD_9.read_text(encoding="utf-8"))
    found: list[Issue] = []
    out = read_project_text(update_project(ten_project(), nine, target=9, allow_lossy=True, issues=found))
    assert "tuning_profiles" not in out and "component_class_settings" not in out
    assert not any("tuning_profile" in c for c in out["net_settings"]["classes"])
    assert out["net_settings"]["meta"]["version"] == JsonNumber("4")
    assert found and {i.code for i in found} == {"kicad.project.dropped-too-new"}


def test_version_alone_is_too_new() -> None:
    data = project(9)
    data["net_settings"]["meta"]["version"] = JsonNumber("5")
    with pytest.raises(LossyWriteError) as caught:
        update_project(text(data), HV3, target=9)
    assert [(i.code, i.where) for i in caught.value.issues] == [
        ("kicad.project.too-new-key", "/net_settings/meta/version")
    ]
    found: list[Issue] = []
    out = read_project_text(update_project(text(data), HV3, target=9, allow_lossy=True, issues=found))
    assert out["net_settings"]["meta"]["version"] == JsonNumber("4")
    assert [(i.code, i.where) for i in found] == [
        ("kicad.project.dropped-too-new", "/net_settings/meta/version")
    ]


def test_downgrade_refused() -> None:
    ten = on_board(HV3, board_10())
    with pytest.raises(DowngradeRefusedError) as caught:
        update_project(ten_project(), ten, target=9, allow_lossy=True)
    error = caught.value
    assert error.cli_code == "FEN-7002" and error.kind == FileKind.BOARD
    assert (error.source_major, error.target_major) == (10, 9)


def test_downgrade_on_request() -> None:
    """Change c0162: a project of a board read at 10 written for 9 with ``downgrade``. Its ten-only
    sections hold the defaults of a fresh KiCad 10 project, so they are dropped as ``same`` without
    ``allow_lossy`` (the maintainer's decision of 2026-10-09); the version pair is rewritten."""
    from fenolite.backends.kicad import resolver

    ten = on_board(HV3, board_10())
    edits: list[resolver.Edit] = []
    found: list[Issue] = []
    out = read_project_text(
        update_project(ten_project(), ten, target=9, downgrade=True, issues=found, edits=edits)
    )
    assert "tuning_profiles" not in out and "component_class_settings" not in out
    assert all("tuning_profile" not in c for c in out["net_settings"]["classes"])
    assert out["net_settings"]["meta"]["version"] == JsonNumber("4")
    assert {(e.row, e.action) for e in edits} == {
        ("project:/component_class_settings", "same"),
        ("project:/net_settings/classes/*/tuning_profile", "same"),
        ("project:/tuning_profiles", "same"),
        ("project:/net_settings/meta/version", "rewrite"),
    }
    assert {i.code for i in found if i.code.startswith("kicad.downgrade")} == {resolver.CHANGED_CODE}


def _with_content() -> str:
    data = project(10)
    data["component_class_settings"]["assignments"] = [{"component_class": "X", "conditions": []}]
    data["tuning_profiles"]["tuning_profiles_impedance_geometric"] = [{"profile_name": "Z50"}]
    data["net_settings"]["classes"][1]["tuning_profile"] = "Z50"
    return text(data)


def test_downgrade_of_content_needs_consent() -> None:
    """The same sections with content (a component class assignment, a tuning profile and a class naming
    it) are ``design`` losses: refused without ``allow_lossy``, dropped and reported with it."""
    from fenolite.backends.kicad import resolver

    ten = on_board(HV3, board_10())
    with pytest.raises(LossyWriteError) as caught:
        update_project(_with_content(), ten, target=9, downgrade=True)
    assert caught.value.droppable
    assert {resolver.row_id(i) for i in caught.value.issues} == {
        "project:/component_class_settings",
        "project:/net_settings/classes/*/tuning_profile",
        "project:/tuning_profiles",
    }
    assert {i.code for i in caught.value.issues} == {resolver.DESIGN_CODE}
    edits: list[resolver.Edit] = []
    found: list[Issue] = []
    out = read_project_text(
        update_project(
            _with_content(), ten, target=9, downgrade=True, allow_lossy=True, issues=found, edits=edits
        )
    )
    assert "tuning_profiles" not in out and "component_class_settings" not in out
    actions = {(e.row, e.action) for e in edits}
    assert ("project:/net_settings/meta/version", "rewrite") in actions
    assert ("project:/tuning_profiles", "design") in actions
    assert {i.code for i in found if i.code.startswith("kicad.downgrade")} == {
        resolver.CHANGED_CODE,
        resolver.LOST_CODE,
    }


def test_one_section_with_content() -> None:
    """Only the section that holds content is a loss: a single class naming a profile."""
    from fenolite.backends.kicad import resolver

    data = project(10)
    data["net_settings"]["classes"][1]["tuning_profile"] = "Z50"
    with pytest.raises(LossyWriteError) as caught:
        update_project(text(data), on_board(HV3, board_10()), target=9, downgrade=True)
    assert {resolver.row_id(i) for i in caught.value.issues} == {
        "project:/net_settings/classes/*/tuning_profile"
    }


def test_target_10_keeps_every_key() -> None:
    out = read_project_text(update_project(ten_project(), HV3, target=10))
    assert "tuning_profiles" in out and "component_class_settings" in out


# --- check severities (capability kicad-file-backend, "Project files carry the check severities";
# --- change c0114) ---------------------------------------------------------------------------------


def with_severities(source: Design, severities: dict[str, str]) -> Design:
    from fenolite.model.rules import RuleSet

    return dataclasses.replace(source, rules=RuleSet(id="rst_x", severities=severities))  # type: ignore[arg-type]


def test_severity_update_changes_only_the_named_key() -> None:
    """Scenario "Update changes only the named key": the others keep their value and their position."""
    data = project(10)
    table = data["board"]["design_settings"]["rule_severities"]  # type: ignore[index]
    table["silk_overlap"] = "warning"  # type: ignore[index]
    table["track_dangling"] = "ignore"  # type: ignore[index]
    before = dict(table)  # type: ignore[arg-type]
    made = with_severities(design({}, {}), {"kicad.drc.silk-overlap": "error"})
    updated = read_project_text(update_project(text(data), made, target=10))
    after = dict(updated["board"]["design_settings"]["rule_severities"])  # type: ignore[index, arg-type]
    assert after["silk_overlap"] == "error" and after["track_dangling"] == "ignore"
    assert list(after) == list(before)
    assert {k: v for k, v in after.items() if k != "silk_overlap"} == {
        k: v for k, v in before.items() if k != "silk_overlap"
    }


def test_severity_update_without_a_severity_keeps_the_table_text() -> None:
    data = project(10)
    data["board"]["design_settings"]["rule_severities"]["silk_overlap"] = "ignore"  # type: ignore[index]
    source = text(data)
    assert update_project(source, design({}, {}), target=10) == update_project(
        source, with_severities(design({}, {}), {}), target=10
    )
    kept = read_project_text(update_project(source, design({}, {}), target=10))
    assert kept["board"]["design_settings"]["rule_severities"]["silk_overlap"] == "ignore"  # type: ignore[index]


def test_severity_update_unknown_key_refused() -> None:
    made = with_severities(design({}, {}), {"kicad.drc.silk-overlaps": "ignore"})
    with pytest.raises(LossyWriteError) as caught:
        update_project(text(project(10)), made, target=10)
    assert caught.value.droppable and caught.value.issues[0].code == "kicad.project.unknown-check"
    found: list[Issue] = []
    updated = update_project(text(project(10)), made, target=10, allow_lossy=True, issues=found)
    assert "silk_overlaps" not in updated and [i.code for i in found] == ["kicad.project.dropped-check"]


def test_severity_update_of_a_project_without_the_table() -> None:
    data = project(10)
    del data["board"]["design_settings"]["rule_severities"]  # type: ignore[index, union-attr]
    made = with_severities(design({}, {}), {"kicad.drc.via-dangling": "error"})
    updated = read_project_text(update_project(text(data), made, target=10))
    assert updated["board"]["design_settings"]["rule_severities"] == {"via_dangling": "error"}  # type: ignore[index]


def test_update_keeps_an_equal_pair_spelling() -> None:
    """Scenario "Update keeps an equal spelling" (change c0104): a pair value that is equal in nanometres
    keeps its text, and a pair key whose model value is ``None`` is left as it is."""
    data = project(10)
    usb = dict(data["net_settings"]["classes"][0])
    usb.update(name="USB", diff_pair_gap=JsonNumber("0.150"), diff_pair_width=JsonNumber("0.2"))
    data["net_settings"]["classes"].append(usb)
    made = design({"USB": None}, {})
    (cls,) = made.circuit.netclasses
    cls = dataclasses.replace(cls, diff_pair_gap=150_000, diff_pair_width=None)
    made = dataclasses.replace(made, circuit=dataclasses.replace(made.circuit, netclasses=(cls,)))
    out = read_project_text(update_project(text(data), made, target=10))
    entry = next(c for c in out["net_settings"]["classes"] if c["name"] == "USB")
    assert entry["diff_pair_gap"] == JsonNumber("0.150") and entry["diff_pair_width"] == JsonNumber("0.2")
    changed = dataclasses.replace(cls, diff_pair_gap=130_000, diff_pair_via_gap=400_000)
    made = dataclasses.replace(made, circuit=dataclasses.replace(made.circuit, netclasses=(changed,)))
    out = read_project_text(update_project(text(data), made, target=10))
    entry = next(c for c in out["net_settings"]["classes"] if c["name"] == "USB")
    assert entry["diff_pair_gap"] == JsonNumber("0.13") and entry["diff_pair_via_gap"] == JsonNumber("0.4")
