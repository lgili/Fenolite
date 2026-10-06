# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Estimated boxes of what a written schematic sheet draws as text, and the pairs that overlap (change
c0070, "Readable sheet layout": the texts of a readable sheet are clear of each other).

Nothing here runs a tool: the boxes are estimated from the file text alone, each one larger than what
KiCad draws.

- **Reference and Value.** Every visible ``Reference`` and ``Value`` property of a symbol instance. A
  character is taken as wide as the font is high (``size``, 1.27 mm in a generated sheet; the glyphs of
  KiCad's font are narrower), and a line as ``LINE`` high, centred on the property's point. KiCad turns a
  field with its symbol: the text is drawn upright when exactly one of the symbol's angle and the field's
  angle is 90 or 270 degrees. A text without ``justify`` is centred on its point. A justified text of an
  unturned, unmirrored symbol starts at its point; for a turned or mirrored symbol KiCad may flip the
  side, so the box then covers both sides of the point.
- **Labels.** Every label: its text at one font size per character plus ``FRAME`` for the frame of a
  global label, from the label's point in the direction of its angle, ``HALF_LABEL`` to each side.
- **Bodies.** The box of the graphics and pins of every symbol instance (``schlayout.unit_bounds``).
- **Wire ends.** The two points of every wire.

Lengths are integer nanometres.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.backends.kicad import sch, schlayout
from fenolite.backends.kicad.schgen import unit_box
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.coords import Point

LINE = 2_000_000
"""The height of the box of one line of 1.27 mm text."""
FRAME = 2_540_000
"""Added to the length of a label's text for its frame."""
HALF_LABEL = 1_270_000
"""Half the width of a label's box, across its direction."""
TEXTS = ("Reference", "Value")
LABELS = ("global_label", "label", "hierarchical_label")
Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class Drawn:
    """One thing a sheet draws: ``kind`` is ``text``, ``label``, ``body`` or ``wire-end``; ``owner`` is
    the reference of its symbol (``""`` for a label or a wire end); ``box`` is ``(x0, y0, x1, y1)``."""

    kind: str
    name: str
    owner: str
    box: Box


def _at(item: Node) -> tuple[int, int, int]:
    at = item.find("at")
    assert at is not None
    atoms = at.atoms()
    angle = int(float(atoms[2].value)) % 360 if len(atoms) > 2 else 0
    return atoms[0].to_nm(), atoms[1].to_nm(), angle


def _effects(item: Node) -> tuple[int, str, bool]:
    """The font size, the horizontal justification (``""`` when centred) and whether the text is hidden."""
    effects = item.find("effects")
    size, justify = 1_270_000, ""
    hidden = _yes(item.find("hide"))
    if effects is not None:
        font = effects.find("font")
        if font is not None and (found := font.find("size")) is not None:
            size = found.atoms()[0].to_nm()
        if (side := effects.find("justify")) is not None:
            justify = next((a.value for a in side.atoms() if a.value in ("left", "right")), "")
        hidden = hidden or _yes(effects.find("hide"))
    return size, justify, hidden


def _yes(node: Node | None) -> bool:
    return node is not None and (not node.atoms() or node.atoms()[0].value == "yes")


def _text_box(prop: Node, turn: int, mirrored: bool) -> Box | None:
    size, justify, hidden = _effects(prop)
    text = prop.atoms()[1].value
    if hidden or not text:
        return None
    x, y, angle = _at(prop)
    length, half = len(text) * size, LINE * size // 1_270_000 // 2
    upright = (angle in (90, 270)) != (turn in (90, 270))
    if not justify:
        low, high = -(length // 2) - 1, length // 2 + 1
    elif turn or mirrored:
        low, high = -length, length
    elif upright:  # reads upwards: a left-justified text starts at its point and ends above it
        low, high = (-length, 0) if justify == "left" else (0, length)
    else:
        low, high = (0, length) if justify == "left" else (-length, 0)
    if upright:
        return (x - half, y + low, x + half, y + high)
    return (x + low, y - half, x + high, y + half)


def _label_box(label: Node) -> Box:
    size, _, _ = _effects(label)
    x, y, angle = _at(label)
    length = len(label.atoms()[0].value) * size + (FRAME if label.name == "global_label" else 0)
    dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[angle]
    ex, ey = x + dx * length, y + dy * length
    wide, high = (0, HALF_LABEL) if dy == 0 else (HALF_LABEL, 0)
    return (min(x, ex) - wide, min(y, ey) - high, max(x, ex) + wide, max(y, ey) + high)


def drawn(text: str) -> list[Drawn]:
    """Everything the sheet file ``text`` draws that a text may not lie on, in file order."""
    root = parse(text)
    sheet = sch.read_schematic(text)
    definitions = {f"{d.library}:{d.name}" if d.library else d.name: d for d in sheet.lib_symbols}
    found: list[Drawn] = []
    for wire in root.nodes("wire"):
        pts = wire.find("pts")
        assert pts is not None
        for index, xy in enumerate(pts.nodes("xy")):
            x, y = (a.to_nm() for a in xy.atoms())
            found.append(Drawn("wire-end", f"wire {index}", "", (x, y, x, y)))
    for head in LABELS:
        for label in root.nodes(head):
            found.append(Drawn("label", label.atoms()[0].value, "", _label_box(label)))
    for item in root.nodes("symbol"):
        lib_id = item.find("lib_id")
        assert lib_id is not None
        x, y, turn = _at(item)
        mirror = item.find("mirror")
        flip = mirror.atoms()[0].value if mirror is not None else ""
        unit = item.find("unit")
        props = {p.atoms()[0].value: p for p in item.nodes("property")}
        ref = props["Reference"].atoms()[1].value
        definition = definitions.get(lib_id.atoms()[0].value)
        if definition is not None:
            box = unit_box(ref, definition, unit.atoms()[0].to_int() if unit is not None else 1)
            x0, y0, x1, y1 = schlayout.unit_bounds(box, turn, flip)
            found.append(Drawn("body", ref, ref, (x + x0, y + y0, x + x1, y + y1)))
        for key in TEXTS:
            text_box = _text_box(props[key], turn, bool(flip)) if key in props else None
            if text_box is not None:
                found.append(Drawn("text", f"{ref} {key}", ref, text_box))
    return found


def _overlap(a: Box, b: Box) -> bool:
    """Whether two boxes share more than an edge; a point inside a box overlaps it."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def overlaps(text: str) -> list[str]:
    """One line per pair of the sheet file ``text`` in which a Reference or Value text lies on a label,
    on another text, on a symbol's body or pins, or on a wire end."""
    items = drawn(text)
    found: list[str] = []
    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            if "text" not in (first.kind, second.kind):
                continue
            a, b = first.box, second.box
            if first.kind == "wire-end" or second.kind == "wire-end":
                point, box = (a, b) if first.kind == "wire-end" else (b, a)
                hit = box[0] < point[0] < box[2] and box[1] < point[1] < box[3]
            else:
                hit = _overlap(a, b)
            if hit:
                found.append(f"{first.kind} {first.name} {a} and {second.kind} {second.name} {b}")
    return found


def written(text: str, ref: str, key: str) -> tuple[Point, int, str]:
    """How the property ``key`` of the symbol ``ref`` is written in the sheet file ``text``: its point,
    its angle in degrees and its horizontal justification (``""`` when centred)."""
    for item in parse(text).nodes("symbol"):
        props = {p.atoms()[0].value: p for p in item.nodes("property")}
        if "Reference" in props and props["Reference"].atoms()[1].value == ref:
            x, y, angle = _at(props[key])
            return Point(x, y), angle, _effects(props[key])[1]
    raise KeyError(ref)
