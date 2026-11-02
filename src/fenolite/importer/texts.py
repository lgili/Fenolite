# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the KiCad reader keeps in the slots of a board text and of a dimension, read for the import
(change c0277): the ``knockout`` atom of a text's ``layer`` and the ``face``, ``bold`` and ``italic``
children of its font, which ``design.text()`` says; the ``format`` and ``style`` of a linear dimension,
which ``design.dimension()`` writes with fixed values but its extension offset. The reader projects the
rest itself.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.sexpr import AtomKind, Node
from fenolite.core.coords import Point
from fenolite.model.base import Opaque
from fenolite.model.board import Dimension, Graphic, Keepout, Text, Zone

FONT_KEPT = frozenset({"size", "thickness"})
"""Font children the reader projects into the model."""
SKIPPED = frozenset({"render_cache"})
"""Text children the import leaves to the tool: the outlines KiCad caches for a font face."""


@dataclass(frozen=True, slots=True)
class TextStyle:
    knockout: bool = False
    bold: bool = False
    italic: bool = False
    face: str = ""


def _flag(node: Node) -> bool | None:
    atoms = node.atoms()
    if node.nodes() or len(atoms) > 1:
        return None
    if not atoms:
        return True  # the bare token of older files
    return {"yes": True, "no": False}.get(atoms[0].value)


def _font(font: Node, found: dict[str, object]) -> bool:
    for child in font.nodes():
        name = child.name
        if name in FONT_KEPT:
            continue
        if name in ("bold", "italic"):
            flag = _flag(child)
            if flag is None:
                return False
            found[name] = flag
        elif name == "face":
            atoms = child.atoms()
            if len(atoms) != 1 or atoms[0].kind != AtomKind.STRING or child.nodes():
                return False
            found["face"] = atoms[0].value
        else:
            return False
    for atom in font.atoms():  # the bare tokens of older files
        if atom.value not in ("bold", "italic"):
            return False
        found[atom.value] = True
    return True


def _effects(effects: Node, text: Text, found: dict[str, object]) -> bool:
    for child in effects.nodes():
        if child.name == "font":
            if not _font(child, found):
                return False
        elif child.name == "justify":
            mirrored = any(a.value == "mirror" for a in child.atoms())
            if mirrored != text.layer.startswith("B."):
                return False  # the writer mirrors a text on a back layer, and only there
        else:
            return False
    return not effects.atoms()


def text_style(text: Text) -> TextStyle | None:
    """The style of ``text`` from its slots; ``None`` when a slot holds something ``design.text()`` cannot
    say (a hidden text, a mirror that does not follow the layer side, an unknown child)."""
    found: dict[str, object] = {}
    bag = text.ext.get("kicad")
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if not isinstance(slot, Opaque):
            continue
        child = slotlib.opaque_child(slot)
        if not isinstance(child, Node):
            return None
        if child.name == "layer":
            extra = [a.value for a in child.atoms()[1:]]
            if extra != ["knockout"]:
                return None
            found["knockout"] = True
        elif child.name == "effects":
            if not _effects(child, text, found):
                return None
        elif child.name not in SKIPPED:
            return None
    return TextStyle(**found)  # type: ignore[arg-type]


DIMENSION_FORMAT = {"prefix": '""', "suffix": '""', "units_format": "1"}
"""The children of a dimension's ``format`` that ``design.dimension()`` writes with these values; ``units``
and ``precision`` are model fields."""
DIMENSION_STYLE = {
    "arrow_length": "1.27",
    "arrow_direction": "outward",
    "extension_height": "0.58642",
    "keep_text_aligned": "yes",
}
"""The children of a dimension's ``style`` that ``design.dimension()`` writes with these values (``pcb``,
"Dimensions"); ``thickness`` is the model's ``width`` and ``extension_offset`` a DSL argument."""


UNITS_OF_CODE = {"0": "in", "1": "mils", "2": "mm", "3": "auto"}
"""The units of each ``units`` code of a dimension's ``format`` (S-0001); the reader projects only 0 and 2."""


@dataclass(frozen=True, slots=True)
class DimensionStyle:
    extension_offset: int | None = None
    units: str = "mm"
    """The units of the ``format`` slot, which the reader does not project for mils and automatic units."""
    text_at: Point | None = None
    """Where a text placed by hand stands (``text_position_mode 2``; change c0277)."""


def _children_match(node: Node, fixed: dict[str, str], free: frozenset[str]) -> dict[str, Node] | None:
    found: dict[str, Node] = {}
    for child in node.nodes():
        if child.name in found:
            return None
        found[child.name] = child
        if child.name in free:
            continue
        atoms = child.atoms()
        if child.name not in fixed or child.nodes() or len(atoms) != 1 or atoms[0].text != fixed[child.name]:
            return None
    return found if not node.atoms() else None


def dimension_style(dimension: Dimension) -> DimensionStyle | None:
    """The extension offset of a linear dimension whose ``format`` and ``style`` the DSL writes; ``None``
    when another child or value is in them (a prefix, automatic units, a text position…)."""
    gap: int | None = None
    units = dimension.units
    manual = False
    text_at: Point | None = None
    bag = dimension.ext.get("kicad")
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if not isinstance(slot, Opaque):
            continue
        child = slotlib.opaque_child(slot)
        if not isinstance(child, Node):
            return None
        if child.name == "format":
            fields = _children_match(child, DIMENSION_FORMAT, frozenset({"units", "precision"}))
            if fields is None:
                return None
            held = fields.get("units")
            code = [a.text for a in held.atoms()] if held is not None and not held.nodes() else []
            if len(code) != 1 or code[0] not in UNITS_OF_CODE:
                return None
            units = UNITS_OF_CODE[code[0]]
            held = fields.get("precision")
            if held is None or [a.text for a in held.atoms()] != [str(dimension.precision)] or held.nodes():
                return None
        elif child.name == "style":
            found = _children_match(
                child, DIMENSION_STYLE, frozenset({"thickness", "extension_offset", "text_position_mode"})
            )
            if found is None:
                return None
            mode = found.get("text_position_mode")
            mode_atoms = [a.text for a in mode.atoms()] if mode is not None and not mode.nodes() else ["0"]
            if mode_atoms not in (["0"], ["2"]):
                return None
            manual = mode_atoms == ["2"]
            offset = found.get("extension_offset")
            if offset is not None:
                atoms = offset.atoms()
                if len(atoms) != 1 or offset.nodes():
                    return None
                try:
                    gap = atoms[0].to_nm()
                except ValueError:
                    return None
        elif child.name == "gr_text":
            at = child.find("at")
            try:
                text_at = (
                    _point(at.with_children(at.children[:2]))
                    if at is not None and len(at.atoms()) >= 2
                    else None
                )
            except ValueError:
                return None
        else:
            return None
    if manual and text_at is None:
        return None
    return DimensionStyle(None if gap == 500_000 else gap, units, text_at if manual else None)


def special_style(dimension: Dimension) -> tuple[str, Point | None] | None:
    """The units and the hand-placed text position of a radial, leader or centre dimension whose ``format``
    and ``style`` are those the build writes (``pcb.special_dimension_children``) and whose text has the
    effects it writes; ``None`` for another one (change c0277). A leader's text position is its ``gr_text``
    ``at``, given when it is not the build's default; a radial one's is KiCad's to draw."""
    from fenolite.backends.kicad.pcb import leader_text_at, special_dimension_children

    bag = dimension.ext.get("kicad")
    read: dict[str, Node] = {}
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if not isinstance(slot, Opaque):
            continue
        child = slotlib.opaque_child(slot)
        if (
            not isinstance(child, Node)
            or child.name not in ("format", "style", "gr_text")
            or child.name in read
        ):
            return None
        read[child.name] = child
    units = dimension.units
    held = read["format"].find("units") if "format" in read else None
    if held is not None:
        code = [a.text for a in held.atoms()]
        if len(code) != 1 or code[0] not in UNITS_OF_CODE:
            return None
        units = UNITS_OF_CODE[code[0]]
    text_at: Point | None = None
    shown = read.get("gr_text")
    if shown is not None:
        at = shown.find("at")
        if at is None or len(at.atoms()) < 2:
            return None
        try:
            where = _point(at.with_children(at.children[:2]))
        except ValueError:
            return None
        if dimension.kind == "leader" and where != leader_text_at(dimension):
            text_at = where
    model = dataclasses.replace(dimension, units=units, text_position=text_at)  # type: ignore[arg-type]
    expected = special_dimension_children(model, "")
    if sorted(read) != sorted(name for name, nodes in expected.items() if nodes):
        return None
    for name in ("format", "style"):
        if name in read and read[name] != expected[name][0]:
            return None
    if shown is not None:
        made = expected["gr_text"][0]
        assert isinstance(made, Node)
        if shown.find("effects") != made.find("effects") or shown.find("layer") != made.find("layer"):
            return None
    return units, text_at


def _plain_stroke(stroke: Node) -> bool:
    """A ``stroke`` the DSL writes again: its width (the model's) and a ``solid`` or ``default`` type; a
    dashed or coloured stroke is not."""
    for child in stroke.nodes():
        if child.name == "type":
            if [a.value for a in child.atoms()] not in (["solid"], ["default"]):
                return False
        elif child.name != "width":
            return False
    return not stroke.atoms()


def area_placement(area: Keepout) -> str | None:
    """The sheet of a placement rule area from its slots (change c0277): ``""`` for an area without a
    ``placement``, ``None`` for one ``design.rule_area()`` cannot say (disabled, or placing by another
    source than a sheet)."""
    bag = area.ext.get("kicad")
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if not isinstance(slot, Opaque):
            continue
        child = slotlib.opaque_child(slot)
        if not isinstance(child, Node) or child.name != "placement":
            continue
        enabled = child.find("enabled")
        sheet = child.find("sheetname")
        heads = sorted(c.name for c in child.nodes())
        if heads != ["enabled", "sheetname"] or enabled is None or sheet is None:
            return None
        if len(sheet.atoms()) != 1 or [a.value for a in enabled.atoms()] not in (["yes"], ["no"]):
            return None
        if [a.value for a in enabled.atoms()] == ["no"]:
            # KiCad 9 writes a disabled placement on every rule area: no placement (change c0277)
            return "" if not sheet.atoms()[0].value else None
        return sheet.atoms()[0].value
    return ""


def zone_arc_ring(zone: Zone) -> tuple[tuple[Point, ...], dict[int, Point]] | None:
    """The vertices and the arc edges (index → mid) of a zone outline that the reader kept in its slots
    because it holds an arc (change c0277): one ``polygon`` whose ``pts`` hold ``xy`` and ``arc`` items, an
    arc's end being a vertex, a line joining an item's last point to the next one's first. ``None`` for
    another outline (several polygons, an unknown item)."""
    bag = zone.ext.get("kicad")
    polygons: list[Node] = []
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if isinstance(slot, Opaque):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name == "polygon":
                polygons.append(child)
    if len(polygons) != 1:
        return None
    pts = polygons[0].find("pts")
    if pts is None or len(polygons[0].nodes()) != 1:
        return None
    points: list[Point] = []
    bends: dict[int, Point] = {}

    def add(point: Point) -> None:
        if not points or points[-1] != point:
            points.append(point)

    try:
        for item in pts.nodes():
            if item.name == "xy":
                add(_point(item))
            elif item.name == "arc":
                ends = [item.find(head) for head in ("start", "mid", "end")]
                if len(item.nodes()) != 3:
                    return None
                start, mid, end = (_point(found) for found in ends)
                add(start)
                bends[len(points) - 1] = mid
                points.append(end)
            else:
                return None
    except ValueError:
        return None
    if len(points) > 1 and points[-1] == points[0]:
        points.pop()
    return (tuple(points), bends) if len(points) >= 3 or (len(points) == 2 and bends) else None


def _point(node: Node | None) -> Point:
    """The point of an ``(xy x y)``-shaped node, in nanometres; ``ValueError`` for anything else."""
    if node is None:
        raise ValueError("no point")
    atoms = node.atoms()
    if len(atoms) != 2 or node.nodes():
        raise ValueError(f"not a point: {node.name}")
    return Point(atoms[0].to_nm(), atoms[1].to_nm())


NO_NET = ""
"""What ``graphic_net`` gives for a graphic without a net."""


def graphic_net(graphic: Graphic, numbers: Mapping[int, str]) -> str | None:
    """The name of the net of a copper graphic from its slots (change c0277): ``(net 1)`` of a KiCad 9 board,
    named through ``numbers`` (the source net table), or ``(net "GND")`` of a KiCad 10 one; ``NO_NET``
    for a graphic without a net, and ``None`` when a slot holds something ``design.line()`` and the other
    graphic calls cannot say (a lock, a net that names no net, an unknown child)."""
    found = NO_NET
    bag = graphic.ext.get("kicad")
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if not isinstance(slot, Opaque):
            continue
        child = slotlib.opaque_child(slot)
        if isinstance(child, Node) and child.name == "stroke":
            if not _plain_stroke(child):
                return None
            continue
        if not isinstance(child, Node) or child.name != "net" or child.nodes() or len(child.atoms()) != 1:
            return None
        atom = child.atoms()[0]
        if atom.kind == AtomKind.STRING:
            found = atom.value
        elif atom.value.isdigit():
            found = numbers.get(int(atom.value), "") if int(atom.value) else NO_NET
            if not found and int(atom.value):
                return None
        else:
            return None
    return found


__all__ = [
    "NO_NET",
    "area_placement",
    "zone_arc_ring",
    "DimensionStyle",
    "TextStyle",
    "dimension_style",
    "graphic_net",
    "special_style",
    "text_style",
]
