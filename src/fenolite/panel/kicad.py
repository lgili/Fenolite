# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad panel board (capability kicad-file-backend, "Panel boards written"; change c0173, design
Decisions 4 and 5).

The board is assembled from the source board's own tree, so every item of each copy keeps its form byte for
byte but for what moves: each item is copied once per copy, every point of the board frame moved by the
copy's exact integer translation after its quarter turn (``PanelCopy.place``), every absolute angle turned
with it, every uuid replaced by ``ids.item_uuid(<copy key>, <source uuid>)``, and every net renamed
``B<k>/<name>``. The copies' outer edges are dropped: the panel's rings replace them (``layout.outline`` on
``Edge.Cuts``), and a copy's own cut-outs and slots stay. Then the panel's own items: V-score lines as
``gr_line`` on the user layer whose user name is the score layer (``User.<n>``, added when missing), one
``Fenolite_Panel:MouseBites_<n>x<d>mm_P<p>mm`` footprint of unnumbered ``np_thru_hole`` pads per row of
mouse-bite holes (refs ``MB<k>``), and c0118's generated fiducial and tooling-hole footprints (refs as the
script names them, ``PFID<n>`` and ``PTH<n>`` when placed by the layout).

The source must be a board of the target's major: the panel keeps its format version. The panel's top-left
corner is written at ``BOARD_ORIGIN`` (100, 100) mm, as a design script's board.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from fenolite.backends.kicad import versions
from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.embed import placed_tree
from fenolite.backends.kicad.mod import prepare_authored_definition, write_footprint
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.core.trig import FULL_TURN
from fenolite.core.units import Nm, Udeg, format_length
from fenolite.model.board import Graphic, Pad
from fenolite.model.circuit import Component
from fenolite.model.holes import HOLE_FLAGS, HOLE_LAYERS
from fenolite.model.library import FootprintDef
from fenolite.model.panel import Panel
from fenolite.panel import ids
from fenolite.panel.layout import PanelCopy, PanelLayout, Rect

ORIGIN = Point(100_000_000, 100_000_000)
"""Where the panel's top-left corner is written: the board origin of a design script (``docs/dsl.md``)."""
PANEL_LIBRARY = "Fenolite_Panel"
EDGE_WIDTH: Nm = 100_000
"""The pen of the panel's ``Edge.Cuts`` lines, 0.1 mm, as a design script's board outline."""
COORDINATES = frozenset({"start", "end", "mid", "center", "xy", "at"})
TURNED = frozenset({"pad", "property", "fp_text", "fp_text_box"})
"""Children of a footprint whose ``at`` angle is absolute in the file (``board.md``)."""
HEADER = ("version", "generator", "generator_version", "general", "paper", "title_block", "layers", "setup")
TRAILER = frozenset({"embedded_fonts", "embedded_files"})


class PanelWriteError(ValueError):
    """The source board cannot be written as a panel of this target."""


def _mm(value: int) -> str:
    return format_length(value).removesuffix("mm")


def _shift(p: Point) -> Point:
    return Point(p.x + ORIGIN.x, p.y + ORIGIN.y)


def source_major(root: Node) -> int:
    """The KiCad major of a board tree, from its ``version``."""
    found = root.find("version")
    version = found.atoms()[0].to_int() if found is not None and found.atoms() else 0
    major = versions.major_for(versions.FileKind.BOARD, version)
    if major is None:
        raise PanelWriteError(f"the board's format version {version} is no KiCad major Fenolite writes")
    return major


# --- numbers and angles ----------------------------------------------------------------------------------


def _nm(atom: Node | Atom) -> int:
    assert isinstance(atom, Atom)
    return atom.to_nm(exact=False)


def _degrees(atom: Atom) -> Decimal:
    return Decimal(atom.text)


def _angle(value: Decimal) -> Atom:
    turned = value % 360
    text = format(turned.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return Atom(text if text not in ("", "-0") else "0", AtomKind.NUMBER)


def _turn(at: Node, rotation: Udeg, *, keep: bool) -> Node:
    """``at`` with its angle turned by ``rotation``; a missing angle is added unless the result is 0, and a
    0 is dropped from an ``at`` that had none (``keep`` keeps a written 0)."""
    atoms = list(at.children)
    degrees = Decimal(rotation) / 1_000_000
    if len(atoms) > 2 and isinstance(atoms[2], Atom):
        atoms[2] = _angle(_degrees(atoms[2]) + degrees)
        if not keep and atoms[2].text == "0":
            del atoms[2]
    elif rotation % FULL_TURN:
        atoms.insert(2, _angle(degrees))
    return at.with_children(atoms)


# --- the copy of one item ---------------------------------------------------------------------------------


@dataclass
class _Copy:
    copy: PanelCopy
    key: str
    nets: dict[int, int]
    names: dict[str, str]
    numbered: bool

    def point(self, x: Atom, y: Atom) -> tuple[Atom, Atom]:
        moved = _shift(self.copy.place(Point(_nm(x), _nm(y))))
        return Atom.from_nm(moved.x), Atom.from_nm(moved.y)

    def uuid(self, value: str) -> str:
        return ids.item_uuid(self.key, value)

    def net(self, child: Node) -> Node:
        atoms = child.atoms()
        if not atoms:
            return child
        if atoms[0].kind == AtomKind.NUMBER:
            number = atoms[0].to_int()
            new = [Atom.integer(self.nets.get(number, 0))]
            if len(atoms) > 1:
                new.append(Atom.string(self.names.get(atoms[1].value, atoms[1].value)))
            return child.with_children(new)
        return child.with_children([Atom.string(self.names.get(atoms[0].value, atoms[0].value))])


def _common(child: Node, c: _Copy) -> Node | None:
    """The uuid, net and member rewrites every node shares, or ``None`` when ``child`` needs none."""
    if child.name in ("uuid", "tstamp") and child.atoms():
        atom = child.atoms()[0]
        new = c.uuid(atom.value)
        return child.with_children([Atom.string(new) if atom.kind == AtomKind.STRING else Atom.symbol(new)])
    if child.name == "members":
        return child.with_children(
            [Atom.string(c.uuid(a.value)) if isinstance(a, Atom) else a for a in child.children]
        )
    if child.name == "net":
        return c.net(child)
    if child.name == "net_name" and child.atoms() and child.atoms()[0].value:
        return child.with_children([Atom.string(c.names.get(child.atoms()[0].value, child.atoms()[0].value))])
    return None


def _absolute(item: Node, c: _Copy) -> Node:
    """``item`` with every board-frame point moved, every absolute angle turned, uuids and nets renamed."""
    children: list[Node | Atom] = []
    for child in item.children:
        if not isinstance(child, Node):
            children.append(child)
            continue
        common = _common(child, c)
        if common is not None:
            children.append(common)
            continue
        atoms = child.atoms()
        if (
            child.name in COORDINATES
            and len(atoms) >= 2
            and all(a.kind == AtomKind.NUMBER for a in atoms[:2])
        ):
            x, y = c.point(atoms[0], atoms[1])
            moved = child.with_children([x, y, *child.children[2:]])
            children.append(_turn(moved, c.copy.rotation, keep=True) if child.name == "at" else moved)
            continue
        children.append(_absolute(child, c))
    return item.with_children(children)


def _local(item: Node, c: _Copy) -> Node:
    """A child of a footprint: its points stay in the footprint frame, its absolute angles turn."""
    children: list[Node | Atom] = []
    for child in item.children:
        if not isinstance(child, Node):
            children.append(child)
            continue
        common = _common(child, c)
        if common is not None:
            children.append(common)
        elif child.name == "at" and item.name in TURNED:
            children.append(_turn(child, c.copy.rotation, keep=item.name != "pad"))
        else:
            children.append(_local(child, c))
    return item.with_children(children)


def _footprint(item: Node, c: _Copy) -> Node:
    children: list[Node | Atom] = []
    for child in item.children:
        if not isinstance(child, Node):
            children.append(child)
            continue
        common = _common(child, c)
        if common is not None:
            children.append(common)
        elif child.name == "at":
            atoms = child.atoms()
            x, y = c.point(atoms[0], atoms[1])
            children.append(
                _turn(child.with_children([x, y, *child.children[2:]]), c.copy.rotation, keep=False)
            )
        elif child.name == "zone":
            children.append(_absolute(child, c))  # a footprint's zone is held in the board frame
        else:
            children.append(_local(child, c))
    return item.with_children(children)


# --- the edges of a copy --------------------------------------------------------------------------------


def _layer(item: Node) -> str:
    found = item.find("layer")
    return found.atoms()[0].value if found is not None and found.atoms() else ""


def _points(item: Node) -> list[Point]:
    found: list[Point] = []
    for child in item.children:
        if isinstance(child, Node):
            atoms = child.atoms()
            if child.name in COORDINATES and len(atoms) >= 2:
                found.append(Point(_nm(atoms[0]), _nm(atoms[1])))
            else:
                found += _points(child)
    return found


def _on_box(item: Node, box: Rect) -> bool:
    """Whether a root graphic on ``Edge.Cuts`` lies on the board box's perimeter: the board's outer edge,
    which the panel's rings replace."""
    if item.name not in ("gr_line", "gr_rect", "gr_poly") or _layer(item) != "Edge.Cuts":
        return False
    points = _points(item)
    if not points:
        return False
    if item.name == "gr_line":
        a, b = points[0], points[-1]
        return (a.x == b.x and a.x in (box.x0, box.x1)) or (a.y == b.y and a.y in (box.y0, box.y1))
    return all(p.x in (box.x0, box.x1) or p.y in (box.y0, box.y1) for p in points)


# --- the panel's own items -------------------------------------------------------------------------------


def _gr_line(a: Point, b: Point, layer: str, width: Nm, uuid_text: str) -> Node:
    return node(
        "gr_line",
        node("start", Atom.from_nm(a.x), Atom.from_nm(a.y)),
        node("end", Atom.from_nm(b.x), Atom.from_nm(b.y)),
        node("stroke", node("width", Atom.from_nm(width)), node("type", Atom.symbol("solid"))),
        node("layer", Atom.string(layer)),
        node("uuid", Atom.string(uuid_text)),
    )


def mouse_bites(holes: int, drill: Nm, pitch: Nm) -> FootprintDef:
    """``Fenolite_Panel:MouseBites_<n>x<d>mm_P<p>mm``: ``holes`` unnumbered non-plated holes of ``drill``,
    ``pitch`` apart along the footprint's X axis, centred on its origin, with a courtyard around them on
    both sides and the flags that keep it out of the position file and the bill of materials."""
    name = f"MouseBites_{holes}x{_mm(drill)}mm_P{_mm(pitch)}mm"
    lib_id = f"{PANEL_LIBRARY}:{name}"
    pads = tuple(
        Pad(
            id=derived_id("pad", ids.BACKEND, f"{lib_id}:pad:{j}"),
            number="",
            shape="circle",
            size=Size(drill, drill),
            position=Point((2 * j - (holes - 1)) * pitch // 2, 0),
            kind="np_thru_hole",
            drill=drill,
            layers=HOLE_LAYERS,
        )
        for j in range(holes)
    )
    half_x = ((holes - 1) * pitch + drill + 1) // 2 + 50_000
    half_y = (drill + 1) // 2 + 50_000
    graphics = tuple(
        Graphic(
            id=derived_id("gfx", ids.BACKEND, f"{lib_id}:graphic:{layer}"),
            kind="rect",
            layer=layer,
            points=(Point(-half_x, -half_y), Point(half_x, half_y)),
            width=50_000,
        )
        for layer in ("F.CrtYd", "B.CrtYd")
    )
    return FootprintDef(
        id=derived_id("fpd", ids.BACKEND, lib_id),
        name=name,
        library=PANEL_LIBRARY,
        flags=("board_only", *HOLE_FLAGS),
        pads=pads,
        graphics=graphics,
    )


@dataclass(frozen=True, slots=True)
class _Placed:
    defn: FootprintDef
    ref: str
    at: Point
    rotation: Udeg
    side: str
    key: str


def _panel_footprints(panel: Panel, laid: PanelLayout) -> list[_Placed]:
    from fenolite.dsl import assembly

    placed: list[_Placed] = []
    spec = panel.tabs
    pitch = spec.drill + spec.hole_gap
    k = 0
    for tab in laid.tabs:
        rows: dict[int, list[Point]] = {}
        for hole in tab.holes:
            across = hole.x if tab.axis == "y" else hole.y
            rows.setdefault(across, []).append(hole)
        for across, holes in sorted(rows.items()):
            k += 1
            along = sorted(h.y if tab.axis == "y" else h.x for h in holes)
            middle = (along[0] + along[-1]) // 2
            at = Point(across, middle) if tab.axis == "y" else Point(middle, across)
            rotation = 90_000_000 if tab.axis == "y" else 0
            defn = mouse_bites(len(holes), tab.drill, pitch)
            placed.append(
                _Placed(
                    prepare_authored_definition(defn), f"MB{k}", at, rotation, "top", f"{tab.id}:row:{across}"
                )
            )
    for fiducial in laid.fiducials:
        defn = assembly.fiducial_footprint(
            fiducial.copper, fiducial.mask, fiducial.mask, local=False
        ).definition
        placed.append(
            _Placed(
                prepare_authored_definition(defn), fiducial.ref, fiducial.at, 0, fiducial.side, fiducial.id
            )
        )
    for hole in laid.tooling_holes:
        defn = assembly.tooling_hole_footprint(hole.drill, None).definition
        placed.append(_Placed(prepare_authored_definition(defn), hole.ref, hole.at, 0, "top", hole.id))
    return placed


def _hidden_fields(tree: Node) -> Node:
    """A panel footprint with its ``Reference`` and ``Value`` hidden: on a rail or a tab, a visible text
    would lie over the holes' copper layers or at the panel's edge (``silk_over_copper``,
    ``silk_edge_clearance``); the references stay in the file."""
    children: list[Node | Atom] = []
    for child in tree.children:
        if (
            isinstance(child, Node)
            and child.name == "property"
            and child.atoms()
            and child.atoms()[0].value in ("Reference", "Value")
        ):
            if child.find("hide") is None:
                kept = list(child.children)
                at = next(
                    (i for i, c in enumerate(kept) if isinstance(c, Node) and c.name == "layer"),
                    len(kept) - 1,
                )
                kept.insert(at + 1, node("hide", Atom.symbol("yes")))
                child = child.with_children(kept)
        children.append(child)
    return tree.with_children(children)


# --- the board -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KicadPanel:
    """The files of a KiCad panel, by path relative to the output folder, and what they hold."""

    files: dict[str, bytes]
    board: str
    score_layer: str | None
    footprints: int


def _layers(layers: Node, name: str) -> tuple[Node, str]:
    """The layer table with a user layer whose user name is ``name`` (the first free ``User.<n>``) and that
    layer's canonical name."""
    taken: set[str] = set()
    for row in layers.nodes():
        atoms = row.atoms()
        if len(atoms) >= 2:
            taken.add(atoms[0].value)
            if len(atoms) >= 3 and atoms[-1].kind == AtomKind.STRING and atoms[-1].value == name:
                return layers, atoms[0].value
    for n in range(1, 46):
        canonical = f"User.{n}"
        if canonical not in taken:
            row = Node(
                Atom.integer(37 + 2 * n), (Atom.string(canonical), Atom.symbol("user"), Atom.string(name))
            )
            return layers.with_children([*layers.children, row]), canonical
    raise PanelWriteError("the board declares every user layer; none is free for the score lines")


def _source_nets(root: Node, numbered: bool) -> list[tuple[int, str]]:
    if numbered:
        return [
            (row.atoms()[0].to_int(), row.atoms()[1].value)
            for row in root.nodes("net")
            if len(row.atoms()) >= 2 and row.atoms()[0].to_int() != 0
        ]
    names: dict[str, None] = {}

    def visit(item: Node) -> None:
        for child in item.nodes():
            if child.name in ("net", "net_name") and child.atoms() and child.atoms()[0].value:
                names.setdefault(child.atoms()[0].value, None)
            else:
                visit(child)

    visit(root)
    return [(0, name) for name in names]


def panel_board_text(
    panel: Panel, laid: PanelLayout, source_text: str, *, target: int
) -> tuple[str, str | None]:
    """The text of the panel board and the canonical name of its score layer (``None`` without scores)."""
    root = parse(source_text)
    major = source_major(root)
    if major != target:
        raise PanelWriteError(
            f"the board was written for KiCad {major}; a panel keeps its format, so its target is {major}"
        )
    numbered = any(len(row.atoms()) >= 2 for row in root.nodes("net"))
    nets = _source_nets(root, numbered)
    header: list[Node | Atom] = []
    items: list[Node] = []
    trailer: list[Node] = []
    for child in root.children:
        if not isinstance(child, Node):
            header.append(child)
        elif child.name in HEADER or child.name == "property":
            header.append(child)
        elif child.name == "net":
            continue
        elif child.name in TRAILER:
            trailer.append(child)
        else:
            items.append(child)
    score_layer: str | None = None
    if laid.score_lines:
        for index, child in enumerate(header):
            if isinstance(child, Node) and child.name == "layers":
                table, score_layer = _layers(child, panel.vscore.layer_name)
                header[index] = table
    body: list[Node | Atom] = list(header)
    if numbered:
        body.append(node("net", Atom.integer(0), Atom.string("")))
    number = 0
    for copy in laid.copies:
        mapping: dict[int, int] = {}
        names: dict[str, str] = {}
        for old, name in nets:
            number += 1
            mapping[old] = number
            names[name] = f"B{copy.k}/{name}"
            if numbered:
                body.append(node("net", Atom.integer(number), Atom.string(names[name])))
        c = _Copy(copy, ids.copy_key(copy.row, copy.col), mapping, names, numbered)
        for item in items:
            if _on_box(item, laid.board):
                continue
            body.append(_footprint(item, c) if item.name == "footprint" else _absolute(item, c))
    for placed in _panel_footprints(panel, laid):
        component = Component(
            id=derived_id("cmp", ids.BACKEND, placed.key), ref=placed.ref, value=placed.defn.name
        )
        tree = placed_tree(
            placed.defn,
            component=component,
            at=_shift(placed.at),
            rotation=placed.rotation,
            side="bottom" if placed.side == "bottom" else "top",
            locked=True,
            key=f"{ids.BACKEND}:{placed.key}",
        )
        body.append(_hidden_fields(tree))
    for r, ring in enumerate(laid.outline):
        for e, start in enumerate(ring):
            end = ring[(e + 1) % len(ring)]
            body.append(
                _gr_line(
                    _shift(start), _shift(end), "Edge.Cuts", EDGE_WIDTH, ids.item_uuid("edge", f"{r}:{e}")
                )
            )
    if score_layer is not None:
        for line in laid.score_lines:
            a, b = line.points()
            body.append(
                _gr_line(
                    _shift(a),
                    _shift(b),
                    score_layer,
                    panel.vscore.line_width,
                    ids.item_uuid("vscore", line.id),
                )
            )
    body += trailer
    return dumps(root.with_children(body), style="kicad"), score_layer


def footprint_files(panel: Panel, laid: PanelLayout, *, target: int) -> dict[str, bytes]:
    """The library files of the generated footprints and the ``fp-lib-table`` that names them."""
    files: dict[str, bytes] = {}
    libraries: set[str] = set()
    for placed in _panel_footprints(panel, laid):
        defn = placed.defn
        libraries.add(defn.library)
        path = f"lib/{defn.library}.pretty/{defn.name}.kicad_mod"
        files.setdefault(path, write_footprint(defn, target=target).encode("utf-8"))
    if libraries:
        rows = "".join(
            f'\t(lib (name "{name}") (type "KiCad") (uri "${{KIPRJMOD}}/lib/{name}.pretty") (options "") '
            f'(descr "Footprints generated by Fenolite"))\n'
            for name in sorted(libraries)
        )
        files["fp-lib-table"] = f"(fp_lib_table\n\t(version 7)\n{rows})\n".encode()
    return files


def project_text(source_project: str | None, name: str, copies: int, synthesize: Callable[[], str]) -> str:
    """The panel's project file: the source board's own, with its file name and its net-class assignments
    and patterns made to hold the renamed nets of every copy; else ``synthesize()``."""
    if source_project is None:
        return synthesize()
    data: dict[str, Any] = json.loads(source_project)
    meta: dict[str, Any] = data.setdefault("meta", {})
    meta["filename"] = f"{name}.kicad_pro"
    settings: Any = data.get("net_settings")
    if isinstance(settings, dict):
        table = cast("dict[str, Any]", settings)
        patterns: Any = table.get("netclass_patterns")
        if isinstance(patterns, list):
            for row in cast("list[Any]", patterns):
                if isinstance(row, dict) and isinstance(cast("dict[str, Any]", row).get("pattern"), str):
                    entry = cast("dict[str, Any]", row)
                    entry["pattern"] = f"B*/{entry['pattern']}"
        assignments: Any = table.get("netclass_assignments")
        if isinstance(assignments, dict):
            given = cast("dict[str, Any]", assignments)
            table["netclass_assignments"] = {
                f"B{k}/{net}": value for k in range(1, copies + 1) for net, value in given.items()
            }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


__all__ = [
    "EDGE_WIDTH",
    "KicadPanel",
    "ORIGIN",
    "PANEL_LIBRARY",
    "PanelWriteError",
    "footprint_files",
    "mouse_bites",
    "panel_board_text",
    "project_text",
    "source_major",
]
