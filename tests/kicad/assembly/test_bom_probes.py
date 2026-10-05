# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What ``kicad-cli sch export bom`` writes for the call of ``KicadCli.export_bom`` (capability
kicad-oracle, "BOM export through the package runner"; hypothesis H-K-BOM-CSV; change c0064). The
schematics are those ``build`` writes for the running major; the cases are in ``_asmcases``."""

from __future__ import annotations

import _asmcases as ac
import _probes
import pytest

from fenolite.backends.kicad import bom as kicad_bom

pytestmark = pytest.mark.needs_kicad
PROBES = (
    "bom-csv-header",
    "bom-csv-rows",
    "bom-csv-units",
    "bom-csv-dnp",
    "bom-csv-left-out",
    "bom-csv-unknown-field",
)


@pytest.mark.parametrize("probe", PROBES)
def test_probe(probe: str) -> None:
    assert _probes.run(probe) == "equal"


def test_the_file_is_quoted_csv_with_the_asked_header() -> None:
    """Every field is in double quotes and separated by commas, the tool's defaults on both majors; a
    reader that expects them is ``read_bom_csv``."""
    text = ac.bom_text("bill")
    lines = text.splitlines()
    assert lines[0] == ",".join(f'"{name}"' for name in ac.PROBE_FIELDS)
    assert all(line.startswith('"') and line.endswith('"') for line in lines[1:]) and len(lines) == 5
    rows = kicad_bom.read_bom_csv(text, fields=ac.PROBE_FIELDS)
    assert {row.ref: dict(row.properties) for row in rows} == {
        "D1": {},
        "R1": {ac.BIN: "A7"},
        "R2": {ac.BIN: "A7"},
        "U1": {},
    }


def test_the_export_writes_one_csv() -> None:
    run = ac.exported("bill", ac.PROBE_FIELDS)
    assert run.ok and [name for name in run.outputs if name.endswith(".csv")] == ["bom.csv"]


def test_the_cases_are_not_vacuous() -> None:
    """The bill design does hold a power flag, a DNP part and two parts of one value; the units design
    does hold a part with three units."""
    bill = ac.bom_output("bill", ac.major()).files[ac.schematic_name("bill")].decode("utf-8")
    assert "#FLG" in bill and "(dnp yes)" in bill and bill.count('(property "Value" "330"') == 2
    units = ac.bom_output("units", ac.major()).files[ac.schematic_name("units")].decode("utf-8")
    assert units.count('(property "Reference" "U2"') == 3
