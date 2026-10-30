# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the KiCad reader keeps in the slots of a board text and of a dimension, read for the import
(change c0277): the ``knockout`` atom of a text's ``layer`` and the ``face``, ``bold`` and ``italic``
children of its font, which ``design.text()`` says; the ``format`` and ``style`` of a linear dimension,
which ``design.dimension()`` writes with fixed values but its extension offset. The reader projects the
rest itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.sexpr import AtomKind, Node
from fenolite.model.base import Opaque
from fenolite.model.board import Dimension, Graphic, Text

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
    "text_position_mode": "0",
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
            found = _children_match(child, DIMENSION_STYLE, frozenset({"thickness", "extension_offset"}))
            if found is None:
                return None
            offset = found.get("extension_offset")
            if offset is not None:
                atoms = offset.atoms()
                if len(atoms) != 1 or offset.nodes():
                    return None
                try:
                    gap = atoms[0].to_nm()
                except ValueError:
                    return None
        elif child.name != "gr_text":
            return None
    return DimensionStyle(None if gap == 500_000 else gap, units)


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


__all__ = ["NO_NET", "DimensionStyle", "TextStyle", "dimension_style", "graphic_net", "text_style"]
