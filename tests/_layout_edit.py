# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Token edits of a built board, the stand-in for work done in KiCad (c0019 Decision 20).

``edit_blink`` moves ``D1`` 4 mm to the right and routes ``LED_A`` from ``R1`` pad 2 by one ``F.Cu``
segment to a via and one ``B.Cu`` segment to ``D1`` pad 2, with the fixed uuids ``EDIT_UUIDS``.
``add_filled_zone`` adds a zone with two authored ``filled_polygon`` lists. Pad positions come from
``read_board`` of the text, so the items land on the pads whatever the target. Net references use the
form the board already uses: numbers with a table up to 9.0, names from board version 20251028.
"""

from __future__ import annotations

import re
from fractions import Fraction

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point
from fenolite.core.units import Nm, format_length
from fenolite.model.board import FootprintInstance

MM = 1_000_000
EDIT_UUIDS: tuple[str, str, str] = (
    "00000000-0000-4000-8000-0000000e0001",
    "00000000-0000-4000-8000-0000000e0002",
    "00000000-0000-4000-8000-0000000e0003",
)
"""The ``F.Cu`` segment, the ``B.Cu`` segment and the via of ``edit_blink``."""
ZONE_UUID = "00000000-0000-4000-8000-0000000e0010"
D1_SHIFT = 4 * MM


def mm(nm: Nm) -> str:
    return format_length(nm, "mm")[: -len("mm")]


def _reference(fp: Node) -> str | None:
    for prop in fp.nodes("property"):
        atoms = prop.atoms()
        if len(atoms) >= 2 and atoms[0].value == "Reference":
            return atoms[1].value
    return None


def _shift_at(node: Node, dx: Nm, dy: Nm) -> Node:
    children: list[Node | Atom] = []
    for child in node.children:
        if isinstance(child, Node) and child.name == "at":
            atoms = child.atoms()
            x = Fraction(atoms[0].value) + Fraction(dx, MM)
            y = Fraction(atoms[1].value) + Fraction(dy, MM)
            rest = [a.value for a in atoms[2:]]
            child = parse(f"(at {mm(int(x * MM))} {mm(int(y * MM))}{''.join(' ' + r for r in rest)})")
        children.append(child)
    return node.with_children(children)


def move_footprint(text: str, ref: str, dx: Nm, dy: Nm) -> str:
    """``text`` with the footprint of ``ref`` moved by ``(dx, dy)`` (its ``at``; children are relative)."""
    root = parse(text)
    children: list[Node | Atom] = []
    found = 0
    for child in root.children:
        if isinstance(child, Node) and child.name == "footprint" and _reference(child) == ref:
            child = _shift_at(child, dx, dy)
            found += 1
        children.append(child)
    assert found == 1, f"{ref}: {found} footprints"
    return dumps(root.with_children(children), style="kicad")


def add_items(text: str, *items: str) -> str:
    """``text`` with each item text appended as a root child, before the closing parenthesis."""
    root = parse(text)
    return dumps(root.with_children([*root.children, *(parse(item) for item in items)]), style="kicad")


def net_ref(text: str, name: str, *, zone: bool = False, pad: bool = False) -> str:
    """The reference of net ``name`` in the form ``text`` uses (a ``net_name`` follows for a 9.0 zone, and a
    9.0 pad names the net after its number)."""
    match = re.search(rf'^\t\(net (\d+) "{re.escape(name)}"\)', text, flags=re.M)
    if match is None:
        return f'(net "{name}")'
    number = match.group(1)
    if pad:
        return f'(net {number} "{name}")'
    return f'(net {number}) (net_name "{name}")' if zone else f"(net {number})"


def _footprint(text: str, ref: str) -> FootprintInstance:
    design = read_board(text)
    assert design.board is not None
    ids = {c.id: c.ref for c in design.circuit.components}
    (fp,) = [f for f in design.board.footprints if ids.get(f.component_id or "") == ref]
    return fp


def pad_position(text: str, ref: str, number: str) -> Point:
    """The board position of pad ``number`` of ``ref``: ``at`` plus the stored pad position, which a bottom
    footprint already holds mirrored (``H-G-BOTTOM-PLACE``); the blink parts are unrotated."""
    fp = _footprint(text, ref)
    (pad,) = [p for p in fp.pads if p.number == number]
    assert fp.rotation == 0, "the helper places items on unrotated parts only"
    return Point(fp.position.x + pad.position.x, fp.position.y + pad.position.y)


def edit_blink(text: str) -> str:
    """``D1`` moved 4 mm right, and ``LED_A`` routed from ``R1`` pad 2 through a via to ``D1`` pad 2."""
    moved = move_footprint(text, "D1", D1_SHIFT, 0)
    start = pad_position(moved, "R1", "2")
    end = pad_position(moved, "D1", "2")
    via = Point(start.x + 2 * MM, start.y)
    net = net_ref(moved, "LED_A")
    seg_f, seg_b, via_uuid = EDIT_UUIDS
    items = (
        f"(segment (start {mm(start.x)} {mm(start.y)}) (end {mm(via.x)} {mm(via.y)}) (width 0.25) "
        f'(layer "F.Cu") {net} (uuid "{seg_f}"))',
        f"(segment (start {mm(via.x)} {mm(via.y)}) (end {mm(end.x)} {mm(end.y)}) (width 0.25) "
        f'(layer "B.Cu") {net} (uuid "{seg_b}"))',
        f'(via (at {mm(via.x)} {mm(via.y)}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") {net} '
        f'(uuid "{via_uuid}"))',
    )
    return add_items(moved, *items)


def add_filled_zone(text: str, *, net: str, layer: str) -> str:
    """A zone on ``net`` and ``layer`` over the blink board (100–150 × 100–130 mm), with two authored
    ``filled_polygon`` lists."""
    ref = net_ref(text, net, zone=True)
    zone = (
        f'(zone {ref} (layer "{layer}") (uuid "{ZONE_UUID}") (name "{net}_{layer.split(".")[0]}") '
        "(hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) (filled_areas_thickness no) "
        "(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) "
        "(polygon (pts (xy 101 101) (xy 149 101) (xy 149 129) (xy 101 129))) "
        f'(filled_polygon (layer "{layer}") (pts (xy 101.5 101.5) (xy 148.5 101.5) '
        "(xy 148.5 128.5) (xy 101.5 128.5))) "
        f'(filled_polygon (layer "{layer}") (pts (xy 120 120) (xy 122 120) (xy 122 122) (xy 120 122))))'
    )
    return add_items(text, zone)


__all__ = [
    "D1_SHIFT",
    "EDIT_UUIDS",
    "ZONE_UUID",
    "add_filled_zone",
    "add_items",
    "edit_blink",
    "move_footprint",
    "net_ref",
    "pad_position",
]
