# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The round-trip level RT-A3 (capability altium-verification, "Round-trip level RT-A3"; change c0090): a
document is read into the model, the model is written as new documents, and those are read again.

``rt_a3`` judges one trip from its parts: the first model, what ``lower.write_design`` made of it, and the
model of the written documents. It touches no file: ``AltiumBackend.model_roundtrip`` reads the input,
writes the new documents into a temporary folder of its own and reads them. What the write left out is
taken out of the first model before the comparison and counted, so the verdict says whether the write
and the import agree on what was written, and the counts say what a rewritten document does not hold.
"""

# evidence: see roundtrip, import_evidence

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any

import fenolite.backends.altium.import_evidence as import_evidence
from fenolite.backends.altium.lower import FREE_PAD_REASON, ProjectWrite
from fenolite.backends.altium.roundtrip import (
    EVIDENCE_BODIES,
    EVIDENCE_RT_A3,
    RECORD_PREFIX,
    RT_A3_SCOPE,
)
from fenolite.backends.base import Change, ModelCompare, ModelRoundTrip
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import Transform
from fenolite.model.board import FootprintInstance
from fenolite.model.circuit import Component
from fenolite.model.design import Design

_BOARD_FIELDS: Mapping[str, str] = MappingProxyType(
    {"track": "tracks", "arc": "arcs", "via": "vias", "zone": "zones"}
)


def without_unwritten(design: Design, kept: Mapping[str, Sequence[str]], *, from_board: bool) -> Design:
    """``design`` without the entities whose ids ``kept`` lists per kind (``lower.AltiumInputs.not_lowered``):
    what a write left out and counted is not part of the comparison. A footprint that was not written goes
    with its pads, and a component body that was not written leaves its footprint (change c0121).
    ``from_board`` tells that the circuit was synthesised from the board (a PCB document
    read alone): then a component whose footprint was not written goes too, and a net loses the members
    whose pads were not written, as the second reading cannot hold them. The graphics and texts of a
    footprint that are counted under ``footprint-graphic``, ``footprint-copper`` and ``footprint-text`` go
    too (change c0126)."""
    board = design.board
    gone = {kind: frozenset(ids) for kind, ids in kept.items()}
    circuit = design.circuit
    lost_components: set[str] = set()
    lost_pins: set[tuple[str, str]] = set()
    if board is not None:
        footprints: list[Any] = []
        for footprint in board.footprints:
            if footprint.id in gone.get("footprint", ()):
                lost_components.add(footprint.component_id)
                continue
            pads = tuple(pad for pad in footprint.pads if pad.id not in gone.get("pad", ()))
            numbers = {pad.number for pad in pads}
            lost_pins |= {
                (footprint.component_id, pad.number) for pad in footprint.pads if pad.number not in numbers
            }
            bodies = tuple(body for body in footprint.bodies if body.id not in gone.get("body", ()))
            # the items of a footprint that the write left out and counted (change c0126)
            lost = gone.get("footprint-graphic", frozenset()) | gone.get("footprint-copper", frozenset())
            graphics = tuple(graphic for graphic in footprint.graphics if graphic.id not in lost)
            texts = tuple(text for text in footprint.texts if text.id not in gone.get("footprint-text", ()))
            footprints.append(
                dataclasses.replace(footprint, pads=pads, bodies=bodies, graphics=graphics, texts=texts)
            )
        changes: dict[str, Any] = {"footprints": tuple(footprints)}
        for kind, name in _BOARD_FIELDS.items():
            changes[name] = tuple(item for item in getattr(board, name) if item.id not in gone.get(kind, ()))
        board = dataclasses.replace(board, **changes)
    nets = [net for net in circuit.nets if net.id not in gone.get("net", ())]
    components = list(circuit.components)
    if from_board:
        components = [c for c in components if c.id not in lost_components]
        nets = [
            dataclasses.replace(
                net,
                members=tuple(
                    m
                    for m in net.members
                    if m.component_id not in lost_components and (m.component_id, m.pin) not in lost_pins
                ),
            )
            for net in nets
        ]
    # a pin-to-pad map that no footprint model of the generated schematic holds (change c0123)
    unmapped = gone.get("pin-pad-map", frozenset())
    components = [dataclasses.replace(c, pin_pad_map=()) if c.id in unmapped else c for c in components]
    classes = tuple(c for c in circuit.netclasses if c.id not in gone.get("netclass", ()))
    circuit = dataclasses.replace(circuit, components=tuple(components), nets=tuple(nets), netclasses=classes)
    return dataclasses.replace(design, circuit=circuit, board=board)


def _free_pad_view(design: Design, converted: Sequence[str] = ()) -> Design:
    """Represent exactly the reported detached pads as the reader's free-pad footprints.

    Anonymous footprints are ordered by geometry on both sides so inserting a detached pad cannot
    renumber an existing anonymous owner. Every pad and its position remain in the comparison.
    """
    if design.board is None:
        return design
    refs = {c.id: c.ref for c in design.circuit.components}
    footprints: list[FootprintInstance] = []
    components = list(design.circuit.components)
    for fp in design.board.footprints:
        detached = tuple(p for p in fp.pads if p.id in converted)
        footprints.append(dataclasses.replace(fp, pads=tuple(p for p in fp.pads if p.id not in converted)))
        frame = Transform.placement(fp.position, fp.rotation)
        for pad in detached:
            cid = "rta3-free-" + pad.id
            refs[cid] = ""
            components.append(Component(id=cid, ref=""))
            footprints.append(
                FootprintInstance(
                    id=cid,
                    component_id=cid,
                    lib_ref="",
                    position=frame.apply(pad.position),
                    attributes=("board_only",),
                    pads=(
                        dataclasses.replace(
                            pad, position=Point(0, 0), rotation=frame.apply_angle(pad.rotation)
                        ),
                    ),
                )
            )
    named = [fp for fp in footprints if refs.get(fp.component_id, fp.component_id)]
    anonymous = sorted(
        (fp for fp in footprints if not refs.get(fp.component_id, fp.component_id)),
        key=lambda fp: (
            fp.position.x,
            fp.position.y,
            fp.rotation,
            fp.side,
            tuple((p.number, p.position.x, p.position.y, p.size.w, p.size.h) for p in fp.pads),
        ),
    )
    order = {fp.component_id: i for i, fp in enumerate(anonymous)}
    named_components = [c for c in components if c.ref]
    anonymous_components = sorted(
        (c for c in components if not c.ref), key=lambda c: order.get(c.id, len(order))
    )
    return dataclasses.replace(
        design,
        board=dataclasses.replace(design.board, footprints=tuple(named + anonymous)),
        circuit=dataclasses.replace(
            design.circuit, components=tuple(named_components + anonymous_components)
        ),
    )


def unwritten_counts(written: ProjectWrite, census: Mapping[str, int]) -> dict[str, int]:
    """What the written documents do not hold, per kind: the model items that the write left out
    (``AltiumInputs.counts``), and under ``RECORD_PREFIX`` the records of the first reading that the import
    maps to no model entity (``census``: the categories of ``adapter.codes.Census``)."""
    counts: Counter[str] = Counter(written.inputs.counts())
    for category, count in census.items():
        counts[RECORD_PREFIX + category] += count
    return dict(sorted(counts.items()))


def rt_a3(
    first: Design,
    written: ProjectWrite,
    second: Design | None,
    *,
    compare: ModelCompare,
    census: Mapping[str, int] = MappingProxyType({}),
    from_board: bool = False,
    bodies: Callable[[Design, Design], Sequence[Change]] | None = None,
) -> ModelRoundTrip:
    """The verdict of one trip: ``first`` is the model of the document that was read, ``written`` what
    ``lower.write_design(first, allow_lossy=True)`` gave, and ``second`` the model of the written document
    of the kind that was read (``None`` when the write gave none: not judged, reason ``no-document``).
    The two models are compared with ``compare`` under ``RT_A3_SCOPE`` after ``without_unwritten``.
    ``unwritten`` never changes ``equal``. ``bodies`` (change c0121) is the comparison of the kind ``body``
    that the caller hands in when the write was asked for component bodies
    (``bodydiff.body_differences`` inside ``roundtrip.BODY_SCOPE``, as ``Change`` values), or ``None``: it
    is given the first model without the bodies that the write left out and the second reading, each
    difference is a ``/body/<n>``, and the evidence then names ``H-A-PCBX-BODY-READBACK``."""
    counts = unwritten_counts(written, census)
    done = dict(written.inputs.written)
    files = tuple(written.files)
    if second is None:
        return ModelRoundTrip(
            False, False, unwritten=counts, written=done, files=files, reason="no-document",
            evidence=Evidence(Level.UNVERIFIED),
        )  # fmt: skip
    reference = without_unwritten(first, written.inputs.not_lowered, from_board=from_board)
    detached = written.inputs.changed.get("pad", {}).get(FREE_PAD_REASON, ())
    if detached:
        reference = _free_pad_view(reference, detached)
        second = _free_pad_view(second)
    report = compare(reference, second, RT_A3_SCOPE)
    evidence = Evidence.combine(EVIDENCE_RT_A3, import_evidence.EVIDENCE)
    changes = report.changes
    if bodies is not None:
        changes = (*changes, *bodies(reference, second))
        evidence = Evidence.combine(evidence, EVIDENCE_BODIES)
    return ModelRoundTrip(True, not changes, changes, counts, done, files, evidence=evidence)


__all__ = ["rt_a3", "unwritten_counts", "without_unwritten"]
