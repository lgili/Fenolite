# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Preserve authored project rule representations through import (c0352)."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, copy_project, imported

from fenolite.backends.kicad import _json
from fenolite.backends.kicad.pro import read_project
from fenolite.cli._script import run_design_script
from fenolite.dsl import to_model


def test_import_emits_actual_default_class_and_rebuilds_its_fields(tmp_path: Path) -> None:
    source = copy_project(tmp_path)
    data = _json.loads(source.read_text())
    default = next(cls for cls in data["net_settings"]["classes"] if cls["name"] == "Default")
    default["clearance"] = _json.JsonNumber("0.15")
    default["track_width"] = _json.JsonNumber("0.31")
    source.write_text(_json.dumps(data))
    result = imported(tmp_path, source, "--confirm")
    assert result.exit_code == 0, result.error
    script = tmp_path / "out" / "design.py"
    model = to_model(run_design_script(script).design)
    classes = {cls.name: cls for cls in model.circuit.netclasses}
    assert "Default" in classes, "native Default must not disappear from emitted canonical code"
    assert (classes["Default"].clearance, classes["Default"].track_width) == (150_000, 310_000)
    assert "Power" in classes
    assert build(script.parent).exit_code == 0
    info = read_project(script.parent / "built" / "two_sheet.kicad_pro")
    rebuilt = {cls.name: cls for cls in info.classes}
    assert (rebuilt["Default"].clearance, rebuilt["Default"].track_width) == (150_000, 310_000)
    assert (rebuilt["Power"].clearance, rebuilt["Power"].track_width) == (200_000, 500_000)
