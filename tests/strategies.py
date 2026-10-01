# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hypothesis strategies shared by the tests: lengths, angles, ids, small valid designs and geometry."""

from __future__ import annotations

import random
from dataclasses import replace

from hypothesis import strategies as st

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.geometry import Arc, GeometryError, Transform, convex_hull
from fenolite.model import (
    Board,
    Component,
    Design,
    FootprintInstance,
    Layer,
    Net,
    NetClass,
    Pad,
    Pin,
    PinRef,
    Track,
    Via,
)

lengths = st.integers(min_value=-(10**9), max_value=10**9)
positive_lengths = st.integers(min_value=1, max_value=10**8)
angles = st.integers(min_value=-360_000_000, max_value=360_000_000)
points = st.builds(Point, lengths, lengths)
names = st.text(alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ0123456789_", min_size=1, max_size=8)


@st.composite
def designs(draw: st.DrawFn, max_components: int = 5) -> Design:
    """A small structurally valid design (no validation errors)."""
    seed = draw(st.integers(min_value=0, max_value=2**32 - 1))
    rng = random.Random(seed)
    design = Design.new(draw(names), seed=seed)
    netclass = NetClass(id=new_id("cls", rng), name="default", clearance=draw(positive_lengths))
    count = draw(st.integers(min_value=1, max_value=max_components))
    components: list[Component] = []
    for index in range(count):
        pins = tuple(Pin(id=new_id("pin", rng), number=str(n + 1)) for n in range(draw(st.integers(1, 3))))
        properties = draw(st.dictionaries(names, names, max_size=2))
        components.append(
            Component(id=new_id("cmp", rng), ref=f"U{index + 1}", pins=pins, properties=properties)
        )
    all_pins = [PinRef(c.id, p.number) for c in components for p in c.pins]
    n_nets = draw(st.integers(min_value=1, max_value=max(1, len(all_pins) // 2)))
    nets = []
    for index in range(n_nets):
        members = tuple(sorted(all_pins[index::n_nets]))
        nets.append(Net(id=new_id("net", rng), name=f"N{index}", netclass_id=netclass.id, members=members))
    net_of = {m: n.id for n in nets for m in n.members}
    footprints = []
    for component in components:
        pads = tuple(
            Pad(
                id=new_id("pad", rng),
                number=pin.number,
                shape="rect",
                size=Size(500_000, 600_000),
                position=Point(int(pin.number) * 1_000_000, 0),
                layers=("F.Cu",),
                net_id=net_of.get(PinRef(component.id, pin.number)),
            )
            for pin in component.pins
        )
        footprints.append(
            FootprintInstance(
                id=new_id("fp", rng),
                component_id=component.id,
                lib_ref="Lib:FP",
                position=draw(points),
                rotation=draw(angles),
                pads=pads,
            )
        )
    tracks = tuple(
        Track(
            id=new_id("trk", rng),
            start=draw(points),
            end=draw(points),
            width=draw(positive_lengths),
            layer=draw(st.sampled_from(["F.Cu", "B.Cu"])),
            net_id=draw(st.sampled_from([n.id for n in nets])),
        )
        for _ in range(draw(st.integers(0, 4)))
    )
    vias = tuple(
        Via(
            id=new_id("via", rng),
            position=draw(points),
            diameter=600_000,
            drill=300_000,
            layers=("F.Cu", "B.Cu"),
        )
        for _ in range(draw(st.integers(0, 2)))
    )
    layers = (
        Layer(id=new_id("lay", rng), name="F.Cu", kind="copper", ordinal=0),
        Layer(id=new_id("lay", rng), name="B.Cu", kind="copper", ordinal=31),
    )
    board = design.board or Board(id=new_id("brd", rng))
    board = replace(board, layers=layers, footprints=tuple(footprints), tracks=tracks, vias=vias)
    circuit = replace(design.circuit, components=tuple(components), nets=tuple(nets), netclasses=(netclass,))
    return replace(design, circuit=circuit, board=board)


# --- geometry -------------------------------------------------------------------------------------

small_coords = st.integers(min_value=-1000, max_value=1000)
small_points = st.builds(Point, small_coords, small_coords)
"""Points in a ±1 µm square: dense enough to hit collinear and touching cases."""


@st.composite
def rings(draw: st.DrawFn, max_size: int = 12) -> tuple[Point, ...]:
    """Simple convex rings in normal form (positive orientation), from the convex hull of random points."""
    pts = draw(st.lists(small_points, min_size=3, max_size=max_size))
    hull = convex_hull(pts)
    if len(hull) < 3:
        hull = (Point(0, 0), Point(10, 0), Point(0, 10))
    return hull


def _arc_or_none(points: tuple[Point, Point, Point]) -> Arc | None:
    try:
        return Arc(*points)
    except GeometryError:
        return None


def arcs(coords: st.SearchStrategy[int] = lengths) -> st.SearchStrategy[Arc]:
    """Valid three-point arcs (straight ones included when the points happen to be collinear)."""
    point = st.builds(Point, coords, coords)
    valid = st.tuples(point, point, point).map(_arc_or_none).filter(lambda a: a is not None)
    return valid  # type: ignore[return-value]


transforms = st.builds(
    Transform.placement,
    st.builds(Point, lengths, lengths),
    angles,
    st.booleans(),
)


# --- KiCad S-expressions --------------------------------------------------------------------------


def kicad_strings(max_size: int = 20) -> st.SearchStrategy[str]:
    """Any text without NUL or surrogates: quotes, backslashes, controls, non-ASCII."""
    chars = st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00")
    special = st.sampled_from(
        ['"', "\\", "\n", "\r", "\t", "\x0b", "\x01", "\x7f", "é", "日", "(", ")", "#", " "]
    )
    return st.text(alphabet=st.one_of(chars, special), max_size=max_size)


_SYMBOL_START = "abcdefghijklmnopqrstuvwxyzABCDEFXYZ_.:/#$*+-{}~!@%&'`=\\|<>?,;^"
_SYMBOL_REST = _SYMBOL_START + '0123456789"é'


def _symbol_atom(text: str) -> Atom | None:
    try:
        return Atom(text, AtomKind.SYMBOL)
    except ValueError:
        return None


symbol_atoms = (
    st.builds(
        lambda a, b: a + b, st.sampled_from(list(_SYMBOL_START)), st.text(alphabet=_SYMBOL_REST, max_size=8)
    )
    .map(_symbol_atom)
    .filter(lambda a: a is not None)
)
number_atoms = st.one_of(
    st.integers(-(10**12), 10**12).map(Atom.from_nm),
    st.integers(-(10**9), 10**9).map(Atom.integer),
    st.from_regex(r"-?([0-9]{1,4}\.?[0-9]{0,8}|\.[0-9]{1,6})([eE][-+]?[0-9]{1,2})?", fullmatch=True).map(
        lambda text: Atom(text, AtomKind.NUMBER)
    ),
)
string_atoms = kicad_strings().map(Atom.string)
atoms = st.one_of(symbol_atoms, number_atoms, string_atoms)  # type: ignore[arg-type]
heads = st.one_of(symbol_atoms, st.sampled_from([Atom.symbol(n) for n in ("pts", "xy", "at", "kicad_pcb")]),
                  st.integers(0, 64).map(Atom.integer))  # fmt: skip


def _xy() -> st.SearchStrategy[Node]:
    return st.builds(lambda x, y: Node(Atom.symbol("xy"), (x, y)), number_atoms, number_atoms)


def _nodes(children: st.SearchStrategy[list[Node | Atom]]) -> st.SearchStrategy[Node]:
    return st.builds(lambda h, c: Node(h, tuple(c)), heads, children)


nested_nodes = st.recursive(
    _nodes(st.lists(atoms, max_size=4)) | _xy(),
    lambda inner: (
        _nodes(st.lists(st.one_of(atoms, inner), max_size=6))
        | st.builds(
            lambda c: Node(Atom.symbol("pts"), tuple(c)), st.lists(st.one_of(_xy(), inner), max_size=8)
        )
    ),
    max_leaves=25,
)
comment_lines = st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r\n"),
                        max_size=10).map(lambda s: "#" + s)  # fmt: skip


@st.composite
def sexpr_trees(draw: st.DrawFn) -> Node:
    """Trees with comments on the root only."""
    root = draw(nested_nodes)
    comments = tuple(draw(st.lists(comment_lines, max_size=2)))
    return Node(root.head, root.children, comments=comments)
