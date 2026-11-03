# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical migration follows reviewed plans, refusal, backups and atomic rollback (c0218)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _checkcli import run
from _cliexamples import folder_snapshot

from fenolite.model import canonical
from fenolite.model.design import Design

SOURCE = Path(__file__).resolve().parents[3] / "tests/data/model/v0.5.0"


def _legacy(folder: Path) -> Path:
    target = folder / "model"
    shutil.copytree(SOURCE, target)
    return target


def test_plan_is_readonly_and_confirmation_keeps_every_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = _legacy(tmp_path)
    before = folder_snapshot(tmp_path)
    code, reply, _, _ = run(monkeypatch, tmp_path, "migrate", "model", "--dry-run")
    assert code == 0 and folder_snapshot(tmp_path) == before
    assert {key: reply["result"][key] for key in ("from", "to", "steps")} == {
        "from": "0",
        "to": "1.0",
        "steps": ["0 -> 1.0"],
    }
    assert len(reply["result"]["plan"]) == 6
    assert {p["kind"] for p in reply["result"]["plan"]} == {"fenolite"}
    plan = reply["result"]["plan_id"]
    code, _, error, _ = run(monkeypatch, tmp_path, "migrate", "model")
    assert code == 4 and error["code"] == "FEN-4001" and folder_snapshot(tmp_path) == before
    code, written, _, _ = run(monkeypatch, tmp_path, "migrate", "model", "--confirm", "--plan", plan)
    assert code == 0 and len(written["receipt"]["written"]) == len(written["receipt"]["backup"]) == 6
    for name, _, _ in canonical.LAYER_FILES:
        assert (model / (name + ".bak")).read_bytes() == (SOURCE / name).read_bytes()
    assert (model / "SOURCE").read_bytes() == (SOURCE / "SOURCE").read_bytes()
    assert canonical.load_dir(model).header.schema_version == "1.0"
    assert not canonical.load_dir(model).findings.issues
    assert written["evidence"]["level"] == "INFERRED" and written["evidence"]["hypotheses"] == [
        "H-G-MODEL-OWN"
    ]


def test_current_folder_is_a_noop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    canonical.dump_dir(Design.new("authored", seed=1), tmp_path / "model")
    before = folder_snapshot(tmp_path)
    for flags in ((), ("--dry-run",), ("--confirm",)):
        code, reply, _, _ = run(monkeypatch, tmp_path, "migrate", "model", *flags)
        assert code == 0 and reply["issues"] == [] and reply["receipt"] is None
        assert reply["result"] == {"from": "1.0", "to": "1.0", "steps": []}
        assert folder_snapshot(tmp_path) == before


def test_reviewed_plan_refuses_an_edited_layer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = _legacy(tmp_path)
    code, reply, _, _ = run(monkeypatch, tmp_path, "migrate", "model", "--dry-run")
    assert code == 0
    with (model / "board.json").open("a") as stream:
        stream.write("\n")
    before = folder_snapshot(tmp_path)
    code, _, error, _ = run(
        monkeypatch, tmp_path, "migrate", "model", "--confirm", "--plan", reply["result"]["plan_id"]
    )
    assert code == 4 and error["code"] == "FEN-4002" and folder_snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "version,expected", [("1.1", "FEN-3002"), ("2.0", "FEN-3002"), ("1.0.1", "FEN-3004"), (1, "FEN-3004")]
)
def test_unsupported_versions_write_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: object, expected: str
) -> None:
    model = tmp_path / "model"
    model.mkdir()
    (model / "meta.json").write_text(json.dumps({"schema_version": version}))
    before = folder_snapshot(tmp_path)
    code, _, error, _ = run(monkeypatch, tmp_path, "migrate", "model", "--confirm")
    assert code == 3 and error["code"] == expected and folder_snapshot(tmp_path) == before


def test_diff_refuses_future_minor_with_both_versions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in ("a", "b"):
        model = tmp_path / name / ".fenolite"
        canonical.dump_dir(Design.new("authored", seed=1), model)
    meta = tmp_path / "a/.fenolite/meta.json"
    data = json.loads(meta.read_text())
    data["schema_version"] = "1.1"
    meta.write_text(json.dumps(data))
    code, _, error, _ = run(monkeypatch, tmp_path, "diff", "a", "b")
    assert code == 3 and error["code"] == "FEN-3002"
    assert "1.1" in error["message"] and "1.0" in error["message"]


def test_invalid_layer_prevents_all_writes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = _legacy(tmp_path)
    data = json.loads((model / "board.json").read_text())
    data["new_unknown_field"] = 7
    (model / "board.json").write_text(json.dumps(data))
    before = folder_snapshot(tmp_path)
    code, _, error, _ = run(monkeypatch, tmp_path, "migrate", "model", "--confirm")
    assert code == 3 and error["code"] == "FEN-3004" and folder_snapshot(tmp_path) == before


def test_mid_commit_failure_rolls_back_every_layer_and_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fenolite.core.io as fio

    model = _legacy(tmp_path)
    (model / "meta.json.bak").write_bytes(b"previous backup")
    before = folder_snapshot(tmp_path)
    replace = fio.os.replace
    failed = False

    def fail_once(source: object, target: object) -> None:
        nonlocal failed
        if Path(str(target)) == model / "board.json" and str(source).endswith(".tmp") and not failed:
            failed = True
            raise OSError("authored mid-commit failure")
        replace(source, target)  # type: ignore[arg-type]

    monkeypatch.setattr(fio.os, "replace", fail_once)
    code, _, error, _ = run(monkeypatch, tmp_path, "migrate", "model", "--confirm")
    assert failed and code == 1 and error["code"] == "FEN-1002"
    assert folder_snapshot(tmp_path) == before
