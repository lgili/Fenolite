# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 temporary field-font project; no GUI/native-save claim (c0326)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _drawn
from _buildhelp import LIBS, build, project

from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Net, Part, connect, copper, mm
from fenolite.model.board import Track
from fenolite.model.drawn import DrawnField, DrawnFont


def field_font(text: str, native_font: Node) -> str:
    """Put a visible, unchanged-text Footprint field at an original authored point."""
    root = parse(text)
    changed = 0
    children: list[Atom | Node] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "symbol" and child.find("lib_id") is not None:
            properties: list[Atom | Node] = []
            for prop in child.children:
                if (
                    isinstance(prop, Node)
                    and prop.name == "property"
                    and prop.atoms()[0].value == "Footprint"
                ):
                    items: list[Atom | Node] = []
                    for item in prop.children:
                        if isinstance(item, Node) and item.name == "hide":
                            continue
                        if isinstance(item, Node) and item.name == "at":
                            item = node(
                                "at", Atom.from_nm(40_000_000), Atom.from_nm(30_000_000), Atom.integer(0)
                            )
                        elif isinstance(item, Node) and item.name == "effects":
                            item = node("effects", native_font)
                        items.append(item)
                    prop = prop.with_children(items)
                    changed += 1
                properties.append(prop)
            child = child.with_children(properties)
        children.append(child)
    assert changed == 1
    return dumps(root.with_children(children))


def original(folder: Path, native_font: Node | None = None, *, target: int = 9) -> Path:
    """An original one-resistor board with routed copper and matching visible field text.

    Circuit, geometry and temporary CAD are authored for Fenolite and dedicated CC0-1.0. The local
    Footprints id deliberately agrees between board and sheet, isolating font loss from alias text.
    """
    folder.mkdir(parents=True)
    project(folder, {"Footprints": str(LIBS / "Mini_v9.pretty")}, {"Mini": str(LIBS / "Mini_v9.kicad_sym")})
    design = Design("font_probe")
    design.board(mm(30), mm(20))
    resistor = Part("R1", "Mini:Mini_R", footprint="Footprints:Mini_R_0603", value="1k")
    design.add(resistor)
    resistor.place(mm(15), mm(10))
    net = Net("FONT_PROBE")
    connect(net, resistor[1], resistor[2])
    design.track("probe", resistor.pad(1), resistor.pad(2), width=mm("0.25"))
    output = build(design, target=target, project_dir=folder)
    assert not [issue for issue in output.issues if issue.severity == "error"], output.issues
    for relative, data in output.files.items():
        if relative.startswith(".fenolite/"):
            continue
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    # The pure fixture builder does not apply script copper intents. Author the intended routed
    # pad-to-pad segment in its native board, so strict level 5 is actually compared, never skipped.
    board = folder / "font_probe.kicad_pcb"
    actual = read_board(board)
    assert actual.board is not None
    footprint = actual.board.footprints[0]
    assert footprint.rotation == 0
    first, second = footprint.pads
    track = Track(
        id=derived_id("trk", "drawn-font", "authored-pad-link"),
        start=Point(footprint.position.x + first.position.x, footprint.position.y + first.position.y),
        end=Point(footprint.position.x + second.position.x, footprint.position.y + second.position.y),
        width=250_000,
        layer="F.Cu",
        net_id=first.net_id,
    )
    actual = dataclasses.replace(actual, board=dataclasses.replace(actual.board, tracks=(track,)))
    board.write_text(write_board(actual, target=target).text, encoding="utf-8")
    schematic = folder / "font_probe.kicad_sch"
    native_font = native_font or node("font", node("size", Atom.from_nm(250_000), Atom.from_nm(250_000)))
    schematic.write_text(field_font(schematic.read_text(encoding="utf-8"), native_font), encoding="utf-8")
    assert not (folder / ".fenolite").exists()
    return folder


def styled_hierarchy(folder: Path, *, target: int = 9, font: DrawnFont | None = None) -> Path:
    """Original CC0 full drawing with styled text surfaces and one actual routed segment.

    This temporary derivative uses only Fenolite's authored mini-library/full fixture. Native GUI
    saving is not part of its provenance. Reference/Value/Footprint and sheet-property texts stay
    code-owned; only their typed style and pose are authored here.
    """
    value = _drawn.drawn("full")
    font = font or DrawnFont(Size(500_000, 750_000))
    sheets = []
    for sheet in value.sheets:
        refs = tuple(
            dataclasses.replace(
                ref,
                pins=tuple(dataclasses.replace(pin, font=font, justify="") for pin in ref.pins),
                fields=(
                    DrawnField("Sheetname", Point(ref.at.x, ref.at.y - 3_000_000), font=font),
                    DrawnField(
                        "Sheetfile",
                        Point(ref.at.x, ref.at.y + ref.size.h + 3_000_000),
                        justify="right",
                        hide=True,
                        font=font,
                    ),
                ),
            )
            for ref in sheet.sheet_refs
        )
        sheets.append(
            dataclasses.replace(
                sheet,
                symbols=tuple(
                    dataclasses.replace(
                        symbol, fields=tuple(dataclasses.replace(field, font=font) for field in symbol.fields)
                    )
                    for symbol in sheet.symbols
                ),
                powers=tuple(
                    dataclasses.replace(
                        power,
                        fields=(DrawnField("Value", Point(power.at.x, power.at.y + 2_000_000), font=font),),
                    )
                    for power in sheet.powers
                ),
                labels=tuple(dataclasses.replace(label, font=font, justify="") for label in sheet.labels),
                sheet_refs=refs,
            )
        )
    drawing = dataclasses.replace(value, sheets=tuple(sheets))
    design = _drawn.design("full")
    design.track(
        "font_control",
        (mm(35), mm(25)),
        (mm(37), mm(25)),
        width=mm("0.25"),
        net=next(iter(design.nets.values())),
    )
    output = build(
        design,
        target,
        project_dir=_drawn.folder("full"),
        drawn=drawing,
        drawn_file="schematic.toml",
        copper_intents=copper(design),
    )
    assert output.files and not any(issue.severity == "error" for issue in output.issues), output.issues
    folder.mkdir(parents=True)
    for relative, data in output.files.items():
        if relative.startswith(".fenolite/"):
            continue
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    assert not (folder / ".fenolite").exists()
    return folder
