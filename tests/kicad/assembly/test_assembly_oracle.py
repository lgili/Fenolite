# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The placement table against ``kicad-cli`` (capability kicad-oracle, "Assembly tables agree with
kicad-cli"; hypothesis H-K-POS-ROWS; change c0064).

``pcb export pos --format csv --units mm --side both`` is the judge of the rows: reference, value, package
name, X, Y, rotation and side. The comparison of the two BOM sources (``H-K-BOM-MODEL``) is not here: it
needs a schematic that ``kicad-cli`` can export from, which the schematic writer (c0061) brings.
"""

from __future__ import annotations

import csv
import io

import _asmcases as ac
import _probes
import pytest

from fenolite.exports import placement
from fenolite.exports.assembly import DEFAULT, render_csv

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("name", ac.SUBJECTS)
def test_pos_rows(name: str) -> None:
    problems = ac.row_problems(name)
    assert not problems, "; ".join(problems[:5])


def test_pos_rows_probe() -> None:
    assert _probes.run("pos-rows") == "equal"


def test_bottom_side_part_is_compared() -> None:
    """The comparison is not vacuous: the built blink has a bottom-side part, and KiCad lists it."""
    design, text = ac.subject("blink")
    sides = {row["Ref"]: row["Side"] for row in ac.kicad_rows(text)}
    assert sides == {"D1": "bottom", "R1": "top", "U1": "top"}
    rows, _ = ac.model_rows(design)
    assert {row.ref: row.side for row in rows} == sides


def test_rotations_are_the_same_angle_spelled_differently() -> None:
    """What ``docs/assembly.md`` says about angles, measured: under the default template Fenolite prints
    the stored angle within [0°, 360°), and KiCad prints the same angle within (−180°, 180°]."""
    turned = ac.spelled_rotations("turned")
    assert turned == {
        "D1": ("270.00", "-90.000000"),  # on the bottom: the stored angle on both sides, no mirror
        "R1": ("180.00", "180.000000"),
        "U1": ("270.00", "-90.000000"),
    }
    assert ac.spelled_rotations("fixture") == {"D1": ("30.00", "30.000000"), "R1": ("90.00", "90.000000")}


def test_dnp_and_excluded_parts() -> None:
    """KiCad's file keeps a DNP part and leaves out a part excluded from position files. The default
    template leaves the DNP part out as well, so it is KiCad's file without the DNP rows."""
    design, text = ac.subject("flagged")
    assert [row["Ref"] for row in ac.kicad_rows(text)] == ["D1", "R1"]
    source = placement.rows_from_model(design)
    assert [(row.ref, row.dnp) for row in source] == [("D1", False), ("R1", True)]
    assert [row.ref for row in placement.apply(source, DEFAULT.placement)] == ["D1"]


def test_the_rendered_file_reads_as_the_same_table() -> None:
    """The CSV bytes of the default template hold KiCad's columns in KiCad's order."""
    design, text = ac.subject("blink")
    _, cells = ac.model_rows(design)
    header = [column.name for column in ac.KEEP_DNP.columns]
    rendered = list(csv.reader(io.StringIO(render_csv(header, cells, DEFAULT.csv).decode("utf-8"))))
    assert rendered[0] == ["ref", "value", "footprint_name", "x", "y", "rotation", "side"]
    for mine, theirs in zip(rendered[1:], ac.kicad_rows(text), strict=True):
        assert mine[:3] == [theirs["Ref"], theirs["Val"], theirs["Package"]] and mine[6] == theirs["Side"]
        assert [float(v) for v in mine[3:6]] == [float(theirs[k]) % 360 if k == "Rot" else float(theirs[k])
                                                 for k in ("PosX", "PosY", "Rot")]  # fmt: skip
