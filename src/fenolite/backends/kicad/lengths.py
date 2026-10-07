# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The length of a net as KiCad's DRC counts it (capability board-frame, "KiCad net lengths"; facts:
``docs/formats/kicad/length.md``; user guide ``docs/analyses.md``, "Length").

KiCad's length of a net is the centre-line length of all its tracks and arcs, plus one height per via,
plus the die length of each of its pads. The two majors count a via apart (``H-K-NETLEN-VIA10``,
``H-K-NETLEN-VIA9``), so every function takes the major. The depths of the copper layers come from
``Board.stackup``, else from the default stack-up KiCad assumes for a file without one
(``H-K-NETLEN-STACKUP``).

Everything here computes on the design it is given; only ``length_facts`` opens a file, the project file
of the ``ProjectSet`` it is handed, to read one switch and the major.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from fractions import Fraction
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Literal

from fenolite.backends.base import BoardPad, LengthFacts, NetLength, ProjectSet
from fenolite.backends.kicad import pcb, pro, versions
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.sexpr import AtomKind, Node
from fenolite.backends.kicad.slots import from_ext, opaque_child
from fenolite.backends.kicad.stackup import copper_names
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import BBox, GeometryError, Thick, arc_length, segment_length, thick_bbox, thick_touch
from fenolite.model.base import Entity, Opaque
from fenolite.model.board import Board, Via
from fenolite.model.design import Design

EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=("H-K-NETLEN-STACKUP", "H-K-NETLEN-TOTAL", "H-K-NETLEN-VIA10", "H-K-NETLEN-VIA9"),
)
"""Stays ``INFERRED`` when the four rows are verified: they cover benches, not every board."""

DEFAULT_COPPER_NM = 35_000
"""The thickness of every copper layer of the default stack-up."""
DEFAULT_MASKS_NM = 20_000
"""What the default stack-up takes off the board thickness for its two masks."""
ARC_TOL_NM = 1_000
"""The chord error of the polyline an arc is tested with against a via's disc."""

DEFAULT_STACKUP = "kicad.length.default-stackup"
BAD_DIE = "kicad.length.bad-die"
LENGTH_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({DEFAULT_STACKUP: "info", BAD_DIE: "warning"})
"""The closed table of the codes this module gives."""

StackupSource = Literal["board", "default", "none"]
_HEIGHTS_KEY = ("board", "design_settings", "rules", "use_height_for_length_calcs")


def _issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, LENGTH_ISSUE_CODES[code], message, where=where, hint=hint)


def _half_even(value: Fraction) -> int:
    floor = value.numerator // value.denominator
    rest = value - floor
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and floor % 2):
        return floor + 1
    return floor


def _opaque(entity: Entity, name: str) -> Node | None:
    """The first opaque child ``name`` of the node an entity was read from."""
    bag = entity.ext.get("kicad")
    if bag is None:
        return None
    for slot in from_ext(bag):
        if isinstance(slot, Opaque) and slot.fragment.lstrip("( \t").startswith(name):
            child = opaque_child(slot)
            if isinstance(child, Node) and child.name == name:
                return child
    return None


# --- depths ---------------------------------------------------------------------------------------


def board_thickness(board: Board) -> Nm:
    """The ``(general (thickness …))`` of the file the board was read from, else the thickness the writer
    writes for a board without a stack-up. It is what KiCad counts, not a value of the model."""
    general = _opaque(board, "general")
    node = general.find("thickness") if general is not None else None
    atoms = node.atoms() if node is not None else ()
    if atoms and atoms[0].kind == AtomKind.NUMBER:
        try:
            value = atoms[0].to_nm(exact=False)
        except ValueError:
            value = 0
        if value > 0:
            return value
    return pcb.DEFAULT_THICKNESS


def has_unread_stackup(board: Board) -> bool:
    """Whether the file the board was read from holds a stack-up node that the reader projected no
    stack-up from (``kicad.board.stackup-unused``). KiCad 10.0.6 still counts the thicknesses of such a
    node for via heights (probe ``length-via-four-unprojected``), so neither the default stack-up nor any
    other depth is claimed for it."""
    if board.stackup is not None:
        return False
    setup = _opaque(board, "setup")
    return setup is not None and setup.find("stackup") is not None


def _rows(board: Board) -> tuple[list[tuple[str | None, Fraction]], StackupSource]:
    """The copper and dielectric rows from top to bottom as (copper layer name or ``None``, thickness),
    and where they come from. No rows when they cannot be known."""
    copper = copper_names(board.layers)
    stack = board.stackup
    if stack is not None:
        rows = [
            (entry.name if entry.kind == "copper" else None, Fraction(entry.thickness))
            for entry in stack.layers
            if entry.kind in ("copper", "dielectric")
        ]
        named = [name for name, _ in rows if name is not None]
        if len(named) < 2 or named != list(copper):
            return [], "none"
        return rows, "board"
    count = len(copper)
    if count < 2 or has_unread_stackup(board):
        return [], "none"
    dielectric = Fraction(board_thickness(board) - DEFAULT_MASKS_NM - count * DEFAULT_COPPER_NM, count - 1)
    if dielectric <= 0:
        return [], "none"
    made: list[tuple[str | None, Fraction]] = []
    for index, name in enumerate(copper):
        made.append((name, Fraction(DEFAULT_COPPER_NM)))
        if index < count - 1:
            made.append((None, dielectric))
    return made, "default"


def layer_depths(board: Board, *, major: int) -> tuple[Mapping[str, Nm], StackupSource]:
    """The depth of each copper layer as KiCad ``major`` counts it, and where the thicknesses come from.

    On 9 every copper layer lies at the thickness above it plus half its own. On 10 the same holds for
    inner layers, while the first copper layer lies at 0 and the last at the sum of every copper and
    dielectric thickness. Each depth is computed exactly and rounded half to even once. Mask, paste and
    silkscreen entries do not count. The mapping is empty, with ``none``, when the depths are unknown: a
    stack-up that does not hold the board's copper layers, or a file whose stack-up node was not read."""
    rows, source = _rows(board)
    if not rows:
        return MappingProxyType({}), "none"
    names = [name for name, _ in rows if name is not None]
    total = sum((thickness for _, thickness in rows), Fraction(0))
    depths: dict[str, Nm] = {}
    above = Fraction(0)
    for name, thickness in rows:
        if name is not None:
            if major >= 10 and name == names[0]:
                depths[name] = 0
            elif major >= 10 and name == names[-1]:
                depths[name] = _half_even(total)
            else:
                depths[name] = _half_even(above + thickness / 2)
        above += thickness
    return MappingProxyType(depths), source


# --- die lengths and the project switch -------------------------------------------------------------


def die_lengths(design: Design, *, issues: list[Issue] | None = None) -> Mapping[str, Nm]:
    """Pad id → die length in nm, from the opaque ``(die_length X)`` of each pad (``X`` in millimetres). A
    pad without one has no entry; a value that is not a non-negative decimal gives one
    ``kicad.length.bad-die`` and counts as 0."""
    found: dict[str, Nm] = {}
    board = design.board
    if board is None:
        return MappingProxyType(found)
    refs = {c.id: c.ref for c in design.circuit.components}
    for footprint in board.footprints:
        for pad in footprint.pads:
            node = _opaque(pad, "die_length")
            if node is None:
                continue
            atoms = node.atoms()
            text = atoms[0].text if atoms else ""
            value: Fraction | None = None
            if atoms and atoms[0].kind == AtomKind.NUMBER:
                try:
                    value = Fraction(text) * 1_000_000
                except (ValueError, ZeroDivisionError):
                    value = None
            if value is None or value < 0:
                if issues is not None:
                    name = f"{refs.get(footprint.component_id, '?')}-{pad.number}"
                    issues.append(
                        _issue(
                            BAD_DIE,
                            f"pad {name} holds the die length {text!r}, which is not a non-negative "
                            "decimal of millimetres; it counts as 0",
                            pad.id,
                            "correct the die length of the pad in KiCad's pad properties",
                        )
                    )
                continue
            if value > 0:
                found[pad.id] = _half_even(value)
    return MappingProxyType(found)


def counts_via_heights(project_text: str | None) -> bool:
    """False exactly when the project file sets ``board.design_settings.rules.use_height_for_length_calcs``
    to ``false``; true without a project file, for a text that does not parse, and without the key."""
    if project_text is None:
        return True
    try:
        value: object = pro.read_project_text(project_text)
    except FormatError:
        return True
    for key in _HEIGHTS_KEY:
        if not isinstance(value, dict):
            return True
        value = value.get(key)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return value is not False


# --- via joins --------------------------------------------------------------------------------------

_Shape = tuple[str, BBox, Thick]


def _net_shapes(
    design: Design, pads: Sequence[BoardPad], nets: Collection[str] | None
) -> dict[str, list[_Shape]]:
    """Net id → the copper that can join a via: its tracks and arcs on copper layers and the copper entries
    of its pads, each with its layer and box. Zone fills are not copper a via joins."""
    board = design.board
    found: dict[str, list[_Shape]] = {}
    if board is None:
        return found
    copper = set(copper_names(board.layers))

    def add(net_id: str | None, layer: str, shape: Thick) -> None:
        if net_id is None or layer not in copper or (nets is not None and net_id not in nets):
            return
        found.setdefault(net_id, []).append((layer, thick_bbox(shape), shape))

    for track in board.tracks:
        try:
            add(track.net_id, track.layer, Thick((track.start, track.end), max(track.width, 0)))
        except (GeometryError, ValueError):
            continue
    for arc in board.arcs:
        try:
            core = GeoArc(arc.start, arc.mid, arc.end).polygonize(ARC_TOL_NM)
        except GeometryError:
            core = (arc.start, arc.end)
        try:
            add(arc.net_id, arc.layer, Thick(core, max(arc.width, 0)))
        except (GeometryError, ValueError):
            continue
    for pad in pads:
        for entry in pad.copper:
            try:
                add(pad.net_id, entry.layer, Thick(entry.core, entry.width, entry.filled))
            except (GeometryError, ValueError):
                continue
    return found


def via_span(via: Via, copper: Sequence[str]) -> tuple[str, ...]:
    """The copper layers a via reaches, in table order: every one for a through via, those from its first
    to its last layer for another kind."""
    order = {name: index for index, name in enumerate(copper)}
    ends = [order[name] for name in via.layers if name in order]
    if via.via_type == "through" or len(ends) < 2:
        return tuple(copper)
    return tuple(copper[min(ends) : max(ends) + 1])


def _joined(via: Via, shapes: Iterable[_Shape], copper: Sequence[str]) -> tuple[str, ...]:
    span = set(via_span(via, copper))
    try:
        disc = Thick((via.position,), max(via.diameter, 1))
    except (GeometryError, ValueError):
        return ()
    box = thick_bbox(disc)
    hit: set[str] = set()
    for layer, other, shape in shapes:
        if layer in hit or layer not in span:
            continue
        if other.x0 > box.x1 or other.x1 < box.x0 or other.y0 > box.y1 or other.y1 < box.y0:
            continue
        if thick_touch(disc, shape):
            hit.add(layer)
    return tuple(name for name in copper if name in hit)


def joined_layers(design: Design, via: Via, pads: Sequence[BoardPad]) -> tuple[str, ...]:
    """The copper layers of the via's span, in table order, on which a track or an arc of its net, or a
    copper entry of a pad of its net, touches the via's disc."""
    board = design.board
    if board is None or via.net_id is None:
        return ()
    shapes = _net_shapes(design, pads, (via.net_id,))
    return _joined(via, shapes.get(via.net_id, ()), copper_names(board.layers))


def via_height(
    via: Via, joined: Collection[str], depths: Mapping[str, Nm], copper: Sequence[str], *, major: int
) -> Nm:
    """The height a via adds to its net's length. On 10: the depth difference between the first and the
    last joined layer in table order, 0 below two. On 9: the depth difference between the via's own two end
    layers when both are joined, else 0. A layer without a depth joins nothing."""
    span = via_span(via, copper)
    present = [name for name in span if name in joined and name in depths]
    if major >= 10:
        return abs(depths[present[-1]] - depths[present[0]]) if len(present) >= 2 else 0
    if len(span) < 2 or span[0] not in present or span[-1] not in present:
        return 0
    return abs(depths[span[-1]] - depths[span[0]])


# --- nets -------------------------------------------------------------------------------------------


def net_lengths(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    depths: Mapping[str, Nm],
    major: int,
    count_vias: bool = True,
    nets: Collection[str] | None = None,
    die: Mapping[str, Nm] | None = None,
) -> Mapping[str, NetLength]:
    """Net name → its length, for every net with a pad, a track, an arc or a via on the board, or only for
    those named in ``nets``. ``die`` holds the die lengths per pad id (``die_lengths`` when ``None``)."""
    board = design.board
    if board is None:
        return MappingProxyType({})
    names = {net.id: net.name for net in design.circuit.nets}
    wanted = {net_id for net_id, name in names.items() if nets is None or name in nets}
    copper = copper_names(board.layers)
    on_copper = set(copper)
    die_of = die_lengths(design) if die is None else die
    routed: dict[str, int] = {}
    heights: dict[str, int] = {}
    dies: dict[str, int] = {}
    counts: dict[str, int] = {}
    seen: set[str] = set()

    def wants(net_id: str | None) -> bool:
        return net_id is not None and net_id in wanted

    for track in board.tracks:
        if wants(track.net_id) and track.layer in on_copper:
            key = track.net_id or ""
            seen.add(key)
            routed[key] = routed.get(key, 0) + segment_length(track.start, track.end)
    for arc in board.arcs:
        if wants(arc.net_id) and arc.layer in on_copper:
            key = arc.net_id or ""
            seen.add(key)
            routed[key] = routed.get(key, 0) + arc_length(arc.start, arc.mid, arc.end)
    for pad in pads:
        if wants(pad.net_id):
            key = pad.net_id or ""
            seen.add(key)
            dies[key] = dies.get(key, 0) + die_of.get(pad.pad_id, 0)
    vias = [via for via in board.vias if wants(via.net_id)]
    shapes = (
        _net_shapes(design, pads, {via.net_id or "" for via in vias})
        if vias and count_vias and depths
        else {}
    )
    for via in vias:
        key = via.net_id or ""
        seen.add(key)
        counts[key] = counts.get(key, 0) + 1
        if count_vias and depths:
            joined = _joined(via, shapes.get(key, ()), copper)
            heights[key] = heights.get(key, 0) + via_height(via, joined, depths, copper, major=major)
    found: dict[str, NetLength] = {}
    for net_id in sorted(seen, key=lambda item: names[item]):
        r, v, d = routed.get(net_id, 0), heights.get(net_id, 0), dies.get(net_id, 0)
        found[names[net_id]] = NetLength(names[net_id], r, v, d, r + v + d, counts.get(net_id, 0))
    return MappingProxyType(found)


def _project_text(project: ProjectSet | None) -> str | None:
    if project is None:
        return None
    path = project.files.get(PurePosixPath(project.board).with_suffix(".kicad_pro").as_posix())
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _major(given: int | None, project_text: str | None, design: Design) -> int:
    """The argument; else the major of the project file; else that of the board's source format; else the
    default target."""
    if given is not None:
        return given
    if project_text is not None:
        try:
            found = pro.read_project(project_text).major
        except FormatError:
            found = None
        if found is not None:
            return found
    info = pcb.source_info(design)
    if info is not None and info.major is not None:
        return info.major
    return versions.DEFAULT_TARGET


def length_facts(
    design: Design,
    *,
    project: ProjectSet | None = None,
    major: int | None = None,
    nets: Collection[str] | None = None,
    issues: list[Issue] | None = None,
) -> LengthFacts:
    """The lengths of the nets of ``design`` as KiCad ``major`` counts them (``LengthSource``). Never
    raises for a project file that fails to read: via heights then count, as without one."""
    text = _project_text(project)
    chosen = _major(major, text, design)
    count_vias = counts_via_heights(text)
    board = design.board
    if board is None:
        return LengthFacts({}, {}, {}, chosen, "none", count_vias, EVIDENCE)
    depths, source = layer_depths(board, major=chosen)
    if source == "default" and issues is not None:
        thickness = board_thickness(board)
        issues.append(
            _issue(
                DEFAULT_STACKUP,
                f"the board holds no stack-up, so via heights are counted on the default stack-up KiCad "
                f"assumes: copper layers of {DEFAULT_COPPER_NM // 1000} µm and equal dielectrics in a board "
                f"of {thickness // 1000} µm",
                "/board/stackup",
                "declare the stack-up in the design script, or set it in KiCad's Board Setup",
            )
        )
    die = die_lengths(design, issues=issues)
    pads = board_pads(design)
    found = net_lengths(
        design, pads=pads, depths=depths, major=chosen, count_vias=count_vias, nets=nets, die=die
    )
    return LengthFacts(found, depths, die, chosen, source, count_vias, EVIDENCE)


__all__ = [
    "ARC_TOL_NM",
    "BAD_DIE",
    "DEFAULT_COPPER_NM",
    "DEFAULT_MASKS_NM",
    "DEFAULT_STACKUP",
    "EVIDENCE",
    "LENGTH_ISSUE_CODES",
    "board_thickness",
    "counts_via_heights",
    "has_unread_stackup",
    "die_lengths",
    "joined_layers",
    "layer_depths",
    "length_facts",
    "net_lengths",
    "via_height",
    "via_span",
]
