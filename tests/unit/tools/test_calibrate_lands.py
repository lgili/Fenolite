# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``tools/calibrate_lands.py`` (change c0260, requirement "Calibration of land goals")."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

from fenolite.catalog.footprints import generate, read_package
from fenolite.catalog.footprints.calibration import (
    Sample,
    calibrate,
    lower_median,
    ratio_step,
    sample,
    to_step,
)
from fenolite.catalog.footprints.lands import LANDS, Goals, LandTable
from fenolite.catalog.footprints.record import package_from

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools" / "calibrate_lands.py"
RECORDS = ROOT / "tests" / "data" / "packages" / "calibration"


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("calibrate_lands", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_calibration_is_reproducible() -> None:
    done = subprocess.run(
        [sys.executable, str(TOOL), "--check"], capture_output=True, text=True, cwd=ROOT, check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "is up to date" in done.stdout
    for cls in LANDS[1].goals:
        line = next(row for row in done.stdout.splitlines() if row.startswith(f"{cls}: calibrated"))
        assert all(name in line for name in LANDS[1].calibration[cls])


def test_rendering_equals_the_committed_table() -> None:
    tool = _tool()
    result, text = tool.run()
    assert text == (ROOT / "src" / "fenolite" / "catalog" / "footprints" / "_table1.py").read_text(
        encoding="utf-8"
    )
    assert dict(result.goals) == dict(LANDS[1].goals)


def test_uncalibrated_class() -> None:
    two = [Sample("A", "smd-tab", Goals(1, 2, 3)), Sample("B", "smd-tab", Goals(1, 2, 3))]
    result = calibrate(two)
    assert "smd-tab" not in result.goals and result.used["smd-tab"] == ("A", "B")
    raw = tomllib.loads((ROOT / "tests" / "data" / "packages" / "soic8.toml").read_text(encoding="utf-8"))
    raw.pop("land")
    package = package_from(raw)
    table = LandTable(version=1, goals=dict(result.goals))
    generated = generate(package, table=table)
    assert generated.footprint is None and [i.code for i in generated.issues] == ["package.no-goals"]


def test_median_and_rounding() -> None:
    assert lower_median([4, 1, 3, 2]) == 2 and lower_median([5, 1, 3]) == 3
    assert (to_step(25_000), to_step(-25_000), to_step(24_999), to_step(-4_999)) == (
        30_000,
        -30_000,
        20_000,
        0,
    )
    from fractions import Fraction

    assert ratio_step(Fraction(5, 6)) == Fraction(83, 100) and ratio_step(Fraction(1, 200)) == Fraction(
        1, 100
    )


def test_every_calibration_record_samples() -> None:
    names = []
    for path in sorted(RECORDS.glob("*.toml")):
        found = sample(read_package(path.read_text(encoding="utf-8"), file=path.name))
        assert found.goals is not None or found.ratio is not None
        names.append(found.name)
    assert len(names) == len(set(names)) == 27
