# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual source-sheet factories (board-to-code, "Modules per sheet"; c0275).

All hierarchy variants below are made from the authored project in temporary folders only.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from _drawn import build as drawn_build
from _importcode import DATA, PROJECT, STAMP, board_only, build, built_board, copy_project, imported

from fenolite.api import run
from fenolite.backends.kicad import drawn, sch, slots
from fenolite.backends.kicad.sch import read_schematic, write_schematic
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.model.base import Opaque
from fenolite.model.schematic import SchematicSheet


def _created(sheet: SchematicSheet) -> SchematicSheet:
    """Keep the native drawing when changing a fixture's modelled sheet cardinality."""
    fragments = [
        slot.fragment
        for slot in slots.from_ext(sheet.ext.get("kicad"), ".")
        if isinstance(slot, Opaque) and parse(slot.fragment).name not in drawn.HEADER_HEADS
    ]
    return replace(sheet, ext={sch.DRAWN_EXT: sch.opaque_ext(fragments)})


def test_source_sheet_files(tmp_path: Path) -> None:
    reply = imported(tmp_path, PROJECT, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["modules"] == ["ch1", "ch2"]
    text = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert '_sheet_ch1.sheet(design, path="ch1"' in text
    assert '_sheet_ch2.sheet(design, path="ch2"' in text
    assert "r201 = Part(" not in text
    assert sorted(p.name for p in (tmp_path / "out" / "sheets").glob("*.py")) == [
        "__init__.py",
        "ch1.py",
        "ch2.py",
    ]
    second = (tmp_path / "out" / "sheets" / "ch2.py").read_text(encoding="utf-8")
    assert 'refs.get("R101", "R201")' in second and 'name="R101"' in second
    assert build(tmp_path / "out").exit_code == 0
    design = built_board(tmp_path / "out").design
    paths = {c.ref: c.properties.get("fenolite.path") for c in design.circuit.components}
    assert paths["R101"] == "ch1/R101" and paths["R201"] == "ch2/R101"


def test_group_members_across_source_sheet_factories(tmp_path: Path) -> None:
    """A group can refer to a factory-local part and a root part without leaking local variables."""
    project = copy_project(tmp_path / "src")
    board = project.with_suffix(".kicad_pcb")
    root = parse(board.read_text(encoding="utf-8"))
    refs: dict[str, str] = {}
    for footprint in root.nodes("footprint"):
        for prop in footprint.nodes("property"):
            atoms = prop.atoms()
            if len(atoms) >= 2 and atoms[0].value == "Reference":
                uuid = footprint.find("uuid")
                assert uuid is not None
                refs[atoms[1].value] = uuid.atoms()[0].value
    group = parse(
        '(group "mixed" (uuid "02750000-0000-4000-8000-000000000001") '
        f'(members "{refs["J1"]}" "{refs["R101"]}"))'
    )
    board.write_text(dumps(root.with_children([*root.children, group])) + "\n", encoding="utf-8")
    reply = imported(tmp_path, project, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    assert build(tmp_path / "out").exit_code == 0
    text = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'design.group("mixed", design.parts["ch1/R101"], j1)' in text


def test_altium_source_sheet_files(tmp_path: Path) -> None:
    made = run(
        "build",
        str(DATA / "src" / "two_sheet.py"),
        "--target",
        "altium",
        "--altium-sheets",
        "modules",
        "--out",
        "alt",
        "--confirm",
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert made.exit_code == 0, made.error
    reply = imported(tmp_path, tmp_path / "alt" / "two_sheet.PrjPcb", "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["modules"] == ["ch1", "ch2"]
    source_files = [p for p in (tmp_path / "alt").glob("*.SchDoc") if p.stem != "two_sheet"]
    assert len(source_files) == 2
    from fenolite.importer.emit.design import module_name

    assert sorted(p.stem for p in (tmp_path / "out" / "sheets").glob("*.py")) == sorted(
        ["__init__", *[module_name(p.stem) for p in source_files]]
    )
    assert build(tmp_path / "out").exit_code == 0


def _shared_project(tmp_path: Path) -> Path:
    """Two instances of one actual source file, with distinct instance references and board poses."""
    project = copy_project(tmp_path)
    root_file = project.with_suffix(".kicad_sch")
    root = read_schematic(root_file)
    first, second = [read_schematic(root_file.parent / ref.file) for ref in root.sheets]
    by_prefix = {symbol.ref[0]: symbol for symbol in second.symbols}
    symbols = tuple(
        replace(symbol, uses=(*symbol.uses, *by_prefix[symbol.ref[0]].uses)) for symbol in first.symbols
    )
    # One physical sheet must use a local channel label, so its two instances remain separate nets.
    labels = tuple(
        replace(label, kind="local", name="A", shape="") if label.name == "CH1_A" else label
        for label in first.labels
    )
    shared = replace(_created(first), symbols=symbols, labels=labels)
    (project.parent / "channel.kicad_sch").write_text(write_schematic(shared).text, encoding="utf-8")
    root = replace(
        _created(root), sheets=tuple(replace(ref, file="channel.kicad_sch") for ref in root.sheets)
    )
    root_file.write_text(write_schematic(root).text, encoding="utf-8")
    board = project.with_suffix(".kicad_pcb")
    board.write_text(board.read_text().replace('"CH1_A"', '"/ch1/A"').replace('"CH2_A"', '"/ch2/A"'))
    return project


def _net_constructors(script: str) -> list[str]:
    return [
        node.args[0].value
        for node in ast.walk(ast.parse(script))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Net"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]


def test_repeated_sheet(tmp_path: Path) -> None:
    project = _shared_project(tmp_path)
    reply = imported(tmp_path, project, "--confirm")
    assert reply.exit_code == 0, reply.error
    out = tmp_path / "out"
    assert sorted(p.name for p in (out / "sheets").glob("*.py")) == ["__init__.py", "channel.py"]
    main = (out / "design.py").read_text(encoding="utf-8")
    assert main.count("_sheet_channel.sheet(") == 2
    assert 'refs={"D101": "D201", "R101": "R201"}' in main
    sheet = (out / "sheets" / "channel.py").read_text(encoding="utf-8")
    assert sheet.count("def sheet(") == 1
    assert sorted(_net_constructors(sheet)) == ["/ch1/A", "/ch2/A"]
    assert sorted(_net_constructors(main)) == ["GND", "VIN"]
    assert 'gnd = nets["gnd"]' in sheet and 'vin = nets["vin"]' in sheet
    emitted = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert build(out).exit_code == 0
    design = built_board(out).design
    paths = {c.ref: c.properties.get("fenolite.path") for c in design.circuit.components}
    assert paths["R101"] == "ch1/R101" and paths["R201"] == "ch2/R101"
    assert imported(tmp_path, project, "--confirm", out="again").exit_code == 0
    assert emitted == {
        p.relative_to(tmp_path / "again"): p.read_bytes()
        for p in (tmp_path / "again").rglob("*")
        if p.is_file()
    }


def test_net_created_at_deepest_common_sheet(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    root_file = project.with_suffix(".kicad_sch")
    root = read_schematic(root_file)
    # An authored intermediate sheet owns the net joining both child channels; VIN/GND also reach J1.
    power = SchematicSheet(
        id=root.id,
        native_ids={"kicad": "bcab8921-8324-4ef7-bc88-0230aa615e85"},
        name="power",
        sheets=root.sheets,
    )
    (project.parent / "power.kicad_sch").write_text(write_schematic(power).text, encoding="utf-8")
    parent = replace(root.sheets[0], name="power", file="power.kicad_sch")
    root_file.write_text(write_schematic(replace(_created(root), sheets=(parent,))).text, encoding="utf-8")
    board = project.with_suffix(".kicad_pcb")
    board.write_text(board.read_text().replace('"CH1_A"', '"CHANNEL_A"').replace('"CH2_A"', '"CHANNEL_A"'))
    for child_ref in root.sheets:
        child_file = project.parent / child_ref.file
        child = read_schematic(child_file)
        labels = tuple(
            replace(label, name="CHANNEL_A") if label.name in ("CH1_A", "CH2_A") else label
            for label in child.labels
        )
        child_file.write_text(write_schematic(replace(_created(child), labels=labels)).text)
    reply = imported(tmp_path, project, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["equivalence"]["equivalent"]
    out = tmp_path / "out"
    scripts = {path.stem: path.read_text() for path in out.rglob("*.py")}
    assert sorted(_net_constructors(scripts["design"])) == ["GND", "VIN"]
    assert _net_constructors(scripts["power"]) == ["CHANNEL_A"]
    assert not _net_constructors(scripts["ch1"]) and not _net_constructors(scripts["ch2"])
    assert 'channel_a = nets["channel_a"]' in scripts["ch1"]
    assert "channel_a=channel_a" in scripts["power"]
    assert build(out).exit_code == 0
    paths = {c.ref: c.properties.get("fenolite.path") for c in built_board(out).design.circuit.components}
    assert paths["R101"] == "power/ch1/R101" and paths["R201"] == "power/ch2/R101"


def test_local_net_does_not_shadow_factory_parameters(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    board = project.with_suffix(".kicad_pcb")
    board.write_text(board.read_text().replace('"CH1_A"', '"module"').replace('"CH2_A"', '"refs"'))
    reply = imported(tmp_path, project, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["equivalence"]["equivalent"]
    assert build(tmp_path / "out").exit_code == 0


def test_source_sheet_filename_sanitized(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    root_file = project.with_suffix(".kicad_sch")
    root = read_schematic(root_file)
    old, second = root.sheets
    (project.parent / old.file).rename(project.parent / "Power Supply.kicad_sch")
    first = replace(old, name="Power Supply", file="Power Supply.kicad_sch")
    root_file.write_text(write_schematic(replace(root, sheets=(first, second), ext={})).text)
    reply = imported(tmp_path, project, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert (tmp_path / "out" / "sheets" / "power_supply.py").is_file()
    renamed = [i for i in (reply.envelope or {})["issues"] if i["code"] == "import.sheet-renamed"]
    assert any("Power Supply" in i["message"] and "power_supply" in i["message"] for i in renamed)


def test_board_without_schematic_writes_no_sheets_folder(tmp_path: Path) -> None:
    reply = imported(tmp_path, board_only(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert not (tmp_path / "out" / "sheets").exists()


def test_single_sheet_writes_no_sheets_folder(tmp_path: Path) -> None:
    # Use a complete single-sheet project, rather than orphaning board parts by deleting child sheets.
    made = drawn_build("flat")
    folder = tmp_path / "original"
    for relative, data in made.files.items():
        if relative.startswith(".fenolite/"):
            continue
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    project = next(folder.glob("*.kicad_pro"))
    reply = imported(tmp_path, project, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert not (tmp_path / "out" / "sheets").exists()
    assert build(tmp_path / "out").exit_code == 0


def test_sheet_name_sanitized(tmp_path: Path) -> None:
    """A KiCad sheet named ``Power Supply`` is the module ``power_supply``, and ``import.sheet-renamed``
    says so."""
    from _importcode import sheeted

    reply = imported(tmp_path, sheeted(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["modules"] == ["ch2", "power_supply"]
    (renamed,) = [i for i in (reply.envelope or {})["issues"] if i["code"] == "import.sheet-renamed"]
    assert renamed["severity"] == "info" and "Power Supply" in renamed["message"]
    assert "power_supply" in renamed["message"]
    assert build(tmp_path / "out").exit_code == 0
    design = built_board(tmp_path / "out", "sheeted").design
    paths = {c.ref: c.properties.get("fenolite.path") for c in design.circuit.components}
    assert paths == {
        "J1": "J1",
        "R101": "power_supply/R101",
        "D101": "power_supply/D101",
        "R201": "ch2/R201",
        "D201": "ch2/D201",
    }
