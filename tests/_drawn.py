# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the drawn schematic tests (change c0276): the authored fixtures of ``tests/data/drawn/`` and
``examples/drawn/``, built hermetically, and their sheets read back, extracted and resolved."""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import runpy
import shutil
from pathlib import Path
from typing import Any

from _buildhelp import build as build_design_of

import fenolite.cli.main as cli_main
from fenolite.api.sides import read_side
from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import sch, symembed
from fenolite.backends.kicad.schlayout import pin_point
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, to_model
from fenolite.lens.build import BuildOutput
from fenolite.lens.drawn import read_drawn, write_drawn
from fenolite.model.circuit import Circuit
from fenolite.model.drawn import DrawnLabel, DrawnLabelKind, DrawnSchematic, DrawnSheet
from fenolite.model.drawn_connect import DrawnNetlist, PinKey, PinPoint, component_path, resolve
from fenolite.model.library import SymbolDef
from fenolite.model.schematic import SchematicSheet, SymbolInstance

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "data" / "drawn"
EXAMPLE = ROOT / "examples" / "drawn"
BLOCKS = ROOT / "examples" / "blocks"
NAMES = ("flat", "full", "hier", "bus", "repeat")
"""The authored fixtures, each a folder with ``design.py``, ``schematic.toml`` and library tables."""


def folder(name: str) -> Path:
    """The folder of fixture ``name``; ``example`` is ``examples/drawn``."""
    return EXAMPLE if name == "example" else FIXTURES / name


def design(name: str) -> Design:
    found = runpy.run_path(str(folder(name) / "design.py"))["design"]
    assert isinstance(found, Design)
    return found


def text(name: str) -> str:
    return (folder(name) / "schematic.toml").read_text(encoding="utf-8")


def drawn(name: str) -> DrawnSchematic:
    return read_drawn(text(name), file="schematic.toml")


def slash_aliases(kind: DrawnLabelKind = "local") -> tuple[Design, DrawnSchematic]:
    """Two disjoint authored wire islands with native aliases for one net (H-K-SCH-SLASH)."""
    code = design("flat")
    net = code.nets.pop("SDA")
    net.name = "A/B"
    code.nets[net.name] = net
    value = drawn("flat")
    positions = pins(value, "flat")
    root = value.sheets[0]
    index = {symbol.part: k for k, symbol in enumerate(root.symbols)}
    first = next(pin.at for pin in positions[(root.key, "symbol", index["U1"])] if pin.number == "17")
    second = next(pin.at for pin in positions[(root.key, "symbol", index["R1"])] if pin.number == "1")
    first_end = dataclasses.replace(first, x=first.x + 2_540_000)
    second_end = dataclasses.replace(second, x=second.x + 2_540_000)
    shape = "" if kind == "local" else "input"
    root = dataclasses.replace(
        root,
        wires=((first, first_end), (second, second_end)),
        junctions=(),
        labels=(DrawnLabel(kind, "A/B", first_end, shape=shape),
                DrawnLabel(kind, "A{slash}B", second_end, shape=shape)),
    )  # fmt: skip
    return code, dataclasses.replace(value, sheets=(root,))


def excluded_passive(sheet: SchematicSheet, target: int, *, defect: str = "") -> Node:
    """Append an authored native passive instance excluded from board and BOM (H-K-EQ-SCHSIDE)."""
    base = library()["Mini:Mini_R"]
    definition = SymbolDef(
        id=derived_id("sym", "authored", "excluded-passive"),
        name="AuthoredPassive",
        library="Mini",
        properties={"Reference": "R", "Value": "EXCLUDED"},
        pins=tuple(dataclasses.replace(pin, etype="input" if defect == "active" else pin.etype,
                                       hidden=defect == "hidden") for pin in base.pins),
        graphics=base.graphics,
    )  # fmt: skip
    instance = SymbolInstance(
        id=derived_id("sci", "authored", "excluded-passive"),
        lib_ref=definition.lib_id,
        position=Point(50_800_000, 101_600_000),
        ref="R9",
        value="EXCLUDED",
        in_bom=defect == "in_bom",
        on_board=defect == "on_board",
        dnp=True,
        properties={"Reference": "R9", "Value": "EXCLUDED", "Footprint": "", "Datasheet": ""},
    )
    embedded = symembed.embed_symbol(definition, target=target)
    created = SchematicSheet(id=derived_id("sch", "authored", "excluded-passive"), name="excluded",
                             lib_symbols=(embedded.definition,), symbols=(instance,))  # fmt: skip
    authored = parse(sch.write_schematic(created, target=target).text)
    native = authored.nodes("symbol")[0]
    authored_library = authored.find("lib_symbols")
    assert authored_library is not None
    definitions = authored_library.nodes("symbol")
    if defect == "power":
        # An authored native power marker, independently of the authored-library synthesis path.
        definition_node = definitions[0]
        power = Node(Atom.symbol("power"), (Atom.symbol("global"),) if target >= 10 else ())
        definitions = (definition_node.with_children((*definition_node.children, power)),)
    root = sch.rebuild_schematic(sheet)
    symbols = root.find("lib_symbols")
    assert symbols is not None
    added = symbols.with_children((*symbols.children, *definitions))
    return root.with_children((*(added if c is symbols else c for c in root.children), native))


def bom_only_instance(sheet: SchematicSheet, target: int, *, defect: str = "", dnp: bool = False) -> Node:
    """Append an original pinless purchasing accessory; planted flags/pins never qualify (c0334)."""
    from fenolite.model.library import SymbolGraphic

    definition = SymbolDef(
        id=derived_id("sym", "authored", "purchasing-accessory"),
        name="AuthoredAccessory",
        library="Mini",
        properties={"Reference": "M", "Value": "ACCESSORY"},
        graphics=(SymbolGraphic("rect", (Point(-1_270_000, -1_270_000), Point(1_270_000, 1_270_000))),),
        pins=library()["Mini:Mini_R"].pins if defect in {"pins", "hidden"} else (),
    )
    if defect == "hidden":
        definition = dataclasses.replace(
            definition, pins=tuple(dataclasses.replace(pin, hidden=True) for pin in definition.pins)
        )
    embedded = symembed.embed_symbol(definition, target=target)
    metadata = "AuthoredMetadata:NoPhysicalGeometry"
    instance = SymbolInstance(
        id=derived_id("sci", "authored", "purchasing-accessory"),
        lib_ref=definition.lib_id,
        position=Point(20_320_000, 20_320_000),
        ref="M1",
        value="ACCESSORY",
        footprint=metadata,
        dnp=dnp,
        in_bom=defect != "no_bom",
        on_board=defect == "on_board",
        properties={"Reference": "M1", "Value": "ACCESSORY", "Footprint": metadata, "Datasheet": ""},
        uses=tuple(
            dataclasses.replace(use, ref=f"M{index + 1}") for index, use in enumerate(sheet.symbols[0].uses)
        )
        if sheet.symbols
        else (),
    )
    created = SchematicSheet(
        id=derived_id("sch", "authored", "purchasing-accessory"),
        name="accessory",
        lib_symbols=(embedded.definition,),
        symbols=(instance,),
    )
    native = parse(sch.write_schematic(created, target=target).text).nodes("symbol")[0]
    definition_node = embedded.node
    if defect == "power":
        definition_node = definition_node.with_children(
            (
                *definition_node.children,
                Node(Atom.symbol("power"), (Atom.symbol("global"),) if target >= 10 else ()),
            )
        )
    root = sch.rebuild_schematic(sheet)
    symbols = root.find("lib_symbols")
    assert symbols is not None
    added = symbols.with_children((*symbols.children, *((definition_node,) if defect != "missing" else ())))
    return root.with_children((*(added if child is symbols else child for child in root.children), native))


def bom_only_multiunit(sheet: SchematicSheet, target: int, *, defect: str = "") -> Node:
    """Two original pinless units of one purchasing part; independently plant inconsistent flags."""
    from fenolite.model.library import SymbolUnit

    root = bom_only_instance(sheet, target)
    read = sch.read_schematic(dumps(root))
    definition = next(symbol for symbol in read.lib_symbols if symbol.name == "AuthoredAccessory")
    definition = dataclasses.replace(definition, units=(SymbolUnit(1, 1), SymbolUnit(2, 1)), ext={})
    embedded = symembed.embed_symbol(definition, target=target)
    first = next(symbol for symbol in read.symbols if symbol.ref == "M1")
    second = dataclasses.replace(
        first,
        id=derived_id("sci", "authored", "accessory-unit2"),
        native_ids={},
        ext={},
        unit=2,
        position=Point(first.position.x + 10_160_000, first.position.y),
        in_bom=defect != "no_bom",
        on_board=defect == "on_board",
        dnp=defect == "dnp",
        uses=tuple(dataclasses.replace(use, unit=2) for use in first.uses),
    )
    created = SchematicSheet(
        id=derived_id("sch", "authored", "accessory-unit2"),
        name="unit2",
        lib_symbols=(embedded.definition,),
        symbols=(second,),
    )
    native = parse(sch.write_schematic(created, target=target).text).nodes("symbol")[0]
    library = root.find("lib_symbols")
    assert library is not None
    changed = library.with_children(
        tuple(
            embedded.node
            if isinstance(node, Node) and node.name == "symbol" and node.atoms()[0].value == definition.lib_id
            else node
            for node in library.children
        )
    )
    return root.with_children((*(changed if child is library else child for child in root.children), native))


def build(name: str, target: int = 10, value: DrawnSchematic | None = None, **kwargs: object) -> BuildOutput:
    """The build of fixture ``name`` with its drawn schematic (or ``value``), hermetic: the project tables of
    the fixture's folder only."""
    return build_design_of(
        design(name),
        target,
        project_dir=folder(name),
        drawn=value if value is not None else drawn(name),
        drawn_file="schematic.toml",
        **kwargs,
    )


def sheets(output: BuildOutput) -> tuple[SchematicSheet, dict[str, SchematicSheet]]:
    """The root and the child sheets that ``output`` plans, read back."""
    texts = {p: d.decode("utf-8") for p, d in output.files.items() if p.endswith(".kicad_sch")}
    root_file = root_name(output)
    root = sch.read_schematic(texts[root_file], file=root_file)
    children = {p: sch.read_schematic(t, file=p) for p, t in texts.items() if p != root_file}
    return root, children


def library() -> dict[str, SymbolDef]:
    """The authored mini library by lib id (``Mini:<name>``)."""
    text = (ROOT / "tests" / "data" / "libs" / "Mini_v9.kicad_sym").read_text(encoding="utf-8")
    return {f"Mini:{symbol.name}": symbol for symbol in read_symbol_library(text, library="Mini")}


def pins(value: DrawnSchematic, name: str) -> dict[PinKey, tuple[PinPoint, ...]]:
    """The pin points of every drawn item of ``value``, from the mini library and the components of fixture
    ``name``: no build, no file but the library."""
    symbols = library()
    components = {component_path(c): c for c in to_model(design(name)).circuit.components}
    found: dict[PinKey, tuple[PinPoint, ...]] = {}
    for instance in value.walk()[0]:
        sheet = value.sheet(instance.sheet)
        assert sheet is not None
        for k, symbol in enumerate(sheet.symbols):
            component = components.get(instance.component(symbol.part))
            if component is None or (sheet.key, "symbol", k) in found:
                continue
            definition = symbols[component.lib_symbol_ref]
            found[(sheet.key, "symbol", k)] = tuple(
                PinPoint(
                    pin.number,
                    pin_point(symbol.at, pin.position, symbol.rotation // 1_000_000, symbol.mirror),
                    pin.etype,
                    pin.hidden,
                    pin.name,
                )  # fmt: skip
                for pin in definition.pins_of(symbol.unit, 1)
            )
        for k, power in enumerate(sheet.powers):
            definition = symbols[power.symbol]
            found[(sheet.key, "power", k)] = tuple(
                PinPoint(
                    pin.number,
                    pin_point(power.at, pin.position, power.rotation // 1_000_000),
                    pin.etype,
                    pin.hidden,
                    pin.name,
                )  # fmt: skip
                for pin in definition.pins_of(1, 1)
            )
    return found


def netlist(name: str, value: DrawnSchematic | None = None) -> DrawnNetlist:
    """The nets of fixture ``name`` (or of ``value`` with the components of ``name``), from the file alone."""
    found = value if value is not None else drawn(name)
    return resolve(found, pins(found, name), design_name=name)


def circuit(name: str) -> Circuit:
    return to_model(design(name)).circuit


def root_name(output: BuildOutput) -> str:
    """The root schematic file of ``output``."""
    return next(p for p in output.files if p.endswith(".kicad_sch") and "/" not in p)


def resolved(output: BuildOutput) -> tuple[DrawnSchematic, DrawnNetlist, Circuit]:
    """The drawn schematic that ``output``'s sheets give back, its nets and the circuit of the build."""
    root, children = sheets(output)
    circuit = output.design.circuit
    found = kdrawn.extract_with_pins(
        root, children, components=kdrawn.refs_to_paths(circuit), root_file=root_name(output)
    )
    return found.drawn, kdrawn._resolve_extracted(found), circuit


def cli_build(script: Path, out: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    """``fenolite build SCRIPT --out OUT --confirm --json`` in this process: the exit code and the envelope
    (the error object when the build failed before one)."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main(["build", str(script), "--out", str(out), "--confirm", "--json", *extra])
    text = stdout.getvalue() or stderr.getvalue().strip().splitlines()[-1]
    return code, json.loads(text) if text else {}


def blocks_top(folder: Path, drop: str = "") -> Path:
    """The block example (change c0251) under ``folder`` with a drawn root whose block instances ``ch0`` and
    ``ch1`` are ``generated`` sheets (change c0276, "Generated sheets inside a drawing"): the root is the
    extraction of the example's generated build in ``folder / "gen"``, with the sheet pins the generator
    gives, less the pin ``drop`` of ``ch0``. Returns the script, which loads ``schematic.toml``."""
    source = folder / "blocks"
    shutil.copytree(BLOCKS, source)
    gen = folder / "gen"
    code, envelope = cli_build(source / "design.py", gen)
    assert code == 0, envelope
    root_file = gen / "blocks_demo.kicad_sch"
    tree = sch.sheet_files(root_file)
    root = sch.read_schematic(root_file, file=root_file.name)
    children = {f: sch.read_schematic(gen / f, file=f) for f in tree.files[1:]}
    circuit = read_side(gen).design.circuit
    found = kdrawn.extract(
        root, children, components=kdrawn.refs_to_paths(circuit), root_file=root_file.name
    )[0]
    top = found.sheets[0]
    refs = tuple(
        dataclasses.replace(ref, pins=tuple(p for p in ref.pins if p.name != drop))
        if ref.module == "ch0"
        else ref
        for ref in top.sheet_refs
    )
    assert {ref.module for ref in refs} == {"ch0", "ch1"}
    sheets = (dataclasses.replace(top, sheet_refs=refs), *(DrawnSheet(r.sheet, generated=True) for r in refs))
    (source / "schematic.toml").write_text(write_drawn(dataclasses.replace(found, sheets=sheets)), "utf-8")
    script = source / "design.py"
    script.write_text(
        script.read_text(encoding="utf-8") + '\ndesign.load_schematic("schematic.toml")\n', "utf-8"
    )
    return script


__all__ = [
    "BLOCKS",
    "EXAMPLE",
    "FIXTURES",
    "NAMES",
    "blocks_top",
    "build",
    "cli_build",
    "design",
    "drawn",
    "folder",
    "resolved",
    "root_name",
    "sheets",
    "text",
]
