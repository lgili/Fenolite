# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The field benches (c0030; capability kicad-oracle, "Footprint fields pass the field oracle").

Unlike the probes of ``_fieldprobe`` (boards written as text, run before the model knew fields), these
boards go through the model: ``Mini_R_0603`` and ``Mini_QFP-32_7x7mm_P0.8mm`` placed with
``place_footprint``, references of ten characters in the library's 1 mm text, fields set with ``set_field``
or ``place_outside``, an outline with optional cut-outs, and ``write_board``. Each folder holds a project
file whose ``min_silk_clearance`` is 0.1 mm; nothing is committed.

Every verdict is read from the ``silk_edge_clearance`` items of one field, matched by the uuid of its
``property`` node, and every "no violation" verdict sits in a report whose crossing control fires.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _fieldprobe
from _boards import mm, square
from _triad import library

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.fields import DEFAULT_GAP, field_anchor, outside_box, place_outside, set_field
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board, FootprintField, FootprintInstance, Outline, Side
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
MM = 1_000_000
R, QFP = "Mini_R_0603", "Mini_QFP-32_7x7mm_P0.8mm"
PLACEMENTS: tuple[tuple[Side, int], ...] = (
    ("top", 0),
    ("top", 30),
    ("top", 90),
    ("bottom", 0),
    ("bottom", 30),
    ("bottom", 90),
)
SIDES = ("top", "bottom", "left", "right")
TOLERANCE = 10
"""Nanometres per axis between a DRC item position and ``field_anchor``."""
INSIDE = 100_000
"""How far inside the courtyard box the anchor of an outside control lies, on the top and bottom sides."""
INSIDE_SIDEWAYS = 1_000_000
"""The same on the left and right sides: sideways the ink of a text starts about 0.27 mm from its anchor
(the side bearing of the first glyph), so an anchor 0.1 mm inside the box leaves the ink 0.17 mm outside it
and KiCad reports nothing (measured on 9.0.9 and 10.0.6)."""
FIELD_VALUES = (
    "name",
    "position",
    "rotation",
    "layer",
    "size",
    "thickness",
    "visible",
    "h_justify",
    "v_justify",
    "mirrored",
    "native_ids",
)


@dataclass(frozen=True)
class Case:
    """One footprint of a bench: its group, its component and what its Reference is expected to give."""

    group: str
    key: str
    component: Component
    footprint: FootprintInstance
    expect: int
    unlocked: bool = False
    """Insert ``(unlocked yes)`` into the written Reference node (the keep-upright canary)."""

    @property
    def reference(self) -> FootprintField:
        return next(f for f in self.footprint.fields if f.name == "Reference")

    @property
    def uuid(self) -> str:
        return self.reference.native_ids["kicad"]


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


class _Placer:
    """Places footprints with ten-character references ``R000000001`` …, numbered in call order."""

    def __init__(self, target: int) -> None:
        self.target = target
        self.n = 0

    def place(
        self, name: str, at: Point, angle: int = 0, side: Side = "top"
    ) -> tuple[Component, FootprintInstance]:
        self.n += 1
        ref = f"R{self.n:09d}"
        defn = read_footprint(library(self.target) / f"{name}.kicad_mod", library="Mini")
        component = Component(id=_id("cmp", self.n), ref=ref, value=name, lib_footprint_ref=defn.lib_id)
        return component, place_footprint(
            defn, component=component, at=at, rotation=angle * MM, side=side, key=ref
        )


def _design(
    cases: Sequence[Case], width: float, height: float, cutouts: Sequence[tuple[Point, ...]] = ()
) -> Design:
    board = Board(
        id=_id("brd", 1),
        outline=Outline(id=_id("out", 1), points=square(0, 0, width, height), cutouts=tuple(cutouts)),
        layers=created_layers(2),
        footprints=tuple(case.footprint for case in cases),
    )
    circuit = Circuit(components=tuple(case.component for case in cases))
    return dataclasses.replace(Design.new("fields", seed=0), circuit=circuit, board=board)


# --- the edge bench: anchors, angle, justification, mirror, keep-upright, hidden ------------------

EDGE_SIZE = (160, 130)


@cache
def edge_cases(target: int) -> tuple[Case, ...]:
    placer = _Placer(target)
    cases: list[Case] = []
    row = 0

    def left(name: str, side: Side, angle: int) -> tuple[Component, FootprintInstance, int]:
        nonlocal row
        row += 1
        y = 5 + 5 * row
        component, footprint = placer.place(name, mm(20, y), angle, side)
        return component, footprint, y

    for name in (R, QFP):
        for side, angle in PLACEMENTS:
            component, footprint, y = left(name, side, angle)
            moved = set_field(footprint, "Reference", anchor=mm(0, y))
            cases.append(Case("anchors", f"{name}-{side}-{angle}", component, moved, 1))
    component, footprint, y = left(R, "top", 0)
    hidden = set_field(footprint, "Reference", anchor=mm(0, y), visible=False)
    cases.append(Case("hidden", "hidden", component, hidden, 0))
    for side, word, expect in (
        ("top", "left", 0),
        ("top", "right", 1),
        ("bottom", "left", 1),
        ("bottom", "right", 0),
    ):
        component, footprint, y = left(R, side, 0)  # type: ignore[arg-type]
        placed = set_field(footprint, "Reference", anchor=mm(1, y), angle=0, justify=(word, "center"))  # type: ignore[arg-type]
        cases.append(Case("justify", f"{side}-{word}", component, placed, expect))
    for unlocked in (False, True):
        component, footprint, y = left(R, "top", 0)
        turned = set_field(
            footprint, "Reference", anchor=mm(1, y), angle=180 * MM, justify=("left", "center")
        )
        cases.append(
            Case("upright", "unlocked" if unlocked else "kept", component, turned, int(unlocked), unlocked)
        )
    for x, angle, expect in ((60, 0, 0), (80, 90, 1)):
        component, footprint = placer.place(R, mm(x, 15), 90)
        turned = set_field(footprint, "Reference", anchor=mm(x, 2), angle=angle * MM)
        cases.append(Case("angle", f"board-{angle}", component, turned, expect))
    return tuple(cases)


@cache
def inside_cases(target: int) -> tuple[Case, ...]:
    """The anchor canaries with their Reference moved 40 mm inside the board, and one crossing control."""
    cases: list[Case] = []
    for case in edge_cases(target):
        if case.group != "anchors":
            continue
        anchor = field_anchor(case.footprint, case.reference)
        moved = set_field(case.footprint, "Reference", anchor=Point(40 * MM, anchor.y))
        cases.append(dataclasses.replace(case, group="inside", footprint=moved, expect=0))
    placer = _Placer(target)
    placer.n = 900
    component, footprint = placer.place(R, mm(20, 5))
    control = set_field(footprint, "Reference", anchor=mm(0, 5))
    cases.append(Case("control", "control", component, control, 1))
    return tuple(cases)


# --- the outside bench: place_outside beside a cut-out equal to the courtyard box -----------------

OUTSIDE_PITCH = (40, 18)
OUTSIDE_COLUMNS = 5


def _ring(footprint: FootprintInstance) -> tuple[Point, ...]:
    box = outside_box(footprint)
    return (Point(box.x0, box.y0), Point(box.x1, box.y0), Point(box.x1, box.y1), Point(box.x0, box.y1))


def _inside_anchor(footprint: FootprintInstance, side: str) -> Point:
    """A point within the box, ``INSIDE`` (``INSIDE_SIDEWAYS``) from the edge that ``side`` names."""
    box = outside_box(footprint)
    cx, cy = (box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2
    return {
        "top": Point(cx, box.y0 + INSIDE),
        "bottom": Point(cx, box.y1 - INSIDE),
        "left": Point(box.x0 + INSIDE_SIDEWAYS, cy),
        "right": Point(box.x1 - INSIDE_SIDEWAYS, cy),
    }[side]


@cache
def outside_cases(target: int) -> tuple[Case, ...]:
    placer = _Placer(target)
    wanted: list[tuple[str, str, Side, int, bool]] = []
    for side in SIDES:
        wanted += [(R, side, face, angle, False) for face, angle in PLACEMENTS]
        wanted += [(QFP, side, "top", 0, False), (QFP, side, "bottom", 30, False)]
        wanted += [(R, side, "top", 0, True), (R, side, "bottom", 0, True)]
    cases: list[Case] = []
    for index, (name, side, face, angle, control) in enumerate(wanted):
        column, row = index % OUTSIDE_COLUMNS, index // OUTSIDE_COLUMNS
        at = mm(25 + OUTSIDE_PITCH[0] * column, 15 + OUTSIDE_PITCH[1] * row)
        component, footprint = placer.place(name, at, angle, face)
        placed = place_outside(footprint, "Reference", side=side)  # type: ignore[arg-type]
        if control:
            placed = set_field(placed, "Reference", anchor=_inside_anchor(footprint, side))
        key = f"{name}-{side}-{face}-{angle}"
        cases.append(Case("control" if control else "outside", key, component, placed, int(control)))
    return tuple(cases)


def outside_size() -> tuple[float, float]:
    rows = -(-len(outside_cases(9)) // OUTSIDE_COLUMNS)
    return 50 + OUTSIDE_PITCH[0] * (OUTSIDE_COLUMNS - 1), 30 + OUTSIDE_PITCH[1] * (rows - 1)


# --- writing and judging --------------------------------------------------------------------------


def _unlock(text: str, uuids: Sequence[str]) -> str:
    """The board text with ``(unlocked yes)`` inserted after ``at`` in the property nodes of ``uuids``."""
    if not uuids:
        return text
    root = parse(text)
    done = 0

    def visit(node: Node) -> Node:
        nonlocal done
        if node.name == "property":
            uuid = node.find("uuid")
            if uuid is not None and uuid.atoms() and uuid.atoms()[0].value in uuids:
                at = node.find("at")
                assert at is not None
                children: list[Node | object] = []
                for child in node.children:
                    children.append(child)
                    if child is at:
                        children.append(parse("(unlocked yes)"))
                done += 1
                return node.with_children(children)  # type: ignore[arg-type]
            return node
        if node.name not in ("kicad_pcb", "footprint"):
            return node
        return node.with_children([visit(c) if isinstance(c, Node) else c for c in node.children])

    edited = visit(root)
    assert done == len(uuids)
    return dumps(edited, style="kicad")


def bench(name: str, target: int) -> tuple[tuple[Case, ...], Design]:
    if name == "edge":
        cases = edge_cases(target)
        return cases, _design(cases, *EDGE_SIZE)
    if name == "inside":
        cases = inside_cases(target)
        return cases, _design(cases, *EDGE_SIZE)
    cases = outside_cases(target)
    return cases, _design(cases, *outside_size(), cutouts=[_ring(case.footprint) for case in cases])


def bench_text(name: str, target: int) -> str:
    cases, design = bench(name, target)
    text = write_board(design, target=target).text
    return _unlock(text, [case.uuid for case in cases if case.unlocked])


@cache
def observed(name: str, target: int) -> dict[str, list[_fieldprobe.Hit]] | None:
    """Case key → the ``silk_edge_clearance`` items of its Reference, for one bench written for ``target``."""
    cases, _ = bench(name, target)
    report = _fieldprobe.drc(bench_text(name, target), 0.1)
    if report is None:
        return None
    by_uuid = _fieldprobe.hits(report)
    return {f"{case.group}:{case.key}": by_uuid.get(case.uuid, []) for case in cases}


def _found(name: str, target: int, group: str) -> list[tuple[Case, list[_fieldprobe.Hit]]] | None:
    hits = observed(name, target)
    if hits is None:
        return None
    cases, _ = bench(name, target)
    return [(case, hits[f"{case.group}:{case.key}"]) for case in cases if case.group == group]


def anchors_outcome(target: int) -> str:
    """``present`` when every crossing Reference gives one violation whose item names the field and lies
    within ``TOLERANCE`` of ``field_anchor``."""
    found = _found("edge", target, "anchors")
    if found is None:
        return "reject"
    if not any(hits for _, hits in found):
        return "absent"
    for case, hits in found:
        want = field_anchor(case.footprint, case.reference)
        if len(hits) != 1 or hits[0].description != f"Reference field of {case.component.ref}":
            return "different"
        if abs(hits[0].position.x - want.x) > TOLERANCE or abs(hits[0].position.y - want.y) > TOLERANCE:
            return "different"
    return "present"


def counts_outcome(name: str, target: int, group: str) -> str:
    """``present`` when every case of the group gives its expected count, ``different`` otherwise."""
    found = _found(name, target, group)
    if found is None:
        return "reject"
    return "present" if all(len(hits) == case.expect for case, hits in found) else "different"


def silent_outcome(name: str, target: int, group: str, control: tuple[str, str]) -> str:
    """``absent`` when no field of ``group`` is reported while every control of ``control`` (bench group) is;
    ``inconclusive`` when a control is silent."""
    found, controls = _found(name, target, group), _found(name, target, control[1])
    if found is None or controls is None:
        return "reject"
    if not controls or any(len(hits) != case.expect for case, hits in controls):
        return "inconclusive"
    return "absent" if not any(hits for _, hits in found) else "present"


# --- re-save on 10.0.6 ---------------------------------------------------------------------------


@cache
def resave_design() -> Design:
    """A target-10 bench whose fields were moved, turned, hidden, resized and justified."""
    placer = _Placer(10)
    cases: list[Case] = []
    for index, (side, angle) in enumerate(PLACEMENTS):
        component, footprint = placer.place(
            R if index % 2 == 0 else QFP, mm(20 + 25 * index, 30), angle, side
        )
        edited = set_field(
            footprint,
            "Reference",
            anchor=Point(footprint.position.x + 2 * MM, footprint.position.y - 8 * MM),
            angle=(45 * index) * MM,
            size=Size(800_000, 900_000),
            thickness=120_000,
            justify=("left", "bottom") if index % 2 == 0 else ("right", "top"),
        )
        edited = set_field(
            edited, "Value", visible=index % 2 == 1, layer="B.SilkS" if side == "bottom" else "F.SilkS"
        )
        edited = place_outside(edited, "Value", side=SIDES[index % 4], gap=DEFAULT_GAP)
        cases.append(Case("resave", f"{side}-{angle}", component, edited, 0))
    return _design(cases, 180, 60)


def field_values(design: Design) -> dict[str, tuple[object, ...]]:
    """Property uuid → the field's values. A re-save may write the footprints in another order, so the
    fields are compared by uuid."""
    assert design.board is not None
    return {
        field.native_ids["kicad"]: tuple(getattr(field, name) for name in FIELD_VALUES)
        for footprint in design.board.footprints
        for field in footprint.fields
    }


def resave_outcome() -> str:
    """``equal`` when the fields read from the re-saved board equal the written ones (uuids included)."""
    text = write_board(resave_design(), target=10).text
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "fields.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        project = Path(tmp) / "fields.kicad_pro"
        project.write_text(_fieldprobe.project_text(0.1), encoding="utf-8")
        saved = _fieldprobe.runner().upgrade_board(board, files={project.name: project}).decode("utf-8")
    written, again = read_board(text), read_board(saved)
    if saved == text:
        return "inconclusive"
    return "equal" if field_values(again) == field_values(written) else "different"


def bench_probes() -> Probes:
    probes: Probes = {"field-bench-resave": (resave_outcome, (10,))}
    for target, majors in ((9, (9, 10)), (10, (10,))):
        probes |= {
            f"field-bench-anchors-t{target}": (lambda t=target: anchors_outcome(t), majors),
            f"field-bench-inside-t{target}": (
                lambda t=target: silent_outcome("inside", t, "inside", ("inside", "control")),
                majors,
            ),
            f"field-bench-angle-t{target}": (lambda t=target: counts_outcome("edge", t, "angle"), majors),
            f"field-bench-justify-t{target}": (lambda t=target: counts_outcome("edge", t, "justify"), majors),
            f"field-bench-upright-t{target}": (lambda t=target: counts_outcome("edge", t, "upright"), majors),
            f"field-bench-hidden-t{target}": (
                lambda t=target: silent_outcome("edge", t, "hidden", ("edge", "anchors")),
                majors,
            ),
            f"field-bench-outside-t{target}": (
                lambda t=target: silent_outcome("outside", t, "outside", ("outside", "control")),
                majors,
            ),
        }
    return probes


EXPECTED: dict[str, str] = {
    "anchors": "present",
    "inside": "absent",
    "angle": "present",
    "justify": "present",
    "upright": "present",
    "hidden": "absent",
    "outside": "absent",
}

__all__ = [
    "EXPECTED",
    "Case",
    "anchors_outcome",
    "bench",
    "bench_probes",
    "bench_text",
    "edge_cases",
    "inside_cases",
    "observed",
    "outside_cases",
    "resave_design",
    "resave_outcome",
]
