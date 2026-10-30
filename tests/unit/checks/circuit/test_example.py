# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reference example of change c0253 (capability electrical-contracts, "Contract reference example";
hypothesis ``H-G-CIRCUIT-EXAMPLE``)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from _contracts import SENSOR, sensor, sensor_model

from fenolite.analysis.requirements import UNIT_KEYS, load_requirements
from fenolite.checks.circuit import judge_circuit
from fenolite.cli._contracts import classes_of


def _judged(tmp_path: Path, variant: str):  # type: ignore[no-untyped-def]
    model, devices = sensor_model(sensor(tmp_path), variant)
    return judge_circuit(model, devices=devices, classes=classes_of(model))


def test_good_and_bad_sensors(tmp_path: Path) -> None:
    """Scenario "Good and bad sensors": nothing above info on the good variant, exactly the four designed
    findings with their values on the bad one."""
    good = _judged(tmp_path / "good", "good")
    assert [i for i in good.issues if i.severity != "info"] == []
    bad = _judged(tmp_path / "bad", "bad")
    found = {i.code: i for i in bad.issues if i.severity != "info"}
    assert sorted(found) == [
        "circuit.expect-unsure",
        "circuit.rating-current",
        "circuit.rating-power",
        "circuit.rating-voltage",
    ]
    assert len([i for i in bad.issues if i.severity != "info"]) == 4
    for code, texts in {
        "circuit.rating-voltage": ("C1", "buck1/C_in", "13.2V", "8V", "capacitor_voltage"),
        "circuit.rating-current": ("L1", "1.2A", "1A"),
        "circuit.expect-unsure": ("buck1/expect#1", "VOUT set by the divider"),
        "circuit.rating-power": ("R9", "176mW", "100mW"),
    }.items():
        assert all(text in found[code].message for text in texts), found[code].message


def test_requirements_use_unit_keys_only() -> None:
    text = (SENSOR / "requirements.toml").read_text(encoding="utf-8")
    assert text.startswith("# requirements.toml: authored for Fenolite")
    raw = {raw for raw, _kind in UNIT_KEYS.values()}
    rows = [row for table in tomllib.loads(text).values() if isinstance(table, list) for row in table]
    assert rows and not any(raw & set(row) for row in rows)
    assert load_requirements(text).currents[0].milliamps == 3000
