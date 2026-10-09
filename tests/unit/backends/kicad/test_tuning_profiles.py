# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tuning profiles for impedance targets, written and read (capability kicad-file-backend, "Tuning profiles
for impedance targets" and "Tuning profiles are read into impedance targets"; change c0105)."""

from __future__ import annotations

import dataclasses
from functools import cache
from pathlib import Path
from typing import Any, cast

import pytest
from _buildhelp import build
from _zdesign import zdesign

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.pro import TEN_ONLY_PATHS, apply_project, read_project
from fenolite.backends.kicad.proerrors import ISSUE_CODES
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.tuning import (
    ENTRY_KEYS,
    LAYER_KEYS,
    PROFILE_KEY_PATHS,
    PROFILES_POINTER,
    apply_profile_keys,
    lower_profile,
)
from fenolite.core.errors import Issue
from fenolite.model.design import Design
from fenolite.model.rules import ImpedanceTarget, TraceGeometry

ROOT = Path(__file__).resolve().parents[4]
GUI_SAVE = ROOT / "tests" / "data" / "kicad" / "project" / "tuning_10.kicad_pro"


@cache
def designs() -> tuple[Design, Design]:
    """The built bench design with both targets, and the same design without them."""
    with_targets = build(zdesign()).layout
    without = build(zdesign(se50=False, usb90=False)).layout
    assert with_targets is not None and without is not None
    return with_targets, without


def _pro(
    design: Design, target: int = 10, existing: str | None = None, issues: list[Issue] | None = None
) -> str:
    files = write_triad(design, name="z", target=target, existing_project=existing, issues=issues)
    return files["z.kicad_pro"]


def _profiles(text: str) -> list[JsonObject]:
    return cast(list[JsonObject], _json.get(_json.loads(text), PROFILES_POINTER))


def _class_key(text: str, name: str) -> object:
    classes = cast(list[JsonObject], _json.get(_json.loads(text), "/net_settings/classes"))
    return next(c for c in classes if c["name"] == name).get("tuning_profile")


def _flat(value: Any, path: str = "") -> dict[str, str]:
    if isinstance(value, dict):
        out: dict[str, str] = {}
        for key, item in cast(dict[str, Any], value).items():
            out.update(_flat(item, f"{path}/{key}"))
        return out
    if isinstance(value, list):
        out = {}
        for index, item in enumerate(cast(list[Any], value)):
            out.update(_flat(item, f"{path}/{index}"))
        return out
    return {path: repr(value)}


def test_two_targets_synthesised_for_target_10() -> None:
    with_targets, without = designs()
    text = _pro(with_targets)
    se50, usb90 = _profiles(text)
    assert (se50["profile_name"], usb90["profile_name"]) == ("SE50", "USB90")
    assert usb90["type"] == JsonNumber("1") and usb90["target_impedance"] == JsonNumber("90")
    assert '"target_impedance": 90,' in text
    (entry,) = cast(list[JsonObject], usb90["layer_entries"])
    assert entry["width"] == JsonNumber("200000") and entry["diff_pair_gap"] == JsonNumber("150000")
    assert (entry["top_reference_layer"], entry["bottom_reference_layer"]) == ("", "In1.Cu")
    assert se50["type"] == JsonNumber("0") and len(cast(list[Any], se50["layer_entries"])) == 2
    assert _class_key(text, "SE50") == "SE50" and _class_key(text, "USB90") == "USB90"
    # every other key path equals the file written for the same design without targets
    plain = _flat(_json.loads(_pro(dataclasses.replace(with_targets, rules=dataclasses.replace(
        cast(Any, with_targets.rules), impedance=())))))  # fmt: skip
    found = _flat(_json.loads(text))
    governed = ("/tuning_profiles/tuning_profiles_impedance_geometric/", "/tuning_profile")
    assert {k: v for k, v in found.items() if not any(g in k or k.endswith(g) for g in governed)} == {
        k: v for k, v in plain.items() if not any(g in k or k.endswith(g) for g in governed)
    }
    assert without.rules is not None and not without.rules.impedance


def test_entry_has_the_written_key_set() -> None:
    target = ImpedanceTarget(
        id="imp_00000000-0000-4000-8000-000000000001",
        name="S",
        kind="single",
        netclass_ids=(),
        ohms="",
        layers=(TraceGeometry("In2.Cu", ("In1.Cu", "B.Cu"), 150_000),),
    )
    entry = lower_profile(target)
    assert tuple(entry) == ENTRY_KEYS
    assert entry["target_impedance"] == JsonNumber("0") and entry["enable_time_domain_tuning"] is False
    (row,) = cast(list[JsonObject], entry["layer_entries"])
    assert tuple(row) == LAYER_KEYS
    assert (row["top_reference_layer"], row["bottom_reference_layer"]) == ("In1.Cu", "B.Cu")
    assert row["diff_pair_gap"] == JsonNumber("0") and row["delay"] == JsonNumber("0")
    assert entry["via_overrides"] == [] and entry["via_prop_delay"] == JsonNumber("0")


def test_target_9() -> None:
    with_targets = build(zdesign(), target=9).layout
    assert with_targets is not None
    text = _pro(with_targets, target=9)
    data = _json.loads(text)
    assert "tuning_profiles" not in data
    assert all("tuning_profile" not in c for c in cast(list[JsonObject], data["net_settings"]["classes"]))
    plain = dataclasses.replace(
        with_targets, rules=dataclasses.replace(cast(Any, with_targets.rules), impedance=())
    )
    assert text == _pro(plain, target=9)
    assert "/tuning_profiles/tuning_profiles_impedance_geometric" in TEN_ONLY_PATHS
    assert "/net_settings/classes/*/tuning_profile" in TEN_ONLY_PATHS
    assert {p for p in PROFILE_KEY_PATHS if "*/*" not in p} <= TEN_ONLY_PATHS | {
        "/tuning_profiles/tuning_profiles_impedance_geometric/*"
    }


def _user_project(se50_class_key: str = "") -> str:
    with_targets, _ = designs()
    data = _json.loads(_pro(with_targets))
    gui = {
        "profile_name": "GUI_50",
        "type": JsonNumber("0"),
        "target_impedance": JsonNumber("50.0"),
        "enable_time_domain_tuning": False,
        "layer_entries": [],
        "via_prop_delay": JsonNumber("0"),
        "via_overrides": [],
    }
    old = lower_profile(dataclasses.replace(cast(Any, with_targets.rules).impedance[0]))
    cast(list[Any], old["layer_entries"])[0]["width"] = JsonNumber("300000")
    data["tuning_profiles"]["tuning_profiles_impedance_geometric"] = [gui, old]
    classes = cast(list[JsonObject], data["net_settings"]["classes"])
    rf = dict(classes[0])
    rf["name"], rf["tuning_profile"] = "RF", "GUI_50"
    classes.append(rf)
    for entry in classes:
        if entry["name"] in ("SE50", "USB90"):
            entry["tuning_profile"] = se50_class_key if entry["name"] == "SE50" else ""
    return _json.dumps(data)


def test_profiles_of_the_user_are_kept() -> None:
    with_targets, _ = designs()
    existing = _user_project()
    text = _pro(with_targets, existing=existing)
    gui, se50, usb90 = _profiles(text)
    assert _json.structural_equal(gui, _profiles(existing)[0])
    assert '"target_impedance": 50.0' in text
    assert cast(list[JsonObject], se50["layer_entries"])[0]["width"] == JsonNumber("350000")
    assert usb90["profile_name"] == "USB90"
    assert _class_key(text, "RF") == "GUI_50"


def test_class_key_reassigned() -> None:
    with_targets, _ = designs()
    issues: list[Issue] = []
    text = apply_profile_keys(_user_project("GUI_50"), with_targets, target=10, issues=issues)
    assert _class_key(text, "SE50") == "SE50"
    (found,) = [i for i in issues if i.code == "kicad.project.profile-reassigned"]
    assert found.severity == "warning" and "SE50" in found.message and "GUI_50" in found.message
    assert ISSUE_CODES["kicad.project.profile-reassigned"] == "warning"


def test_design_without_targets_returns_the_text() -> None:
    _, without = designs()
    assert apply_profile_keys("not json", without, target=10) == "not json"


def _read_back(pro_text: str, board_text: str, issues: list[Issue] | None = None) -> Design:
    board = read_board(board_text, file="z.kicad_pcb")
    return apply_project(board, read_project(pro_text, file="z.kicad_pro", issues=issues), issues=issues)


def test_read_written_targets_read_back() -> None:
    with_targets, _ = designs()
    files = write_triad(with_targets, name="z", target=10)
    design = _read_back(files["z.kicad_pro"], files["z.kicad_pcb"])
    assert design.rules is not None
    se50, usb90 = design.rules.impedance
    names = {c.id: c.name for c in design.circuit.netclasses}
    assert (se50.name, se50.kind, [names[i] for i in se50.netclass_ids], se50.ohms) == (
        "SE50",
        "single",
        ["SE50"],
        "50",
    )
    assert se50.layers == (
        TraceGeometry("F.Cu", ("In1.Cu",), 350_000),
        TraceGeometry("B.Cu", ("In2.Cu",), 350_000),
    )
    assert (usb90.kind, usb90.ohms, usb90.tolerance_percent) == ("differential", "90", "")
    assert usb90.layers == (TraceGeometry("F.Cu", ("In1.Cu",), 200_000, 150_000),)


@pytest.mark.parametrize("width", ["350000.5", None])
def test_read_malformed_entry_skipped(width: str | None) -> None:
    with_targets, _ = designs()
    files = write_triad(with_targets, name="z", target=10)
    data = _json.loads(files["z.kicad_pro"])
    entry = cast(list[Any], _profiles(files["z.kicad_pro"])[0]["layer_entries"])[0]
    if width is None:
        del entry["width"]
    else:
        entry["width"] = JsonNumber(width)
    data["tuning_profiles"]["tuning_profiles_impedance_geometric"][0] = _profiles(files["z.kicad_pro"])[0]
    data["tuning_profiles"]["tuning_profiles_impedance_geometric"][0]["layer_entries"][0] = entry
    issues: list[Issue] = []
    design = _read_back(_json.dumps(data), files["z.kicad_pcb"], issues)
    assert design.rules is not None
    se50 = design.rules.impedance[0]
    assert [row.layer for row in se50.layers] == ["B.Cu"]
    unread = [i for i in issues if i.code == "kicad.project.unread-entry"]
    assert len(unread) == 1 and "SE50" in unread[0].message and unread[0].severity == "info"


def test_read_width_written_with_a_point() -> None:
    with_targets, _ = designs()
    files = write_triad(with_targets, name="z", target=10)
    text = files["z.kicad_pro"].replace('"width": 350000', '"width": 350000.0')
    design = _read_back(text, files["z.kicad_pcb"])
    assert design.rules is not None and design.rules.impedance[0].layers[0].width == 350_000


def test_read_unknown_layer_skipped() -> None:
    with_targets, _ = designs()
    files = write_triad(with_targets, name="z", target=10)
    text = files["z.kicad_pro"].replace('"signal_layer": "B.Cu"', '"signal_layer": "In7.Cu"')
    issues: list[Issue] = []
    design = _read_back(text, files["z.kicad_pcb"], issues)
    assert design.rules is not None and [r.layer for r in design.rules.impedance[0].layers] == ["F.Cu"]
    assert any(i.code == "kicad.project.unread-entry" and "In7.Cu" in i.message for i in issues)


def test_read_profiles_no_class_names() -> None:
    with_targets, _ = designs()
    files = write_triad(with_targets, name="z", target=10)
    text = files["z.kicad_pro"].replace('"tuning_profile": "SE50"', '"tuning_profile": ""')
    text = text.replace('"tuning_profile": "USB90"', '"tuning_profile": "NOPE"')
    issues: list[Issue] = []
    design = _read_back(text, files["z.kicad_pcb"], issues)
    assert design.rules is None or design.rules.impedance == ()
    assert not [i for i in issues if i.code.startswith("kicad.project.")]


@pytest.mark.skipif(not GUI_SAVE.is_file(), reason="the GUI save of task 1.4 needs KiCad 10.0.6's GUI (owed)")
def test_gui_save() -> None:  # pragma: no cover - runs once the authored save is committed
    saved = _json.loads(GUI_SAVE.read_text(encoding="utf-8"))
    entries = cast(list[JsonObject], _json.get(saved, PROFILES_POINTER))
    assert entries and all(tuple(entry) == ENTRY_KEYS for entry in entries)
    for entry in entries:
        for row in cast(list[JsonObject], entry["layer_entries"]):
            assert tuple(row) == LAYER_KEYS
