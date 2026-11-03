# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A declared native input survives actual import/moved-folder build (c0351)."""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest
from _project_template import SETTINGS, authored, built, imported, snapshot


@pytest.mark.parametrize("target", [9, 10])
def test_actual_import_and_fresh_build_retain_unmanaged_native_settings(target, tmp_path) -> None:
    source = authored(tmp_path / "original", target)
    before = snapshot(source.parent)
    code = imported(tmp_path, source, target=target)
    template = code / "native/project.kicad_pro"
    assert template.read_bytes() == source.read_bytes()
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    script = (code / "design.py").read_text()
    assert "design.kicad_project(" in script and expected in script
    moved = tmp_path / "moved-code"
    shutil.move(code, moved)
    rebuilt = built(tmp_path, moved, target=target)
    project = json.loads(rebuilt.read_text())
    actual = project["schematic"]["drawing"]
    assert {key: actual[key] for key in SETTINGS} == SETTINGS
    assert project["board"]["design_settings"]["rules"]["min_via_annular_width"] == 0.19
    assert snapshot(source.parent) == before
