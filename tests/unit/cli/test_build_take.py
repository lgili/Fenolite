# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite build --take`` (capability edit-merge, "Take option of build", "Take specificity", "Take
effects", "Takes are reported", "Conflict finding", "Conflicts stop writes"; change c0250)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _edit_help import base_of as _base
from _edit_help import edit as _edit
from _edit_help import issues as _issues
from _edit_help import value as _value
from _project import Project, footprint

MM = 1_000_000


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_build_conflict_and_takes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7"}})
    p.edit_script('value="330"', 'value="470"')
    before = p.files()
    code, env, _ = p.build("--confirm")
    (conflict,) = _issues(env, "sync.conflict")
    assert code == 5 and p.files() == before
    assert conflict["where"] == "R1#value" and "both-changed" in conflict["message"]
    assert "--take code:R1#value" in conflict["hint"] and "--take cad:R1#value" in conflict["hint"]
    assert env["result"]["preserved"]["edits"]["conflicts"][0]["key"] == "R1#value"  # type: ignore[index]
    code, env, err = p.build("--take", "cad:R1#value", "--confirm")
    assert code == 0, err
    assert _value(p, "R1") == ("4k7", "4k7")
    assert _base(p)["R1"]["value"] == {"code": "470", "out": "4k7"}
    assert env["result"]["preserved"]["edits"]["taken"] == ["R1#value"]  # type: ignore[index]
    assert [i["where"] for i in _issues(env, "edit.unrecorded")] == ["R1#value"]


def test_build_take_the_code_for_a_whole_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7", "move": (0, 2 * MM)}})
    p.edit_script('value="330"', 'value="470"')
    p.edit_script("r1.place(mm(32), mm(9))", "r1.place(mm(35), mm(9))")
    code, env, _ = p.build("--dry-run")
    assert code == 5 and sorted(i["where"] for i in _issues(env, "sync.conflict")) == [
        "R1#position",
        "R1#value",
    ]
    code, _, err = p.build("--take", "code:R1", "--confirm")
    assert code == 0, err
    fp, component = footprint(p.read(), "R1")
    assert component.value == "470" and fp.position.x == 135 * MM and fp.position.y == 109 * MM  # type: ignore[attr-defined]
    code, env, _ = p.build("--dry-run")
    assert code == 0 and not _issues(env, "sync.conflict")


def test_build_unused_take(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, _ = p.build("--take", "cad:R1#value", "--dry-run")
    (unused,) = _issues(env, "edit.take-unused")
    assert code == 0 and unused["where"] == "cad:R1#value" and unused["severity"] == "warning"


@pytest.mark.parametrize("takes", [("mine:R1",), ("code:R1", "cad:R1")])
def test_build_malformed_take(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, takes: tuple[str, ...]
) -> None:
    p = Project(tmp_path, monkeypatch)
    flags = [flag for take in takes for flag in ("--take", take)]
    code, _, err = p.build(*flags, "--dry-run")
    error = json.loads(err)
    assert code == 2 and error["code"] == "FEN-2001"
    if takes == ("mine:R1",):
        assert "mine:R1" in error["message"]


def test_frozen_build_refuses_an_unrecorded_edit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    _edit(p, {"R1": {"value": "4k7"}})
    before = p.files()
    code, env, err = p.build("--frozen", "--dry-run")
    error = json.loads(err)
    assert code == 7 and error["code"] == "FEN-7004" and "edits.toml" in error["hint"]
    (refused,) = [i for i in _issues(env, "lock.changed") if i["where"] == "R1#value"]
    assert refused["severity"] == "error" and "4k7" in refused["message"]
    code, _, _ = p.build("--frozen", "--confirm")
    assert code == 7 and p.files() == before


def test_frozen_build_refuses_a_take(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, err = p.build("--take", "cad:R1#value", "--frozen", "--dry-run")
    assert code == 7 and json.loads(err)["code"] == "FEN-7004"
    (refused,) = _issues(env, "lock.changed")
    assert refused["where"] == "--take" and "cad:R1#value" in refused["message"]
    code, _, err = p.build("--frozen", "--dry-run")
    assert code == 0, err
