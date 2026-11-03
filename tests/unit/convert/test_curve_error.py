# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual authored project conversion keeps unsupported geometry loss in its closed ledger (c0340)."""

from __future__ import annotations

from pathlib import Path

import _drawn_fonts
import pytest

from fenolite import api
from fenolite.backends.kicad import pro
from fenolite.convert import LossyConversionError, convert_project
from fenolite.convert.report import BY_NAME


def test_explicit_project_curve_conversion_refuses_or_reports_exact_existing_loss(tmp_path: Path) -> None:
    folder = _drawn_fonts.original(tmp_path / "original", target=10)
    path = folder / "font_probe.kicad_pro"
    data = pro.read_project_text(path.read_text())
    data["board"]["design_settings"]["rules"]["max_error"] = pro.JsonNumber("0.01")
    path.write_text(pro.write_project_text(data))
    with pytest.raises(LossyConversionError) as error:
        convert_project(path, to="altium", pour="outline")
    assert "project-curve-error" in error.value.report.refused
    row = error.value.report.row("project-curve-error")
    assert row is not None and (row.source, row.written, row.lost) == (1, 0, 1)
    assert row.group == "project" and row.loss == "refuse"
    assert BY_NAME["project-curve-error"].loss == "refuse"
    allowed = convert_project(path, to="altium", allow_lossy=True, pour="outline")
    assert allowed.report.row("project-curve-error") == row
    strict = api.run(
        "convert", str(path), "--to", "altium", "--out", "out", "--dry-run", cwd=tmp_path, seed=0
    )
    assert strict.exit_code == 7 and strict.error and strict.error["code"] == "FEN-7001"
    assert not strict.result.get("plan") and not (tmp_path / "out").exists()
