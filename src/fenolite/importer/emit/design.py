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
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import cast

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.lowering import MINIMUM_KEYS
from fenolite.backends.kicad.outline import edge_outline
from fenolite.backends.kicad.pro import project_minimums, template
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
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
from fenolite.importer.tables import (
    ORIGIN,
    Table,
    copper_tables,
    has_teardrops,
    protect_arguments,
    teardrop_arguments,
)
from fenolite.importer.texts import area_placement, dimension_style, graphic_net, text_style, zone_arc_ring
from fenolite.importer.vendor import natural, vendor
from fenolite.model.base import Entity, Opaque
from fenolite.model.board import (
    Board,
    Dimension,
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


def net_numbers(design: Design) -> dict[int, str]:
    """Each number of the source's net table and the name of its net, as the KiCad reader keeps them in the
    nets' ``kicad`` bags (a KiCad 9 board numbers its nets; change c0277)."""
    found: dict[int, str] = {}
    for net in design.circuit.nets:
        bag = net.ext.get("kicad")
        number = dict(bag.payload).get("number", "") if bag is not None else ""
        if number.isdigit():
            found[int(number)] = net.name
    return found


def _kinds(board: Board) -> dict[str, str]:
    return {layer.name: layer.kind for layer in board.layers}


_USER = re.compile(r"^User\.([1-9][0-9]*)$")


def user_layers(board: Board) -> tuple[int, dict[str, str]]:
    """The user layers the code declares for ``board`` (change c0277): ``User.1`` up to the highest
    ``User.<k>`` of its table (45 at most), and the user name each of them has there."""
    count = 0
    names: dict[str, str] = {}
    for layer in board.layers:
        found = _USER.fullmatch(layer.name)
        if found is None or int(found.group(1)) > 45:
            continue
        count = max(count, int(found.group(1)))
        bag = layer.ext.get("kicad")
        alias = dict(bag.payload).get("user_name", "") if bag is not None else ""
        if alias and alias != layer.name:
            names[layer.name] = alias
    return count, names


def _user_lines(board: Board) -> list[list[str]]:
    count, names = user_layers(board)
    if not count:
        return []
    kwargs: tuple[tuple[str, Expr], ...] = ()
    if names:
        ordered = sorted(names.items(), key=lambda item: natural(item[0]))
        kwargs = (("names", Dct(tuple((name, text(alias)) for name, alias in ordered))),)
    return [statement(Call("design.user_layers", (number(count),), kwargs))]


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
        if "epsilon_r" in extras or "loss_tangent" in extras:
            return None
        return "silkscreen", None, extras
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
    if settings.smoothing != ZONE_DEFAULT.smoothing:
        out.append(("smoothing", text(settings.smoothing)))  # change c0277
        if settings.smoothing_radius != ZONE_DEFAULT.smoothing_radius:
            out.append(("smoothing_radius", length(settings.smoothing_radius)))
    unsaid = (
        (
            settings.smoothing == ZONE_DEFAULT.smoothing
            and settings.smoothing_radius != ZONE_DEFAULT.smoothing_radius
        )
        or settings.fill_mode != ZONE_DEFAULT.fill_mode
        or settings.hatch != ZONE_DEFAULT.hatch
    )
    if unsaid:
        ledger.add("zone-setting", zone.name or zone.id)
    if zone.locked:
        out.append(("locked", Raw("True")))
    return out


def _zones(
    board: Board,
    names: Mapping[str, str],
    nets: Mapping[str, str],
    layers: Sequence[str],
    ledger: Ledger,
    members: dict[str, Expr] | None = None,
    writer: _Writer | None = None,
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
        ring, bends = tuple(zone.outline), dict[int, Point]()
        if len(ring) < 3 and writer is not None:
            # an outline with an arc stays in the zone's slots; the code writes it with arc_to (change c0277)
            found = zone_arc_ring(zone)
            if found is not None:
                ring, bends = found
        if len(ring) < 3:
            ledger.add("zone-outline", where)
            continue
        args: list[tuple[str, Expr]] = [("layers", Tup(tuple(text(layer) for layer in zone.layers)))]
        if net is not None and zone.name == net and net not in named and net not in keys:
            named.add(net)
            keys.add(net)
            identity = net
        elif (
            zone.name and zone.name == zone.name.strip() and zone.name not in named and zone.name not in keys
        ):
            named.add(zone.name)
            keys.add(zone.name)
            args.append(("name", text(zone.name)))
            identity = zone.name
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
            identity = f"{stem}/{index}"
        if bends and writer is not None:
            args.append(("outline", _ring_path(ring, bends, writer)))
        else:
            args.append(("outline", Tup(tuple(_xy(p) for p in ring))))
        args += _zone_args(zone, ledger)
        target: Expr = Raw(nets[net]) if net is not None else Raw("None")
        out.append(statement(Call("design.zone", (target,), tuple(args))))
        if members is not None:
            members[_native(zone)] = text(identity)
    return out


def _areas(
    board: Board, layers: Sequence[str], ledger: Ledger, members: dict[str, Expr] | None = None
) -> list[list[str]]:
    from fenolite.dsl.items import AREA_NAME

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
        if area.name and AREA_NAME.fullmatch(area.name) and area.name.casefold() not in names:
            names.add(area.name.casefold())
            first: Expr = text(area.name)
            identity = area.name
        else:
            if area.name:
                ledger.add("rule-area-name", area.name)
            index += 1
            first = text("")
            args.append(("key", text(f"area/{index}")))
            identity = f"area/{index}"
        if members is not None:
            members[_native(area)] = text(identity)
        placement = area_placement(area)
        if placement is None:
            ledger.add("rule-area-placement", area.name or area.id)
        elif placement:
            args.append(("placement", text(placement)))
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


def _graphic(graphic: Graphic, key: str, net: Expr | None = None) -> Call | None:
    made = _graphic_call(graphic, key)
    if made is None or net is None:
        return made
    return dataclasses.replace(made, kwargs=(*made.kwargs, ("net", net)))


def _graphic_call(graphic: Graphic, key: str) -> Call | None:
    points = graphic.points
    if graphic.width < 0 and not (graphic.width == -1 and graphic.filled and graphic.kind != "line"):
        return None
    # a filled shape of width -1 nm has no outline: width=None says it (change c0277)
    width: Expr = length(graphic.width) if graphic.width >= 0 else Raw("None")
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


def _text(item: Text, key: str, copper: bool) -> Call | None:
    """``design.text()`` of a board text, with the style the reader keeps in its slots (change c0277);
    ``None`` for a text the DSL cannot say."""
    if not all(line.isprintable() for line in item.text.split("\n")):
        return None
    if item.size.w <= 0 or item.size.h <= 0 or item.thickness <= 0:
        return None
    style = text_style(item)
    if style is None or (style.knockout and not copper and not item.layer.endswith(".SilkS")):
        return None
    words = [w for w in (item.h_justify, item.v_justify) if w != "center"]
    size: Expr = (
        length(item.size.w) if item.size.w == item.size.h else Tup((length(item.size.w), length(item.size.h)))
    )
    kwargs: list[tuple[str, Expr]] = [
        ("layer", text(item.layer)),
        ("size", size),
        ("thickness", length(item.thickness)),
    ]
    if item.rotation:
        kwargs.append(("rot", angle(item.rotation)))
    if words:
        kwargs.append(("justify", text(" ".join(words))))
    for name in ("knockout", "bold", "italic"):
        if getattr(style, name):
            kwargs.append((name, Raw("True")))
    if style.face:
        kwargs.append(("face", text(style.face)))
    return Call("design.text", (text(key), text(item.text), _xy(item.position)), tuple(kwargs))


def _dimension(item: Dimension, key: str) -> Call | None:
    """``design.dimension()`` of an aligned or orthogonal dimension whose format and style are those a
    created dimension writes, but for its line width and its extension offset (change c0277); ``None``
    for another one."""
    if item.start == item.end or not 0 <= item.precision <= 4:
        return None
    style = dimension_style(item)
    if style is None:
        return None
    kwargs: list[tuple[str, Expr]] = [("offset", length(item.offset))]
    if item.layer != "Dwgs.User":
        kwargs.append(("layer", text(item.layer)))
    if item.direction is not None:
        kwargs.append(("direction", text(item.direction)))
    if style.units != "mm":
        kwargs.append(("units", text(style.units)))
    if item.precision != 4:
        kwargs.append(("precision", number(item.precision)))
    if item.size is not None:
        if item.size.w <= 0 or item.size.h <= 0:
            return None
        pair = Tup((length(item.size.w), length(item.size.h)))
        kwargs.append(("size", length(item.size.w) if item.size.w == item.size.h else pair))
    for name in ("thickness", "width"):
        value = getattr(item, name)
        if value is not None:
            if value <= 0:
                return None
            kwargs.append((name, length(value)))
    if style.extension_offset is not None:
        kwargs.append(("extension_offset", length(style.extension_offset)))
    if style.text_at is not None:
        kwargs.append(("text_at", _xy(style.text_at)))  # a text placed by hand (change c0277)
    return Call("design.dimension", (text(key), _xy(item.start), _xy(item.end)), tuple(kwargs))


def _native(item: Entity) -> str:
    return item.native_ids.get("kicad", "")


def _drawings(
    board: Board,
    ledger: Ledger,
    members: dict[str, Expr] | None = None,
    net_vars: Mapping[str, str] | None = None,
    numbers: Mapping[int, str] | None = None,
) -> list[list[str]]:
    from fenolite.dsl.items import BOARD_LAYER_KINDS

    # a DSL board holds the standard layers and the user layers it declares (design.user_layers, c0277)
    count, _ = user_layers(board)
    declared = {f"User.{k}" for k in range(1, count + 1)}
    kinds = {
        name: kind
        for name, kind in _kinds(board).items()
        if name in BOARD_LAYER_KINDS or name in declared or kind in ("edge", "copper")
    }
    out: list[list[str]] = []
    counters: dict[tuple[str, str], int] = {}

    def gkey(graphic: Graphic) -> tuple[object, ...]:
        return (graphic.layer, graphic.kind, tuple((p.x, p.y) for p in graphic.points), graphic.width)

    for graphic in sorted(board.graphics, key=gkey):
        kind = kinds.get(graphic.layer, "")
        if kind == "edge":
            continue
        if kind not in (*DRAWING_KINDS, "copper"):
            ledger.add("drawing-layer", f"{graphic.kind} on {graphic.layer}")
            continue
        # a copper graphic takes its net (change c0277); a slot design.line() cannot say leaves it out
        net = graphic_net(graphic, numbers or {})
        if net is not None and net and (kind != "copper" or net not in (net_vars or {})):
            net = None
        slot = (graphic.layer, graphic.kind)
        counters[slot] = counters.get(slot, 0) + 1
        key = f"{segment(graphic.layer)}/{graphic.kind}/{counters[slot]}"
        made = None if net is None else _graphic(graphic, key, Raw((net_vars or {})[net]) if net else None)
        if made is None:
            ledger.add("drawing", f"{graphic.kind} on {graphic.layer}")
            continue
        out.append(statement(made))
        if members is not None:
            members[_native(graphic)] = text(key)

    def tkey(item: Text) -> tuple[object, ...]:
        return (item.layer, item.position.x, item.position.y, item.text)

    for item in sorted(board.texts, key=tkey):
        kind = kinds.get(item.layer, "")
        if kind not in (*DRAWING_KINDS, "copper"):
            ledger.add("text-layer", f"text on {item.layer}")
            continue
        slot = (item.layer, "text")
        counters[slot] = counters.get(slot, 0) + 1
        key = f"{segment(item.layer)}/text/{counters[slot]}"
        made = _text(item, key, kind == "copper")
        if made is None:
            ledger.add("text", item.text[:40])
            continue
        out.append(statement(made))
        if members is not None:
            members[_native(item)] = text(key)

    def dkey(item: Dimension) -> tuple[object, ...]:
        return (item.layer, item.start.x, item.start.y, item.end.x, item.end.y, item.offset)

    for dimension in sorted(board.dimensions, key=dkey):
        where = f"{dimension.kind} on {dimension.layer}"
        if kinds.get(dimension.layer, "") not in DRAWING_KINDS:
            ledger.add("dimension", where)
            continue
        slot = (dimension.layer, "dimension")
        counters[slot] = counters.get(slot, 0) + 1
        key = f"{segment(dimension.layer)}/dimension/{counters[slot]}"
        made = _dimension(dimension, key)
        if made is None:
            ledger.add("dimension-style", where)
            continue
        out.append(statement(made))
        if members is not None:
            members[_native(dimension)] = text(key)
    return out


def _root_nodes(board: Board) -> list[Node]:
    """The root nodes the reader keeps in the board's slots, in file order."""
    bag = board.ext.get("kicad")
    found: list[Node] = []
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if isinstance(slot, Opaque):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node):
                found.append(child)
    return found


def _group_nodes(board: Board) -> list[Node]:
    """The root ``group`` nodes the reader keeps in the board's slots."""
    return [child for child in _root_nodes(board) if child.name == "group"]


def _verbatim_node(tree: Node, numbers: Mapping[int, str], built: Mapping[str, str]) -> Node | None:
    """``tree`` as a verbatim item says it (change c0277): a net named by its number (a KiCad 9 board) named
    by its name, and each copper uuid of a ``members`` list the uuid its table row takes in the build;
    ``None`` when a net number or a member names nothing the code writes."""
    if tree.name == "net":
        atoms = tree.atoms()
        if len(atoms) == 1 and atoms[0].kind == AtomKind.STRING:
            return tree
        name = numbers.get(int(atoms[0].value)) if len(atoms) == 1 and atoms[0].value.isdigit() else None
        return None if not name else tree.with_children([Atom.string(name)])
    if tree.name == "members":
        mapped = [built.get(a.value) for a in tree.atoms()]
        if any(found is None for found in mapped) or tree.nodes():
            return None
        return tree.with_children([Atom.string(cast(str, found)) for found in mapped])
    children: list[Node | Atom] = []
    for child in tree.children:
        if isinstance(child, Node):
            made = _verbatim_node(child, numbers, built)
            if made is None:
                return None
            children.append(made)
        else:
            children.append(child)
    return tree.with_children(children)


def _verbatim(
    board: Board,
    numbers: Mapping[int, str],
    built: Mapping[str, str],
    members: dict[str, Expr],
    ledger: Ledger,
) -> list[list[str]]:
    """``design.verbatim()`` of each root item the reader keeps and no other call says (change c0277): a
    ``generated`` tuning pattern, an image, a target, a barcode… keyed ``<head>/<n>`` in file order. An item
    that names copper the code does not write, or a net by a number the source table lacks, is unexpressed
    by its head."""
    from fenolite.backends.kicad import verbatim as verbatimlib
    from fenolite.backends.kicad.sexpr import dumps

    out: list[list[str]] = []
    counters: dict[str, int] = {}
    for child in _root_nodes(board):
        if child.name in verbatimlib.ROOT_REFUSED or child.name in coverage.INFRASTRUCTURE:
            continue
        made = _verbatim_node(child, numbers, built)
        if made is None:
            ledger.add(child.name, child.name)
            continue
        counters[child.name] = counters.get(child.name, 0) + 1
        key = f"{segment(child.name)}/{counters[child.name]}"
        out.append(statement(Call("design.verbatim", (text(key), text(dumps(made, style="compact"))))))
        held = child.find("uuid")
        if held is not None and held.atoms():
            members[held.atoms()[0].value] = text(key)
    return out


def _groups(board: Board, members: dict[str, Expr], ledger: Ledger) -> list[list[str]]:
    """``design.group()`` calls for the board's groups whose members the code writes (change c0277); a
    group holding a member it does not write (copper, a part or a drawing left out) is unexpressed. A group
    inside a group is written after it, so the inner group's key exists."""
    pending: list[tuple[str, str, bool, list[str], str]] = []
    for node_ in _group_nodes(board):
        atoms = node_.atoms()
        name = atoms[0].value if atoms else ""
        held = node_.find("uuid")
        uuid = held.atoms()[0].value if held is not None and held.atoms() else ""
        lock = node_.find("locked")
        locked = lock is not None and [a.value for a in lock.atoms()] in ([], ["yes"])
        listed = node_.find("members")
        uuids = [a.value for a in listed.atoms()] if listed is not None else []
        pending.append((name, uuid, locked, uuids, name or "group"))
    out: list[list[str]] = []
    said = Counter(flat(expr) for expr in members.values())
    taken: set[str] = set(said)
    # a key two items share (a zone and a rule area of one name) names neither in design.group()
    ambiguous = {uuid for uuid, expr in members.items() if said[flat(expr)] > 1}
    index = 0
    progress = True
    while pending and progress:
        progress = False
        for item in sorted(pending, key=lambda g: (g[0], g[3])):
            name, uuid, locked, uuids, _ = item
            if not uuids or not all(u in members and u not in ambiguous for u in uuids):
                continue
            pending.remove(item)
            progress = True
            if name and NAME.fullmatch(name) and flat(text(name)) not in taken:
                key = name
                kwargs: list[tuple[str, Expr]] = []
            else:
                index += 1
                while flat(text(f"group/{index}")) in taken:
                    index += 1
                key = f"group/{index}"
                kwargs = [("key", text(key))]
            taken.add(flat(text(key)))
            if locked:
                kwargs.append(("locked", Raw("True")))
            listed_members = tuple(sorted((members[u] for u in uuids), key=flat))
            out.append(statement(Call("design.group", (text(name), *listed_members), tuple(kwargs))))
            if uuid:
                members[uuid] = text(key)
    for _, _, _, _, label in pending:
        ledger.add("group", label)
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
            if table.free:
                args.append(("free", Raw("True")))  # KiCad's free vias (change c0277)
            if table.teardrop is not None:
                imports.add("teardrop")
                stated: list[tuple[str, Expr]] = []
                for name, value in teardrop_arguments(table.teardrop):
                    if isinstance(value, bool):
                        stated.append((name, Raw("True" if value else "False")))
                    elif name in ("max_length", "max_width"):
                        stated.append((name, length(cast(int, value))))
                    else:
                        stated.append((name, number(cast(int, value))))
                args.append(("teardrop", Call("teardrop", (), tuple(stated))))
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


def board_only_keys(design: Design) -> tuple[Design, dict[str, str], frozenset[str]]:
    """``design`` with a key in place of the reference of each footprint that shares its reference or has
    one a script cannot name (change c0277), the source reference of each such component by id, and the
    ids of the components that the code writes as board-only parts: those, and the footprints that carry
    KiCad's ``board_only`` attribute. A key is the reference cut to the name alphabet (``fp`` when nothing
    is left), then ``_<n>``, the lowest number no other reference or key holds, in placement order."""
    board = design.board
    if board is None:
        return design, {}, frozenset()
    refs = {c.id: c.ref for c in design.circuit.components}
    counts = Counter(refs.get(fp.component_id, "") for fp in board.footprints)
    taken = {ref for ref in refs.values() if NAME.fullmatch(ref)}
    shown: dict[str, str] = {}
    keys: dict[str, str] = {}
    board_only = {fp.component_id for fp in board.footprints if "board_only" in fp.attributes}

    def order(fp: FootprintInstance) -> tuple[object, ...]:
        return (natural(refs.get(fp.component_id, "")), fp.side, fp.position.x, fp.position.y, fp.id)

    for fp in sorted(board.footprints, key=order):
        ref = refs.get(fp.component_id, "")
        if fp.component_id in keys or (NAME.fullmatch(ref) and counts[ref] == 1):
            continue
        base = re.sub(r"[^A-Za-z0-9_.+-]", "", ref) or "fp"
        number = 1
        while f"{base}_{number}" in taken:
            number += 1
        keys[fp.component_id] = f"{base}_{number}"
        taken.add(keys[fp.component_id])
        shown[fp.component_id] = ref
        board_only.add(fp.component_id)
    if not keys:
        return design, shown, frozenset(board_only)
    components = tuple(
        dataclasses.replace(c, ref=keys[c.id]) if c.id in keys else c for c in design.circuit.components
    )
    keyed = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=components))
    return keyed, shown, frozenset(board_only)


def emit(source: Source, options: Options) -> Emission:
    """The files of the Fenolite project folder of ``source``."""
    design = source.design
    if design.board is None:
        raise ValueError("the source holds no board")
    design, shown, board_only = board_only_keys(design)
    board = design.board
    assert board is not None
    ledger = Ledger()
    issues: list[Issue] = []
    writer = _Writer()
    header = options.provenance.header()
    board_lines, copper_count = _board(design, writer, ledger)
    board_lines += _stackup(board, copper_count, writer, ledger)
    board_lines += _title_block(board, ledger)
    board_lines += _user_lines(board)
    layers = _copper_names(copper_count)
    names = {net.id: net.name for net in design.circuit.nets}
    refs = {c.id: c.ref for c in design.circuit.components}
    vendored = vendor(design, source.board_text, target=options.target)
    issues += vendored.issues
    if shown:
        bare = sum(
            1 for fp in board.footprints if fp.component_id in shown and "board_only" not in fp.attributes
        )
        listed = ", ".join(sorted({repr(ref) for ref in shown.values()}, key=natural)[:3])
        said = (
            f"{len(shown)} footprint(s) share a reference or have none a script can name ({listed}): "
            "they are board-only parts named by key"
        )
        if bare:
            said += f"; {bare} of them gain KiCad's board_only attribute"
        issues.append(issue("import.board-only", said, where="footprints"))
    tables = copper_tables(board, names)
    for kind, count in tables.left_out.items():
        ledger.add(kind, count=count)
    ledger.teardrops_lost += tables.teardrops_lost
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
            continue
        ledger.teardrops_lost += any(has_teardrops(pad) for pad in footprint.pads)
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
                if net.startswith(UNCONNECTED) and other.startswith(UNCONNECTED):
                    continue  # KiCad names an open pad's net per pad; the build names them again (c0277)
                ledger.add("pad-net-conflict", f"{ref}.{pad.number}")
                continue
            seen[(ref, pad.number)] = net
            members.setdefault(net, {})[(ref, pad.number)] = None
    used_nets = {net for net, pins in members.items() if not (len(pins) == 1 and net.startswith(UNCONNECTED))}
    used_nets |= {table.net for table in kept_tables}
    used_nets |= {names[z.net_id] for z in board.zones if z.net_id in names}
    numbers = net_numbers(design)
    copper_layers = {layer.name for layer in board.layers if layer.kind == "copper"}
    graphic_nets = (graphic_net(g, numbers) for g in board.graphics if g.layer in copper_layers)
    used_nets |= {found for found in graphic_nets if found and found in names.values()}
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
        if component.id not in board_only:
            lock_refs["/".join(path)] = ref  # a board-only part keeps its ref and no lock entry
        lib_id = vendored.footprints[ref]
        kwargs = [("footprint", text(lib_id))]
        if component.value:
            kwargs.append(("value", text(component.value)))
        written = shown.get(component.id, ref)
        if path[-1] != written:
            kwargs.append(("name", text(path[-1])))
        props = _properties(component.properties)
        if props is not None:
            kwargs.append(("properties", props))
        if component.dnp:
            kwargs.append(("dnp", Raw("True")))
        if component.id in board_only:
            kwargs.append(("board_only", Raw("True")))
        part_lines.append(
            statement(Call("Part", (text(written), text(vendored.symbols[ref])), tuple(kwargs)), target=var)
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
    grouped: dict[str, Expr] = {
        _native(fp): Raw(part_vars[refs[fp.component_id]]) for fp in footprints if _native(fp)
    }
    zone_lines = _zones(board, names, net_vars, layers, ledger, grouped, writer)
    area_lines = _areas(board, layers, ledger, grouped)
    drawing_lines = _drawings(board, ledger, grouped, net_vars, numbers)
    verbatim_lines = _verbatim(board, numbers, tables.built, grouped, ledger)
    group_lines = _groups(board, grouped, ledger)
    coverage.scan(design, ledger)
    issues += coverage.regenerated_issues(ledger)
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
        verbatim_lines,
        group_lines,
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
