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
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.dsl.design import MINIMUM_KINDS, Design, ImpedanceSpec
from fenolite.dsl.errors import DslError
from fenolite.dsl.items import DimensionSpec, GraphicSpec, TextSpec
from fenolite.dsl.module import Module as DslModule
from fenolite.dsl.part import FieldRequest, PadZoneRequest, Part, Placement, pad_pairs
from fenolite.dsl.shape import ring_box
from fenolite.model.board import (
    Board,
    Dimension,
    Graphic,
    Keepout,
    Outline,
    OutlineArc,
    StackLayer,
    Stackup,
    Text,
    Zone,
)
from fenolite.model.circuit import Circuit, Component, Interface, Module, Net, NetClass, PinRef
from fenolite.model.design import SCHEMA_VERSION, DesignHeader
from fenolite.model.design import Design as ModelDesign
from fenolite.model.findings import Findings
from fenolite.model.manufacturing import Manifest
from fenolite.model.pairs import PAIR_ROLES
from fenolite.model.presentation import SheetFrameRef
from fenolite.model.rules import (
    ImpedanceTarget,
    PadSelection,
    ProximityRule,
    Rule,
    RuleSet,
    Selector,
    TraceGeometry,
)

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
        "rule": ("rul", "rule:<kind>[:<net class>] or rule:named:<rule name>"),
        "area": ("kpo", "area:<area name>"),
        "text": ("txt", "text:<drawing key>"),
        "graphic": ("gfx", "graphic:<drawing key>"),
        "dimension": ("dim", "dimension:<drawing key>"),
        "stackup": ("stk", "stackup"),
        "stack_layer": ("sly", "stack_layer:<k>"),
        "impedance": ("imp", "impedance:<target name>"),
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


def stack_rank(layer: str) -> tuple[int, int]:
    """The place of a copper layer name in stack order: ``F.Cu``, ``In1.Cu`` … ``In<n>.Cu``, ``B.Cu``;
    any other name after them."""
    if layer == "F.Cu":
        return (0, 0)
    if layer.startswith("In") and layer.endswith(".Cu") and layer[2:-3].isdigit():
        return (1, int(layer[2:-3]))
    if layer == "B.Cu":
        return (2, 0)
    return (3, 0)


def _target_classes(design: Design, spec: ImpedanceSpec) -> tuple[str, ...]:
    """The class names a target governs: the named ones, or the class of each pair's two nets."""
    what = f"impedance() {spec.name!r}"
    if spec.netclasses:
        for name in spec.netclasses:
            if name not in design.rules.netclasses:
                raise DslError(f"{what}: netclass {name!r} is not a declared net class")
        return spec.netclasses
    found: list[str] = []
    for itf in spec.pairs:
        roles = PAIR_ROLES[itf.kind]
        nets = [itf.members.get(role) for role in roles]
        classes = sorted({net.netclass for net in nets if net is not None and net.netclass is not None})
        if len(classes) != 1 or any(net is None or net.netclass is None for net in nets):
            held = ", ".join(classes) if classes else "no class"
            raise DslError(
                f"{what}: the nets of the pair {itf.name} must be in one net class, and they are in {held}; "
                "put both nets in the class of the target with design.rules.netclass()"
            )
        if classes[0] not in found:
            found.append(classes[0])
    return tuple(found)


def _impedance(design: Design, taken: set[str]) -> tuple[tuple[ImpedanceTarget, ...], tuple[Rule, ...]]:
    """The targets of ``design.rules.impedance()`` in call order, and the rules derived from them: per
    trace a ``track_width`` rule and, for a pair target, a ``diff_pair_gap`` rule on the trace's layer,
    each with ``min`` = ``opt`` = ``max`` (``docs/impedance.md``; change c0105). ``taken`` holds the names
    of the other rules; a derived name among them raises ``DslError``."""
    targets: list[ImpedanceTarget] = []
    rules: list[Rule] = []
    for spec in design.rules.impedance_targets.values():
        classes = _target_classes(design, spec)
        leaves = tuple(Selector("netclass", name) for name in classes)
        selector = leaves[0] if len(leaves) == 1 else Selector("or", items=leaves)
        traces = sorted(spec.traces, key=lambda t: stack_rank(t.layer))
        kind = "differential" if spec.differential else "single"
        targets.append(
            ImpedanceTarget(
                id=key_id("impedance", spec.name),
                name=spec.name,
                kind=kind,
                netclass_ids=tuple(key_id("netclass", name) for name in classes),
                ohms=spec.ohms,
                tolerance_percent=spec.tolerance,
                layers=tuple(
                    TraceGeometry(t.layer, tuple(sorted(t.refs, key=stack_rank)), t.width, t.gap)
                    for t in traces
                ),
            )
        )
        derived = [("track_width", t.layer, t.width) for t in traces]
        derived += [("diff_pair_gap", t.layer, t.gap) for t in traces if t.gap is not None]
        for rule_kind, layer, value in derived:
            name = f"{rule_kind}_{spec.name}_{layer}"
            if name in taken:
                raise DslError(
                    f"impedance() {spec.name!r}: the derived rule {name!r} is named like another rule"
                )
            taken.add(name)
            rules.append(
                Rule(
                    id=key_id("rule", "named", name),
                    name=name,
                    kind=rule_kind,  # type: ignore[arg-type]
                    selector_a=selector,
                    layers=(layer,),
                    min=value,
                    opt=value,
                    max=value,
                    severity="error",
                    priority=spec.priority,
                )
            )
    return tuple(targets), tuple(rules)


def _selections(design: Design, side: tuple[object, ...], what: str) -> tuple[PadSelection, ...]:
    """The pad selections of one side of a ``near()`` rule: a part gives its path, a ``part.pad()`` its
    path, number and index, and a module one selection per part of it and of its sub-modules, in path
    order. ``DslError`` names a part or a module that is not in the design."""
    from fenolite.dsl.intents import PadRef
    from fenolite.dsl.module import Module
    from fenolite.dsl.part import Part

    def known(part: Part) -> str:
        if design.parts.get(part.path) is not part:
            raise DslError(f"{what}: part {part.ref} is not in the design")
        return part.path

    found: list[PadSelection] = []
    for item in side:
        if isinstance(item, PadRef):
            found.append(PadSelection(known(item.part), item.number, item.index))
        elif isinstance(item, Part):
            found.append(PadSelection(known(item)))
        elif isinstance(item, Module):
            if design.modules.get(item.path) is not item:
                raise DslError(f"{what}: module {item.path} is not in the design")
            prefix = f"{item.path}/"
            paths = sorted(path for path in design.parts if path.startswith(prefix))
            if not paths:
                raise DslError(f"{what}: module {item.path} holds no part")
            found += [PadSelection(path) for path in paths]
    return tuple(dict.fromkeys(found))


def _proximity(design: Design) -> tuple[ProximityRule, ...]:
    """One model rule per ``design.near()`` call, in key order."""
    return tuple(
        ProximityRule(
            name=key,
            parts=_selections(design, spec.parts, f"near() {key!r}: parts"),
            anchor=_selections(design, spec.anchor, f"near() {key!r}: anchor"),
            within=spec.within,
            severity=spec.severity,
        )
        for key, spec in sorted(design.near_rules.items())
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
            diff_pair_width=spec.diff_pair_width,
            diff_pair_gap=spec.diff_pair_gap,
            diff_pair_via_gap=spec.diff_pair_via_gap,
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
    if design.outline_path is not None:
        rings = (design.outline_path, *design.cutout_paths)
        x0, y0 = BOARD_ORIGIN.x, BOARD_ORIGIN.y
        outline = Outline(
            id=key_id("outline"),
            points=rings[0].points,
            cutouts=tuple(ring.points for ring in rings[1:]),
            arcs=tuple(
                OutlineArc(index, edge, mid) for index, ring in enumerate(rings) for edge, mid in ring.arcs
            ),
        )
        # a zone without an outline takes the box of the board ring's vertices and arc mid points
        bx0, by0, bx1, by1 = ring_box(rings[0])
        box = (Point(bx0, by0), Point(bx1, by0), Point(bx1, by1), Point(bx0, by1))
        zones = tuple(
            Zone(
                id=key_id("zone", name),
                outline=(
                    box if spec.outline is None else tuple(Point(x0 + x, y0 + y) for x, y in spec.outline)
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
    plain_rules = _rules(design)
    targets, derived = _impedance(design, {rule.name for rule in plain_rules})
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
            keepouts=_keepouts(design),
            texts=_texts(design),
            graphics=_graphics(design),
            dimensions=_dimensions(design),
            stackup=_stackup(design),
            sheet=_sheet(design),
            title_block=design.block,
            via_protection=design.via_default[0] if design.via_default is not None else None,
        ),
        rules=RuleSet(
            id=key_id("rules"),
            rules=plain_rules + derived,
            severities=dict(sorted(design.rules.severities.items())),
            proximity=_proximity(design),
            heights=tuple(limit for _, limit in sorted(design.height_limits.items())),
            impedance=targets,
        ),
        findings=Findings(waivers=tuple(waiver for _, waiver in sorted(design.waivers.items()))),
        manufacturing=Manifest(id=key_id("manifest")),
    )


SHEET_SUFFIX = ".kicad_wks"


def _at(pair: tuple[int, int]) -> Point:
    return Point(BOARD_ORIGIN.x + pair[0], BOARD_ORIGIN.y + pair[1])


def _keepouts(design: Design) -> tuple[Keepout, ...]:
    """One model keep-out per ``rule_area()``, in name order."""
    return tuple(
        Keepout(
            id=key_id("area", name),
            outline=tuple(_at(p) for p in area.outline),
            layers=area.layers,
            name=name,
            no_tracks="tracks" in area.forbid,
            no_vias="vias" in area.forbid,
            no_pads="pads" in area.forbid,
            no_copper_pour="pours" in area.forbid,
            no_footprints="footprints" in area.forbid,
        )
        for name, area in sorted(design.rule_areas.items())
    )


def _texts(design: Design) -> tuple[Text, ...]:
    out: list[Text] = []
    for key, spec in sorted(design.drawings.items()):
        if not isinstance(spec, TextSpec):
            continue
        words = (spec.justify or "").split()
        out.append(
            Text(
                id=key_id("text", key),
                text=spec.text,
                position=_at(spec.at),
                layer=spec.layer,
                size=Size(spec.size, spec.size),
                thickness=spec.thickness,
                rotation=spec.rotation,
                h_justify=next((w for w in words if w in ("left", "right")), "center"),  # type: ignore[arg-type]
                v_justify=next((w for w in words if w in ("top", "bottom")), "center"),  # type: ignore[arg-type]
            )
        )
    return tuple(out)


def _graphics(design: Design) -> tuple[Graphic, ...]:
    return tuple(
        Graphic(
            id=key_id("graphic", key),
            kind=spec.kind,
            layer=spec.layer,
            points=tuple(_at(p) for p in spec.points),
            width=spec.width,
            filled=spec.fill,
        )
        for key, spec in sorted(design.drawings.items())
        if isinstance(spec, GraphicSpec)
    )


def _dimensions(design: Design) -> tuple[Dimension, ...]:
    return tuple(
        Dimension(
            id=key_id("dimension", key),
            kind=spec.kind,
            layer=spec.layer,
            start=_at(spec.start),
            end=_at(spec.end),
            offset=spec.offset,
            direction=spec.direction,
            units=spec.units,
            precision=spec.precision,
            size=Size(spec.size, spec.size) if spec.size is not None else None,
            thickness=spec.thickness,
            width=spec.width,
        )
        for key, spec in sorted(design.drawings.items())
        if isinstance(spec, DimensionSpec)
    )


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


def heights(design: Design) -> Mapping[str, Nm]:
    """The stated height of each part that has one (``Part(height=…)``), by component path in path order.

    Plain data for the build, which gives each placed footprint a body of that height (change c0140);
    ``to_model`` puts no height into the circuit."""
    return MappingProxyType(
        {path: part.height for path, part in sorted(design.parts.items()) if part.height is not None}
    )


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


def outline_locked(design: Design) -> bool:
    """Whether ``board(…, locked=True)`` was called: the script's outline then replaces an outline edited
    in KiCad on a rebuild (``docs/lens.md``, "Outline changes"). False before ``board()`` is called. The
    lock is a build parameter: the model's ``Outline`` holds no such field."""
    return design.outline_locked


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
    "outline_locked",
    "placements",
    "planes",
    "stackup_locked",
    "to_model",
    "via_protection_locked",
]
