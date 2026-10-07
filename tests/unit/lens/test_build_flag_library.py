# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The library that holds the power flag (capability kicad-schematic, "Generated sheet content" and
"Embedded symbols of a generated sheet"; design-dsl, "Build writes the schematic and its libraries";
change c0143).

A design with parts of the built-in catalog (library ``Fenolite``) and a ``Power`` interface was refused
with ``build.vendor-unsafe-name``, because the flag lay in a library ``fenolite`` (releases 0.2.0 and
0.2.1). The flag now joins a library of the design whose name differs from ``fenolite`` in letter case
only; every other design keeps the library ``fenolite`` and its bytes. The Altium build of the same
design is in ``test_build_flag_library_altium.py``."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import BLINK_DIR, blink, footprint_file, project, resolver, symbol_lib
from _flagdesign import FLAGGED, SHEET, catalog_definitions, regulator_design

from fenolite.backends.kicad import symembed
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.dsl import Design, Net, Part, Power, Symbol, connect, mm, placements, to_model
from fenolite.lens.build import BuildOutput, build_design

OLD = "lib/fenolite.kicad_sym"
NEW = "lib/Fenolite.kicad_sym"
TARGETS = (9, 10)


def _build(design: Design, target: int = 10, project_dir: Path = BLINK_DIR, **kwargs: object) -> BuildOutput:
    return build_design(
        to_model(design),
        placements(design),
        name=design.name,
        copper=2,
        resolver=resolver(target, project_dir),
        target=target,
        **kwargs,  # type: ignore[arg-type]
    )


def _errors(output: BuildOutput) -> list[tuple[str, str]]:
    return [(issue.code, issue.where) for issue in output.issues if issue.severity == "error"]


def _names(output: BuildOutput, rel: str) -> list[str]:
    library = Path(rel).stem
    return sorted(s.name for s in read_symbol_library(output.files[rel].decode("utf-8"), library=library))


def _rows(output: BuildOutput) -> int:
    return output.files["sym-lib-table"].decode("utf-8").count("(lib ")


def test_the_flag_library_of_a_design() -> None:
    assert symembed.flag_library([]) == "fenolite" == symembed.FLAG_LIBRARY
    assert symembed.flag_library(["Mini", "Device"]) == "fenolite"
    assert symembed.flag_library(["Mini", "Fenolite"]) == "Fenolite"
    assert symembed.flag_library(["fenoLITE", "FENOLITE"]) == "FENOLITE"  # the first in sorted order
    assert symembed.is_power_flag("fenolite:PWR_FLAG") and symembed.is_power_flag("Fenolite:PWR_FLAG")
    assert not symembed.is_power_flag("Fenolite:LED") and not symembed.is_power_flag("power:PWR_FLAG")
    assert symembed.power_flag(10).lib_id == "fenolite:PWR_FLAG"
    assert symembed.power_flag(10, "Fenolite").lib_id == "Fenolite:PWR_FLAG"


@pytest.mark.parametrize("target", TARGETS)
def test_catalog_parts_with_a_power_interface_build(target: int) -> None:
    """Scenario "Catalog parts with a supply": the flag lies in the catalog's library."""
    design = regulator_design()
    output = _build(design, target, **catalog_definitions())
    assert _errors(output) == [] and output.files
    assert NEW in output.files and OLD not in output.files and _rows(output) == 1
    assert _names(output, NEW) == ["Connector_2", "Linear_Regulator", "PWR_FLAG"]
    sheet = output.files[SHEET].decode("utf-8")
    assert sheet.count('(lib_id "Fenolite:PWR_FLAG")') == len(FLAGGED) and "fenolite:PWR_FLAG" not in sheet
    assert sheet.count('(symbol "Fenolite:PWR_FLAG"') == 1
    assert output.summary["schematic"]["power_flags"] == len(FLAGGED)  # type: ignore[index]


@pytest.mark.parametrize("target", TARGETS)
def test_the_flag_symbol_is_the_same_in_either_library(target: int) -> None:
    here = symembed.write_symbol_library([symembed.power_flag(target, "Fenolite")], target=target)
    assert here == symembed.write_symbol_library([symembed.power_flag(target)], target=target)


@pytest.mark.parametrize("target", TARGETS)
def test_catalog_parts_without_a_supply_get_no_flag(target: int) -> None:
    design = regulator_design(power=False)
    output = _build(design, target, **catalog_definitions())
    assert _errors(output) == [] and _names(output, NEW) == ["Connector_2", "Linear_Regulator"]
    assert "PWR_FLAG" not in output.files[SHEET].decode("utf-8")


@pytest.mark.parametrize("target", TARGETS)
def test_a_design_without_such_a_library_keeps_its_files(
    target: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Other designs keep their bytes": the blink names no library like ``fenolite``, so its flag
    stays in ``lib/fenolite.kicad_sym`` and no file differs from a build that never looks for a host."""
    output = _build(blink(), target)
    assert _errors(output) == [] and OLD in output.files and NEW not in output.files
    assert _names(output, OLD) == ["PWR_FLAG"]
    assert '(lib_id "fenolite:PWR_FLAG")' in output.files["blink.kicad_sch"].decode("utf-8")
    monkeypatch.setattr(symembed, "flag_library", lambda libraries: symembed.FLAG_LIBRARY)
    assert _build(blink(), target).files == output.files


def _mine(library: str, name: str) -> Symbol:
    symbol = Symbol(library, name, reference="J")
    symbol.pin("1", "P", etype="passive", at=(mm(0), mm(0)), length=mm(2.54))
    return symbol


def test_an_authored_library_of_that_name_holds_the_flag() -> None:
    """A library the design authors and no part uses decides too: one file, the flag beside its symbol."""
    mine = _mine("Fenolite", "Mine")
    output = _build(blink(), authored_symbols={mine.lib_id: mine.definition})
    assert _errors(output) == [] and OLD not in output.files
    assert _names(output, NEW) == ["Mine", "PWR_FLAG"]
    assert '(lib_id "Fenolite:PWR_FLAG")' in output.files["blink.kicad_sch"].decode("utf-8")


def test_an_authored_symbol_of_the_flags_name_is_refused() -> None:
    """Scenario "The flag's name is taken": located at the symbol, nothing written."""
    mine = _mine("Fenolite", "PWR_FLAG")
    output = _build(blink(), authored_symbols={mine.lib_id: mine.definition})
    assert output.files == {} and _errors(output) == [("build.reserved-library", "Fenolite:PWR_FLAG")]


def _project_design(tmp_path: Path, first: str, *, power: bool) -> BuildOutput:
    """Two two-pin parts on symbols ``first`` and ``Two`` of a project library ``FENOLITE``."""
    (tmp_path / "T.pretty").mkdir()
    (tmp_path / "T.pretty" / "F2.kicad_mod").write_text(
        footprint_file("F2", ["1", "2"]), encoding="utf-8", newline="\n"
    )
    pins = [("1", "A"), ("2", "B")]
    (tmp_path / "FENOLITE.kicad_sym").write_text(
        symbol_lib({"PWR_FLAG": pins, "Two": pins}), encoding="utf-8", newline="\n"
    )
    folder = project(tmp_path, {"T": "${KIPRJMOD}/T.pretty"}, {"FENOLITE": "${KIPRJMOD}/FENOLITE.kicad_sym"})
    design = Design("taken")
    design.board(mm(30), mm(20))
    j1 = Part("J1", f"FENOLITE:{first}", footprint="T:F2")
    j2 = Part("J2", "FENOLITE:Two", footprint="T:F2")
    design.add(j1, j2)
    vin, gnd = Net("VIN"), Net("GND")
    connect(vin, j1[1], j2[1])
    connect(gnd, j1[2], j2[2])
    if power:
        design.add(Power(vin, gnd))
    j1.place(mm(8), mm(10))
    j2.place(mm(20), mm(10))
    return _build(design, project_dir=folder)


def test_a_project_library_of_that_name_holds_the_flag(tmp_path: Path) -> None:
    output = _project_design(tmp_path, "Two", power=True)
    assert _errors(output) == [] and OLD not in output.files
    assert _names(output, "lib/FENOLITE.kicad_sym") == ["PWR_FLAG", "Two"] and _rows(output) == 1
    assert '(lib_id "FENOLITE:PWR_FLAG")' in output.files["taken.kicad_sch"].decode("utf-8")


def test_a_placed_symbol_of_the_flags_name_is_refused(tmp_path: Path) -> None:
    output = _project_design(tmp_path, "PWR_FLAG", power=True)
    assert output.files == {} and _errors(output) == [("build.reserved-library", "FENOLITE:PWR_FLAG")]


def test_a_symbol_of_the_flags_name_builds_where_no_flag_is_needed(tmp_path: Path) -> None:
    """Without a flag no name is kept: the design builds as it did."""
    output = _project_design(tmp_path, "PWR_FLAG", power=False)
    assert _errors(output) == [] and _names(output, "lib/FENOLITE.kicad_sym") == ["PWR_FLAG", "Two"]
