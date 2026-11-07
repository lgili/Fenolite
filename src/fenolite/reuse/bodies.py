# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""3D bodies copied between boards by pad fit (change c0175, task 10.4; design, "Additions from the
survey", package 10).

A placed footprint of the target board that has neither a body nor a model takes those of a placed footprint
of the reference board whose pads fit its own: the pads are paired by number (each number found once in both
footprints, the same numbers on both sides, at least two distinct places), and ``reuse.fit.fit_rigid`` finds
the quarter turn and the translation, in the footprint frame, that lay the reference pads on the target pads
within the tolerance. A mirrored fit is no fit: a body is never mirrored onto a pad set. The bodies and models
are then moved by that fit: an outline point ``p`` becomes ``T·p``, a model offset ``(x, y, z)`` becomes
``(T·(x, y), z)``, and its turn about Z gains the fit's turn (both counter-clockwise, as ``ModelRef``).
A model turned about X or Y is copied only by a fit without a turn, since the order of the three turns is not
modelled here.

Each fitted target names the turn it was copied with; ``BodyCopy.variants`` lists, per model, every turn it
was copied with: the rotation variants that a target which stores one model entry per rotation needs. Writing
those entries into an Altium document is not done here: it waits on the edit gates of change c0241 and on a
kit measurement of how a body's rotation selects its model-store entry (task 10.4 stays open for it).

Builds on ``H-G-REUSE-FIT`` (``INFERRED``); no tool judges a copied body, so the copy is ``INFERRED``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from fenolite.core.coords import Point
from fenolite.core.trig import QUARTER_TURN
from fenolite.core.units import Nm
from fenolite.model.board import ComponentBody, FootprintInstance, ModelRef, Pad
from fenolite.model.design import Design
from fenolite.reuse.fit import DEFAULT_TOLERANCE, Rigid, fit_rigid

BodyStatus = Literal["copied", "kept", "no-fit", "ambiguous", "tilted"]
"""What happened to a target footprint: ``copied`` (it took a reference's bodies and models), ``kept`` (it
already had a body or a model), ``no-fit`` (no reference footprint with a body fits its pads), ``ambiguous``
(fitting references would give different bodies) and ``tilted`` (the one fitting reference has a model turned
about X or Y and the fit turns it)."""


@dataclass(frozen=True, slots=True)
class BodyRow:
    """One placed footprint of the target board: its id, the reference footprint it took its bodies from
    (``None`` without one), what happened, the fit's quarter turns (0 to 3) and its largest pad distance."""

    target: str
    source: str | None
    status: BodyStatus
    turn: int = 0
    residual: Nm = 0


@dataclass(frozen=True, slots=True)
class BodyCopy:
    """The target design with the copied bodies, a row per placed footprint in board order, and per model
    name the sorted quarter turns it was copied with."""

    design: Design
    rows: tuple[BodyRow, ...]
    variants: tuple[tuple[str, tuple[int, ...]], ...]


def pad_fit(
    reference: Sequence[Pad], target: Sequence[Pad], *, tolerance: Nm = DEFAULT_TOLERANCE
) -> Rigid | None:
    """The unmirrored rigid fit, in the footprint frame, that lays the ``reference`` pads on the ``target``
    pads paired by number, or ``None``: other numbers, fewer than two pads with a number found once at two
    distinct places, a mirrored best fit or a pad farther than ``tolerance``."""
    numbers = Counter(pad.number for pad in reference)
    if numbers != Counter(pad.number for pad in target):
        return None
    goals = {pad.number: pad.position for pad in target if numbers[pad.number] == 1}
    pairs = [(pad.position, goals[pad.number]) for pad in reference if numbers[pad.number] == 1]
    if len({source for source, _ in pairs}) < 2:
        return None
    rigid = fit_rigid(pairs, tolerance=tolerance)
    if rigid.transform.mirror or rigid.residual > tolerance:
        return None
    return rigid


def _moved(
    footprint: FootprintInstance, rigid: Rigid
) -> tuple[tuple[ComponentBody, ...], tuple[ModelRef, ...]]:
    transform = rigid.transform
    bodies = tuple(
        replace(body, outline=tuple(transform.apply(point) for point in body.outline))
        for body in footprint.bodies
    )
    models: list[ModelRef] = []
    for model in footprint.models:
        x, y, z = model.offset
        moved = transform.apply(Point(x, y))
        rx, ry, rz = model.rotation
        models.append(
            replace(model, offset=(moved.x, moved.y, z), rotation=(rx, ry, transform.apply_angle(rz)))
        )
    return bodies, tuple(models)


def _tilted(footprint: FootprintInstance) -> bool:
    return any(model.rotation[0] or model.rotation[1] for model in footprint.models)


def copy_bodies(reference: Design, target: Design, *, tolerance: Nm = DEFAULT_TOLERANCE) -> BodyCopy:
    """Copy bodies and models onto every placed footprint of ``target`` that has none, from the placed
    footprints of ``reference`` whose pads fit its own (see the module). Nothing else of ``target`` changes;
    a board-less design gives no row."""
    sources = [
        footprint
        for footprint in (reference.board.footprints if reference.board is not None else ())
        if footprint.bodies or footprint.models
    ]
    if target.board is None:
        return BodyCopy(target, (), ())
    rows: list[BodyRow] = []
    placed: list[FootprintInstance] = []
    turns: dict[str, set[int]] = {}
    for footprint in target.board.footprints:
        if footprint.bodies or footprint.models:
            rows.append(BodyRow(footprint.id, None, "kept"))
            placed.append(footprint)
            continue
        fits = [
            (source, rigid)
            for source in sources
            if (rigid := pad_fit(source.pads, footprint.pads, tolerance=tolerance))
        ]
        if not fits:
            rows.append(BodyRow(footprint.id, None, "no-fit"))
            placed.append(footprint)
            continue
        source, rigid = min(fits, key=lambda item: (item[1].residual, item[0].id))
        turn = rigid.transform.rot_udeg // QUARTER_TURN
        moved = _moved(source, rigid)
        if any(_moved(other, fit) != moved for other, fit in fits):
            rows.append(BodyRow(footprint.id, None, "ambiguous", turn, rigid.residual))
            placed.append(footprint)
            continue
        if turn and _tilted(source):
            rows.append(BodyRow(footprint.id, source.id, "tilted", turn, rigid.residual))
            placed.append(footprint)
            continue
        bodies, models = moved
        placed.append(replace(footprint, bodies=bodies, models=models))
        rows.append(BodyRow(footprint.id, source.id, "copied", turn, rigid.residual))
        for name in {model.name for model in models} | {body.model for body in bodies if body.model}:
            turns.setdefault(name, set()).add(turn)
    design = replace(target, board=replace(target.board, footprints=tuple(placed)))
    variants = tuple((name, tuple(sorted(found))) for name, found in sorted(turns.items()))
    return BodyCopy(design, tuple(rows), variants)


__all__ = ["BodyCopy", "BodyRow", "BodyStatus", "copy_bodies", "pad_fit"]
