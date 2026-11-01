# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``design.py`` and ``copper.py`` of an import (change c0275, design decisions 4 to 7 and 10).

``emit(source, options)`` is pure: it orders every statement by stable keys (net names, component paths,
item keys, then coordinates), never by file order, dict order or ``PYTHONHASHSEED``, and records in a
``Ledger`` every item it cannot write. Coordinates are written in the frame of ``place()``: the source
point minus ``BOARD_ORIGIN``, so the build writes the source coordinates exactly.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import cast

from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.lowering import MINIMUM_KEYS
from fenolite.backends.kicad.outline import edge_outline
from fenolite.backends.kicad.pcb import OUTLINE_WIDTH
from fenolite.backends.kicad.pro import project_minimums, template
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.importer import coverage
from fenolite.importer.codes import issue
from fenolite.importer.coverage import Ledger, Unexpressed
from fenolite.importer.emit.printer import (
    Call,
    Dct,
    Expr,
    Raw,
    Sub,
    Tup,
    angle,
    area_mm2,
    flat,
    identifier,
    length,
    number,
    statement,
    string,
    text,
)
from fenolite.importer.keys import lock_of, segment
from fenolite.importer.provenance import Provenance
from fenolite.importer.source import Source
from fenolite.importer.tables import ORIGIN, Table, copper_tables, protect_arguments
from fenolite.importer.vendor import natural, vendor
from fenolite.model.board import (
    Board,
    FootprintInstance,
    Graphic,
    Keepout,
    Outline,
    StackLayer,
    Text,
    Zone,
    ZoneSettings,
)
from fenolite.model.design import Design
from fenolite.model.rules import Rule, Selector

COPPER_COUNTS = (2, 4, 6, 8)
NAME = re.compile(r"^[A-Za-z0-9_.+-]+$")
DESIGN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
UNCONNECTED = "unconnected-("
PATH_PROPERTY = "fenolite.path"
SKIPPED_PROPERTIES = frozenset(
    {"reference", "value", "footprint", "datasheet", "description", "sheetfile", "sheetname"}
)
"""Property names (case-folded) that the footprint library or KiCad gives, not the part."""
DRAWING_KINDS = ("silkscreen", "soldermask", "fabrication", "user")
"""The layer kinds a DSL drawing may be on (``dsl.items.DRAWING_LAYER_KINDS``)."""
FORBID = (
    ("tracks", "no_tracks"),
    ("vias", "no_vias"),
    ("pads", "no_pads"),
    ("pours", "no_copper_pour"),
    ("footprints", "no_footprints"),
)
RESERVED = frozenset(
    {
        "design",
        "copper",
        "sheets",
        "n",
        "mm",
        "arc_to",
        "connect",
        "protect",
        "Design",
        "Module",
        "Net",
        "Part",
    }
)
ZONE_DEFAULT = ZoneSettings()
CLASS_FIELDS = (
    "clearance",
    "track_width",
    "via_diameter",
    "via_drill",
    "diff_pair_width",
    "diff_pair_gap",
    "diff_pair_via_gap",
)
"""The lengths of a net class that ``design.rules.netclass()`` takes."""


@dataclass(frozen=True, slots=True)
class Options:
    """The design name, the provenance of the header and the KiCad major of the vendored library."""

    name: str
    provenance: Provenance
    target: int = 10


@dataclass(frozen=True, slots=True)
class Emission:
    """The emitted files by relative path, what was left out, the counts, the module paths, the issues,
    each part key (component path) with its ref, and the refs whose footprint is a variant ``<name>_2``."""

    files: Mapping[str, bytes]
    unexpressed: tuple[Unexpressed, ...]
    counts: Mapping[str, int]
    modules: tuple[str, ...]
    issues: tuple[Issue, ...]
    refs: Mapping[str, str] = field(default_factory=lambda: {})
    variants: tuple[str, ...] = ()


def design_name(seed: str) -> str:
    """``seed`` as a design name (``DESIGN_NAME`` of the DSL)."""
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", seed).strip("_.-") or "imported"
    return name if DESIGN_NAME.fullmatch(name) else f"d{name}"


def _xy(point: Point) -> Tup:
    return Tup((length(point.x - ORIGIN.x), length(point.y - ORIGIN.y)))


def _kinds(board: Board) -> dict[str, str]:
    return {layer.name: layer.kind for layer in board.layers}


def _copper_names(count: int) -> tuple[str, ...]:
    return ("F.Cu", *(f"In{i}.Cu" for i in range(1, count - 1)), "B.Cu")


class _Writer:
    """The statements of ``design.py``, the names it imports and the identifiers it took."""

    def __init__(self) -> None:
        self.sections: list[list[str]] = []
        self.imports: set[str] = {"Design"}
        self.taken: set[str] = set(RESERVED)

    def section(self, statements: Sequence[list[str]]) -> None:
        body = [line for item in statements for line in item]
        if body:
            self.sections.append(body)

    def call(self, func: str, *args: Expr, **kwargs: Expr) -> Call:
        return Call(func, tuple(args), tuple(kwargs.items()))


def _ring_path(points: Sequence[Point], mids: Mapping[int, Point], writer: _Writer) -> Tup:
    """A closed path of ``board(outline=…)`` or ``cutout()``: the vertices, each arc as ``arc_to``."""
    items: list[Expr] = [_xy(points[0])]
    count = len(points)
    for k in range(count):
        end = points[(k + 1) % count]
        if k in mids:
            writer.imports.add("arc_to")
            items.append(Call("arc_to", (_xy(mids[k]), _xy(end))))
        elif k < count - 1:
            items.append(_xy(end))
    return Tup(tuple(items))


def _outline(design: Design) -> Outline | None:
    """The outline of the board's root edge graphics; footprint edges come back with their footprints."""
    board = design.board
    assert board is not None
    bare = dataclasses.replace(design, board=dataclasses.replace(board, footprints=()))
    return edge_outline(bare)


def _losses(board: Board, copper: int, ledger: Ledger) -> None:
    """What a DSL board writes its own way (change c0281): the stroke of its outline (``outline-width``,
    one row per source width that is not ``OUTLINE_WIDTH``) and its non-copper layer table
    (``layer-table``, the names one side holds and the other does not)."""
    kinds = _kinds(board)
    widths: dict[int, int] = {}
    for graphic in board.graphics:
        if kinds.get(graphic.layer) == "edge" and graphic.width != OUTLINE_WIDTH:
            widths[graphic.width] = widths.get(graphic.width, 0) + 1
    for width, count in sorted(widths.items()):
        ledger.add("outline-width", f"{width} nm instead of {OUTLINE_WIDTH} nm", count)
    try:
        written = {layer.name for layer in created_layers(copper) if layer.kind != "copper"}
    except ValueError:
        return  # a copper count no DSL board has is already ``copper-count``
    held = {layer.name for layer in board.layers if layer.kind != "copper"}
    missing, extra = sorted(written - held), sorted(held - written)
    if missing:
        ledger.add("layer-table", "the source lacks " + ", ".join(missing), len(missing))
    if extra:
        ledger.add("layer-table", "the DSL board lacks " + ", ".join(extra), len(extra))


def _board(design: Design, writer: _Writer, ledger: Ledger) -> tuple[list[list[str]], int]:
    board = design.board
    assert board is not None
    copper = sum(1 for layer in board.layers if layer.kind == "copper")
    chosen = next((count for count in COPPER_COUNTS if count >= copper), COPPER_COUNTS[-1])
    if chosen != copper:
        ledger.add("copper-count", f"{copper} copper layers")
    outline = _outline(design)
    out: list[list[str]] = []
    extra: list[tuple[str, Expr]] = [("copper", number(chosen))] if chosen != 2 else []
    if outline is None:
        ledger.add("outline", "no closed board outline on Edge.Cuts")
        xs = [fp.position.x for fp in board.footprints] or [ORIGIN.x]
        ys = [fp.position.y for fp in board.footprints] or [ORIGIN.y]
        width = max(max(xs) - ORIGIN.x, 1_000_000) + 1_000_000
        height = max(max(ys) - ORIGIN.y, 1_000_000) + 1_000_000
        out.append(statement(Call("design.board", (length(width), length(height)), tuple(extra))))
        return out, chosen
    mids: dict[int, dict[int, Point]] = {}
    for arc in outline.arcs:
        mids.setdefault(arc.ring, {})[arc.edge] = arc.mid
    points = outline.points
    xs, ys = sorted({p.x for p in points}), sorted({p.y for p in points})
    corners = {Point(xs[0], ys[0]), Point(xs[-1], ys[0]), Point(xs[-1], ys[-1]), Point(xs[0], ys[-1])}
    rectangle = (
        len(points) == 4 and not mids.get(0) and set(points) == corners and len(xs) == 2 and len(ys) == 2
        and Point(xs[0], ys[0]) == ORIGIN
    )  # fmt: skip
    if rectangle:
        size = (length(xs[-1] - xs[0]), length(ys[-1] - ys[0]))
        out.append(statement(Call("design.board", size, tuple(extra))))
    else:
        ring = _ring_path(points, mids.get(0, {}), writer)
        out.append(statement(Call("design.board", (), (("outline", ring), *extra))))
    for index, cut in enumerate(outline.cutouts, start=1):
        out.append(statement(Call("design.cutout", (_ring_path(cut, mids.get(index, {}), writer),))))
    return out, chosen


_PLAIN = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


def _stack_entry(layer: StackLayer) -> tuple[str, int | None, dict[str, str]] | None:
    """The ``fenolite.dsl.stack`` function, thickness and text arguments of one stack-up row; ``None`` for
    a row the DSL cannot say."""
    extras: dict[str, str] = {}
    if layer.material:
        extras["material"] = layer.material
    for name in ("epsilon_r", "loss_tangent"):
        value: str = getattr(layer, name)
        if value:
            if not _PLAIN.fullmatch(value):
                return None
            extras[name] = value
    if layer.color:
        extras["color"] = layer.color
    if layer.kind == "silkscreen":
        if layer.thickness:
            return None
        return "silkscreen", None, {k: v for k, v in extras.items() if k == "color"}
    if layer.kind == "soldermask":
        return "mask", layer.thickness, extras
    if layer.kind == "copper":
        return ("copper", layer.thickness, extras) if not extras and layer.thickness > 0 else None
    if layer.kind == "dielectric" and layer.thickness > 0:
        return ("prepreg" if layer.dielectric_kind == "prepreg" else "core"), layer.thickness, extras
    return None


def _stackup(board: Board, copper: int, writer: _Writer, ledger: Ledger) -> list[list[str]]:
    """``design.stackup()`` of the board's stack-up, checked by the DSL itself before it is written; a
    paste row without values is KiCad's own, which the build writes again."""
    stackup = board.stackup
    if stackup is None or not stackup.layers:
        return []
    from fenolite.dsl import stack as dsl_stack
    from fenolite.dsl.design import Design as DslDesign
    from fenolite.dsl.errors import DslError
    from fenolite.dsl.units import Length

    rows: list[tuple[str, int | None, dict[str, str]]] = []
    for layer in stackup.layers:
        if layer.kind == "solderpaste" and not (layer.thickness or layer.material or layer.color):
            continue
        made = _stack_entry(layer)
        if made is None:
            ledger.add("stackup", f"{layer.name} ({layer.kind})")
            return []
        if layer.kind == "silkscreen":
            for name in ("material", "epsilon_r", "loss_tangent"):
                if getattr(layer, name):
                    ledger.add("stackup-field", f"{layer.name} {name}")
        rows.append(made)
    probe = DslDesign("probe")
    probe.board(Length(1_000_000), Length(1_000_000), copper=copper)
    try:
        probe.stackup(
            *(
                getattr(dsl_stack, kind)(*(() if thick is None else (Length(thick),)), **extras)
                for kind, thick, extras in rows
            ),
            finish=stackup.finish or None,
            impedance_controlled=stackup.impedance_controlled,
        )
    except DslError as error:
        ledger.add("stackup", str(error)[:80])
        return []
    calls = tuple(
        Call(
            f"stack.{kind}",
            () if thick is None else (length(thick),),
            tuple((name, text(value)) for name, value in extras.items()),
        )
        for kind, thick, extras in rows
    )
    kwargs: list[tuple[str, Expr]] = []
    if stackup.finish:
        kwargs.append(("finish", text(stackup.finish)))
    if stackup.impedance_controlled:
        kwargs.append(("impedance_controlled", Raw("True")))
    writer.imports.add("stack")
    return [statement(Call("design.stackup", calls, tuple(kwargs)))]


TITLE_FIELDS = ("title", "date", "revision", "organization", "doc_id", "responsible", "approver")


def _title_block(board: Board, ledger: Ledger) -> list[list[str]]:
    """``design.title_block()`` of the board's title block, checked by the DSL before it is written."""
    block = board.title_block
    if block is None:
        return []
    from fenolite.dsl.design import Design as DslDesign
    from fenolite.dsl.errors import DslError

    given = {name: getattr(block, name) for name in TITLE_FIELDS if getattr(block, name)}
    try:
        DslDesign("probe").title_block(**given, variables=dict(block.params))
    except DslError as error:
        ledger.add("title-block", str(error)[:80])
        return []
    kwargs: list[tuple[str, Expr]] = [(name, text(value)) for name, value in given.items()]
    if block.params:
        kwargs.append(("variables", Dct(tuple((k, text(v)) for k, v in sorted(block.params.items())))))
    return [statement(Call("design.title_block", (), tuple(kwargs)))] if kwargs else []


def _path_of(design: Design, component_id: str, ref: str, sheet: str) -> tuple[str, ...]:
    """The component path of a part: its ``fenolite.path`` (a board built by Fenolite), else the KiCad sheet
    path of its footprint (``sheetname``, ``/power/ch1/``) with its ref, else its ref alone."""
    component = next((c for c in design.circuit.components if c.id == component_id), None)
    path = component.properties.get(PATH_PROPERTY, "") if component is not None else ""
    segments = tuple(path.split("/")) if path else ()
    if segments and all(NAME.fullmatch(s) for s in segments):
        return segments
    return (*(module_name(part) for part in sheet.split("/") if part), ref)


def module_name(sheet: str) -> str:
    """A KiCad sheet name as a module name: lower case, ``[a-z0-9_]``."""
    return re.sub(r"[^a-z0-9_]+", "_", sheet.lower()).strip("_") or "sheet"


def _sheet_names(board: Board, text: str) -> dict[str, str]:
    """The ``sheetname`` of each footprint of the board read from ``text``, by footprint id."""
    from fenolite.backends.kicad.sexpr import parse

    root = parse(text) if text else None
    nodes = root.nodes("footprint") if root is not None else ()
    found: dict[str, str] = {}
    for footprint in board.footprints:
        locator = footprint.provenance.locator if footprint.provenance is not None else ""
        match = re.fullmatch(r"/kicad_pcb/footprint\[(\d+)\]", locator)
        if match is None or int(match.group(1)) >= len(nodes):
            continue
        child = nodes[int(match.group(1))].find("sheetname")
        atoms = child.atoms() if child is not None else ()
        if atoms and atoms[0].value.strip("/"):
            found[footprint.id] = atoms[0].value
    return found


def _properties(properties: Mapping[str, str]) -> Dct | None:
    kept = {
        name: value
        for name, value in properties.items()
        if name.casefold() not in SKIPPED_PROPERTIES
        and not name.casefold().startswith(("fenolite.", "ki_"))
        and name == name.strip()
        and name.isprintable()
        and value.isprintable()
        and name
    }
    return Dct(tuple((name, text(value)) for name, value in sorted(kept.items()))) if kept else None


MINIMUM_KINDS = ("clearance", "track_width", "via_diameter", "via_drill", "hole_size", "edge_clearance")
"""The keywords of ``design.rules.minimum()``, in its order."""


def _minimum_of(rule: Rule, classes: set[str]) -> tuple[str | None, str] | None:
    """The scope (``None`` for the board, else a class name) and keyword of a custom rule that is a plain
    minimum ``design.rules.minimum()`` writes; ``None`` for any other rule."""
    if rule.min is None or rule.max is not None or rule.opt is not None or rule.selector_b is not None:
        return None
    if rule.layers or rule.severity != "error":
        return None
    selector = rule.selector_a
    kind = str(rule.kind)
    if selector.op == "item_kind" and selector.value == "via" and kind == "hole_size":
        return None, "via_drill"
    if kind not in MINIMUM_KINDS or kind == "via_drill":
        return None
    if selector.op == "all":
        return None, kind
    if selector.op == "netclass" and selector.value in classes:
        return selector.value, kind
    return None


SELECT_ITEMS = ("track", "via", "pad", "zone")
"""The item kinds ``select.item()`` takes."""
_WRITTEN_NAME = re.compile(r"^fenolite_\d+_(.+)$")
_PRECEDENCE = {"or": 1, "and": 2, "not": 3}


def _selector(selector: Selector, classes: set[str], parent: int = 0) -> str | None:
    """The ``fenolite.dsl.select`` expression of a model selector; ``None`` for one the DSL cannot write
    (a layer leaf, an undeclared class, an item kind ``select.item()`` does not take)."""
    op, value = selector.op, selector.value
    if op == "all":
        return "select.ALL" if parent == 0 else None
    leaf = {"net": "net", "netclass": "netclass", "ref": "ref", "area": "area", "diff_pair": "pair"}
    if op in leaf:
        if op == "netclass" and value != "Default" and "*" not in value and value not in classes:
            return None
        return f"select.{leaf[op]}({string(value)})" if value else None
    if op == "item_kind":
        return f"select.item({string(value)})" if value in SELECT_ITEMS else None
    if op in ("and", "or", "not"):
        rank = _PRECEDENCE[op]
        parts = [_selector(item, classes, rank) for item in selector.items]
        if any(part is None for part in parts) or not parts:
            return None
        if op == "not":
            return f"~{parts[0]}" if len(parts) == 1 else None
        text = f" {'&' if op == 'and' else '|'} ".join(cast(list[str], parts))
        return f"({text})" if parent > rank else text
    return None


def _rule_call(rule: Rule, classes: set[str], taken: set[str]) -> Call | None:
    """``design.rules.rule()`` of a custom rule, or ``None`` when its selectors cannot be written."""
    where = _selector(rule.selector_a, classes)
    between = None if rule.selector_b is None else _selector(rule.selector_b, classes)
    if where is None or (rule.selector_b is not None and between is None):
        return None
    match = _WRITTEN_NAME.match(rule.name)
    name = match.group(1) if match and match.group(1) not in taken else rule.name
    if name in taken:
        return None
    taken.add(name)
    kwargs: list[tuple[str, Expr]] = []
    if where != "select.ALL":
        kwargs.append(("where", Raw(where)))
    if between is not None:
        kwargs.append(("between", Raw(between)))
    if rule.layers:
        kwargs.append(("layers", Tup(tuple(text(layer) for layer in rule.layers))))
    for label in ("min", "opt", "max"):
        value = getattr(rule, label)
        if value is not None:
            kwargs.append((label, length(value)))
    if rule.severity != "error":
        kwargs.append(("severity", text(rule.severity)))
    if rule.priority:
        kwargs.append(("priority", number(rule.priority)))
    return Call("design.rules.rule", (text(name), text(str(rule.kind))), tuple(kwargs))


def _minimums(source: Source, classes: set[str], ledger: Ledger, writer: _Writer) -> list[list[str]]:
    """``design.rules.minimum()`` calls: the custom rules that are plain minimums, then the project's
    board-setup minimums that differ from a new project's and that no rule gave; then a
    ``design.rules.rule()`` call for each other custom rule the DSL can write."""
    scopes: dict[str | None, dict[str, int]] = {}
    others: list[Call] = []
    taken: set[str] = set()
    for rule in source.custom_rules:
        found = _minimum_of(rule, classes)
        if found is None or found[1] in scopes.get(found[0], {}):
            made = _rule_call(rule, classes, taken)
            if made is None:
                ledger.add("custom-rule", rule.name)
            else:
                others.append(made)
            continue
        scopes.setdefault(found[0], {})[found[1]] = cast(int, rule.min)
    if source.major in MINIMUM_KEYS:
        fresh = project_minimums(template(source.major))
        board = scopes.setdefault(None, {})
        for kind, key in MINIMUM_KEYS[source.major].items():
            value = source.minimums.get(key)
            if value is not None and value != fresh.get(key) and value > 0 and kind not in board:
                board[kind] = value
    out: list[list[str]] = []
    for scope in sorted(scopes, key=lambda name: (name is not None, name or "")):
        values = scopes[scope]
        given: list[tuple[str, Expr]] = [
            (kind, length(values[kind])) for kind in MINIMUM_KINDS if kind in values
        ]
        if scope is not None:
            given.append(("netclass", text(scope)))
        if values:
            out.append(statement(Call("design.rules.minimum", (), tuple(given))))
    if any("select." in flat(call) for call in others):
        writer.imports.add("select")
    out += [statement(call) for call in others]
    return out


def _zone_args(zone: Zone, ledger: Ledger) -> list[tuple[str, Expr]]:
    settings = zone.settings
    out: list[tuple[str, Expr]] = []
    if zone.priority:
        out.append(("priority", number(zone.priority)))
    for name in ("clearance", "min_thickness", "thermal_gap", "thermal_spoke_width"):
        value = getattr(settings, name)
        if value != getattr(ZONE_DEFAULT, name):
            out.append((name, length(value)))
    if settings.connection != ZONE_DEFAULT.connection:
        out.append(("connection", text(settings.connection)))
    if settings.island_removal != ZONE_DEFAULT.island_removal:
        out.append(("islands", text(settings.island_removal)))
        if settings.island_removal == "below_area":
            out.append(("min_island_area", area_mm2(settings.min_island_area)))
    unsaid = (
        settings.smoothing != ZONE_DEFAULT.smoothing
        or settings.smoothing_radius != ZONE_DEFAULT.smoothing_radius
        or settings.fill_mode != ZONE_DEFAULT.fill_mode
        or settings.hatch != ZONE_DEFAULT.hatch
    )
    if unsaid:
        ledger.add("zone-setting", zone.name or zone.id)
    if zone.locked:
        out.append(("locked", Raw("True")))
    return out


def _zones(
    board: Board, names: Mapping[str, str], nets: Mapping[str, str], layers: Sequence[str], ledger: Ledger
) -> list[list[str]]:
    out: list[list[str]] = []
    named: set[str] = set()
    keys: set[str] = set()
    counters: dict[str, int] = {}

    def order(zone: Zone) -> tuple[object, ...]:
        net = names.get(zone.net_id or "", "")
        return (net, zone.name, zone.layers, tuple((p.x, p.y) for p in zone.outline), zone.priority)

    for zone in sorted(board.zones, key=order):
        net = names.get(zone.net_id or "")
        where = zone.name or net or zone.id
        if not zone.layers or any(layer not in layers for layer in zone.layers):
            ledger.add("zone-layer", where)
            continue
        if len(zone.outline) < 3:
            ledger.add("zone-outline", where)
            continue
        args: list[tuple[str, Expr]] = [("layers", Tup(tuple(text(layer) for layer in zone.layers)))]
        if net is not None and zone.name == net and net not in named and net not in keys:
            named.add(net)
            keys.add(net)
        elif (
            zone.name and zone.name == zone.name.strip() and zone.name not in named and zone.name not in keys
        ):
            named.add(zone.name)
            keys.add(zone.name)
            args.append(("name", text(zone.name)))
        else:
            if zone.name:
                ledger.add("zone-name", zone.name)
            stem = segment(net) if net is not None else "zone"
            index = counters.get(stem, 0) + 1
            while f"{stem}/{index}" in keys:
                index += 1
            counters[stem] = index
            keys.add(f"{stem}/{index}")
            args.append(("key", text(f"{stem}/{index}")))
        args.append(("outline", Tup(tuple(_xy(p) for p in zone.outline))))
        args += _zone_args(zone, ledger)
        target: Expr = Raw(nets[net]) if net is not None else Raw("None")
        out.append(statement(Call("design.zone", (target,), tuple(args))))
    return out


def _areas(board: Board, layers: Sequence[str], ledger: Ledger) -> list[list[str]]:
    out: list[list[str]] = []
    names: set[str] = set()
    index = 0

    def order(area: Keepout) -> tuple[object, ...]:
        return (area.name, area.layers, tuple((p.x, p.y) for p in area.outline))

    for area in sorted(board.keepouts, key=order):
        if any(layer not in layers for layer in area.layers) or len(area.outline) < 3:
            ledger.add("rule-area-layer", area.name or area.id)
            continue
        args: list[tuple[str, Expr]] = []
        if area.name and NAME.fullmatch(area.name) and area.name.casefold() not in names:
            names.add(area.name.casefold())
            first: Expr = text(area.name)
        else:
            if area.name:
                ledger.add("rule-area-name", area.name)
            index += 1
            first = text("")
            args.append(("key", text(f"area/{index}")))
        if area.layers and tuple(area.layers) != tuple(layers):
            args.insert(0, ("layers", Tup(tuple(text(layer) for layer in area.layers))))
        forbid = tuple(text(word) for word, flag in FORBID if getattr(area, flag))
        if forbid:
            args.insert(
                1 if area.layers and tuple(area.layers) != tuple(layers) else 0, ("forbid", Tup(forbid))
            )
        ring = Tup(tuple(_xy(p) for p in area.outline))
        out.append(statement(Call("design.rule_area", (first, ring), tuple(args))))
    return out


def _graphic(graphic: Graphic, key: str) -> Call | None:
    points = graphic.points
    if graphic.width < 0:
        return None
    width = length(graphic.width)
    fill = (("fill", Raw("True")),) if graphic.filled else ()
    layer = ("layer", text(graphic.layer))
    if graphic.kind == "line" and len(points) == 2 and points[0] != points[1] and graphic.width > 0:
        return Call("design.line", (text(key), _xy(points[0]), _xy(points[1])), (layer, ("width", width)))
    if graphic.kind in ("rect", "circle") and len(points) == 2 and (graphic.width > 0 or graphic.filled):
        a, b = points
        if graphic.kind == "rect" and (a.x == b.x or a.y == b.y):
            return None
        if graphic.kind == "circle" and a == b:
            return None
        return Call(f"design.{graphic.kind}", (text(key), _xy(a), _xy(b)), (layer, ("width", width), *fill))
    if graphic.kind == "arc" and len(points) == 3 and graphic.width > 0:
        a, m, b = points
        if (m.x - a.x) * (b.y - a.y) == (m.y - a.y) * (b.x - a.x):
            return None
        return Call("design.arc", (text(key), _xy(a), _xy(m), _xy(b)), (layer, ("width", width)))
    if graphic.kind == "polygon" and len(points) >= 3 and (graphic.width > 0 or graphic.filled):
        ring = Tup(tuple(_xy(p) for p in points))
        return Call("design.polygon", (text(key), ring), (layer, ("width", width), *fill))
    return None


def _text(item: Text, key: str) -> Call | None:
    if not item.text or not item.text.isprintable() or item.size.w != item.size.h:
        return None
    if item.size.w <= 0 or item.thickness <= 0:
        return None
    words = [w for w in (item.h_justify, item.v_justify) if w != "center"]
    kwargs: list[tuple[str, Expr]] = [
        ("layer", text(item.layer)),
        ("size", length(item.size.w)),
        ("thickness", length(item.thickness)),
    ]
    if item.rotation:
        kwargs.append(("rot", angle(item.rotation)))
    if words:
        kwargs.append(("justify", text(" ".join(words))))
    return Call("design.text", (text(key), text(item.text), _xy(item.position)), tuple(kwargs))


def _drawings(board: Board, ledger: Ledger) -> list[list[str]]:
    from fenolite.dsl.items import BOARD_LAYER_KINDS

    # a DSL board holds the standard layers only: a drawing on another user layer cannot be written
    kinds = {
        name: kind
        for name, kind in _kinds(board).items()
        if name in BOARD_LAYER_KINDS or kind in ("edge", "copper")
    }
    out: list[list[str]] = []
    counters: dict[tuple[str, str], int] = {}

    def gkey(graphic: Graphic) -> tuple[object, ...]:
        return (graphic.layer, graphic.kind, tuple((p.x, p.y) for p in graphic.points), graphic.width)

    for graphic in sorted(board.graphics, key=gkey):
        kind = kinds.get(graphic.layer, "")
        if kind == "edge":
            continue
        if kind not in DRAWING_KINDS:
            ledger.add(
                "copper-drawing" if kind == "copper" else "drawing-layer",
                f"{graphic.kind} on {graphic.layer}",
            )
            continue
        slot = (graphic.layer, graphic.kind)
        counters[slot] = counters.get(slot, 0) + 1
        made = _graphic(graphic, f"{segment(graphic.layer)}/{graphic.kind}/{counters[slot]}")
        if made is None:
            ledger.add("drawing", f"{graphic.kind} on {graphic.layer}")
            continue
        out.append(statement(made))

    def tkey(item: Text) -> tuple[object, ...]:
        return (item.layer, item.position.x, item.position.y, item.text)

    for item in sorted(board.texts, key=tkey):
        kind = kinds.get(item.layer, "")
        if kind not in DRAWING_KINDS:
            ledger.add("text-layer", f"text on {item.layer}")
            continue
        slot = (item.layer, "text")
        counters[slot] = counters.get(slot, 0) + 1
        made = _text(item, f"{segment(item.layer)}/text/{counters[slot]}")
        if made is None:
            ledger.add("text", item.text[:40])
            continue
        out.append(statement(made))
    return out


def _copper_file(tables: Sequence[Table], header: Sequence[str]) -> str:
    imports = {"Design", "Net", "mm"}
    body: list[str] = []
    for table in tables:
        net = Sub("n", text(table.net))
        rows = Tup(tuple(Tup(tuple(number(v) for v in row)) for row in table.rows))
        args: list[tuple[str, Expr]] = [("net", net)]
        if table.kind == "via":
            args += [("diameter", length(table.diameter)), ("drill", length(table.drill)), ("rows_nm", rows)]
            if table.via_kind != "through":
                args.append(("kind", text(table.via_kind)))
                assert table.layers is not None
                args.append(("layers", Tup(tuple(text(layer) for layer in table.layers))))
            said = protect_arguments(table.protection)
            if said:
                imports.add("protect")
                values = tuple((name, Raw("True" if v is True else "False" if v is False else string(str(v))))
                               for name, v in said)  # fmt: skip
                args.append(("protection", Call("protect", (), values)))
        else:
            args += [("layer", text(table.layer)), ("width", length(table.width)), ("rows_nm", rows)]
        if table.locked:
            args.append(("locked", Raw("True")))
        body += statement(Call(f"design.{table.kind}_table", (text(table.key),), tuple(args)), 1)
    lines = [
        *header,
        "",
        f"from fenolite.dsl import {', '.join(sorted(imports, key=lambda n: (n[0].islower(), n)))}",
        "",
        "",
        "def apply(design: Design, n: dict[str, Net]) -> None:",
        '    """The tracks, arcs and vias of the board, as tables of rows in nanometres."""',
        *body,
    ]
    return "\n".join(lines) + "\n"


def emit(source: Source, options: Options) -> Emission:
    """The files of the Fenolite project folder of ``source``."""
    design = source.design
    board = design.board
    if board is None:
        raise ValueError("the source holds no board")
    ledger = Ledger()
    issues: list[Issue] = []
    writer = _Writer()
    header = options.provenance.header()
    board_lines, copper_count = _board(design, writer, ledger)
    if source.backend == "kicad":
        # an Altium document's outline and layers are those of its in-memory conversion, not of its author
        assert design.board is not None
        _losses(design.board, copper_count, ledger)
    board_lines += _stackup(board, copper_count, writer, ledger)
    board_lines += _title_block(board, ledger)
    layers = _copper_names(copper_count)
    names = {net.id: net.name for net in design.circuit.nets}
    refs = {c.id: c.ref for c in design.circuit.components}
    vendored = vendor(design, source.board_text, target=options.target)
    issues += vendored.issues
    tables = copper_tables(board, names)
    for kind, count in tables.left_out.items():
        ledger.add(kind, count=count)
    kept_tables: list[Table] = []
    for table in tables.tables:
        if table.kind != "via" and table.layer not in layers:
            ledger.add("copper-layer", table.layer, count=len(table.rows))
            continue
        if table.layers is not None and any(layer not in layers for layer in table.layers):
            ledger.add("copper-layer", "-".join(table.layers), count=len(table.rows))
            continue
        kept_tables.append(table)
    # the footprints the code writes: one per ref, a ref the DSL takes, a footprint the library derived
    placed: list[FootprintInstance] = []
    taken_refs: set[str] = set()
    for footprint in sorted(board.footprints, key=lambda fp: (natural(refs.get(fp.component_id, "")), fp.id)):
        ref = refs.get(footprint.component_id, "")
        if not NAME.fullmatch(ref):
            ledger.add("footprint-ref", ref or footprint.lib_ref)
        elif ref in taken_refs:
            ledger.add("duplicate-ref", ref)
        elif ref not in vendored.footprints:
            ledger.add("footprint", ref)
        else:
            taken_refs.add(ref)
            placed.append(footprint)
    # pads by net
    members: dict[str, dict[tuple[str, str], None]] = {}
    seen: dict[tuple[str, str], str] = {}
    for footprint in placed:
        ref = refs[footprint.component_id]
        for pad in footprint.pads:
            net = names.get(pad.net_id or "")
            if net is None:
                continue
            if not pad.number:
                ledger.add("pad-net-unnumbered", f"{ref} on {net}")
                continue
            other = seen.get((ref, pad.number))
            if other is not None and other != net:
                ledger.add("pad-net-conflict", f"{ref}.{pad.number}")
                continue
            seen[(ref, pad.number)] = net
            members.setdefault(net, {})[(ref, pad.number)] = None
    used_nets = {net for net, pins in members.items() if not (len(pins) == 1 and net.startswith(UNCONNECTED))}
    used_nets |= {table.net for table in kept_tables}
    used_nets |= {names[z.net_id] for z in board.zones if z.net_id in names}
    net_vars: dict[str, str] = {}
    net_lines: list[list[str]] = []
    for net in sorted(used_nets):
        var = identifier(net, writer.taken, prefix="net")
        net_vars[net] = var
        net_lines.append(statement(Call("Net", (text(net),)), target=var))
    if net_vars:
        writer.imports.add("Net")
    # net classes
    class_lines: list[list[str]] = []
    by_class: dict[str, list[str]] = {}
    for net in design.circuit.nets:
        if net.netclass_id is not None and net.name in net_vars:
            by_class.setdefault(net.netclass_id, []).append(net.name)
    for cls in sorted(design.circuit.netclasses, key=lambda c: c.name):
        if cls.name == "Default":
            continue
        kwargs: list[tuple[str, Expr]] = []
        for name in CLASS_FIELDS:
            value = getattr(cls, name)
            if value is not None:
                kwargs.append((name, length(value)))
        listed = sorted(by_class.get(cls.id, ()))
        kwargs.append(("nets", Tup(tuple(Raw(net_vars[n]) for n in listed))))
        class_lines.append(statement(Call("design.rules.netclass", (text(cls.name),), tuple(kwargs))))
    declared = {cls.name for cls in design.circuit.netclasses if cls.name != "Default"}
    class_lines += _minimums(source, declared, ledger, writer)
    # parts
    part_lines: list[list[str]] = []
    place_lines: list[list[str]] = []
    part_vars: dict[str, str] = {}
    lock_refs: dict[str, str] = {}
    containers: dict[tuple[str, ...], list[str]] = {(): []}
    module_vars: dict[tuple[str, ...], str] = {}
    module_lines: list[list[str]] = []
    footprints = placed
    components = {c.id: c for c in design.circuit.components}
    paths: dict[str, tuple[str, ...]] = {}
    sheets = _sheet_names(board, source.board_text)
    renamed: dict[str, str] = {}
    for footprint in footprints:
        ref = refs[footprint.component_id]
        sheet = sheets.get(footprint.id, "")
        paths[ref] = _path_of(design, footprint.component_id, ref, sheet)
        for part in (p for p in sheet.split("/") if p):
            if module_name(part) != part:
                renamed[part] = module_name(part)
    for sheet, module in sorted(renamed.items()):
        issues.append(
            issue("import.sheet-renamed", f"the sheet {sheet!r} is the module {module!r}", where=sheet)
        )
    taken_paths: set[tuple[str, ...]] = set()
    for footprint in sorted(
        footprints, key=lambda fp: tuple(natural(s) for s in paths[refs[fp.component_id]])
    ):
        ref = refs[footprint.component_id]
        path = paths[ref]
        if path in taken_paths:
            path = (ref,)
        taken_paths.add(path)
        component = components[footprint.component_id]
        var = identifier(ref, writer.taken, prefix="p")
        part_vars[ref] = var
        lock_refs["/".join(path)] = ref
        lib_id = vendored.footprints[ref]
        kwargs = [("footprint", text(lib_id))]
        if component.value:
            kwargs.append(("value", text(component.value)))
        if path[-1] != ref:
            kwargs.append(("name", text(path[-1])))
        props = _properties(component.properties)
        if props is not None:
            kwargs.append(("properties", props))
        part_lines.append(
            statement(Call("Part", (text(ref), text(vendored.symbols[ref])), tuple(kwargs)), target=var)
        )
        for depth in range(1, len(path)):
            prefix = path[:depth]
            if prefix not in module_vars:
                mvar = identifier("_".join(prefix), writer.taken, prefix="m")
                module_vars[prefix] = mvar
                module_lines.append(statement(Call("Module", (text(prefix[-1]),)), target=mvar))
                containers.setdefault(prefix[:-1], []).append(mvar)
                containers[prefix] = []
        containers[path[:-1]].append(var)
        at = footprint.position
        place: list[tuple[str, Expr]] = []
        if footprint.rotation:
            place.append(("rot", angle(footprint.rotation)))
        if footprint.side == "bottom":
            place.append(("side", text("bottom")))
        if footprint.locked:
            place.append(("locked", Raw("True")))
        xy = (length(at.x - ORIGIN.x), length(at.y - ORIGIN.y))
        place_lines.append(statement(Call(f"{var}.place", xy, tuple(place))))
    if part_vars:
        writer.imports.add("Part")
    if module_vars:
        writer.imports.add("Module")
    add_lines: list[list[str]] = []
    for prefix in sorted(module_vars, key=lambda p: (-len(p), p)):
        held = containers.get(prefix, [])
        if held:
            add_lines.append(statement(Call(f"{module_vars[prefix]}.add", tuple(Raw(v) for v in held))))
    if containers[()]:
        add_lines.append(statement(Call("design.add", tuple(Raw(v) for v in containers[()]))))
    connect_lines: list[list[str]] = []
    for net in sorted(members):
        if net not in net_vars:
            continue
        pins = sorted(members[net], key=lambda item: (natural(item[0]), natural(item[1])))
        handles = tuple(Sub(part_vars[r], text(p)) for r, p in pins if r in part_vars)
        if handles:
            connect_lines.append(statement(Call("connect", (Raw(net_vars[net]), *handles))))
    if connect_lines:
        writer.imports.add("connect")
    zone_lines = _zones(board, names, net_vars, layers, ledger)
    area_lines = _areas(board, layers, ledger)
    drawing_lines = _drawings(board, ledger)
    coverage.scan(design, ledger)
    files: dict[str, str] = dict(vendored.files)
    copper_line: list[list[str]] = []
    if kept_tables:
        files["copper.py"] = _copper_file(kept_tables, header)
        mapping = Dct(tuple((net, Raw(var)) for net, var in sorted(net_vars.items())))
        copper_line.append(statement(Call("copper.apply", (Raw("design"), mapping))))
    if any("mm(" in line for section in (board_lines, class_lines, place_lines, zone_lines, area_lines,
                                         drawing_lines) for item in section for line in item):  # fmt: skip
        writer.imports.add("mm")
    for block in (
        [statement(Call("Design", (text(options.name),)), target="design")],
        board_lines,
        net_lines,
        class_lines,
        part_lines,
        module_lines,
        add_lines,
        connect_lines,
        place_lines,
        zone_lines,
        area_lines,
        drawing_lines,
        copper_line,
    ):
        writer.section(block)
    imports = sorted(writer.imports, key=lambda name: (name[0].islower(), name))
    lines = [*header, ""]
    if kept_tables:
        lines.append("import copper")
    lines.append(f"from fenolite.dsl import {', '.join(imports)}")
    for body in writer.sections:
        lines += ["", *body]
    files["design.py"] = "\n".join(lines) + "\n"
    files["design.lock"] = lock_of(options.name, lock_refs)
    rows = ledger.rows()
    counts = {
        "parts": len(part_vars),
        "nets": len(net_vars),
        "tracks": sum(len(t.rows) for t in kept_tables if t.kind == "track"),
        "arcs": sum(len(t.rows) for t in kept_tables if t.kind == "arc"),
        "vias": sum(len(t.rows) for t in kept_tables if t.kind == "via"),
        "zones": len(zone_lines),
        "rule_areas": len(area_lines),
        "drawings": len(drawing_lines),
        "tables": len(kept_tables),
    }
    if vendored.symbols:
        issues.append(
            issue(
                "import.symbol-regenerated",
                f"{len({*vendored.symbols.values()})} symbol(s) drawn by Fenolite from the pad numbers of "
                "their footprints",
                where="lib",
            )
        )
    return Emission(
        files={path: body.encode("utf-8") for path, body in sorted(files.items())},
        unexpressed=rows,
        counts=counts,
        modules=tuple("/".join(p) for p in sorted(module_vars)),
        issues=tuple(issues),
        refs=dict(sorted(lock_refs.items())),
        variants=vendored.variants,
    )


__all__ = ["Emission", "Options", "design_name", "emit"]
