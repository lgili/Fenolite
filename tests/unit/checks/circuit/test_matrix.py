# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stable requirement row ids and the verification matrix (change c0274; capability verification-loop,
"Stable requirement row ids"; hypothesis ``H-G-CIRCUIT-ROW-IDS``)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _contracts import SENSOR, cli, sensor_model

from fenolite.checks.circuit import judge_circuit
from fenolite.checks.circuit.matrix import matrix_row, matrix_text
from fenolite.cli._contracts import classes_of

BOARD = "contract_board/board.py"
MOVED = (
    '    load = design.part("J2", device="Example:LOAD_1A2", value="3V3 LOAD")\n'
    "    connect(v33, load.supply)\n"
)
BLEEDER_AT = '    if bad:\n        bleeder = design.part("R9"'


def _reordered(folder: Path) -> None:
    """The board of ``folder`` with the load and the connector statements moved: the load first, the
    bleeder before the regulator block."""
    path = folder / BOARD
    text = path.read_text(encoding="utf-8")
    assert MOVED in text and BLEEDER_AT in text
    text = text.replace(MOVED, "")
    anchor = '    v33 = design.rail("3V3", ground=gnd)'
    head, tail = text.split(anchor, 1)
    line_end = tail.index("\n") + 1
    text = head + anchor + tail[:line_end] + MOVED + tail[line_end:]
    bleeder_start = text.index(BLEEDER_AT)
    bleeder_end = text.index("        bleeder.place(", bleeder_start)
    bleeder_end = text.index("\n", bleeder_end) + 1
    block = text[bleeder_start:bleeder_end]
    text = text[:bleeder_start] + text[bleeder_end:]
    anchor = "    vref = volt("
    at = text.index(anchor)
    text = text[:at] + block + text[at:]
    path.write_text(text, encoding="utf-8")


def _ids(folder: Path) -> list[str]:
    model, devices = sensor_model(folder, "bad")
    return sorted(
        row.id for row in judge_circuit(model, devices=devices, classes=classes_of(model, devices)).rows
    )


def test_ids_stable_across_order_and_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Ids survive a reordered script": the bad sensor and a reordered copy give the same ids, and
    ``fenolite check --matrix`` on builds with ``--seed 1`` and ``--seed 2`` lists the same ids."""
    plain, moved = tmp_path / "plain", tmp_path / "moved"
    for target in (plain, moved):
        shutil.copytree(SENSOR, target, ignore=shutil.ignore_patterns("__pycache__"))
    _reordered(moved)
    assert (moved / BOARD).read_text(encoding="utf-8") != (plain / BOARD).read_text(encoding="utf-8")
    first = _ids(plain)
    assert first == _ids(moved) and "circuit.rating-voltage:C1:voltage" in first
    seen: list[list[str]] = []
    for seed, folder in (("1", plain), ("2", moved)):
        out = folder / "build"
        code, env = cli(monkeypatch, "build", str(folder / "good.py"), "--out", str(out), "--seed", seed,
                        "--confirm")  # fmt: skip
        assert code == 0, env["issues"]
        code, env = cli(monkeypatch, "check", str(out), "--matrix")
        seen.append([row["id"] for row in env["result"]["matrix"]["rows"]])
    assert seen[0] == seen[1] and seen[0]


def test_matrix_rows_and_text() -> None:
    row = {
        "id": "circuit.rating-voltage:C3:voltage",
        "check": "circuit.rating-voltage",
        "value": {"text": "0..13.2V", "origin": {"kind": "rig"}},
        "limit": {"text": "..12.5V", "source": "policy", "evidence": "UNVERIFIED"},
        "status": "fail",
        "decidable": "build",
        "digest": "9f2c4a1b0d3e5f67",
        "waiver": None,
    }
    found = matrix_row(row)
    assert (found["origin"], found["status"], found["source"]) == ("rig", "fail", "policy")
    assert matrix_row({**row, "waiver": "w"})["status"] == "waived"
    text = matrix_text([found])
    assert text.splitlines()[0].split() == ["id", "check", "value", "limit", "source", "status"]
    assert text.splitlines()[1].split() == [
        "circuit.rating-voltage:C3:voltage", "circuit.rating-voltage", "0..13.2V", "..12.5V", "policy", "fail"
    ]  # fmt: skip
