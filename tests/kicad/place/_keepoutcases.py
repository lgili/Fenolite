# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0113 (capability kicad-oracle, "Placement keep-outs are probed"): the
``place-keepout-*`` rows of ``_probes.PROBES``, which settle ``H-K-PLACE-KEEPOUT``.

Each case is one bench on ``_rulebench``: the probed part ``KP1`` at (20 mm, 20 mm), the control part
``KC1`` outside every area, and one rule area that forbids footprints, given in millimetres around the
probed part. The canary is the one scoped to its own net (c0071), so it never takes the place of the
violation under test. A ``nocrt-*`` case removes the courtyard of the probed part from the written text,
token by token. The verdict is read from the JSON report only: an ``items_not_allowed`` violation that
names the uuid of the probed footprint.

``Mini_R_0603`` at 0°: courtyard rectangle x −1.5..1.5 mm, y −0.75..0.75 mm (line centres, 0.05 mm stroke),
pad copper x 0.35..1.25 mm, Reference text above the courtyard. ``Mini_LED_THT_3mm``: courtyard
x −1.2..3.75 mm, y −2..2 mm, on the front only.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point
from fenolite.model.board import Keepout, Side
from fenolite.placement import legality

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
MM = 1_000_000
UM = 1_000
VIOLATION = "items_not_allowed"
PROBED, CONTROL = "KP1", "KC1"
AT = Point(20 * MM, 20 * MM)
CONTROL_AT = Point(32 * MM, 33 * MM)
BOARD_FILE = "bench.kicad_pcb"
Box = tuple[int, int, int, int]
"""An area as (x0, y0, x1, y1) in nanometres around the probed part."""
WHOLE: Box = (-3 * MM, -2 * MM, 3 * MM, 2 * MM)
WHOLE_THT: Box = (-3 * MM, -4 * MM, 6 * MM, 4 * MM)


def _from_x(x: int) -> Box:
    return (x, -2 * MM, 3 * MM, 2 * MM)


@dataclass(frozen=True)
class Case:
    """One bench: the area and its copper layers, how the probed part is placed, and what KiCad's DRC is
    expected to say about it (measurement 1 of the design, 2026-10-05)."""

    area: Box
    layers: tuple[str, ...]
    expected: str
    side: Side = "top"
    rotation: int = 0
    footprint: str = "Mini_R_0603"
    courtyard: bool = True
    copper_layers: int = 2


CASES: Mapping[str, Case] = {
    "in": Case(WHOLE, ("F.Cu",), "present"),
    "crt-only": Case(_from_x(1_300 * UM), ("F.Cu",), "present"),
    "over-10um": Case(_from_x(1_490 * UM), ("F.Cu",), "present"),
    "touch": Case(_from_x(1_500 * UM), ("F.Cu",), "absent"),
    "gap-10um": Case(_from_x(1_510 * UM), ("F.Cu",), "absent"),
    "gap-30um": Case(_from_x(1_530 * UM), ("F.Cu",), "absent"),
    "text-only": Case((-3 * MM, -2_500 * UM, 3 * MM, -850 * UM), ("F.Cu",), "absent"),
    "rot-crt": Case(_from_x(900 * UM), ("F.Cu",), "absent", rotation=90_000_000),
    "bot-front": Case(WHOLE, ("F.Cu",), "absent", side="bottom"),
    "bot-back": Case(WHOLE, ("B.Cu",), "present", side="bottom"),
    "bot-both": Case(WHOLE, ("F.Cu", "B.Cu"), "present", side="bottom"),
    "top-back": Case(WHOLE, ("B.Cu",), "absent"),
    "inner-only": Case(WHOLE, ("In1.Cu",), "absent", copper_layers=4),
    "tht-front": Case(WHOLE_THT, ("F.Cu",), "present", footprint="Mini_LED_THT_3mm"),
    "tht-back": Case(WHOLE_THT, ("B.Cu",), "absent", footprint="Mini_LED_THT_3mm"),
    "nocrt-in": Case(WHOLE, ("F.Cu",), "absent", courtyard=False),
    "nocrt-pad": Case((300 * UM, -600 * UM, 1_300 * UM, 600 * UM), ("F.Cu",), "absent", courtyard=False),
    "nocrt-mid": Case((-300 * UM, -1 * MM, 300 * UM, 1 * MM), ("F.Cu",), "absent", courtyard=False),
}
"""The 18 cases. ``touch`` puts the area's edge on the line centre of the courtyard; the two gaps lie
inside the 0.05 mm stroke; ``rot-crt`` would meet the courtyard at 0° and misses it at 90°; ``text-only``
covers the Reference text and ends 0.1 mm above the courtyard."""
PRESENT = frozenset(name for name, case in CASES.items() if case.expected == "present")


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def target() -> int:
    return 10 if runner().major() >= 10 else 9


def keepout(case: Case) -> Keepout:
    x0, y0, x1, y1 = case.area
    ring = (
        Point(AT.x + x0, AT.y + y0),
        Point(AT.x + x1, AT.y + y0),
        Point(AT.x + x1, AT.y + y1),
        Point(AT.x + x0, AT.y + y1),
    )
    return Keepout(
        id="kpo_00000000-0000-4000-8000-000000000001", outline=ring, layers=case.layers, no_footprints=True
    )


@cache
def bench(name: str, board_target: int) -> rb.Bench:
    """The bench of case ``name`` for ``board_target``: the canary, the probed part, the control part and
    the rule area."""
    case = CASES[name]
    made = rb.builder()
    made.row()
    made.part(
        "probed",
        PROBED,
        AT,
        target=board_target,
        nets={},
        footprint=case.footprint,
        side=case.side,
        rotation=case.rotation,
    )
    made.part("control", CONTROL, CONTROL_AT, target=board_target, nets={})
    built = made.build()
    board = built.design.board
    assert board is not None
    board = dataclasses.replace(board, layers=created_layers(case.copper_layers), keepouts=(keepout(case),))
    return rb.Bench(dataclasses.replace(built.design, board=board), built.items)


def _without_courtyard(node: Node, ref: str) -> Node:
    """``node`` (a board) without the courtyard graphics of the footprint ``ref``."""

    def is_ref(fp: Node) -> bool:
        for child in fp.nodes("property"):
            atoms = child.atoms()
            if len(atoms) > 1 and atoms[0].value == "Reference" and atoms[1].value == ref:
                return True
        return False

    def on_courtyard(item: Node) -> bool:
        layer = item.find("layer")
        return (
            item.name.startswith("fp_")
            and layer is not None
            and bool(layer.atoms())
            and layer.atoms()[0].value.endswith(".CrtYd")
        )

    children: list[Node | Atom] = []
    for child in node.children:
        if isinstance(child, Node) and child.name == "footprint" and is_ref(child):
            kept = [c for c in child.children if not (isinstance(c, Node) and on_courtyard(c))]
            assert len(kept) < len(child.children), "the footprint has no courtyard to remove"
            children.append(child.with_children(kept))
        else:
            children.append(child)
    return node.with_children(children)


@cache
def board_text(name: str, board_target: int) -> str:
    """The board of case ``name`` as written for ``board_target``; a ``nocrt-*`` case without the courtyard
    of the probed part."""
    text = write_board(bench(name, board_target).design, target=board_target).text
    if CASES[name].courtyard:
        return text
    return dumps(_without_courtyard(parse(text), PROBED))


def report(name: str) -> DrcReport | None:
    """``pcb drc`` on the bench of ``name`` for the running major, with the scoped canary rule."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / BOARD_FILE
        board.write_text(board_text(name, target()), encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(rb.PROJECT, encoding="utf-8")
        (folder / "bench.kicad_dru").write_text(rb.with_scoped_canary("(version 1)\n"), encoding="utf-8")
        files = {"bench.kicad_pro": folder / "bench.kicad_pro", "bench.kicad_dru": folder / "bench.kicad_dru"}
        return runner().drc(board, files=files).report


@dataclass(frozen=True)
class Verdict:
    """What one DRC run says: whether the canary fired, and whether an ``items_not_allowed`` violation
    names the probed footprint and the control footprint."""

    canary: bool
    probed: bool
    control: bool


@cache
def verdict(name: str) -> Verdict | None:
    found = report(name)
    if found is None:
        return None
    made = bench(name, target())
    named = {item.uuid for v in found.violations if v.type == VIOLATION for item in v.items}
    return Verdict(
        rb.canary_fired(found, made),
        bool(named & set(made.uuids("probed:footprint"))),
        bool(named & (set(made.uuids("control:footprint")) | set(made.uuids("control")))),
    )


def outcome(name: str) -> str:
    """``present`` when the DRC names the probed footprint, ``absent`` otherwise; ``inconclusive`` when the
    canary did not fire or the control part was named."""
    found = verdict(name)
    if found is None:
        return "reject"
    if not found.canary or found.control:
        return "inconclusive"
    return rb.outcome(found.probed)


@cache
def legality_verdict(name: str, board_target: int) -> tuple[bool, bool]:
    """Whether ``placement.legality.check`` gives ``place.keepout`` and ``place.keepout-no-courtyard`` for
    the probed part, on the board of the case read back from its written text."""
    design = read_board(board_text(name, board_target), file=BOARD_FILE)
    assert design.board is not None
    names = {fp.id: footprint_ref(design, fp) for fp in design.board.footprints}
    issues = legality.check(
        KicadBackend().placed_extents(design),
        board_outline(design).rings,
        names=names,
        keepouts=design.board.keepouts,
    )
    assert not [i for i in issues if i.where == CONTROL], issues
    codes = {i.code for i in issues if i.where == PROBED}
    return "place.keepout" in codes, "place.keepout-no-courtyard" in codes


def agreement() -> str:
    """``equal`` when the legality check reports ``place.keepout`` for exactly the cases whose probe
    recorded ``present`` on the running major."""
    from _probes import run  # _probes imports this module

    board_target = target()
    for name in CASES:
        recorded = run(f"place-keepout-{name}")
        if recorded not in ("present", "absent"):
            return "inconclusive"
        if legality_verdict(name, board_target)[0] != (recorded == "present"):
            return "different"
    return "equal"


def keepout_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {f"place-keepout-{name}": (lambda name=name: outcome(name), both) for name in CASES}
    probes["place-keepout-agree"] = (agreement, both)
    return probes


__all__ = [
    "CASES",
    "CONTROL",
    "PRESENT",
    "PROBED",
    "agreement",
    "bench",
    "board_text",
    "keepout_probes",
    "legality_verdict",
    "outcome",
    "verdict",
]
