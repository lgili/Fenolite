# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scenes of symbol and footprint libraries for the viewer page (capability library-viewer, change c0179).

``footprint_library_scene(path)`` and ``symbol_library_scene(path)`` give a ``fenolite.view_library.v0``
scene: the library's metadata and one item per footprint, or per symbol part, each with the scene the page
draws. A footprint is placed alone at the origin of a one-part board and drawn by the board scene of c0176,
so a click on a pad gives its exact size; a symbol is drawn by the schematic scenes of c0177 (Altium) and
c0178 (KiCad) on a sheet the size of the symbol. Standard library only.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.backends.base import BoardFrame
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.model.board import Board, FootprintInstance, Layer, LayerKind
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef, Library
from fenolite.view import themes
from fenolite.view.kicad_schematic import symbol_scene, symbol_units
from fenolite.view.scene import build_scene
from fenolite.view.schematic import build_symbol_scene
from fenolite.view.themes import Palette

SCHEMA = "fenolite.view_library.v0"
FOOTPRINT_SUFFIXES = (".pcblib", ".kicad_mod", ".pretty")
SYMBOL_SUFFIXES = (".schlib", ".kicad_sym")
_KINDS: tuple[tuple[str, LayerKind], ...] = (
    (".Cu", "copper"),
    (".SilkS", "silkscreen"),
    (".Silkscreen", "silkscreen"),
    (".Mask", "soldermask"),
    (".Paste", "solderpaste"),
    (".CrtYd", "courtyard"),
    (".Courtyard", "courtyard"),
    (".Fab", "fabrication"),
)


def layer_kind(name: str) -> LayerKind:
    """The kind of a library layer by its name (design, decision 2)."""
    for suffix, kind in _KINDS:
        if name.endswith(suffix):
            return kind
    if name == "Edge.Cuts":
        return "edge"
    if name.startswith("Mech"):
        return "mechanical"
    return "user"


def _files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".kicad_mod")
    return [path]


def _digest(files: list[Path]) -> tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    for file in files:
        data = file.read_bytes()
        total += len(data)
        if len(files) > 1:
            h.update(file.name.encode("utf-8") + b"\0")
        h.update(data)
    return h.hexdigest(), total


def _board_of(fp: FootprintDef) -> Design:
    names = sorted(
        {layer for pad in fp.pads for layer in pad.layers if "*" not in layer}
        | {g.layer for g in fp.graphics}
    )
    names = sorted(set(names) | {"F.Cu", "B.Cu"})
    layers = tuple(
        Layer(id=f"layer{k}", name=name, kind=layer_kind(name), ordinal=k) for k, name in enumerate(names)
    )
    instance = FootprintInstance(
        id="fp1",
        component_id="",
        lib_ref=fp.lib_id,
        position=Point(0, 0),
        pads=fp.pads,
        graphics=fp.graphics,
        bodies=fp.bodies,
    )
    design = Design.new(fp.name or "footprint", seed=0)
    return dataclasses.replace(design, board=Board(id="board1", layers=layers, footprints=(instance,)))


def _extent(points: list[tuple[int, int]]) -> list[int] | None:
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _footprint_info(fp: FootprintDef) -> tuple[list[list[str]], dict[str, Any]]:
    copper: list[tuple[int, int]] = []
    for pad in fp.pads:
        w, h = pad.size.w, pad.size.h
        turned = (pad.rotation // 90_000_000) % 2 == 1 if pad.rotation % 90_000_000 == 0 else False
        hw, hh = (h, w) if turned else (w, h)
        if pad.rotation % 90_000_000:
            hw = hh = max(w, h)
        copper += [
            (pad.position.x - hw // 2, pad.position.y - hh // 2),
            (pad.position.x + hw // 2, pad.position.y + hh // 2),
        ]
    courtyard = [
        (p.x, p.y) for g in fp.graphics if g.layer.endswith(("CrtYd", "Courtyard")) for p in g.points
    ]
    facts = {"pads": len(fp.pads), "copper_nm": _extent(copper), "courtyard_nm": _extent(courtyard)}
    info = [["Footprint", fp.name], ["Pads", str(len(fp.pads))]]
    if fp.description:
        info.append(["Description", fp.description])
    return info, facts


def footprint_library_scene(path: Path, *, kicad: Palette | None = None) -> dict[str, Any]:
    """The scene of a footprint library: an Altium ``.PcbLib``, a KiCad ``.pretty`` folder or a
    ``.kicad_mod``."""
    files = _files(path)
    items: list[dict[str, Any]] = []
    notes: list[str] = []
    backend_name = ""
    for file in files:
        backend = registry.for_path(file)
        if backend is None:
            raise FormatError(f"no backend reads {file.name}", file=file.name)
        backend_name = backend.name
        read = backend.read(file)
        library = read.content
        if not isinstance(library, Library):
            raise FormatError(f"{file.name} is not a footprint library", file=file.name)
        name = themes.theme_for(backend.name)
        palette = kicad if name == "kicad" and kicad is not None else themes.palette(name)
        frame = backend if isinstance(backend, BoardFrame) else None
        for fp in library.footprints:
            info, facts = _footprint_info(fp)
            item: dict[str, Any] = {"name": fp.name, "description": fp.description, "info": info, **facts}
            try:
                scene = build_scene(
                    _board_of(fp),
                    frame,
                    name=fp.name,
                    backend=backend.name,
                    evidence=read.evidence.level.value,
                )
                item["scene"] = themes.apply_board_theme(scene, palette)
            except (ValueError, KeyError, FormatError) as exc:
                item["scene"] = None
                notes.append(f"{fp.name}: not drawn ({type(exc).__name__}: {exc})")
            items.append(item)
    digest, size = _digest(files)
    return _library("pcb", path.name, digest, size, backend_name, items, notes)


def _library(
    lib: str, name: str, digest: str, size: int, backend: str, items: list[dict[str, Any]], notes: list[str]
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "kind": "library",
        "lib": lib,
        "meta": {
            "name": name,
            "sha256": digest,
            "bytes": size,
            "backend": backend,
            "evidence": "INFERRED",
            "counts": {"items": len(items)},
            "notes": notes,
        },
        "items": items,
        "overlays": [],
    }


def symbol_library_scene(path: Path, *, kicad: Palette | None = None) -> dict[str, Any]:
    """The scene of a symbol library: an Altium ``.SchLib`` or a KiCad ``.kicad_sym``."""
    data = path.read_bytes()
    items: list[dict[str, Any]] = []
    if path.suffix.lower() == ".schlib":
        library = read_schlib(data, file=path.name)
        for component in library.components:
            record = next((r for r in component.records if r.record_id == 1), None)
            parts = getattr(record, "part_count", 1) if record is not None else 1
            for part in range(1, parts + 1):
                label = (
                    component.name if parts == 1 else f"{component.name} : Part {chr(ord('A') + part - 1)}"
                )
                scene = build_symbol_scene(library, component, name=label, part=part)
                items.append(_symbol_item(label, component.description, scene))
        backend = "altium"
    else:
        root = parse(data.decode("utf-8"), file=path.name)
        if root.name != "kicad_symbol_lib":
            raise FormatError(f"{path.name} is not a KiCad symbol library", file=path.name)
        symbols: dict[str, Node] = {_name(node): node for node in root.nodes("symbol")}
        palette = kicad or themes.palette("kicad")
        for symbol_name, node in symbols.items():
            units = symbol_units(node, symbols)
            for unit in range(1, units + 1):
                label = symbol_name if units == 1 else f"{symbol_name} : Unit {chr(ord('A') + unit - 1)}"
                scene = symbol_scene(node, symbols, unit=unit, name=label, palette=palette)
                items.append(_symbol_item(label, _description(node), scene))
        backend = "kicad"
    return _library("schematic", path.name, hashlib.sha256(data).hexdigest(), len(data), backend, items, [])


def _name(node: Node) -> str:
    atoms = node.atoms()
    return atoms[0].value if atoms else ""


def _description(node: Node) -> str:
    for prop in node.nodes("property"):
        atoms = prop.atoms()
        if len(atoms) > 1 and atoms[0].value == "Description":
            return atoms[1].value
    return ""


def _symbol_item(label: str, description: str, scene: dict[str, Any]) -> dict[str, Any]:
    pins = scene["meta"]["counts"].get("pins", 0)
    info = [["Symbol", label], ["Pins", str(pins)]]
    if description:
        info.append(["Description", description])
    return {"name": label, "description": description, "info": info, "pins": pins, "scene": scene}


def library_scene(path: Path, *, kicad: Palette | None = None) -> dict[str, Any]:
    """The scene of any library the viewer draws."""
    suffix = path.suffix.lower()
    if suffix in SYMBOL_SUFFIXES:
        return symbol_library_scene(path, kicad=kicad)
    return footprint_library_scene(path, kicad=kicad)


def summary(scene: dict[str, Any]) -> dict[str, Any]:
    """The part of a library scene that a reply carries."""
    return {
        "kind": "library",
        "lib": scene["lib"],
        "counts": dict(scene["meta"]["counts"]),
        "items": [item["name"] for item in scene["items"][:50]],
    }


__all__ = [
    "FOOTPRINT_SUFFIXES",
    "SCHEMA",
    "SYMBOL_SUFFIXES",
    "footprint_library_scene",
    "layer_kind",
    "library_scene",
    "summary",
    "symbol_library_scene",
]
