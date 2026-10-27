# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite publish`` (change c0201; capability file-safety, "Publish guarded by receipts")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _checkcli import run
from _safetyproject import project


def _snapshot_and_edit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    project(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "snap", "--confirm")
    assert code == 0, err
    snap = tmp_path / "snap"
    for name in ("board.kicad_pcb", "board.kicad_pro", "fp-lib-table"):
        with (snap / name).open("ab") as handle:
            handle.write(b"\n")
    (snap / "new.kicad_dru").write_text("(version 1)\n", encoding="utf-8")
    return snap


def test_the_owner_saved_one_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The owner saved one file": nothing is written, and the issue names that file."""
    _snapshot_and_edit(monkeypatch, tmp_path)
    owner = tmp_path / "proj" / "fp-lib-table"
    owner.write_text(owner.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    before = owner.read_bytes(), (tmp_path / "proj" / "board.kicad_pcb").read_bytes()
    args = ("publish", "snap", "--to", "proj", "--receipt", "snap/snapshot.json", "--confirm")
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 5 and [(i["code"], i["where"]) for i in env["issues"]] == [
        ("safety.changed-since-receipt", "fp-lib-table")
    ]
    assert (owner.read_bytes(), (tmp_path / "proj" / "board.kicad_pcb").read_bytes()) == before
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--skip-changed")
    assert code == 0, err
    assert env["result"]["replaced"] == ["board.kicad_pcb", "board.kicad_pro"]
    assert env["result"]["added"] == ["new.kicad_dru"] and env["result"]["changed"] == ["fp-lib-table"]
    assert owner.read_bytes() == before[0] and (tmp_path / "proj" / "board.kicad_pcb.bak").is_file()


def test_receipt_of_a_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The envelope of the last publish is the receipt of the next one."""
    snap = _snapshot_and_edit(monkeypatch, tmp_path)
    args = ("publish", "snap", "--to", "proj", "--receipt", "snap/snapshot.json", "--confirm")
    code, env, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0, err
    (tmp_path / "last.json").write_text(json.dumps(env), encoding="utf-8")
    with (snap / "board.kicad_pcb").open("ab") as handle:
        handle.write(b"\n")
    code, env, err, _ = run(
        monkeypatch, tmp_path, "publish", "snap", "--to", "proj", "--receipt", "last.json", "--dry-run"
    )
    assert code == 0, err
    assert env["result"]["replaced"] == ["board.kicad_pcb"]
    assert env["result"]["unchanged"] == 5  # the other files of the folder snapshot, the new rule file too


def test_a_bad_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _snapshot_and_edit(monkeypatch, tmp_path)
    (tmp_path / "bad.json").write_text('{"x": 1}', encoding="utf-8")
    code, _, err, _ = run(
        monkeypatch, tmp_path, "publish", "snap", "--to", "proj", "--receipt", "bad.json", "--dry-run"
    )
    assert code == 3 and err["code"] == "FEN-3004"
