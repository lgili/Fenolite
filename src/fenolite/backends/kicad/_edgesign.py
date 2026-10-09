# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edges of a model outline as texts, and the uuids that sign them (capability kicad-file-backend,
"Outline lowering"; change c0102).

An edge text is ``line X1 Y1 X2 Y2`` or ``arc X1 Y1 X2 Y2 XM YM`` in nanometres, the two vertices in
increasing ``(x, y)`` order, so it does not depend on the direction of the edge: KiCad's re-save swaps the
ends of a negatively oriented arc (``H-G-ARC-DIR``). The digest of an outline is taken over its sorted edge
texts, and the uuid of an edge holds that digest and its own text. The edge graphics of a board therefore
tell whether they are an outline Fenolite wrote and nobody changed: a move in KiCad keeps the uuid and
changes the text. The board writer and ``outline`` both import this module, which imports neither.
"""

# evidence: see pcb, outline

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from fenolite.core.coords import Point
from fenolite.core.ids import FENOLITE_NS
from fenolite.model.board import Outline

DIGEST_DIGITS = 16


@dataclass(frozen=True, slots=True)
class OutlineEdge:
    """Edge ``edge`` of ring ``ring``: from ``start`` to ``end``, through ``mid`` when it is an arc."""

    ring: int
    edge: int
    start: Point
    end: Point
    mid: Point | None = None


def outline_rings(outline: Outline) -> tuple[tuple[Point, ...], ...]:
    """The rings of ``outline``: its points, then each cut-out."""
    return (tuple(outline.points), *(tuple(ring) for ring in outline.cutouts))


def outline_edges(outline: Outline) -> tuple[OutlineEdge, ...]:
    """Every edge of every ring of ``outline``, in ring and edge order. A ring of one vertex has no edge,
    and a ring of two vertices has two (a straight edge closes back onto the first). An entry of ``arcs``
    that names no edge is ignored here; ``outline.check_outline`` reports it."""
    mids = {(arc.ring, arc.edge): arc.mid for arc in outline.arcs}
    edges: list[OutlineEdge] = []
    for r, ring in enumerate(outline_rings(outline)):
        if len(ring) < 2:
            continue
        for k, start in enumerate(ring):
            edges.append(OutlineEdge(r, k, start, ring[(k + 1) % len(ring)], mids.get((r, k))))
    return tuple(edges)


def edge_text(start: Point, end: Point, mid: Point | None = None) -> str:
    """The text of one edge, its two vertices in increasing ``(x, y)`` order."""
    a, b = sorted(((start.x, start.y), (end.x, end.y)))
    if mid is None:
        return f"line {a[0]} {a[1]} {b[0]} {b[1]}"
    return f"arc {a[0]} {a[1]} {b[0]} {b[1]} {mid.x} {mid.y}"


def edge_texts(outline: Outline) -> tuple[str, ...]:
    """One text per edge of ``outline``, in ring and edge order."""
    return tuple(edge_text(e.start, e.end, e.mid) for e in outline_edges(outline))


def outline_digest(texts: Iterable[str]) -> str:
    """The first 16 hexadecimal digits of the SHA-256 of ``texts`` in sorted order, each followed by a
    newline, in UTF-8."""
    data = "".join(f"{text}\n" for text in sorted(texts)).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:DIGEST_DIGITS]


def _part_uuid(outline: Outline, part: str) -> str:
    # the rule of ``pcb.kicad_uuid`` for a part of an entity; a unit test keeps the two equal
    return str(uuid.uuid5(FENOLITE_NS, f"kicad-out:{outline.id}:{part}"))


def edge_uuid(outline: Outline, digest: str, text: str) -> str:
    """The uuid of the edge ``text`` of an outline whose digest is ``digest``."""
    return _part_uuid(outline, f"outline:{digest}:{text}")


def position_uuid(outline: Outline, ring: int, edge: int) -> str:
    """The uuid a Fenolite before change c0102 gave edge ``edge`` of ring ``ring``."""
    return _part_uuid(outline, f"outline:{ring}:{edge}")


def signed_uuids(outline: Outline) -> tuple[str, ...]:
    """The uuid of each edge of ``outline`` as the writer signs it, in ring and edge order."""
    texts: Sequence[str] = edge_texts(outline)
    digest = outline_digest(texts)
    return tuple(edge_uuid(outline, digest, text) for text in texts)


__all__ = [
    "DIGEST_DIGITS",
    "OutlineEdge",
    "edge_text",
    "edge_texts",
    "edge_uuid",
    "outline_digest",
    "outline_edges",
    "outline_rings",
    "position_uuid",
    "signed_uuids",
]
