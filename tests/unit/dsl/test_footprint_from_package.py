# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``Footprint.from_package`` (change c0260, dsl-footprint-authoring "Generated footprints in a script")."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.dsl import Design, Footprint, mm
from fenolite.dsl.errors import DslError

PACKAGES = Path(__file__).resolve().parents[2] / "data" / "packages"


def _text(stem: str) -> str:
    return (PACKAGES / f"{stem}.toml").read_text(encoding="utf-8")


def test_a_generated_footprint_is_registered() -> None:
    design = Design("demo")
    soic = Footprint.from_package(_text("soic8"))
    design.add_footprint(soic)
    assert "Local:SOIC8_B4.9x3.9_P1.27" in design.footprints
    defn = design.footprints["Local:SOIC8_B4.9x3.9_P1.27"].definition
    assert len(defn.pads) == 8 and defn.bodies and defn.library == "Local"
    with pytest.raises(DslError, match="generated from a package record"):
        soic.pad("9", at=(mm(0), mm(0)), size=(mm(1), mm(1)))
    with pytest.raises(DslError, match="generated from a package record"):
        soic.line((mm(0), mm(0)), (mm(1), mm(0)), layer="F.SilkS", width=mm(0.1))
    with pytest.raises(DslError, match="generated from a package record"):
        soic.net_tie("1", "2")


def test_library_and_positions() -> None:
    mine = Footprint.from_package(_text("soic8"), library="Mine")
    assert mine.lib_id == "Mine:SOIC8_B4.9x3.9_P1.27" and mine.definition.library == "Mine"
    five = Footprint.from_package(_text("connector_xh"), positions=5)
    assert five.lib_id == "Local:CONN5_XH_P2.5" and len(five.definition.pads) == 5


def test_error_finding_in_a_script() -> None:
    inside = _text("soic8").replace('span = "5.80mm..6.20mm"', 'span = "3.0mm..3.5mm"')
    with pytest.raises(DslError, match="package.dimensions-inconsistent"):
        Footprint.from_package(inside)


def test_unreadable_record_and_wrong_arguments() -> None:
    with pytest.raises(DslError, match="FEN-3004"):
        Footprint.from_package('schema = "fenolite.package.v0"\nfamily = "spiral"\n')
    with pytest.raises(DslError, match="read_text"):
        Footprint.from_package(PACKAGES / "soic8.toml")  # type: ignore[arg-type]
    with pytest.raises(DslError, match="unsafe footprint library"):
        Footprint.from_package(_text("soic8"), library="a/b")
