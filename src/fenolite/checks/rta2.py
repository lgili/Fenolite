# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``roundtrip.rta2`` stage (capability verification-loop, "Document check pipeline"; change c0044):
the model that a build stored against the readings of the documents the build wrote.

The built model is the reference. Its circuit kinds are compared with the schematic reading and its other
kinds with the PCB reading, through ``checks.diff.diff_designs`` under the backend's written scope. Since
change c0090 the built model holds the board that was written (footprints, pads, copper), so every kind of
the scope is compared and none is only counted; a model that a build stored before that change holds no
footprint, and ``predates_board`` tells so.
"""

from __future__ import annotations

from fenolite.backends.base import ModelScope, ProjectRead
from fenolite.checks.codes import issue
from fenolite.checks.diff import Change, diff_designs
from fenolite.checks.stages import StageResult, ran
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

CIRCUIT_KINDS = ("component", "net", "no_connect")
"""The kinds compared with the schematic reading; every other kind of a scope goes to the PCB reading (a
net class is a record of the PCB document: a schematic holds none)."""
BOARD_KINDS = (
    "layer", "footprint", "pad", "track", "arc", "via", "zone", "keepout", "text", "graphic", "hole",
    "stack_layer",
)  # fmt: skip
"""The kinds a board holds (``held`` counts them)."""
MAX_ISSUES = 50
"""The issues reported per side; ``summary.differences`` holds the full count."""
_SHOWN = 80


def held(design: Design) -> dict[str, int]:
    """The number of entities of each board kind that ``design`` holds."""
    board = design.board
    if board is None:
        return dict.fromkeys(BOARD_KINDS, 0)
    return {
        "layer": len(board.layers),
        "footprint": len(board.footprints),
        "pad": sum(len(footprint.pads) for footprint in board.footprints),
        "track": len(board.tracks),
        "arc": len(board.arcs),
        "via": len(board.vias),
        "zone": len(board.zones),
        "keepout": len(board.keepouts),
        "text": len(board.texts),
        "graphic": len(board.graphics),
        "hole": len(board.holes),
        "stack_layer": len(board.stackup.layers) if board.stackup is not None else 0,
    }


def predates_board(model: Design, reading: Design) -> bool:
    """Whether ``model`` was stored by a build older than change c0090: its board holds no footprint and
    the PCB document that the build wrote holds one."""
    return held(model)["footprint"] == 0 and held(reading)["footprint"] > 0


def _short(text: str) -> str:
    return text if len(text) <= _SHOWN else text[: _SHOWN - 1] + "…"


def _message(change: Change) -> str:
    if change.change == "changed":
        return f"the built model holds {_short(change.a)} and the written documents read {_short(change.b)}"
    if change.change == "removed":
        return "the built model holds this, and the written documents do not"
    return "the written documents hold this, and the built model does not"


def rta2_stage(model: Design, read: ProjectRead, scope: ModelScope) -> StageResult:
    """RT-A2 of a built project: ``model`` is the model the build stored, ``read`` the two readings of the
    documents it wrote, ``scope`` what the writers write. Each difference is one ``check.rta2-failed`` error
    whose ``where`` is the change's path behind ``schematic:`` or ``pcb:``, at most ``MAX_ISSUES`` per side.
    The summary holds ``level``, ``holds``, ``differences`` and ``compared`` (per side, the kinds
    compared: every kind of the scope). The caller sets the evidence and moves the PCB reading into the
    frame of the model."""
    issues: list[Issue] = []
    compared: dict[str, list[str]] = {}
    total = 0
    sides: tuple[tuple[str, Design | None, tuple[str, ...]], ...] = (
        ("schematic", None if read.schematic is None else read.schematic.design,
         tuple(kind for kind in scope.fields if kind in CIRCUIT_KINDS)),
        ("pcb", None if read.pcb is None else read.pcb.design,
         tuple(kind for kind in scope.fields if kind not in CIRCUIT_KINDS)),
    )  # fmt: skip
    for side, reading, kinds in sides:
        if reading is None:
            continue
        fields = {kind: scope.fields[kind] for kind in kinds}
        report = diff_designs(model, reading, scope=ModelScope(fields, scope.length_tolerance))
        compared[side] = sorted(kinds)
        total += len(report.changes)
        issues += [
            issue("check.rta2-failed", _message(change), where=f"{side}:{change.path}")
            for change in report.changes[:MAX_ISSUES]
        ]
    summary: dict[str, object] = {
        "level": "RT-A2",
        "holds": total == 0,
        "differences": total,
        "compared": compared,
    }
    return ran("roundtrip.rta2", issues, Evidence(), summary)


__all__ = ["BOARD_KINDS", "CIRCUIT_KINDS", "MAX_ISSUES", "held", "predates_board", "rta2_stage"]
