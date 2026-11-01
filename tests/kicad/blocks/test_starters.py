# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Starter usage readback/DRC for the running target; exact-version CI remains a separate proof."""

import json
import shutil
from pathlib import Path

import pytest
from _probes import major, runner

from fenolite.blocks.tests._support import ROOT
from fenolite.testing import load

pytestmark = pytest.mark.needs_kicad
NAMES = ("voltage_divider", "rc_lowpass", "led_indicator", "i2c_pullups", "protected_input")


@pytest.mark.parametrize("target", (9, 10))
@pytest.mark.parametrize("name", NAMES)
def test_starter_usage_drc(name: str, target: int, tmp_path: Path):
    if major() != target:
        pytest.skip(f"target {target} is judged by its own KiCad job")
    source = tmp_path / "source"
    shutil.copytree(ROOT / "usage", source)
    with load(source / f"{name}.py", kicad_version=target) as design:
        files = {
            p.relative_to(design.path).as_posix(): p.read_bytes()
            for p in design.path.rglob("*")
            if p.is_file() and ".fenolite" not in p.parts
        }
        board = next(design.path.glob("*.kicad_pcb")).name
        result = runner().run(
            [
                "pcb",
                "drc",
                "--format",
                "json",
                "--severity-all",
                "--schematic-parity",
                "-o",
                "drc.json",
                board,
            ],
            files=files,
        )
        assert result.ok, result.stderr
        report = json.loads(result.outputs["drc.json"])
        assert not report["violations"], report["violations"]
        assert not report["unconnected_items"], report["unconnected_items"]
        assert not report.get("schematic_parity"), report.get("schematic_parity")
