# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original authored purchasing identities reach conversion before writing (c0319/c0334)."""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path

import _drawn
import pytest

import fenolite.convert as package
from fenolite.api.conversion import convert
from fenolite.backends.altium.lower import LossyWriteError
from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import dumps
from fenolite.convert.report import census
from fenolite.core.errors import FormatError


def authored(folder: Path, *, defect: str = "", multiunit: bool = False) -> Path:
    output = _drawn.build("flat", 10)
    folder.mkdir()
    name = _drawn.root_name(output)
    for relative, data in output.files.items():
        if relative.startswith(".fenolite/"):
            continue
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    path = folder / name
    sheet = sch.read_schematic(path)
    native = (
        _drawn.bom_only_multiunit(sheet, 10, defect=defect)
        if multiunit
        else _drawn.bom_only_instance(sheet, 10, dnp=True, defect=defect)
    )
    path.write_text(dumps(native))
    return path.with_suffix(".kicad_pro")


@pytest.mark.parametrize("target", (9, 10))
def test_bom_only_source_reaches_writer_and_census_with_other_source_context_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
):
    project = authored(tmp_path / "source")
    original = package.read_source(project)
    direction = package.DIRECTIONS[("kicad", "kicad")]
    seen = []

    def spy(source, options):
        seen.append(source)
        return direction.write(source, options)

    monkeypatch.setitem(package.DIRECTIONS, ("kicad", "kicad"), replace(direction, write=spy))
    result = convert(project, to="kicad", kicad_version=target, allow_lossy=True)
    assert len(seen) == 1
    held = seen[0]
    accessory = next((c for c in held.design.circuit.components if c.ref == "M1"), None)
    assert accessory is not None and accessory.bom_only and accessory.dnp and not accessory.pins
    assert held.design.board is not None
    assert all(fp.component_id != accessory.id for fp in held.design.board.footprints)
    for field in fields(original):
        if field.name != "design":
            assert getattr(held, field.name) == getattr(original, field.name), field.name
    assert held.design.rules == original.design.rules
    assert held.design.circuit.nets == original.design.circuit.nets
    assert held.design.circuit.netclasses == original.design.circuit.netclasses
    assert census(held.design)["dnp"] == census(original.design).get("dnp", 0) + 1
    row = result.conversion.report.row("dnp")
    assert row is not None and row.source == row.written == census(held.design)["dnp"]
    assert result.unexplained == ()
    sheet = sch.read_schematic(result.conversion.files[project.with_suffix(".kicad_sch").name].decode())
    native = next(s for s in sheet.symbols if s.ref == "M1")
    assert native.in_bom and not native.on_board and native.dnp


@pytest.mark.needs_kicad
def test_bom_only_altium_conversion_refuses_without_a_partial_result(tmp_path: Path):
    project = authored(tmp_path / "source")
    with pytest.raises(LossyWriteError, match="bom|BOM|not hold"):
        convert(project, to="altium", allow_lossy=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["source"]


@pytest.mark.parametrize("defect", ("pins", "no_bom", "on_board", "missing", "power"))
def test_unqualified_accessory_never_becomes_a_bom_only_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
):
    project = authored(tmp_path / "source", defect=defect)
    direction = package.DIRECTIONS[("kicad", "kicad")]
    seen = []

    def spy(source, options):
        seen.append(source)
        return direction.write(source, options)

    monkeypatch.setitem(package.DIRECTIONS, ("kicad", "kicad"), replace(direction, write=spy))
    convert(project, to="kicad", kicad_version=10, allow_lossy=True)
    assert len(seen) == 1 and not any(c.bom_only for c in seen[0].design.circuit.components)


@pytest.mark.parametrize("defect", ("on_board", "dnp"))
def test_incompatible_bom_units_refuse_before_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
):
    project = authored(tmp_path / "source", defect=defect, multiunit=True)
    direction = package.DIRECTIONS[("kicad", "kicad")]

    def forbidden(source, options):
        pytest.fail("ambiguous BOM units reached the writer")

    monkeypatch.setitem(package.DIRECTIONS, ("kicad", "kicad"), replace(direction, write=forbidden))
    before = {p.relative_to(project.parent): p.read_bytes() for p in project.parent.rglob("*") if p.is_file()}
    with pytest.raises(FormatError, match="incompatible"):
        convert(project, to="kicad", kicad_version=9, allow_lossy=True)
    assert before == {
        p.relative_to(project.parent): p.read_bytes() for p in project.parent.rglob("*") if p.is_file()
    }
