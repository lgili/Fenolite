# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium arcs that draw a straight track, carried through KiCad (change c0485; capability
design-conversion, "A straight Altium arc is kept").

An arc record whose three points lie on one line (a very short arc) is the straight track it draws in a
model that has no centre and radius: the Altium writer writes it as a track (``lower.ARC_STRAIGHT``) and
``import --to python`` holds it as one (``import.arc-as-track``). A conversion to KiCad writes, in the board
property ``PROPERTY`` (``backends.kicad.boardcarrier``), each such arc's pair ``arc`` as the import keeps it
(centre, radius and angles as read, ``adapter.copper.arc_pair``) with its layer, width and net name. The
Altium writer writes that record for the track or straight arc of the same layer, width and net whose ends
are the record's in the written document's frame (``lower.kept_arc``). The ends find it, not a uuid: a
script's build gives its items other uuids.
"""

from __future__ import annotations

import json
from typing import cast

from fenolite.backends.altium.lower import ARC_KEY, KeptStraightArc, pairs_of, straight_arc
from fenolite.model.design import Design

PROPERTY = "Fenolite.Altium.StraightArcs"
"""The board property that carries the arc records (``boardcarrier``)."""
SCHEMA = "fenolite.altium-straight-arcs.v0"


def found(design: Design) -> list[KeptStraightArc]:
    """The arcs of ``design``'s board, read from an Altium document, whose three points lie on one line and
    that keep their record's pair."""
    board = design.board
    if board is None:
        return []
    names = {net.id: net.name for net in design.circuit.nets}
    return [
        KeptStraightArc(pair, arc.layer, arc.width, names.get(arc.net_id or ""))
        for arc in board.arcs
        if (pair := pairs_of(arc).get(ARC_KEY)) is not None and straight_arc(arc) is not None
    ]


def carrier_text(arcs: list[KeptStraightArc]) -> str:
    """The property's JSON text, one entry per arc, sorted."""
    rows = sorted(
        ({"arc": a.pair, "layer": a.layer, "width": a.width, "net": a.net} for a in arcs),
        key=lambda row: json.dumps(row, sort_keys=True),
    )
    return json.dumps({"schema": SCHEMA, "arcs": rows}, sort_keys=True, separators=(",", ":"))


def read_carrier(data: bytes | None) -> list[KeptStraightArc]:
    """The carried arcs; nothing for no property, another schema or text that is no carrier. An entry that
    is not well formed is left out: its track is then written as a track."""
    if not data:
        return []
    try:
        loaded: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return []
    root = cast("dict[str, object]", loaded) if isinstance(loaded, dict) else {}
    entries = root.get("arcs") if root.get("schema") == SCHEMA else None
    kept: list[KeptStraightArc] = []
    for entry in cast("list[object]", entries) if isinstance(entries, list) else []:
        row = cast("dict[str, object]", entry) if isinstance(entry, dict) else {}
        pair, layer, width, net = row.get("arc"), row.get("layer"), row.get("width"), row.get("net")
        if isinstance(pair, str) and isinstance(layer, str) and type(width) is int:
            if net is None or isinstance(net, str):
                kept.append(KeptStraightArc(pair, layer, width, net))
    return kept


__all__ = ["PROPERTY", "SCHEMA", "KeptStraightArc", "carrier_text", "found", "read_carrier"]
