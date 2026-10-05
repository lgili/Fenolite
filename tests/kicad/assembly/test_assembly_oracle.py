# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The assembly tables against ``kicad-cli`` (capability kicad-oracle, "Assembly tables agree with
kicad-cli"; hypotheses H-K-POS-ROWS and H-K-BOM-MODEL; change c0064).

``pcb export pos --format csv --units mm --side both`` is the judge of the placement rows: reference,
value, package name, X, Y, rotation and side. ``sch export bom`` is the judge of the parts of a bill: for
a project that ``build`` wrote, the parts of the model are the parts KiCad lists for the schematic.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import _asmcases as ac
import _probes
import pytest
from _projects import tree_snapshot

from fenolite.cli.main import main
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


# --- the bill of materials (H-K-BOM-MODEL) --------------------------------------------------------

COLUMNS = Path(__file__).resolve().parents[2] / "data" / "assembly" / "columns.toml"


@pytest.mark.parametrize("name", ac.BOM_DESIGNS)
def test_bom_sources(name: str) -> None:
    problems = ac.source_problems(name)
    assert not problems, "; ".join(problems[:5])
    assert _probes.run("bom-model-blink" if name == "bill" else "bom-model-units") == "equal"


def test_bom_sources_compare_something() -> None:
    """The comparison is not vacuous: the bill design has a DNP part and a user property on two parts, and
    every part carries the property a build gives it."""
    parts = {part.ref: part for part in ac.kicad_parts("bill")}
    assert sorted(parts) == ["D1", "R1", "R2", "U1"]
    assert [ref for ref, part in parts.items() if part.dnp] == [ac.DNP_REF]
    assert {ref: part.properties.get(ac.BIN) for ref, part in parts.items()} == {
        "D1": None, "R1": "A7", "R2": "A7", "U1": None,
    }  # fmt: skip
    assert all(part.properties.get("fenolite.path") == ref for ref, part in parts.items())
    assert [part.ref for part in ac.kicad_parts("units")] == ["D1", "R1", "U2"]


def _bom(capsys: pytest.CaptureFixture[str], *args: str) -> dict[str, object]:
    code = main(["bom", *args, "--json"])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    return json.loads(captured.out)


@pytest.mark.parametrize("template", [(), ("--template", str(COLUMNS))], ids=["default", "columns"])
def test_the_command_gives_one_bill_from_both_sources(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], template: tuple[str, ...]
) -> None:
    """``fenolite bom`` on the built bill project: the ``kicad`` source, which gets only the schematic and
    the project file, and the ``model`` source give equal lines, and the project folder is untouched."""
    ac.write_project("bill", tmp_path, cache=True)
    before = tree_snapshot(tmp_path)
    from_kicad = _bom(capsys, str(tmp_path), *template)
    from_model = _bom(capsys, str(tmp_path), "--source", "model", *template)
    assert from_kicad["result"]["source"] == "kicad" and from_model["result"]["source"] == "model"  # type: ignore[index]
    assert from_kicad["result"]["lines"] == from_model["result"]["lines"]  # type: ignore[index]
    assert from_kicad["result"]["lines"]  # type: ignore[index]
    assert from_kicad["evidence"]["oracle"] == f"kicad-cli {_probes.version()}"  # type: ignore[index]
    assert from_kicad["issues"] == from_model["issues"] == []
    assert tree_snapshot(tmp_path) == before
