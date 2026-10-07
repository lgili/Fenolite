# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The bench of the copper locks (change c0108; capability kicad-oracle, "Copper locks pass the oracle";
``H-K-LOCK-FORM``).

One net between pads ``1`` of two ``Mini_R_0603`` copies: a locked segment, a locked via, a locked arc and
an unlocked segment, joined end to end. ``lock_bench(target, locked=False)`` is the same copper without a
lock. Built with ``_rulebench.Builder``; nothing is committed besides this module.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import kicad_uuid, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, walk
from fenolite.core.coords import Point
from fenolite.model.board import Arc
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
MM = rb.MM
NET = "LOCKS"
HALF_TURN = 180_000_000
KINDS = ("segment", "arc", "via")
SEGMENT_ORDER = ("start", "end", "width", "locked", "layer", "net", "uuid")
ARC_ORDER = ("start", "mid", "end", "width", "locked", "layer", "net", "uuid")
VIA_ORDER = ("at", "size", "drill", "layers", "locked", "net", "uuid")


@cache
def lock_bench(target: int, *, locked: bool = True) -> tuple[Design, dict[str, str]]:
    """The bench and the KiCad uuid of ``locked-segment``, ``locked-arc``, ``locked-via`` and
    ``free-segment``."""
    builder = rb.Builder()
    y = builder.row()
    builder.part("a", "RA", Point(rb.LEFT, y), target=target, nets={"1": NET}, rotation=HALF_TURN)
    builder.part("b", "RB", Point(rb.RIGHT, y), target=target, nets={"1": NET})
    centres = {pad.ref: pad.position for pad in board_pads(builder.build().design) if pad.number == "1"}
    a, b = centres["RA"], centres["RB"]
    first, second = Point(a.x + 2 * MM, y), Point(b.x - 2 * MM, y)
    builder.track("locked-segment", NET, y, x0=a.x, x1=first.x)
    builder.via("locked-via", NET, first)
    arc = Arc(
        id="arc_00000000-0000-4000-8000-000000000001",
        start=first,
        mid=Point((first.x + second.x) // 2, y + (second.x - first.x) // 2),
        end=second,
        width=rb.WIDTH,
        layer="F.Cu",
        net_id=builder.net(NET),
    )
    builder.arcs.append(arc)
    builder.track("free-segment", NET, y, x0=second.x, x1=b.x)
    if locked:
        builder.tracks[0] = dataclasses.replace(builder.tracks[0], locked=True)
        builder.vias[0] = dataclasses.replace(builder.vias[0], locked=True)
        builder.arcs[0] = dataclasses.replace(builder.arcs[0], locked=True)
    uuids = {
        "locked-segment": kicad_uuid(builder.tracks[0]),
        "locked-via": kicad_uuid(builder.vias[0]),
        "locked-arc": kicad_uuid(builder.arcs[0]),
        "free-segment": kicad_uuid(builder.tracks[1]),
    }
    return builder.build().design, uuids


def copper_nodes(text: str) -> dict[str, Node]:
    """The ``segment``, ``arc`` and ``via`` nodes of a board text by their uuid."""
    found: dict[str, Node] = {}
    for _locator, node in walk(parse(text)):
        if node.name in KINDS:
            uuid = node.find("uuid")
            if uuid is not None and uuid.atoms():
                found[uuid.atoms()[0].value] = node
    return found


def children(node: Node) -> tuple[str, ...]:
    return tuple(child.name for child in node.nodes())


def compact(node: Node) -> str:
    return dumps(node, style="compact")


def lock_first(text: str) -> str:
    """``text`` with ``(locked yes)`` as the first child of the first segment, arc and via: a token edit
    of a board without locks."""
    out = text
    for kind in KINDS:
        head = f"\t({kind}\n"
        assert head in out, kind
        out = out.replace(head, f"{head}\t\t(locked yes)\n", 1)
    return out


def _runner() -> KicadCli:
    from _probes import runner  # _probes imports this module

    return runner()


def _saved(runner: KicadCli, text: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "locks.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        return runner.upgrade_board(board).decode("utf-8")


@cache
def resaved() -> tuple[str, str]:
    """Fenolite's text of the locked bench for target 10, and that text re-saved by ``pcb upgrade
    --force``."""
    written = write_board(lock_bench(10)[0], target=10).text
    return written, _saved(_runner(), written)


@cache
def resaved_lock_first() -> str:
    """The bench without locks, a lock inserted as the first child of one item of each kind, re-saved."""
    written = write_board(lock_bench(10, locked=False)[0], target=10).text
    return _saved(_runner(), lock_first(written))


def form_outcome() -> str:
    """Probe ``pcb-lock-form`` (major 10): the four items keep the children Fenolite wrote and their
    uuids when KiCad saves the board again."""
    written, saved = resaved()
    ours, theirs = copper_nodes(written), copper_nodes(saved)
    uuids = lock_bench(10)[1].values()
    same = all(uuid in theirs and compact(ours[uuid]) == compact(theirs[uuid]) for uuid in uuids)
    return "equal" if same else "different"


def _report(runner: KicadCli, design: Design, target: int) -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "locks.kicad_pcb"
        board.write_text(write_board(design, target=target).text, encoding="utf-8")
        (folder / "locks.kicad_pro").write_text(rb.PROJECT, encoding="utf-8")
        return runner.drc(board, files={"locks.kicad_pro": folder / "locks.kicad_pro"}).report


@cache
def reports() -> tuple[DrcReport | None, DrcReport | None]:
    """The DRC reports of the bench with and without locks, written for the running major."""
    runner = _runner()
    target = runner.major()
    return (
        _report(runner, lock_bench(target)[0], target),
        _report(runner, lock_bench(target, locked=False)[0], target),
    )


def load_outcome() -> str:
    """Probe ``pcb-lock-load``: the locked bench loads and is judged as the bench without locks."""
    locked, free = reports()
    if locked is None or free is None:
        return "reject"
    return "equal" if locked.entries() == free.entries() else "different"


def lock_probes() -> Probes:
    """The lock probes. ``pcb-lock-load`` is pinned for the major whose results file was written with it;
    the test file runs it on every major."""
    return {"pcb-lock-form": (form_outcome, (10,)), "pcb-lock-load": (load_outcome, (10,))}


__all__ = [
    "ARC_ORDER",
    "SEGMENT_ORDER",
    "VIA_ORDER",
    "children",
    "copper_nodes",
    "form_outcome",
    "load_outcome",
    "lock_bench",
    "lock_first",
    "lock_probes",
    "reports",
    "resaved",
    "resaved_lock_first",
]
