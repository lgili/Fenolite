# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the tests of change c0253 (electrical contracts): small device records authored for the tests,
the sensor example copied and built, and the judge run on a model."""

from __future__ import annotations

import io
import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fenolite.catalog.devices import parse_device
from fenolite.checks.circuit import judge_circuit
from fenolite.checks.circuit.table import CircuitResult
from fenolite.cli import main as cli_main
from fenolite.cli._contracts import classes_of, devices_of
from fenolite.cli._script import run_design_script
from fenolite.dsl import Design, to_model
from fenolite.model import canonical
from fenolite.model.design import Design as ModelDesign
from fenolite.model.library import DeviceDef

ROOT = Path(__file__).resolve().parents[1]
SENSOR = ROOT / "examples" / "circuit" / "sensor"
HEAD = 'schema = "fenolite.device.v0"\nevidence = "UNVERIFIED"\nsummary = "authored for the tests"\n'


def device(text: str) -> DeviceDef:
    """A device record of the tests: ``text`` is the body of a ``fenolite.device.v0`` record."""
    return parse_device(HEAD + text, file="test.toml")


def two_pin(device_id: str, ratings: str, *, symbol: str = "Fenolite:Capacitor") -> DeviceDef:
    """A two-pin device (``P1``, ``P2``) with ``ratings``, the body of its ``[ratings]`` table."""
    return device(
        f'id = "{device_id}"\nsymbol = "{symbol}"\nfootprint = "Fenolite:Chip_0805"\nends = ["P1", "P2"]\n'
        f'[pins]\nP1 = "1"\nP2 = "2"\n[ratings]\n{ratings}\n'
    )


def records(design: Design) -> dict[str, DeviceDef]:
    """The device records of the parts of ``design``, by device id."""
    return {part.device.id: part.device for part in design.parts.values() if part.device is not None}


def judge(design: Design, *, devices: bool = True, classes: bool = True, **more: Any) -> CircuitResult:
    """The judgement of ``design``'s model with its records and the classes of ``roles.classify``."""
    model = to_model(design)
    found = records(design)
    return judge_circuit(
        model,
        devices=found if devices else None,
        classes=classes_of(model, found) if classes else None,
        **more,
    )


def row(result: CircuitResult, row_id: str) -> Any:
    """The row ``row_id`` of ``result``."""
    found = [found for found in result.rows if found.id == row_id]
    assert found, [found.id for found in result.rows]
    return found[0]


def codes(result: CircuitResult, *, at_least: str = "info") -> list[str]:
    order = {"info": 0, "warning": 1, "error": 2}
    return [i.code for i in result.issues if order[i.severity] >= order[at_least]]


def sensor(tmp_path: Path) -> Path:
    """A copy of ``examples/circuit/sensor`` in ``tmp_path``."""
    target = tmp_path / "sensor"
    shutil.copytree(SENSOR, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def sensor_model(folder: Path, variant: str) -> tuple[ModelDesign, Mapping[str, DeviceDef]]:
    """The model of a variant of the sensor and its device records, as ``fenolite check`` resolves them."""
    model = to_model(run_design_script(folder / f"{variant}.py").design)
    return model, devices_of(model, folder)


def cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", out)
        patch.setattr("sys.stderr", err)
        code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or err.getvalue().splitlines()[-1])


def built_sensor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, variant: str = "good") -> Path:
    """The sensor built into ``<copy>/build``. The bad variant's errors stop its build (c0252's build rule),
    so its model is written over a build of the good one: the stage reads the ``.fenolite/`` model only."""
    folder = sensor(tmp_path)
    out = folder / "build"
    code, env = cli(monkeypatch, "build", str(folder / "good.py"), "--out", str(out), "--confirm")
    assert code == 0, env["issues"]
    if variant != "good":
        model, _devices = sensor_model(folder, variant)
        canonical.dump_dir(model, out / ".fenolite")
    return out


__all__ = [
    "SENSOR",
    "built_sensor",
    "cli",
    "codes",
    "device",
    "judge",
    "records",
    "row",
    "sensor",
    "sensor_model",
    "two_pin",
]
