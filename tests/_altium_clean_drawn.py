# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored connected bus with explicit intent on its two unused input pins."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import _drawn
from _buildhelp import LIBS

from fenolite.lens.drawn import write_drawn
from fenolite.model.drawn import DrawnBusAlias


def source(root: Path, *, marked: bool = True) -> Path:
    """Keep the original source unchanged; only the copied control declares unused pins."""
    shutil.copytree(_drawn.folder("bus"), root)
    for table, head, uri in (
        ("fp-lib-table", "fp_lib_table", LIBS / "Mini_v9.pretty"),
        ("sym-lib-table", "sym_lib_table", LIBS / "Mini_v9.kicad_sym"),
    ):
        (root / table).write_text(
            f'({head}\n(version 7)\n(lib (name "Mini") (type "KiCad") '
            f'(uri "{uri.as_posix()}") (options "") (descr "")))\n',
            encoding="utf-8",
        )
    value = _drawn.drawn("bus")
    root_sheet = value.sheets[0]
    symbol_index = next(i for i, symbol in enumerate(root_sheet.symbols) if symbol.part == "U1")
    pins = _drawn.pins(value, "bus")[(root_sheet.key, "symbol", symbol_index)]
    unused = tuple(pin.at for pin in pins if pin.number in {"11", "12"})
    assert len(unused) == 2 and not root_sheet.no_connects
    sheets = []
    for sheet in value.sheets:
        sheets.append(
            dataclasses.replace(
                sheet,
                labels=tuple(
                    dataclasses.replace(label, text="{DATA}") if label.text == "D[0..3]" else label
                    for label in sheet.labels
                ),
                sheet_refs=tuple(
                    dataclasses.replace(
                        ref, pins=tuple(dataclasses.replace(pin, name="{DATA}") for pin in ref.pins)
                    )
                    for ref in sheet.sheet_refs
                ),
                bus_aliases=(DrawnBusAlias("DATA", ("D0", "D1", "D2", "D3")),) if sheet.key == "root" else (),
                no_connects=unused if marked and sheet.key == "root" else (),
            )
        )
    (root / "schematic.toml").write_text(
        write_drawn(dataclasses.replace(value, sheets=tuple(sheets))), encoding="utf-8"
    )
    script = root / "design.py"
    if marked:
        text = script.read_text(encoding="utf-8").replace(
            "from fenolite.dsl import Design, Module, Net, Part, connect, mm",
            "from fenolite.dsl import Design, Module, Net, Part, connect, mm, no_connect",
        )
        text = text.replace(
            'design.load_schematic("schematic.toml")',
            'no_connect(u1[11], u1[12])\ndesign.load_schematic("schematic.toml")',
        )
        script.write_text(text, encoding="utf-8")
    return script
