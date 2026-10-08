# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's ERC on a design with catalog parts and a ``Power`` interface (capability kicad-oracle, "Generated
schematics pass ERC and parity"; kicad-schematic, "Generated sheet content", scenario "Catalog parts
with a supply"; change c0143). The power flag lies in the catalog's library ``Fenolite``, and the running
major reads it there: the regulator's power inputs are driven. Evidence of level ORACLE-VERIFIED(kicad-cli)
for the majors the suite runs on."""

from __future__ import annotations

import _erccases as cases
import pytest
from _buildhelp import resolver
from _flagdesign import SHEET, catalog_definitions, regulator_design

from fenolite.dsl import placements, to_model
from fenolite.lens.build import build_design

pytestmark = pytest.mark.needs_kicad
UNDRIVEN = "power_pin_not_driven"


def _files(*, power: bool) -> dict[str, bytes]:
    design = regulator_design(power=power)
    output = build_design(
        to_model(design),
        placements(design),
        name=design.name,
        copper=2,
        resolver=resolver(cases.major()),
        target=cases.major(),
        **catalog_definitions(),  # type: ignore[arg-type]
    )
    assert output.files, [issue.message for issue in output.issues if issue.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def test_the_flag_in_the_catalog_library_drives_the_supply() -> None:
    files = _files(power=True)
    assert "lib/Fenolite.kicad_sym" in files and "lib/fenolite.kicad_sym" not in files
    found = cases.run_erc(files, SHEET)
    assert found.report is not None, found.run.stderr
    assert [v.type for v in found.report.violations if v.severity == "error"] == []
    assert UNDRIVEN not in {v.type for v in found.report.violations}


def test_without_the_supply_the_inputs_are_not_driven() -> None:
    """The control: the same design without its ``Power`` interface has no flag, and KiCad says so."""
    found = cases.run_erc(_files(power=False), SHEET)
    assert found.report is not None, found.run.stderr
    assert [v.type for v in found.report.violations if v.severity == "error"] == [UNDRIVEN, UNDRIVEN]
