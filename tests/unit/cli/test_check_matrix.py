# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The verification matrix of ``fenolite check --matrix`` (change c0274; capability cli-contract,
"Verification matrix of check")."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _contracts import cli, waived_sensor

from fenolite.checks.circuit.matrix import COLUMNS, model_digest
from fenolite.cli import main as cli_main
from fenolite.model.canonical import load_dir


def _tree(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()
    }


def _raw(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", out)
        patch.setattr("sys.stderr", io.StringIO())
        code = cli_main.main(list(args))
    return code, out.getvalue()


def test_the_matrix_of_the_bad_sensor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "The matrix of the bad sensor"."""
    out, digest = waived_sensor(monkeypatch, tmp_path)
    before = _tree(out)
    first = _raw(monkeypatch, "check", str(out), "--matrix", "--json")
    second = _raw(monkeypatch, "check", str(out), "--matrix", "--json")
    assert first[0] == second[0] == 5
    one, two = json.loads(first[1]), json.loads(second[1])
    assert json.dumps([one["result"], one["issues"]]) == json.dumps([two["result"], two["issues"]])
    found = one["result"]["matrix"]
    rows = {row["id"]: row for row in found["rows"]}
    capacitor = rows["circuit.rating-voltage:C1:voltage"]
    assert (capacitor["status"], capacitor["digest"]) == ("waived", digest)
    assert capacitor["waiver"] == "circuit.rating-voltage:C1:voltage"
    assert rows["circuit.rating-current:L1:current"]["status"] == "fail"
    assert [row["id"] for row in found["rows"]] == sorted(rows)
    assert set(capacitor) == {"id", "check", "value", "limit", "source", "origin", "status", "evidence",
                              "decidable", "digest", "waiver"}  # fmt: skip
    receipt = found["receipt"]
    assert receipt["model_sha256"] == model_digest(load_dir(out / ".fenolite"))
    assert receipt["stages"] == ["circuit.rules", "roles.rules"] or receipt["stages"] == ["circuit.rules"]
    assert len(receipt["devices_sha256"]) == 64
    assert _tree(out) == before


def test_the_matrix_in_a_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "The matrix in a terminal"."""
    out, _digest = waived_sensor(monkeypatch, tmp_path)
    code, text = _raw(monkeypatch, "check", str(out), "--matrix", "--text")
    assert code == 5
    lines = text.splitlines()
    (header,) = [line for line in lines if line.split()[: len(COLUMNS)] == list(COLUMNS)]
    start = lines.index(header)
    body = [line for line in lines[start + 1 :] if line.startswith(("circuit.", "roles."))]
    assert any(line.startswith("circuit.rating-voltage:C1:voltage") and "waived" in line for line in body)


def test_no_matrix_without_the_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, _digest = waived_sensor(monkeypatch, tmp_path)
    _code, env = cli(monkeypatch, "check", str(out), "--stages", "circuit.rules")
    assert "matrix" not in env["result"]
