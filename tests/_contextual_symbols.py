# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored CC0 two-file native symbol snapshots and exact AST mutation helpers (c0327)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from _buildhelp import build as build_design
from _drawn import design as drawn_design
from _drawn import drawn as drawn_value
from _drawn import folder as drawn_folder

from fenolite.backends.kicad import parity_inputs
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.dsl import Design, copper, mm, to_model
from fenolite.importer.emit import Options, emit
from fenolite.importer.provenance import Provenance
from fenolite.importer.source import InputFile, Source, read_kicad

FIXTURE = Path(__file__).resolve().parent / "data/drawn/contextual"
ROOT_FILE = "drawn_repeat.kicad_sch"
FIRST = "sheets/channel.kicad_sch"
SECOND = "sheets/channel_authored_second.kicad_sch"
NATIVE_ID = "Mini:Mini_R"


def source(folder: Path = FIXTURE) -> Source:
    sheets = parity_inputs.read_sheets(folder / ROOT_FILE)
    return Source(
        "drawn_repeat", "kicad", to_model(Design("drawn_repeat")), "", 9,
        tuple(InputFile(name, hashlib.sha256((folder / name).read_bytes()).hexdigest(), "kicad_sch")
              for name in sheets),
        folder=folder, hierarchy=sheets,
    )  # fmt: skip


def definition(text: str, lib_id: str = NATIVE_ID) -> Node:
    library = parse(text).find("lib_symbols")
    assert library is not None
    return next(item for item in library.nodes("symbol") if item.atoms()[0].value == lib_id)


def change(text: str, edit: Callable[[Node], Node], lib_id: str = NATIVE_ID) -> str:
    root = parse(text)
    library = root.find("lib_symbols")
    assert library is not None
    item = definition(text, lib_id)
    changed = library.with_children(tuple(edit(c) if c == item else c for c in library.children))
    return dumps(root.with_children(tuple(changed if c == library else c for c in root.children)))


def property_value(node: Node, key: str, value: str) -> Node:
    return node.with_children(tuple(
        c.with_children((c.children[0], Atom.string(value), *c.children[2:]))
        if isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == key else c
        for c in node.children
    ))  # fmt: skip


def project(folder: Path, target: int = 9) -> Path:
    """Complete owned board/project, with the declared split-child native drawings."""
    design = drawn_design("repeat")
    design.track(
        "context_fidelity",
        (mm(35), mm(25)),
        (mm(37), mm(25)),
        width=mm("0.25"),
        net=next(iter(design.nets.values())),
    )
    made = build_design(
        design,
        target,
        project_dir=drawn_folder("repeat"),
        drawn=drawn_value("repeat"),
        copper_intents=copper(design),
    )
    assert made.files and not any(i.severity == "error" for i in made.issues), made.issues
    files = {name: data for name, data in made.files.items()
             if not name.startswith(".fenolite/")}  # fmt: skip
    files.update({path.relative_to(FIXTURE).as_posix(): path.read_bytes()
                  for path in FIXTURE.rglob("*") if path.suffix in (".kicad_sch", ".kicad_pro")})  # fmt: skip
    for relative, data in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder / "drawn_repeat.kicad_pro"


def code(folder: Path, target: int = 9) -> Path:
    original = read_kicad(project(folder.parent / "original", target))
    made = emit(original, Options("drawn_repeat", Provenance(date="2026-11-02"), target=target))
    for relative, data in made.files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder / "design.py"
