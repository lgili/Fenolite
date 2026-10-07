# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DSL designs as model designs, with ids keyed by names and paths (``docs/dsl.md``, "Ids").

Every object gets ``derived_id(prefix, DSL_BACKEND, key)`` from ``KEYS``, so ids never depend on the
seed or on the order of the script, and no object holds a provenance (no absolute path reaches
``.fenolite/``).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType

from fenolite import __version__
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl.design import MINIMUM_KINDS, Design
from fenolite.dsl.errors import DslError
from fenolite.dsl.module import Module as DslModule
from fenolite.dsl.part import FieldRequest, PadZoneRequest, Part, Placement, pad_pairs
from fenolite.model.board import Board, Outline, StackLayer, Stackup, Zone
from fenolite.model.circuit import Circuit, Component, Interface, Module, Net, NetClass, PinRef
from fenolite.model.design import SCHEMA_VERSION, DesignHeader
from fenolite.model.design import Design as ModelDesign
from fenolite.model.manufacturing import Manifest
from fenolite.model.presentation import SheetFrameRef
from fenolite.model.rules import Rule, RuleSet, Selector

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
        "zone": ("zon", "zone:<name>"),
        "rule": ("rul", "rule:<kind>[:<net class>]"),
        "stackup": ("stk", "stackup"),
        "stack_layer": ("sly", "stack_layer:<k>"),
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
        pin_pad_map=pad_pairs(part.pad_map),
    )


def _rules(design: Design) -> tuple[Rule, ...]:
    """One model rule per ``design.rules.minimum()`` value: the board minimums, then the class minimums
    in class-name order, each group in kind order. A board minimum has priority 0 and a class minimum
    priority 1, so the class minimum governs the items of its class (``docs/dsl.md``, "Design rules")."""
    specs = sorted(
        design.rules.minimums.values(),
        key=lambda s: (s.netclass is not None, s.netclass or "", MINIMUM_KINDS.index(s.kind)),
    )
    return tuple(
        Rule(
            id=key_id("rule", spec.kind, *(() if spec.netclass is None else (spec.netclass,))),
            name=f"min_{spec.kind}" if spec.netclass is None else f"min_{spec.kind}_{spec.netclass}",
            kind=spec.kind,
            selector_a=Selector("all") if spec.netclass is None else Selector("netclass", spec.netclass),
            min=spec.min,
            priority=0 if spec.netclass is None else 1,
        )
        for spec in specs
    ) + tuple(
        Rule(
            id=key_id("rule", "named", spec.name),
            name=spec.name,
            kind=spec.kind,
            selector_a=spec.where,
            selector_b=spec.between,
            layers=spec.layers,
            min=spec.min,
            opt=spec.opt,
            max=spec.max,
            severity=spec.severity,
            priority=spec.priority,
        )
        for spec in design.rules.named.values()
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
    marks = tuple(
        sorted(PinRef(key_id("component", part.path), d) for part in parts for d in part.no_connects)
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
    zones: tuple[Zone, ...] = ()
    if design.size is not None:
        w, h = design.size
        x0, y0 = BOARD_ORIGIN.x, BOARD_ORIGIN.y
        points = (Point(x0, y0), Point(x0 + w, y0), Point(x0 + w, y0 + h), Point(x0, y0 + h))
        outline = Outline(id=key_id("outline"), points=points)
        zones = tuple(
            Zone(
                id=key_id("zone", name),
                outline=(
                    points if spec.outline is None else tuple(Point(x0 + x, y0 + y) for x, y in spec.outline)
                ),
                name=name,
                layers=spec.layers,
                net_id=key_id("net", spec.net) if spec.net is not None else None,
                priority=spec.priority,
                settings=spec.settings,
                locked=spec.locked,
            )
            for name, spec in sorted(design.zones.items())
        )
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
            no_connects=marks,
        ),
        board=Board(
            id=key_id("board"),
            outline=outline,
            zones=zones,
            stackup=_stackup(design),
            sheet=_sheet(design),
            title_block=design.block,
            via_protection=design.via_default[0] if design.via_default is not None else None,
        ),
        rules=RuleSet(id=key_id("rules"), rules=_rules(design)),
        manufacturing=Manifest(id=key_id("manifest")),
    )


SHEET_SUFFIX = ".kicad_wks"


def _stackup(design: Design) -> Stackup | None:
    """The model stack-up of ``Design.stackup()``: one entry per script entry, with the names KiCad gives
    the same rows, ``core`` and ``prepreg`` as the kind of a dielectric; ``None`` without a call."""
    spec = design.stack
    if spec is None:
        return None
    entries: list[StackLayer] = []
    for k, (name, entry) in enumerate(spec.entries):
        dielectric = entry.kind in ("core", "prepreg")
        entries.append(
            StackLayer(
                id=key_id("stack_layer", str(k)),
                name=name,
                kind="dielectric" if dielectric else "soldermask" if entry.kind == "mask" else entry.kind,  # type: ignore[arg-type]
                thickness=entry.thickness,
                material=entry.material,
                epsilon_r=entry.epsilon_r,
                loss_tangent=entry.loss_tangent,
                dielectric_kind=entry.kind if dielectric else None,  # type: ignore[arg-type]
                color=entry.color,
            )
        )
    return Stackup(
        id=key_id("stackup"),
        layers=tuple(entries),
        finish=spec.finish,
        impedance_controlled=spec.impedance_controlled,
    )


def stackup_locked(design: Design) -> bool:
    """The ``locked`` argument of ``Design.stackup()``; ``False`` without a call."""
    return design.stack is not None and design.stack.locked


def via_protection_locked(design: Design) -> bool:
    """The ``locked`` argument of ``Design.via_protection()``; ``False`` without a call."""
    return design.via_default is not None and design.via_default[1]


def _sheet(design: Design) -> SheetFrameRef | None:
    """The model's sheet: the paper of ``sheet()``, and ``<design name>.kicad_wks`` as the drawing sheet
    when the script names one. The script's path never enters the model."""
    frame = design.sheet_frame
    if frame is None or design.sheet_source is None:
        return frame
    return dataclasses.replace(frame, drawing_sheet=f"{design.name}{SHEET_SUFFIX}")


def drawing_sheet_source(design: Design) -> str | None:
    """The drawing sheet that ``sheet()`` names, as written in the script (a path relative to the script's
    folder), or ``None``."""
    return design.sheet_source


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


def fields(design: Design) -> Mapping[str, tuple[FieldRequest, ...]]:
    """The field placement requests of every part that has one: component path, in path order, → its
    requests in name order (``docs/dsl.md``, "Field placement")."""
    out: dict[str, tuple[FieldRequest, ...]] = {}
    for path, part in sorted(design.parts.items()):
        if part.field_requests:
            out[path] = tuple(request for _, request in sorted(part.field_requests.items()))
    return MappingProxyType(out)


def pad_zones(design: Design) -> Mapping[str, tuple[PadZoneRequest, ...]]:
    """The pad zone connection requests of every part that has one: component path, in path order, → its
    requests by pad number and then index, ``None`` first (``docs/dsl.md``, "Zones")."""
    out: dict[str, tuple[PadZoneRequest, ...]] = {}
    for path, part in sorted(design.parts.items()):
        if part.pad_zone_requests:
            out[path] = tuple(
                request
                for _, request in sorted(
                    part.pad_zone_requests.items(),
                    key=lambda entry: (entry[0][0], entry[0][1] is not None, entry[0][1] or 0),
                )
            )
    return MappingProxyType(out)


def planes(design: Design) -> Mapping[str, str]:
    """The internal planes of ``design.board(planes=…)``: inner layer name → net name, in layer order.

    A plane on a net that the design does not hold raises ``DslError`` naming it. The model gets no plane
    entity: a plane is a build parameter, as the copper count is.
    """
    for layer, net in design.planes.items():
        if net not in design.nets:
            raise DslError(f"the plane on {layer} names the net {net!r}, which the design does not hold")
    return MappingProxyType(dict(design.planes))


def _checked_aliases(design: Design) -> tuple[dict[str, str], dict[str, str]]:
    """The ``moved()`` aliases split into part aliases and module aliases, new → old, after the checks."""
    parts: dict[str, str] = {}
    modules: dict[str, str] = {}
    for new, old in sorted(design.aliases.items()):
        if old in design.parts or old in design.modules:
            kind = "part" if old in design.parts else "module"
            raise DslError(f"moved({old!r}, {new!r}): {old!r} is still a {kind} of the design")
        if new in design.parts:
            parts[new] = old
        elif new in design.modules:
            modules[new] = old
        else:
            raise DslError(f"moved({old!r}, {new!r}): {new!r} is not a part or a module of the design")
    return parts, modules


def moves(design: Design) -> Mapping[str, str]:
    """The part aliases of ``moved()``, new component path → old, in path order, with every module alias
    expanded to the parts under the module (``docs/lens.md``, "moved()" and "Module aliases").

    A part alias wins over a module alias for its part, and a longer module path over a shorter one. A
    ``new`` path that is neither a part nor a module, or an ``old`` path that still is one, raises
    ``DslError``: the old part would lose its layout to the new one, so chains are refused too.
    """
    parts, modules = _checked_aliases(design)
    taken = set(parts.values())
    out = dict(parts)
    for path in design.parts:
        if path in out:
            continue
        owners = [new for new in modules if path.startswith(f"{new}/")]
        if not owners:
            continue
        new = max(owners, key=len)
        old = modules[new] + path[len(new) :]
        if old not in taken:
            out[path] = old
    return MappingProxyType(dict(sorted(out.items())))


def module_moves(design: Design) -> Mapping[str, str]:
    """The module aliases of ``moved()``, new module path → old, in path order; the checks of ``moves``
    apply."""
    return MappingProxyType(_checked_aliases(design)[1])


def net_moves(design: Design) -> Mapping[str, str]:
    """The ``moved_net()`` aliases, new net name → old, in name order (``docs/lens.md``, "Net aliases").

    A ``new`` name that is not a net of the design, or an ``old`` name that still is one, raises
    ``DslError``: the old net's copper would move to the new one, so chains are refused too.
    """
    for new, old in sorted(design.net_aliases.items()):
        if new not in design.nets:
            raise DslError(f"moved_net({old!r}, {new!r}): {new!r} is not a net of the design")
        if old in design.nets:
            raise DslError(f"moved_net({old!r}, {new!r}): {old!r} is still a net of the design")
    return MappingProxyType(dict(sorted(design.net_aliases.items())))


__all__ = [
    "BOARD_ORIGIN",
    "DSL_BACKEND",
    "KEYS",
    "PATH_PROPERTY",
    "drawing_sheet_source",
    "fields",
    "pad_zones",
    "key_id",
    "module_moves",
    "moves",
    "net_moves",
    "placements",
    "planes",
    "stackup_locked",
    "to_model",
    "via_protection_locked",
]
