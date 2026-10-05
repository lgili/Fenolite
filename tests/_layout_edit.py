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
from collections.abc import Callable
from fractions import Fraction

from fenolite.backends.kicad.netnames import stored_name
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


def _edit_footprint(text: str, ref: str, change: Callable[[Node], Node]) -> str:
    root = parse(text)
    children: list[Node | Atom] = []
    found = 0
    for child in root.children:
        if isinstance(child, Node) and child.name == "footprint" and _reference(child) == ref:
            child = change(child)
            found += 1
        children.append(child)
    assert found == 1, f"{ref}: {found} footprints"
    return dumps(root.with_children(children), style="kicad")


def move_property(text: str, ref: str, name: str, dx: Nm, dy: Nm) -> str:
    """``text`` with the property ``name`` of the footprint of ``ref`` moved by ``(dx, dy)``."""

    def change(fp: Node) -> Node:
        return fp.with_children(
            [
                _shift_at(c, dx, dy)
                if isinstance(c, Node) and c.name == "property" and c.atoms()[0].value == name
                else c
                for c in fp.children
            ]
        )

    return _edit_footprint(text, ref, change)


def add_to_footprint(text: str, ref: str, item: str) -> str:
    """``text`` with the node ``item`` appended inside the footprint of ``ref``."""
    return _edit_footprint(text, ref, lambda fp: fp.with_children([*fp.children, parse(item)]))


def footprint_node(text: str, ref: str) -> Node:
    """The ``footprint`` node of ``ref``."""
    (found,) = [
        c
        for c in parse(text).children
        if isinstance(c, Node) and c.name == "footprint" and _reference(c) == ref
    ]
    return found


def node_uuid(node: Node) -> str:
    found = node.find("uuid")
    assert found is not None
    return found.atoms()[0].value


def add_group(text: str, uuid: str, *refs: str, name: str = "") -> str:
    """``text`` with a root ``group`` of uuid ``uuid`` whose members are the footprints of ``refs``."""
    members = " ".join(f'"{node_uuid(footprint_node(text, ref))}"' for ref in refs)
    return add_items(text, f'(group "{name}" (uuid "{uuid}") (members {members}))')


def group_members(text: str, uuid: str) -> list[str]:
    """The member uuids of the root group ``uuid``, in order."""
    (group,) = [
        c for c in parse(text).children if isinstance(c, Node) and c.name == "group" and node_uuid(c) == uuid
    ]
    members = group.find("members")
    assert members is not None
    return [a.value for a in members.atoms()]


def add_items(text: str, *items: str) -> str:
    """``text`` with each item text appended as a root child, before the closing parenthesis."""
    root = parse(text)
    return dumps(root.with_children([*root.children, *(parse(item) for item in items)]), style="kicad")


def net_ref(text: str, name: str, *, zone: bool = False, pad: bool = False) -> str:
    """The reference of net ``name`` in the form ``text`` uses (a ``net_name`` follows for a 9.0 zone, and a
    9.0 pad names the net after its number)."""
    name = stored_name(name)  # a board stores a slash of a net name as {slash} (c0061)
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


def _symbols(schematic_text: str) -> tuple[str, dict[str, tuple[int, str, dict[str, str]]]]:
    """The project name of a schematic, and per reference the lowest unit with its uuid and field texts."""
    found: dict[str, tuple[int, str, dict[str, str]]] = {}
    project = ""
    for symbol in parse(schematic_text).nodes("symbol"):
        fields = {p.atoms()[0].value: p.atoms()[1].value for p in symbol.nodes("property")}
        unit = int(symbol.find("unit").atoms()[0].value)  # type: ignore[union-attr]
        uuid = symbol.find("uuid").atoms()[0].value  # type: ignore[union-attr]
        instances = symbol.find("instances")
        if instances is not None and instances.find("project") is not None:
            project = instances.find("project").atoms()[0].value  # type: ignore[union-attr]
        ref = fields.get("Reference", "")
        if ref not in found or unit < found[ref][0]:
            found[ref] = (unit, uuid, fields)
    return project, found


def update_from_schematic(board_text: str, schematic_text: str) -> str:
    """The stand-in for KiCad's "Update PCB from Schematic" (c0061 Decision 18; ``H-K-SCH-UPDATE``).

    Each footprint whose reference a symbol of the schematic has gets ``(sheetname "/")`` and
    ``(sheetfile "<project>.kicad_sch")``, its ``path`` set to ``/<symbol uuid>`` (the symbol's lowest
    unit), and each of its properties that the symbol also has rewritten with the symbol's text. Nothing
    else changes. What the real update writes is the maintainer's report, not this function.
    """
    project, symbols = _symbols(schematic_text)
    root = parse(board_text)
    out: list[Node | Atom] = []
    for child in root.children:
        ref = _reference(child) if isinstance(child, Node) and child.name == "footprint" else None
        if not isinstance(child, Node) or ref is None or ref not in symbols:
            out.append(child)
            continue
        _, uuid, fields = symbols[ref]
        sheet = [parse('(sheetname "/")'), parse(f'(sheetfile "{project}.kicad_sch")')]
        path = parse(f'(path "/{uuid}")')
        kids: list[Node | Atom] = []
        placed = False
        for kid in child.children:
            if isinstance(kid, Node) and kid.name in ("sheetname", "sheetfile"):
                continue
            if isinstance(kid, Node) and kid.name == "property":
                atoms = [a for a in kid.children if isinstance(a, Atom)]
                if len(atoms) >= 2 and atoms[0].value in fields and atoms[1].value != fields[atoms[0].value]:
                    parts = list(kid.children)
                    parts[parts.index(atoms[1])] = Atom.string(fields[atoms[0].value])
                    kid = kid.with_children(parts)
            if isinstance(kid, Node) and kid.name == "path":
                kids += [path, *sheet]
                placed = True
                continue
            if (
                not placed
                and isinstance(kid, Node)
                and (
                    kid.name in ("attr", "pad", "zone", "group", "model", "embedded_fonts")
                    or kid.name.startswith("fp_")
                )
            ):
                kids += [path, *sheet]
                placed = True
            kids.append(kid)
        if not placed:
            kids += [path, *sheet]
        out.append(child.with_children(kids))
    return dumps(root.with_children(out), style="kicad")


__all__ = [
    "D1_SHIFT",
    "EDIT_UUIDS",
    "ZONE_UUID",
    "add_filled_zone",
    "add_group",
    "add_items",
    "add_to_footprint",
    "edit_blink",
    "footprint_node",
    "group_members",
    "move_footprint",
    "move_property",
    "net_ref",
    "node_uuid",
    "pad_position",
    "update_from_schematic",
]
