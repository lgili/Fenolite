# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DSL designs as model designs, with ids keyed by names and paths (``docs/dsl.md``, "Ids").

Every object gets ``derived_id(prefix, DSL_BACKEND, key)`` from ``KEYS``, so ids never depend on the
seed or on the order of the script, and no object holds a provenance (no absolute path reaches
``.fenolite/``).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite import __version__
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl.design import Design
from fenolite.dsl.errors import DslError
from fenolite.dsl.module import Module as DslModule
from fenolite.dsl.part import Part, Placement
from fenolite.model.board import Board, Outline
from fenolite.model.circuit import Circuit, Component, Interface, Module, Net, NetClass, PinRef
from fenolite.model.design import SCHEMA_VERSION, DesignHeader
from fenolite.model.design import Design as ModelDesign
from fenolite.model.manufacturing import Manifest
from fenolite.model.rules import RuleSet

DSL_BACKEND = "dsl"
BOARD_ORIGIN = Point(100_000_000, 100_000_000)
"""Where the board-relative origin is written (a Fenolite choice, ``docs/dsl.md``, "Frame")."""
PATH_PROPERTY = "fenolite.path"
KEYS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "design": ("dsn", "design"),
        "board": ("brd", "board"),
        "outline": ("out", "outline"),
        "rules": ("rst", "rules"),
        "manifest": ("mfn", "manifest"),
        "module": ("mod", "module:<path>"),
        "component": ("cmp", "component:<path>"),
        "pin": ("pin", "pin:<path>:<number>"),
        "net": ("net", "net:<name>"),
        "netclass": ("cls", "netclass:<name>"),
        "interface": ("itf", "interface:<kind>:<name>"),
        "layer": ("lay", "layer:<KiCad name>"),
    }
)
"""Object → (id prefix, key form); ids are ``derived_id(prefix, "dsl", key)``."""


def key_id(kind: str, *parts: str) -> str:
    """The id of a DSL object of ``kind`` (a ``KEYS`` entry), its key filled with ``parts``."""
    prefix, form = KEYS[kind]
    key = form.split(":", 1)[0] + ("".join(f":{p}" for p in parts) if parts else "")
    return derived_id(prefix, DSL_BACKEND, key if parts else form)


def _component(part: Part) -> Component:
    return Component(
        id=key_id("component", part.path),
        ref=part.ref,
        value=part.value,
        lib_symbol_ref=part.lib_id,
        lib_footprint_ref=part.footprint or "",
        properties=dict(sorted({**part.properties, PATH_PROPERTY: part.path}.items())),
    )


def to_model(design: Design) -> ModelDesign:
    """The model design of ``design``: model types only, no validation, no library access."""
    parts = sorted(design.parts.values(), key=lambda p: p.path)
    components = tuple(_component(p) for p in parts)
    classes = {
        name: NetClass(
            id=key_id("netclass", name),
            name=name,
            clearance=spec.clearance,
            track_width=spec.track_width,
            via_diameter=spec.via_diameter,
            via_drill=spec.via_drill,
        )
        for name, spec in sorted(design.rules.netclasses.items())
    }
    members: dict[str, set[PinRef]] = {name: set() for name in design.nets}
    for part in parts:
        for designator, net in part.connections.items():
            members[net.name].add(PinRef(key_id("component", part.path), designator))
    nets = tuple(
        Net(
            id=key_id("net", name),
            name=name,
            netclass_id=classes[net.netclass].id if net.netclass is not None else None,
            members=tuple(sorted(members[name])),
        )
        for name, net in sorted(design.nets.items())
    )
    interfaces = tuple(
        Interface(
            id=key_id("interface", itf.kind, name),
            name=name,
            kind=itf.kind,
            members={role: key_id("net", net.name) for role, net in itf.members.items()},
        )
        for name, itf in sorted(design.interfaces.items())
    )
    modules = tuple(_module(m) for _, m in sorted(design.modules.items()))
    outline = None
    if design.size is not None:
        w, h = design.size
        x0, y0 = BOARD_ORIGIN.x, BOARD_ORIGIN.y
        points = (Point(x0, y0), Point(x0 + w, y0), Point(x0 + w, y0 + h), Point(x0, y0 + h))
        outline = Outline(id=key_id("outline"), points=points)
    return ModelDesign(
        header=DesignHeader(
            id=key_id("design"), name=design.name, schema_version=SCHEMA_VERSION, fenolite_version=__version__
        ),
        circuit=Circuit(
            components=components,
            nets=nets,
            netclasses=tuple(classes.values()),
            interfaces=interfaces,
            modules=modules,
        ),
        board=Board(id=key_id("board"), outline=outline),
        rules=RuleSet(id=key_id("rules")),
        manufacturing=Manifest(id=key_id("manifest")),
    )


def _module(module: DslModule) -> Module:
    parent = module.parent
    return Module(
        id=key_id("module", module.path),
        path=module.path,
        parent=key_id("module", parent.path) if isinstance(parent, DslModule) else None,
        component_ids=tuple(
            key_id("component", c.path) for c in sorted(module.children, key=_path) if isinstance(c, Part)
        ),
    )


def _path(obj: Part | DslModule) -> str:
    return obj.path


def placements(design: Design) -> Mapping[str, Placement]:
    """Each placed component path, in path order, with its placement in the written frame."""
    out: dict[str, Placement] = {}
    for path, part in sorted(design.parts.items()):
        request = part.request
        if request is None:
            continue
        at = Point(BOARD_ORIGIN.x + request.x, BOARD_ORIGIN.y + request.y)
        out[path] = Placement(at, request.rotation, request.side, request.locked)
    return MappingProxyType(out)


def moves(design: Design) -> Mapping[str, str]:
    """The ``moved()`` aliases, new component path → old, in path order (``docs/lens.md``, "moved()").

    A ``new`` path that is not an added part, or an ``old`` path that still is one, raises ``DslError``:
    the old part would lose its layout to the new one, so chains are refused too.
    """
    for new, old in sorted(design.aliases.items()):
        if new not in design.parts:
            raise DslError(f"moved({old!r}, {new!r}): {new!r} is not a part of the design")
        if old in design.parts:
            raise DslError(f"moved({old!r}, {new!r}): {old!r} is still a part of the design")
    return MappingProxyType(dict(sorted(design.aliases.items())))


__all__ = [
    "BOARD_ORIGIN",
    "DSL_BACKEND",
    "KEYS",
    "PATH_PROPERTY",
    "key_id",
    "moves",
    "placements",
    "to_model",
]
