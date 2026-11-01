# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite build`` and the contracts of the stage ``circuit.rules`` (change c0253)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _contracts import cli, sensor, sensor_model

from fenolite.checks.circuit import circuit_stage
from fenolite.cli._contracts import classes_of


def test_circuit_build_and_check_agree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Change c0253, "Build and check agree": the build reports the contract codes of the stage
    ``circuit.rules`` on the same model, at the same severities, and its errors stop the write."""
    folder = sensor(tmp_path)
    code, env = cli(monkeypatch, "build", str(folder / "bad.py"), "--out", str(folder / "build"), "--dry-run")
    built = sorted((i["code"], i["severity"]) for i in env["issues"] if i["code"].startswith("circuit."))
    model, devices = sensor_model(folder, "bad")
    stage = circuit_stage(model, built=True, devices=devices, classes=classes_of(model))
    judged = sorted((i.code, i.severity) for i in stage.issues)
    assert built == judged
    assert {code for code, severity in built if severity != "info"} == {
        "circuit.expect-unsure", "circuit.rating-current", "circuit.rating-power", "circuit.rating-voltage",
    }  # fmt: skip
    assert code == 5
