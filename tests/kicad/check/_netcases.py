# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0020 on the netlist oracle (capability kicad-oracle, "Netlist oracle from
IPC-D-356"): ``netlist-partition`` and ``netlist-label-collision``, settling ``H-K-NET-IPC``.

Each case writes its project into a fresh temporary folder and runs ``pcb export ipcd356`` once per
session through ``KicadOracle.netlist``.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from pathlib import Path

import _fixtures as fx
from _checkcases import runner, workdir
from _projects import STEM, authored_project

from fenolite.backends.base import NetlistOutcome
from fenolite.backends.kicad.ipcd356 import read_ipcd356
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.checks.assignment_compare import board_netlist, compare
from fenolite.model.design import Design

COLLIDING = ("R1-1", "U1-1", "R1-2", "D1-2")
"""The pads on the two nets that ``long_names`` renames."""


def board(root: Path) -> Design:
    name = f"{STEM}.kicad_pcb"
    return read_board((root / name).read_text(encoding="utf-8"), file=name)


@cache
def authored() -> Path:
    return authored_project(workdir("netlist"), major=runner().major(), built=True)


@cache
def collision() -> Path:
    return fx.long_names(workdir("netlist-collision"), major=runner().major())


@cache
def netlist(root: Path) -> NetlistOutcome:
    return KicadOracle(runner()).netlist(project_set(root), board=board(root))


def partition() -> str:
    """``equal`` when every numbered pad of the authored built project is assigned by the export and the
    export's partition equals the board's."""
    outcome = netlist(authored())
    if outcome.netlist is None:
        return "inconclusive"
    listed, _ = board_netlist(board(authored()))
    if outcome.netlist.uncovered or {a.element for a in outcome.netlist.assignments} != {
        a.element for a in listed.assignments
    }:
        return "different"
    return "equal" if not compare(listed, outcome.netlist).differences else "different"


def export_labels(root: Path) -> dict[str, set[str]]:
    """The raw export label of each pad element of ``root``'s board, by truncated key."""
    project = project_set(root)
    others = {name: path for name, path in project.files.items() if name != project.board}
    export = read_ipcd356(runner().export_ipcd356(root / project.board, files=others))
    found: dict[str, set[str]] = {}
    for record in export.records:
        found.setdefault(f"{record.ref}-{record.pin}", set()).add(record.net)
    return found


def label_collision() -> str:
    """``equal`` when the export gives the two long-named nets one label, ``different`` otherwise."""
    labels = export_labels(collision())
    if any(element not in labels for element in COLLIDING):
        return "inconclusive"
    first = labels["R1-1"] | labels["U1-1"]
    second = labels["R1-2"] | labels["D1-2"]
    return "equal" if first == second and len(first) == 1 else "different"


def net_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    both = (9, 10)
    return {"netlist-partition": (partition, both), "netlist-label-collision": (label_collision, both)}


__all__ = ["COLLIDING", "authored", "board", "collision", "export_labels", "net_probes", "netlist"]
