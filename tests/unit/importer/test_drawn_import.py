# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual source drawings survive import, reviewed replay and build (c0276)."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from _buildhelp import build as build_design
from _drawn import bom_only_instance, excluded_passive, slash_aliases
from _drawn import design as drawn_design
from _drawn import drawn as drawing
from _drawn import folder as drawing_folder
from _importcode import ROOT

from fenolite.api import Reply, run
from fenolite.backends.kicad import drawn, sch, symembed
from fenolite.backends.kicad.schgen import GeneratedSchematic
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.backends.kicad.sym import read_symbol_library, write_symbol_library
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import copper, mm
from fenolite.importer.emit import Options, emit
from fenolite.importer.emit.design import board_only_keys, design_name
from fenolite.importer.provenance import Provenance
from fenolite.importer.source import read_kicad
from fenolite.lens.drawn import read_drawn, write_drawn
from fenolite.model.library import SymbolDef, SymbolGraphic
from fenolite.model.schematic import SchematicSheet, SymbolInstance

STAMP = "2026-11-01T00:00:00Z"


def project(folder: Path, name: str, target: int = 10) -> Path:
    folder.mkdir()
    if name == "sensor":
        shutil.copytree(ROOT / "tests/data/fidelity/sensor", folder, dirs_exist_ok=True)
    else:
        if name == "native_names":
            design, value = slash_aliases()
            fixture = "flat"
        else:
            design, value, fixture = drawn_design(name), drawing(name), name
        design.track(
            "fidelity_track",
            (mm(35), mm(25)),
            (mm(37), mm(25)),
            width=mm("0.25"),
            net=next(iter(design.nets.values())),
        )
        made = build_design(
            design,
            target,
            project_dir=drawing_folder(fixture),
            drawn=value,
            drawn_file="schematic.toml",
            copper_intents=copper(design),
        )
        assert made.files and not any(i.severity == "error" for i in made.issues), made.issues
        for relative, data in made.files.items():
            if relative.startswith(".fenolite/"):
                continue
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    return next(folder.glob("*.kicad_pro"))


def snapshot(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def imported(tmp: Path, source: Path, *args: str) -> Reply:
    return run(
        "import",
        str(source),
        "--to",
        "python",
        "--out",
        "code",
        *args,
        cwd=tmp,
        timestamp=STAMP,
    )


@pytest.mark.parametrize("name", ["sensor", "flat", "full", "hier", "bus", "repeat"])
def test_drawn_project_survives_strict_import(name: str, tmp_path: Path) -> None:
    source = project(tmp_path / "original", name)
    assert_strict_roundtrip(tmp_path, source)


def assert_strict_roundtrip(tmp_path: Path, source: Path) -> None:
    before = snapshot(source.parent)
    planned = imported(tmp_path, source, "--dry-run")
    assert planned.exit_code == 0, (planned.error, (planned.envelope or {}).get("issues"))
    assert planned.result["unexpressed"] == []
    assert not (tmp_path / "code").exists()
    confirmed = imported(tmp_path, source, "--confirm", "--plan", planned.result["plan_id"])
    assert confirmed.exit_code == 0, confirmed.error
    assert 'design.load_schematic("schematic.toml")' in (tmp_path / "code/design.py").read_text()
    built = run("build", "code/design.py", "--out", "built", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert built.exit_code == 0, (built.error, (built.envelope or {}).get("issues"))
    assert built.result["schematic"]["source"] == "drawn"
    proof = run(
        "verify-source",
        "code/design.py",
        "--against",
        str(source.parent),
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert proof.exit_code == 0, (proof.error, proof.result.get("differences"))
    assert {str(level["level"]): level["status"] for level in proof.result["levels"]} == {
        **{str(level): "equal" for level in range(1, 9)},
        "S": "equal",
    }
    assert proof.result["differences"] == []
    assert next(level for level in proof.result["levels"] if level["level"] == 5)["compared"] > 0
    assert snapshot(source.parent) == before


@pytest.mark.parametrize("mirror", ["x", "y"])
@pytest.mark.parametrize("target", [9, 10])
def test_mirrored_source_power_survives_strict_import(mirror: str, target: int, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat", target)
    path = next(source.parent.glob("*.kicad_sch"))
    sheet = sch.read_schematic(path)
    assert any(s.ref.startswith("#") for s in sheet.symbols)
    changed = replace(
        sheet, symbols=tuple(replace(s, mirror=mirror) if s.ref.startswith("#") else s for s in sheet.symbols)
    )  # type: ignore[arg-type]
    path.write_text(dumps(sch.rebuild_schematic(changed)))
    assert_strict_roundtrip(tmp_path, source)


@pytest.mark.parametrize("target", [9, 10])
def test_legacy_power_without_flag_survives_strict_import(target: int, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat", target)
    path = source.with_suffix(".kicad_sch")
    root = parse(path.read_text())
    library = root.find("lib_symbols")
    assert library is not None
    definition = next(s for s in library.nodes("symbol") if s.find("power") is not None)

    def legacy(item: Node | Atom) -> Node | Atom:
        if isinstance(item, Atom):
            return item
        if item.name == "pin":
            children = tuple(
                c.with_children((Atom.string("GND"), *c.children[1:]))
                if isinstance(c, Node) and c.name == "name"
                else c
                for c in item.children
            )
            return item.with_children(children)
        return item.with_children(
            tuple(legacy(c) for c in item.children if not isinstance(c, Node) or c.name != "power")
        )

    changed = legacy(definition)
    library = library.with_children(tuple(changed if s is definition else s for s in library.children))
    root = root.with_children(
        tuple(library if isinstance(s, Node) and s.name == "lib_symbols" else s for s in root.children)
    )
    path.write_text(dumps(root))
    native = next(d for d in sch.read_schematic(path).lib_symbols if d.lib_id == "Mini:Mini_GND")
    assert native.power == "" and native.pins[0].name == "GND" and native.pins[0].hidden
    assert_strict_roundtrip(tmp_path, source)
    back = sch.read_schematic(next((tmp_path / "built").glob("*.kicad_sch")))
    assert next(d for d in back.lib_symbols if d.lib_id == "Mini:Mini_GND").power == ""


def graphic_source(folder: Path, target: int = 10) -> Path:
    source = project(folder, "flat", target)
    path = source.with_suffix(".kicad_sch")
    # Native inline fixture authored for Fenolite; no upstream symbol body is copied.
    definition = SymbolDef(
        id=derived_id("sym", "authored", "graphic-badge"),
        name="AuthoredBadge",
        library="Mini",
        in_bom=False,
        on_board=False,
        properties={"Reference": "#SYM", "Value": "BADGE"},
        graphics=(SymbolGraphic("rect", (Point(-1_270_000, -1_270_000), Point(1_270_000, 1_270_000))),),
    )
    embedded = symembed.embed_symbol(definition, target=target)
    instance = SymbolInstance(
        id=derived_id("sci", "authored", "graphic-badge"),
        lib_ref=definition.lib_id,
        position=Point(20_320_000, 20_320_000),
        ref="#SYM1",
        value="BADGE",
        in_bom=False,
        on_board=False,
        properties={"Reference": "#SYM1", "Value": "BADGE", "Footprint": "", "Datasheet": ""},
    )
    badge_sheet = SchematicSheet(
        id=derived_id("sch", "authored", "graphic-badge"),
        name="badge",
        lib_symbols=(embedded.definition,),
        symbols=(instance,),
    )
    native = parse(sch.write_schematic(badge_sheet, target=target).text).nodes("symbol")[0]
    root = parse(path.read_text())
    library = root.find("lib_symbols")
    assert library is not None
    changed = library.with_children((*library.children, embedded.node))
    root = root.with_children((*(changed if s is library else s for s in root.children), native))
    path.write_text(dumps(root))
    return source


def bom_only_source(folder: Path, target: int = 10) -> Path:
    """Original pinless purchasing accessory with explicit BOM inclusion and board exclusion."""
    source = project(folder, "flat", target)
    path = source.with_suffix(".kicad_sch")
    path.write_text(dumps(bom_only_instance(sch.read_schematic(path), target)))
    return source


@pytest.mark.parametrize("target", [9, 10])
def test_bom_only_accessory_survives_strict_import(target: int, tmp_path: Path) -> None:
    source = bom_only_source(tmp_path / "original", target)
    original = read_kicad(source)
    accessory = next(component for component in original.design.circuit.components if component.ref == "M1")
    assert accessory.bom_only and not accessory.pins
    assert not any(fp.component_id == accessory.id for fp in original.design.board.footprints)
    assert_strict_roundtrip(tmp_path, source)


def test_bom_only_accessory_keeps_each_repeated_sheet_instance(tmp_path: Path) -> None:
    source = project(tmp_path / "original", "repeat", 10)
    child = source.parent / "sheets/channel.kicad_sch"
    child.write_text(dumps(bom_only_instance(sch.read_schematic(child), 10, dnp=True)))
    original = read_kicad(source)
    accessories = [component for component in original.design.circuit.components if component.bom_only]
    assert {component.ref for component in accessories} == {"M1", "M2"}
    assert len({component.path for component in accessories}) == 2
    assert all(component.dnp and not component.pins for component in accessories)
    assert_strict_roundtrip(tmp_path, source)


@pytest.mark.parametrize("defect", ["pins", "hidden", "power", "on_board", "missing"])
def test_off_board_accessory_unsafe_forms_do_not_become_bom_only(defect: str, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat", 10)
    path = source.with_suffix(".kicad_sch")
    path.write_text(dumps(bom_only_instance(sch.read_schematic(path), 10, defect=defect)))
    original = read_kicad(source)
    assert not any(component.bom_only for component in original.design.circuit.components)
    planned = imported(tmp_path, source, "--dry-run")
    assert planned.exit_code != 0
    assert not (tmp_path / "code").exists()


def test_planted_bom_flag_loss_is_detected_in_source_comparison(tmp_path: Path) -> None:
    source = bom_only_source(tmp_path / "original", 10)
    assert_strict_roundtrip(tmp_path, source)
    path = source.with_suffix(".kicad_sch")
    root = parse(path.read_text())
    children = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "symbol":
            ref = next(
                prop.atoms()[1].value
                for prop in child.nodes("property")
                if prop.atoms()[0].value == "Reference"
            )
            if ref == "M1":
                child = child.with_children(
                    tuple(
                        Node(prop.head, (Atom.symbol("no"),))
                        if isinstance(prop, Node) and prop.name == "in_bom"
                        else prop
                        for prop in child.children
                    )
                )
        children.append(child)
    path.write_text(dumps(root.with_children(tuple(children))))
    proof = run(
        "verify-source", "code/design.py", "--against", str(source.parent), cwd=tmp_path, timestamp=STAMP
    )
    assert proof.exit_code != 0
    assert any(difference["kind"] == "component-missing" for difference in proof.result["differences"])


@pytest.mark.parametrize("target", [9, 10])
def test_excluded_passive_instance_survives_strict_import(target: int, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat", target)
    path = source.with_suffix(".kicad_sch")
    path.write_text(dumps(excluded_passive(sch.read_schematic(path), target)))
    assert_strict_roundtrip(tmp_path, source)
    built = sch.read_schematic(next((tmp_path / "built").glob("*.kicad_sch")))
    native = next(symbol for symbol in built.symbols if symbol.ref == "R9")
    assert not native.on_board and not native.in_bom and native.dnp
    assert native.position == Point(50_800_000, 101_600_000)
    assert "R9" not in {
        c.ref for c in read_kicad(next((tmp_path / "built").glob("*.kicad_pro"))).design.circuit.components
    }
    value = read_drawn((tmp_path / "code/schematic.toml").read_text())
    assert any((native := drawn.opaque_symbol(item)) is not None and native.ref == "R9"
               for item in value.sheets[0].opaques)  # fmt: skip


@pytest.mark.parametrize("defect", ["in_bom", "on_board", "active", "hidden", "power"])
def test_excluded_passive_instance_rejects_unsafe_forms(defect: str, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat")
    path = source.with_suffix(".kicad_sch")
    path.write_text(dumps(excluded_passive(sch.read_schematic(path), 10, defect=defect)))
    reply = imported(tmp_path, source, "--dry-run")
    assert reply.exit_code == 3 and (reply.error or {})["code"] == "FEN-3004"
    assert "R9" in (reply.error or {})["message"]
    assert not (tmp_path / "code").exists()


@pytest.mark.parametrize("target", [9, 10])
def test_pinless_graphic_symbol_survives_strict_import(target: int, tmp_path: Path) -> None:
    source = graphic_source(tmp_path / "original", target)
    assert_strict_roundtrip(tmp_path, source)
    back = sch.read_schematic(next((tmp_path / "built").glob("*.kicad_sch")))
    badge = next(s for s in back.symbols if s.ref == "#SYM1")
    definition = next(d for d in back.lib_symbols if d.lib_id == badge.lib_ref)
    assert not definition.pins and not definition.in_bom and not definition.on_board
    assert definition.graphics and badge.position == Point(20_320_000, 20_320_000)


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("default_bom,default_board", [(True, False), (False, True), (True, True)])
def test_graphic_instance_exclusions_preserve_differing_library_defaults(
    default_bom: bool, default_board: bool, target: int, tmp_path: Path
) -> None:
    source = graphic_source(tmp_path / "original", target)
    path = source.with_suffix(".kicad_sch")
    root = parse(path.read_text())
    library = root.find("lib_symbols")
    assert library is not None
    badge = next(s for s in library.nodes("symbol") if s.atoms()[0].value == "Mini:AuthoredBadge")
    flags = {"in_bom": default_bom, "on_board": default_board}
    changed = badge.with_children(
        tuple(
            c.with_children((Atom.symbol("yes" if flags[c.name] else "no"),))
            if isinstance(c, Node) and c.name in flags
            else c
            for c in badge.children
        )
    )
    library_new = library.with_children(tuple(changed if c is badge else c for c in library.children))
    path.write_text(
        dumps(root.with_children(tuple(library_new if c is library else c for c in root.children)))
    )
    assert_strict_roundtrip(tmp_path, source)
    back = sch.read_schematic(next((tmp_path / "built").glob("*.kicad_sch")))
    native = next(s for s in back.symbols if s.ref == "#SYM1")
    definition = next(d for d in back.lib_symbols if d.lib_id == native.lib_ref)
    assert (definition.in_bom, definition.on_board) == (default_bom, default_board)
    assert not native.in_bom and not native.on_board and not definition.pins


def test_opaque_graphic_symbol_cannot_gain_electrical_pins(tmp_path: Path) -> None:
    source = graphic_source(tmp_path / "original")
    assert imported(tmp_path, source, "--confirm").exit_code == 0
    path = tmp_path / "code/lib/Mini.kicad_sym"
    root = parse(path.read_text())
    badge = next(s for s in root.nodes("symbol") if s.atoms()[0].value == "AuthoredBadge")
    electrical = parse(
        '(symbol "AuthoredBadge_1_1" (pin input line (at 0 0 0) (length 0) '
        '(name "X" (effects (font (size 1.27 1.27)))) '
        '(number "1" (effects (font (size 1.27 1.27))))))'
    )
    changed = badge.with_children((*badge.children, electrical))
    path.write_text(dumps(root.with_children(tuple(changed if s is badge else s for s in root.children))))
    reply = run("build", "code/design.py", "--out", "refused", "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 5
    assert any(i["code"] == "drawn.part-unknown" for i in (reply.envelope or {})["issues"])
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("flag", ["in_bom", "on_board"])
def test_graphic_symbol_must_be_excluded_from_board_and_bom(flag: str, tmp_path: Path) -> None:
    source = graphic_source(tmp_path / "original")
    path = source.with_suffix(".kicad_sch")
    root = parse(path.read_text())
    native = root.nodes("symbol")[-1]
    changed = native.with_children(
        tuple(
            c.with_children((Atom.symbol("yes"),)) if isinstance(c, Node) and c.name == flag else c
            for c in native.children
        )
    )
    path.write_text(dumps(root.with_children(tuple(changed if c is native else c for c in root.children))))
    reply = imported(tmp_path, source, "--dry-run")
    assert reply.exit_code == 3 and (reply.error or {})["code"] == "FEN-3004"
    assert not (tmp_path / "code").exists()


def test_malformed_opaque_graphic_symbol_is_bad_input(tmp_path: Path) -> None:
    source = graphic_source(tmp_path / "original")
    assert imported(tmp_path, source, "--confirm").exit_code == 0
    path = tmp_path / "code/schematic.toml"
    value = read_drawn(path.read_text())
    sheet = value.sheets[0]
    index = next(i for i, item in enumerate(sheet.opaques) if parse(item.kicad).name == "symbol")
    opaque = sheet.opaques[index]
    native = parse(opaque.kicad)
    at = native.find("at")
    assert at is not None
    bad_at = at.with_children((*at.children[:2], Atom.integer(45)))
    changed = native.with_children(tuple(bad_at if c is at else c for c in native.children))
    opaques = tuple(
        replace(item, kicad=dumps(changed)) if i == index else item for i, item in enumerate(sheet.opaques)
    )
    path.write_text(write_drawn(replace(value, sheets=(replace(sheet, opaques=opaques), *value.sheets[1:]))))
    reply = run("build", "code/design.py", "--out", "refused", "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 3 and (reply.error or {})["code"] == "FEN-3004"
    assert not (tmp_path / "refused").exists()


def embedded_alias(source: Path, lib_id: str, *, qualified_origin: bool = True) -> str:
    """An authored local native copy, retaining its original library id on the placed instance."""
    path = source.with_suffix(".kicad_sch")
    root = parse(path.read_text())
    library = root.find("lib_symbols")
    assert library is not None
    definition = next(s for s in library.nodes("symbol") if s.atoms()[0].value == lib_id)
    old_name = lib_id.partition(":")[2]
    copy_name = "AuthoredCopy"

    def rename(item: Node | Atom) -> Node | Atom:
        if isinstance(item, Atom):
            return item
        children = tuple(rename(c) for c in item.children)
        if item.name == "symbol" and item.atoms():
            name = item.atoms()[0].value
            if name == lib_id:
                children = (Atom.string(copy_name), *children[1:])
            elif name.startswith(old_name + "_"):
                children = (Atom.string(copy_name + name[len(old_name) :]), *children[1:])
        return item.with_children(children)

    copied = rename(definition)
    library_new = library.with_children((*library.children, copied))
    native = next(s for s in root.nodes("symbol") if s.find("lib_id").atoms()[0].value == lib_id)  # type: ignore[union-attr]
    alias = parse('(lib_name "AuthoredCopy")')
    children = tuple(
        c.with_children((Atom.string("LegacyBase"),))
        if not qualified_origin and isinstance(c, Node) and c.name == "lib_id"
        else c
        for c in native.children
    )
    native_new = native.with_children((alias, *children))
    root = root.with_children(
        tuple(library_new if c is library else native_new if c is native else c for c in root.children)
    )
    path.write_text(dumps(root))
    return f"{'Mini' if qualified_origin else '_Source'}:{copy_name}"


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("kind", ["ordinary", "power", "graphic"])
def test_embedded_alias_survives_strict_import(kind: str, target: int, tmp_path: Path) -> None:
    source = (
        graphic_source(tmp_path / "original", target)
        if kind == "graphic"
        else project(tmp_path / "original", "flat", target)
    )
    lib_id = {"ordinary": "Mini:Mini_R", "power": "Mini:Mini_GND", "graphic": "Mini:AuthoredBadge"}[kind]
    canonical = embedded_alias(source, lib_id)
    assert_strict_roundtrip(tmp_path, source)
    back = sch.read_schematic(next((tmp_path / "built").glob("*.kicad_sch")))
    assert canonical in {d.lib_id for d in back.lib_symbols}
    assert any(s.lib_ref == canonical for s in back.symbols)


@pytest.mark.parametrize("kind", ["ordinary", "power"])
def test_embedded_alias_without_original_namespace_uses_private_fallback(kind: str, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat")
    canonical = embedded_alias(
        source, {"ordinary": "Mini:Mini_R", "power": "Mini:Mini_GND"}[kind], qualified_origin=False
    )
    assert_strict_roundtrip(tmp_path, source)
    back = sch.read_schematic(next((tmp_path / "built").glob("*.kicad_sch")))
    assert canonical in {d.lib_id for d in back.lib_symbols}


def test_embedded_alias_collision_cannot_hide_behind_cached_definition(tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat")
    canonical = embedded_alias(source, "Mini:Mini_R")
    path = source.with_suffix(".kicad_sch")
    root = parse(path.read_text())
    library = root.find("lib_symbols")
    assert library is not None
    local = next(s for s in library.nodes("symbol") if s.atoms()[0].value == "AuthoredCopy")
    children = tuple(
        c.with_children((c.children[0], Atom.string("AUTHORED_CONFLICT"), *c.children[2:]))
        if isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == "Value"
        else c
        for c in local.children[1:]
    )
    qualified = local.with_children((Atom.string(canonical), *children))
    native = next(s for s in root.nodes("symbol") if s.find("lib_name") is not None)
    changed = native.with_children(
        tuple(
            c.with_children((Atom.string(canonical),))
            if isinstance(c, Node) and c.name == "lib_name"
            else c.with_children((Atom.string("00000000-0000-4000-8000-000000000009"),))
            if isinstance(c, Node) and c.name == "uuid"
            else c
            for c in native.children
        )
    )
    library_new = library.with_children((*library.children, qualified))
    root = root.with_children((*(library_new if c is library else c for c in root.children), changed))
    path.write_text(dumps(root))
    reply = imported(tmp_path, source, "--dry-run")
    assert reply.exit_code == 3 and "conflicting definitions" in (reply.error or {})["message"]
    assert not (tmp_path / "code").exists()


def unit_alias_source(folder: Path, target: int = 10, *, defect: str = "") -> Path:
    """Two authored units share the original pin points; the second keeps its own native text body."""
    source = project(folder, "flat", target)
    path = source.with_suffix(".kicad_sch")
    root = parse(path.read_text())
    library = root.find("lib_symbols")
    assert library is not None
    definition = next(s for s in library.nodes("symbol") if s.atoms()[0].value == "Mini:Mini_QFP32_IC")
    body = next(s for s in definition.nodes("symbol") if s.nodes("pin"))

    def pin_number(pin: Node) -> int:
        number = pin.find("number")
        assert number is not None
        return int(number.atoms()[0].value)

    first = body.with_children(
        tuple(c for c in body.children if not isinstance(c, Node) or c.name != "pin" or pin_number(c) <= 16)
    )
    second = body.with_children(
        (Atom.string("Mini_QFP32_IC_2_1"), *(p for p in body.nodes("pin") if pin_number(p) > 16))
    )
    primary = definition.with_children((*(first if c is body else c for c in definition.children), second))

    def alias(item: Node | Atom) -> Node | Atom:
        if isinstance(item, Atom):
            return item
        children = tuple(alias(c) for c in item.children)
        if item.name == "symbol":
            name = item.atoms()[0].value
            renamed = (
                "AuthoredUnit2"
                if name == "Mini:Mini_QFP32_IC"
                else name.replace("Mini_QFP32_IC", "AuthoredUnit2", 1)
            )
            children = (Atom.string(renamed), *children[1:])
            if name.endswith("_2_1"):
                children += (
                    parse('(text "AUTHORED_UNIT_BODY" (at 0 0 0) (effects (font (size 1.27 1.27))))'),
                )
        if defect == "incompatible" and item.name == "pin" and pin_number(item) == 17:
            children = tuple(
                c.with_children((Atom.string("AUTHORED_INCOMPATIBLE"), *c.children[1:]))
                if isinstance(c, Node) and c.name == "name"
                else c
                for c in children
            )
        return item.with_children(children)

    copied = alias(primary)
    library_new = library.with_children(
        (*(primary if c is definition else c for c in library.children), copied)
    )
    native = next(
        s for s in root.nodes("symbol") if s.find("lib_id").atoms()[0].value == "Mini:Mini_QFP32_IC"
    )  # type: ignore[union-attr]

    native_first = native.with_children(
        tuple(
            c
            for c in native.children
            if not isinstance(c, Node) or c.name != "pin" or int(c.atoms()[0].value) <= 16
        )
    )
    uuid_index = 0

    def second_unit(item: Node | Atom) -> Node | Atom:
        nonlocal uuid_index
        if isinstance(item, Atom):
            return item
        if item.name == "unit":
            return item.with_children((Atom.integer(1 if defect == "same-unit" else 2),))
        if item.name == "uuid":
            uuid_index += 1
            value = derived_id("sci", "authored", f"unit-alias:{uuid_index}").partition("_")[2]
            return item.with_children((Atom.string(value),))
        children = tuple(
            c
            for c in item.children
            if not isinstance(c, Node) or c.name != "pin" or int(c.atoms()[0].value) > 16
        )
        return item.with_children(tuple(second_unit(c) for c in children))

    second_instance = second_unit(native)
    assert isinstance(second_instance, Node)
    second_instance = second_instance.with_children(
        (parse('(lib_name "AuthoredUnit2")'), *second_instance.children)
    )
    root = root.with_children(
        (
            *(library_new if c is library else native_first if c is native else c for c in root.children),
            second_instance,
        )
    )
    path.write_text(dumps(root))
    return source


@pytest.mark.parametrize("target", [9, 10])
def test_unit_alias_survives_strict_import_and_sync(target: int, tmp_path: Path) -> None:
    source = unit_alias_source(tmp_path / "original", target)
    assert_strict_roundtrip(tmp_path, source)
    file = tmp_path / "code/schematic.toml"
    value = read_drawn(file.read_text())
    assert (
        next(s for s in value.sheets[0].symbols if s.part == "U1" and s.unit == 2).symbol
        == "Mini:AuthoredUnit2"
    )
    assert "AUTHORED_UNIT_BODY" in next((tmp_path / "built").glob("*.kicad_sch")).read_text()
    synced = run(
        "sync", "code/design.py", "--out", "built", "--to-source", "--confirm", cwd=tmp_path, timestamp=STAMP
    )
    assert synced.exit_code == 0, (synced.error, (synced.envelope or {}).get("issues"))
    assert (
        next(
            s for s in read_drawn(file.read_text()).sheets[0].symbols if s.part == "U1" and s.unit == 2
        ).symbol
        == "Mini:AuthoredUnit2"
    )
    built = run(
        "build",
        "code/design.py",
        "--out",
        "rebuilt",
        "--kicad-version",
        str(target),
        "--confirm",
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert built.exit_code == 0, (built.error, (built.envelope or {}).get("issues"))
    assert "AUTHORED_UNIT_BODY" in next((tmp_path / "rebuilt").glob("*.kicad_sch")).read_text()


@pytest.mark.parametrize(
    "defect,words", [("same-unit", "conflicting symbols"), ("incompatible", "incompatible logical pins")]
)
def test_unit_alias_rejects_conflicting_or_incompatible_bindings(
    defect: str, words: str, tmp_path: Path
) -> None:
    source = unit_alias_source(tmp_path / "original", defect=defect)
    reply = imported(tmp_path, source, "--dry-run")
    assert reply.exit_code == 3 and words in (reply.error or {})["message"]
    assert not (tmp_path / "code").exists()


@pytest.mark.parametrize("override,mapped", [(True, False), (True, True), (False, True)])
def test_unit_alias_single_unit_override_survives_sync_and_pad_mapping(
    override: bool, mapped: bool, tmp_path: Path
) -> None:
    source = project(tmp_path / "original", "flat")
    assert imported(tmp_path, source, "--confirm").exit_code == 0
    if override:
        path = tmp_path / "code/lib/Mini.kicad_sym"
        definition = next(s for s in read_symbol_library(path, library="Mini") if s.name == "Mini_R")
        alias = replace(
            definition,
            name="AuthoredSingleUnit",
            ext={},
            native_ids={},
            provenance=None,
            graphics=(*definition.graphics, SymbolGraphic("circle", (Point(0, 0), Point(635_000, 0)))),
        )
        root = parse(path.read_text())
        native = parse(write_symbol_library((alias,), target=10)).nodes("symbol")[0]
        path.write_text(dumps(root.with_children((*root.children, native))))
        file = tmp_path / "code/schematic.toml"
        value = read_drawn(file.read_text())
        sheet = value.sheets[0]
        symbols = tuple(
            replace(s, symbol="Mini:AuthoredSingleUnit") if s.part == "R1" else s for s in sheet.symbols
        )
        file.write_text(
            write_drawn(replace(value, sheets=(replace(sheet, symbols=symbols), *value.sheets[1:])))
        )
    if mapped:
        script = tmp_path / "code/design.py"
        script.write_text(script.read_text() + '\ndesign.parts["R1"].pad_map = {"1": "2", "2": "1"}\n')
    built = run("build", "code/design.py", "--out", "built", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert built.exit_code == 0, (built.error, (built.envelope or {}).get("issues"))
    before = next((tmp_path / "built").glob("*.kicad_sch")).read_bytes()
    synced = run(
        "sync", "code/design.py", "--out", "built", "--to-source", "--confirm", cwd=tmp_path, timestamp=STAMP
    )
    assert synced.exit_code == 0, (synced.error, (synced.envelope or {}).get("issues"))
    after = read_drawn((tmp_path / "code/schematic.toml").read_text())
    assert next(s for s in after.sheets[0].symbols if s.part == "R1").symbol == (
        "Mini:AuthoredSingleUnit" if override else ""
    )
    rebuilt = run("build", "code/design.py", "--out", "rebuilt", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert rebuilt.exit_code == 0, (rebuilt.error, (rebuilt.envelope or {}).get("issues"))
    assert next((tmp_path / "rebuilt").glob("*.kicad_sch")).read_bytes() == before


@pytest.mark.parametrize("binding", ["Mini:MissingAlias", "Mini:Mini_R"])
def test_unit_alias_missing_or_incompatible_build_binding_refuses(binding: str, tmp_path: Path) -> None:
    source = unit_alias_source(tmp_path / "original")
    assert imported(tmp_path, source, "--confirm").exit_code == 0
    file = tmp_path / "code/schematic.toml"
    value = read_drawn(file.read_text())
    sheet = value.sheets[0]
    symbols = tuple(
        replace(s, symbol=binding) if s.part == "U1" and s.unit == 2 else s for s in sheet.symbols
    )
    file.write_text(write_drawn(replace(value, sheets=(replace(sheet, symbols=symbols), *value.sheets[1:]))))
    reply = run("build", "code/design.py", "--out", "refused", "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 5
    assert any(i["code"] == "drawn.part-unknown" for i in (reply.envelope or {})["issues"])
    assert not (tmp_path / "refused").exists()


def test_unit_alias_written_pin_geometry_still_runs_connectivity_guard(tmp_path: Path) -> None:
    source = unit_alias_source(tmp_path / "original")
    assert imported(tmp_path, source, "--confirm").exit_code == 0
    path = tmp_path / "code/lib/Mini.kicad_sym"
    root = parse(path.read_text())
    alias = next(s for s in root.nodes("symbol") if s.atoms()[0].value == "AuthoredUnit2")

    def moved(item: Node | Atom) -> Node | Atom:
        if isinstance(item, Atom):
            return item
        if item.name == "pin" and item.find("number").atoms()[0].value == "17":  # type: ignore[union-attr]
            at = item.find("at")
            assert at is not None
            changed = at.with_children((Atom.integer(100), *at.children[1:]))
            return item.with_children(tuple(changed if c is at else c for c in item.children))
        return item.with_children(tuple(moved(c) for c in item.children))

    changed = moved(alias)
    path.write_text(dumps(root.with_children(tuple(changed if c is alias else c for c in root.children))))
    reply = run("build", "code/design.py", "--out", "refused", "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 5
    assert any(i["code"] == "build.schematic-netlist-differs" for i in (reply.envelope or {})["issues"])
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("target", [9, 10])
def test_root_module_prefix_survives_strict_import(target: int, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat", target)
    path = source.with_suffix(".kicad_pcb")
    root = parse(path.read_text())
    changed: dict[int, Node] = {}
    for footprint in root.nodes("footprint"):
        properties = footprint.nodes("property")
        reference = next(p.atoms()[1].value for p in properties if p.atoms()[0].value == "Reference")
        header = next(p for p in properties if p.atoms()[0].value == "fenolite.path")
        replacement = header.with_children(
            (header.children[0], Atom.string("racine/" + reference), *header.children[2:])
        )
        changed[id(footprint)] = footprint.with_children(
            tuple(replacement if c is header else c for c in footprint.children)
        )
    assert changed
    path.write_text(dumps(root.with_children(tuple(changed.get(id(c), c) for c in root.children))))
    assert_strict_roundtrip(tmp_path, source)
    value = read_drawn((tmp_path / "code/schematic.toml").read_text())
    assert all(s.part.startswith("racine/") for s in value.sheets[0].symbols)


@pytest.mark.parametrize("target", [9, 10])
def test_native_board_only_attribute_keeps_active_source_symbol(target: int, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat", target)
    path = source.with_suffix(".kicad_pcb")
    root = parse(path.read_text())
    footprint = next(
        fp
        for fp in root.nodes("footprint")
        if any(p.atoms()[0].value == "Reference" and p.atoms()[1].value == "R1" for p in fp.nodes("property"))
    )
    attr = footprint.find("attr")
    assert attr is not None
    changed_attr = attr.with_children((*attr.children, Atom.symbol("board_only")))
    changed = footprint.with_children(tuple(changed_attr if c is attr else c for c in footprint.children))
    path.write_text(dumps(root.with_children(tuple(changed if c is footprint else c for c in root.children))))
    assert_strict_roundtrip(tmp_path, source)
    value = read_drawn((tmp_path / "code/schematic.toml").read_text())
    assert any(s.part == "R1" for s in value.sheets[0].symbols)
    built_board = read_kicad(next((tmp_path / "built").glob("*.kicad_pcb"))).design
    ids = {c.id: c.ref for c in built_board.circuit.components}
    assert "board_only" in next(
        fp.attributes for fp in built_board.board.footprints if ids[fp.component_id] == "R1"
    )


@pytest.mark.parametrize("target", [9, 10])
def test_native_names_survive_strict_import_with_both_label_spellings(target: int, tmp_path: Path) -> None:
    source = project(tmp_path / "original", "native_names", target)
    assert_strict_roundtrip(tmp_path, source)
    value = read_drawn((tmp_path / "code/schematic.toml").read_text())
    assert [label.text for label in value.sheets[0].labels] == ["A/B", "A{slash}B"]


def test_keyed_board_only_duplicate_and_unmatched_guards_remain(tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat")
    design = read_kicad(source).design
    board = design.board
    assert board is not None
    component = next(c for c in design.circuit.components if c.ref == "R1")
    footprint = next(fp for fp in board.footprints if fp.component_id == component.id)
    flagged = replace(footprint, attributes=(*footprint.attributes, "board_only"))
    base = replace(
        design,
        board=replace(board, footprints=tuple(flagged if fp is footprint else fp for fp in board.footprints)),
    )
    _, _, unmatched = board_only_keys(base)
    assert component.id in unmatched
    _, _, matched = board_only_keys(base, schematic_refs=frozenset({"R1"}))
    assert component.id not in matched
    twin = replace(component, id=derived_id("cmp", "authored", "duplicate-board-only"))
    other = replace(flagged, id=derived_id("fp", "authored", "duplicate-board-only"), component_id=twin.id)
    duplicate = replace(
        base,
        circuit=replace(base.circuit, components=(*base.circuit.components, twin)),
        board=replace(base.board, footprints=(*base.board.footprints, other)),
    )
    _, shown, keys = board_only_keys(duplicate, schematic_refs=frozenset({"R1"}))
    assert {component.id, twin.id} <= keys and shown[component.id] == shown[twin.id] == "R1"


def test_source_edit_invalidates_review(tmp_path: Path) -> None:
    source = project(tmp_path / "original", "hier")
    planned = imported(tmp_path, source, "--dry-run")
    assert planned.exit_code == 0, planned.error
    sheet = next(p for p in source.parent.rglob("*.kicad_sch") if p.parent != source.parent)
    sheet.write_bytes(sheet.read_bytes() + b"\n")
    reply = imported(tmp_path, source, "--confirm", "--plan", planned.result["plan_id"])
    assert reply.exit_code == 4 and (reply.error or {})["code"] == "FEN-4002"
    assert not (tmp_path / "code").exists()


def test_written_drawing_guard_blocks_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = project(tmp_path / "original", "hier")
    real = drawn.lower_drawn

    def broken(*args: object, **kwargs: object) -> GeneratedSchematic:
        made = real(*args, **kwargs)  # type: ignore[arg-type]
        wire = made.sheet.wires[0]
        shifted = replace(wire, start=Point(wire.start.x + 1_270_000, wire.start.y))
        return replace(made, sheet=replace(made.sheet, wires=(shifted, *made.sheet.wires[1:])))

    monkeypatch.setattr(drawn, "lower_drawn", broken)
    reply = imported(tmp_path, source, "--dry-run")
    assert reply.exit_code == 5
    assert any(
        i["code"] == "import.unequal" and "schematic-netlist-differs" in i["message"]
        for i in (reply.envelope or {})["issues"]
    )
    assert "plan" not in reply.result and not (tmp_path / "code").exists()


def _changed_definition(root: Node) -> Node:
    def change(item: Node | Atom) -> Node | Atom:
        if isinstance(item, Atom):
            return item
        if item.name == "property" and item.atoms()[0].value == "Value":
            children = list(item.children)
            children[1] = Atom.string("AUTHORED_CONFLICT")
            return item.with_children(children)
        return item.with_children(tuple(change(child) for child in item.children))

    library = root.find("lib_symbols")
    assert library is not None
    return root.with_children(tuple(change(child) if child is library else child for child in root.children))


def test_conflicting_source_symbols_refuse_before_staging(tmp_path: Path) -> None:
    from _importcode import copy_project

    source = copy_project(tmp_path)
    child = source.parent / "sheets/ch2.kicad_sch"
    child.write_text(dumps(_changed_definition(parse(child.read_text()))) + "\n")
    reply = imported(tmp_path, source, "--dry-run")
    assert reply.exit_code == 3 and "conflicting definitions" in (reply.error or {})["message"]
    assert not (tmp_path / "code").exists()


def test_hidden_power_pins_stay_hidden(tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat")
    root = sch.read_schematic(source.with_suffix(".kicad_sch"))
    hidden = {(s.lib_id, p.number) for s in root.lib_symbols for p in s.pins if p.hidden}
    assert hidden
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    made = run("build", "code/design.py", "--out", "built", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert made.exit_code == 0, made.error
    back = sch.read_schematic(next((tmp_path / "built").glob("*.kicad_sch")))
    assert hidden <= {(s.lib_id, p.number) for s in back.lib_symbols for p in s.pins if p.hidden}


def test_native_symbol_graphics_survive_both_writes(tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat")
    file = source.with_suffix(".kicad_sch")
    root = parse(file.read_text())
    library = root.find("lib_symbols")
    assert library is not None
    symbol = next(s for s in library.nodes("symbol") if s.atoms()[0].value == "Mini:Mini_R")
    unit = symbol.nodes("symbol")[0]
    authored = parse('(text "AUTHORED_NATIVE_TEXT" (at 0 5 0) (effects (font (size 1.27 1.27))))')
    changed_unit = unit.with_children((*unit.children, authored))
    changed_symbol = symbol.with_children(tuple(changed_unit if n is unit else n for n in symbol.children))
    changed_library = library.with_children(
        tuple(changed_symbol if n is symbol else n for n in library.children)
    )
    file.write_text(
        dumps(root.with_children(tuple(changed_library if n is library else n for n in root.children)))
    )
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert "AUTHORED_NATIVE_TEXT" in (tmp_path / "code/lib/Mini.kicad_sym").read_text()
    built = run("build", "code/design.py", "--out", "built", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert built.exit_code == 0, built.error
    assert "AUTHORED_NATIVE_TEXT" in next((tmp_path / "built").glob("*.kicad_sch")).read_text()


@pytest.mark.parametrize("defect", ["missing-definition", "body-style"])
def test_unrepresentable_source_refuses(tmp_path: Path, defect: str) -> None:
    source = project(tmp_path / "original", "flat")
    file = source.with_suffix(".kicad_sch")
    root = parse(file.read_text())
    if defect == "missing-definition":
        library = root.find("lib_symbols")
        assert library is not None
        root = root.with_children(
            tuple(library.with_children(()) if n is library else n for n in root.children)
        )
    else:
        symbol = root.nodes("symbol")[0]
        body = symbol.find("body_style")
        assert body is not None
        changed = symbol.with_children(
            tuple(body.with_children((Atom.integer(2),)) if n is body else n for n in symbol.children)
        )
        root = root.with_children(tuple(changed if n is symbol else n for n in root.children))
    file.write_text(dumps(root))
    reply = imported(tmp_path, source, "--dry-run")
    assert reply.exit_code == 3 and (reply.error or {})["code"] == "FEN-3004"
    assert not (tmp_path / "code").exists()


def test_source_project_use_precedes_foreign_project(tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat")
    file = source.with_suffix(".kicad_sch")
    first = next(s for s in sch.read_schematic(file).symbols if not s.ref.startswith("#"))
    use = first.uses[0]
    root = parse(file.read_text())
    native = next(
        s
        for s in root.nodes("symbol")
        if any(
            p.atoms()[0].value == "Reference" and p.atoms()[1].value == first.ref for p in s.nodes("property")
        )
    )
    table = native.find("instances")
    assert table is not None
    foreign = parse(f'(project "foreign" (path "{use.path}" (reference "X999") (unit {use.unit})))')
    changed_table = table.with_children((foreign, *table.children))
    changed = native.with_children(tuple(changed_table if n is table else n for n in native.children))
    file.write_text(dumps(root.with_children(tuple(changed if s is native else s for s in root.children))))
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    assert "X999" not in (tmp_path / "code/design.py").read_text()


def test_native_project_rows_override_builtin_ids(tmp_path: Path) -> None:
    source = project(tmp_path / "original", "flat")
    for file in source.parent.rglob("*"):
        if file.suffix not in (".kicad_sch", ".kicad_pcb"):
            continue
        text = file.read_text().replace("Mini:Mini_R_0603", "Fenolite:Chip_0603")
        text = text.replace("Mini:Mini_R", "Fenolite:Resistor").replace('"Mini_R_', '"Resistor_')
        file.write_text(text)
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    built = run("build", "code/design.py", "--out", "built", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert built.exit_code == 0, built.error
    assert built.result["libraries"]["Fenolite:Resistor"] == "project"
    assert built.result["libraries"]["Fenolite:Chip_0603"] == "project"


@pytest.mark.parametrize(
    "kind,target,expected",
    [
        ("board-only", 9, "5548cca3f5ca5bd440e8b50ac1af5a248c0fdf572908be0e81c8027e6a9cd653"),
        ("board-only", 10, "943d7faec8748d20fc396ceb1394785fc29d3c438a07ca1841c0c033884fdbd3"),
        ("edited", 9, "bc05473a8ee53930ff8cb9c6a3211f3b41a1b27ce4716a3c578097ebf88ec28f"),
        ("edited", 10, "92f0cc06c99953fcc8034a105079442495a7af1c7b1c52ef28c592325d17f01b"),
    ],
)
def test_board_only_emission_keeps_bytes(tmp_path: Path, kind: str, target: int, expected: str) -> None:
    # Ordinary maps remain from pre-drawn3da72066. c0318 changes only the edited variant's design.py:
    # native footprint identity plus explicit local definition lookup, proved by independent base96d diff.
    from _importcode import board_only, edited

    source = read_kicad((board_only if kind == "board-only" else edited)(tmp_path))
    made = emit(
        source,
        Options(
            design_name(source.name), Provenance(date="2026-11-01", fenolite="0.7.0.dev0"), target=target
        ),
    )
    files = {path: hashlib.sha256(data).hexdigest() for path, data in made.files.items()}
    assert (
        hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        == expected
    )
