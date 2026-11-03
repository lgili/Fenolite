# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored physical variants retain native identity, including shared sheets (change c0318)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import _drawn
import pytest
from _importcode import PROJECT, build, copy_project, edited, imported

from fenolite.api import equivalent, read_board
from fenolite.backends.kicad import drawn, sch, slots
from fenolite.backends.kicad.sch import read_schematic, write_schematic
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.importer.check import self_check
from fenolite.model import canonical
from fenolite.model.base import Opaque
from fenolite.model.drawn_connect import UnitInfo, component_path, coverage
from fenolite.model.schematic import SchematicSheet

NATIVE = "Mini:Mini_R_0603"
LOCAL = "Mini:Mini_R_0603_2"


def _created(sheet: SchematicSheet) -> SchematicSheet:
    fragments = [
        slot.fragment
        for slot in slots.from_ext(sheet.ext.get("kicad"), ".")
        if isinstance(slot, Opaque) and parse(slot.fragment).name not in drawn.HEADER_HEADS
    ]
    return dataclasses.replace(sheet, ext={sch.DRAWN_EXT: sch.opaque_ext(fragments)})


def _shared_project(tmp: Path) -> Path:
    """One Fenolite-authored physical sheet, two reference/path instances, one changed physical pad."""
    project = copy_project(tmp)
    root_file = project.with_suffix(".kicad_sch")
    root = read_schematic(root_file)
    first, second = [read_schematic(root_file.parent / ref.file) for ref in root.sheets]
    by_prefix = {symbol.ref[0]: symbol for symbol in second.symbols}
    shared = dataclasses.replace(
        _created(first),
        symbols=tuple(
            dataclasses.replace(s, uses=(*s.uses, *by_prefix[s.ref[0]].uses)) for s in first.symbols
        ),
        labels=tuple(
            dataclasses.replace(label, kind="local", name="A", shape="") if label.name == "CH1_A" else label
            for label in first.labels
        ),
    )
    (project.parent / "channel.kicad_sch").write_text(write_schematic(shared).text)
    root_file.write_text(
        write_schematic(
            dataclasses.replace(
                _created(root),
                sheets=tuple(dataclasses.replace(ref, file="channel.kicad_sch") for ref in root.sheets),
            )
        ).text
    )
    text = edited(tmp).read_text().replace('"CH1_A"', '"/ch1/A"').replace('"CH2_A"', '"/ch2/A"')
    project.with_suffix(".kicad_pcb").write_text(text)
    return project


def _snapshot(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def _digest(folder: Path) -> str:
    return hashlib.sha256(
        json.dumps(_snapshot(folder), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _footprints(board: Path) -> tuple[str, ...]:
    return tuple(dumps(node) for node in parse(board.read_text()).nodes("footprint"))


def _assert_physical(source: Path, built: Path) -> None:
    a, b = read_board(source).design, read_board(built).design
    assert a.board is not None and b.board is not None
    by_ref = {c.ref: c.id for c in b.circuit.components}
    first = {c.ref: c.id for c in a.circuit.components}
    source_pads = {c: fp for fp in a.board.footprints for c, cid in first.items() if fp.component_id == cid}
    built_pads = {c: fp for fp in b.board.footprints for c, cid in by_ref.items() if fp.component_id == cid}
    for ref in ("R101", "R201"):
        assert source_pads[ref].lib_ref == built_pads[ref].lib_ref == NATIVE
        assert [p.position for p in source_pads[ref].pads] == [p.position for p in built_pads[ref].pads]
        assert [p.size for p in source_pads[ref].pads] == [p.size for p in built_pads[ref].pads]
    unedited = read_board(PROJECT.with_suffix(".kicad_pcb")).design
    assert unedited.board is not None
    original = next(fp for fp in unedited.board.footprints if fp.component_id == unedited.by_ref["R201"].id)
    assert abs(original.pads[0].position.x - source_pads["R201"].pads[0].position.x) == 100_000
    # The two local pad geometries really differ; identity equality never erases that edit.
    assert [
        (p.position.x - source_pads["R101"].position.x, p.position.y - source_pads["R101"].position.y)
        for p in source_pads["R101"].pads
    ] != [
        (p.position.x - source_pads["R201"].position.x, p.position.y - source_pads["R201"].position.y)
        for p in source_pads["R201"].pads
    ]
    result = equivalent(source, built, level=5, frame="absolute", strict=True)
    assert result.equivalent, result.to_json()
    assert result.to_json()["excluded"] == []
    assert self_check(a, b, ()).explained == ()


@pytest.mark.parametrize("target", (9, 10))
def test_real_variant_builds_native_name_with_exact_pads(tmp_path: Path, target: int) -> None:
    source = edited(tmp_path)
    reply = imported(tmp_path, source, "--confirm", "--kicad-version", str(target))
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    out = tmp_path / "out"
    text = (out / "design.py").read_text()
    assert f'footprint="{NATIVE}"' in text and f'footprint_definition="{LOCAL}"' in text
    local = out / "lib" / "Mini.pretty" / "Mini_R_0603_2.kicad_mod"
    assert local.is_file()
    definition_bytes = local.read_bytes()
    assert build(out, "--kicad-version", str(target)).exit_code == 0
    _assert_physical(source, out / "built" / "edited.kicad_pcb")
    model = canonical.load_dir(out / "built" / ".fenolite")
    assert model.by_ref["R201"].lib_footprint_ref == NATIVE
    assert model.by_ref["R201"].footprint_definition_ref == LOCAL
    before = _footprints(out / "built" / "edited.kicad_pcb")
    assert build(out, "--kicad-version", str(target)).exit_code == 0
    assert _footprints(out / "built" / "edited.kicad_pcb") == before
    _assert_physical(source, out / "built" / "edited.kicad_pcb")
    assert canonical.load_dir(out / "built" / ".fenolite").by_ref["R201"].footprint_definition_ref == LOCAL
    assert local.read_bytes() == definition_bytes


@pytest.mark.parametrize("target", (9, 10))
def test_one_physical_sheet_keeps_native_metadata_for_different_geometry(tmp_path: Path, target: int) -> None:
    project = _shared_project(tmp_path)
    board = project.with_suffix(".kicad_pcb")
    reply = imported(tmp_path, project, "--confirm", "--kicad-version", str(target))
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    out = tmp_path / "out"
    sheet = (out / "sheets" / "channel.py").read_text()
    assert sheet.count("def sheet(") == 1 and f'footprint_definition="{LOCAL}"' in sheet
    assert build(out, "--kicad-version", str(target)).exit_code == 0
    written_symbols = [
        symbol
        for path in (out / "built").rglob("*.kicad_sch")
        for symbol in read_schematic(path).symbols
        if symbol.ref in ("R101", "R201")
    ]
    assert written_symbols and {s.footprint for s in written_symbols} == {NATIVE}
    _assert_physical(board, out / "built" / "two_sheet.kicad_pcb")
    before = _footprints(out / "built" / "two_sheet.kicad_pcb")
    assert build(out, "--kicad-version", str(target)).exit_code == 0
    assert _footprints(out / "built" / "two_sheet.kicad_pcb") == before
    _assert_physical(board, out / "built" / "two_sheet.kicad_pcb")


@pytest.mark.parametrize("changed", ("lib_footprint_ref", "value"))
def test_shared_metadata_guard_compares_native_identity_not_geometry_lookup(changed: str) -> None:
    circuit = _drawn.circuit("repeat")
    parts = tuple(
        dataclasses.replace(c, footprint_definition_ref=LOCAL) if component_path(c) == "ch1/R1" else c
        for c in circuit.components
    )
    units = {component_path(c): UnitInfo(1, frozenset({1})) for c in parts}
    changed_circuit = dataclasses.replace(circuit, components=parts)
    drawing = _drawn.drawn("repeat")
    assert coverage(drawing, changed_circuit, units) == ()
    bad = tuple(
        dataclasses.replace(c, **{changed: "Different"}) if component_path(c) == "ch1/R1" else c
        for c in parts
    )
    issues = coverage(drawing, dataclasses.replace(circuit, components=bad), units)
    assert [i.code for i in issues] == ["drawn.repeated-value-differs"]
    assert issues[0].severity == "error"


@pytest.mark.parametrize("name", ("Mini_R_0603_2", "Mini_R_0603_99", "Other"))
def test_actual_native_name_change_is_not_explained_as_a_variant(name: str) -> None:
    source = read_board(PROJECT.with_suffix(".kicad_pcb")).design
    assert source.board is not None
    cid = source.by_ref["R201"].id
    bad = dataclasses.replace(
        source,
        board=dataclasses.replace(
            source.board,
            footprints=tuple(
                dataclasses.replace(fp, lib_ref=f"Mini:{name}") if fp.component_id == cid else fp
                for fp in source.board.footprints
            ),
        ),
    )
    report = self_check(source, bad, ())
    assert not report.equivalent and report.explained == ()
    assert any(d.level == 3 and d.kind == "footprint-name" for d in report.unexplained)
    assert not equivalent(source, bad, level=3).equivalent


@pytest.mark.parametrize(
    "target,expected",
    (
        (9, "021ad831c254ca8cc7908258abf68881a987f78e1e7607b4ced093f3c128a526"),
        (10, "f89bb04ccb4d8bece6b5fdfd76a5c774e2dda952ef141815a4d2503efc0bca8d"),
    ),
)
def test_ordinary_import_and_rebuild_keep_every_byte(tmp_path: Path, target: int, expected: str) -> None:
    """Pins include c0344 identity caches and c0339 absent-title-block preservation.

    All rebuilt files retain that baseline except the three empty native title blocks
    deliberately omitted by c0339 and their paired manifest hashes;
    c0342 leaves nonalias imports unchanged. The source fixture changed only
    .pro top_level_sheets/sheets, to stay a fresh build after c0344.
    """
    assert imported(tmp_path, PROJECT, "--confirm", "--kicad-version", str(target)).exit_code == 0
    out = tmp_path / "out"
    assert _digest(out) == "34ce82be48949789f53cb7985d26bfe4be00806334b65ef316a520ad22359f03"
    assert build(out, "--kicad-version", str(target)).exit_code == 0
    assert _digest(out / "built") == expected


def test_altium_does_not_silently_use_native_identity_as_geometry(tmp_path: Path) -> None:
    assert imported(tmp_path, edited(tmp_path), "--confirm").exit_code == 0
    reply = build(tmp_path / "out", "--target", "altium")
    assert reply.exit_code == 3 and reply.error is not None
    assert reply.error["code"] == "FEN-3004" and "footprint_definition" in reply.error["message"]
    assert not (tmp_path / "out" / "built").exists()


def test_missing_local_definition_never_falls_back_to_native_geometry(tmp_path: Path) -> None:
    assert imported(tmp_path, edited(tmp_path), "--confirm").exit_code == 0
    script = tmp_path / "out" / "design.py"
    script.write_text(
        script.read_text().replace(f'footprint_definition="{LOCAL}"', 'footprint_definition="Absent:R"')
    )
    reply = build(tmp_path / "out")
    assert reply.exit_code == 3 and reply.error is not None and reply.error["code"] == "FEN-3001"
    assert "'Absent'" in reply.error["message"]
    assert not (tmp_path / "out" / "built").exists()


def test_same_unit_electrical_conflict_still_refuses_with_a_physical_variant(tmp_path: Path) -> None:
    """Changing a pin's electrical type under one source symbol ID is never a physical variant."""
    project = copy_project(tmp_path)
    project.with_suffix(".kicad_pcb").write_bytes(edited(tmp_path).read_bytes())
    child = project.parent / "sheets" / "ch2.kicad_sch"
    root = parse(child.read_text())
    library = root.find("lib_symbols")
    assert library is not None

    def changed(item: Node | Atom) -> Node | Atom:
        if isinstance(item, Atom):
            return item
        if item.name == "pin" and item.atoms()[0].value == "passive":
            return item.with_children((Atom.symbol("input"), *item.children[1:]))
        return item.with_children(tuple(changed(c) for c in item.children))

    root = root.with_children(tuple(changed(c) if c is library else c for c in root.children))
    child.write_text(dumps(root) + "\n")
    before = {p: p.read_bytes() for p in project.parent.rglob("*") if p.is_file()}
    reply = imported(tmp_path, project, "--confirm")
    assert reply.exit_code == 3 and "conflicting definitions" in (reply.error or {})["message"]
    assert not (tmp_path / "out").exists()
    assert {p: p.read_bytes() for p in before} == before
