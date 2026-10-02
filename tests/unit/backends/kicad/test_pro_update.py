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


def test_target_10_keeps_every_key() -> None:
    out = read_project_text(update_project(ten_project(), HV3, target=10))
    assert "tuning_profiles" in out and "component_class_settings" in out
