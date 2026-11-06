# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the scope functions of change c0462 read from a PCB document (``read.scope.ScopeDocument``).

``scope_document`` gathers it from a read ``PcbDocument`` and the copper layers of its board;
``read.scope.for_kind`` gives it a rule kind's parent objects (``ScopeDocument.parents``). The facts each
field rests on are in ``docs/formats/altium/rule-file.md``, "Scope functions that read the document".
"""

# evidence: see import_evidence, read.project

from __future__ import annotations

import struct
from collections.abc import Mapping

from fenolite.backends.altium.read.pcb import PcbDocument
from fenolite.backends.altium.read.pcbprims import PadRecord, TextRecord, ViaRecord
from fenolite.backends.altium.read.rules import CopperLayers
from fenolite.backends.altium.read.scope import (
    ScopeClass,
    ScopeComponent,
    ScopeDocument,
    ScopeLayer,
    ScopePad,
    ScopePair,
)

MULTI_LAYER_ID = 74
TOP_ID, BOTTOM_ID = 1, 32
DISPLAY_UNITS: Mapping[int, str] = {0: "mm", 1: "mil"}
"""``DISPLAYUNIT`` of the board record → the unit of a number of a query (``pcb-document.md``: 1 with a grid
in mils, 0 with a metric one; that the query takes this unit is ``INFERRED``, ``H-A-RD-PRJ-SCOPE-UNIT``)."""
PAIR_STORAGE = "DifferentialPairs6"


def _fields(record: bytes) -> dict[str, str]:
    text = record.rstrip(b"\x00").decode("latin-1")
    found: dict[str, str] = {}
    for part in text.split("|"):
        key, sep, value = part.partition("=")
        if sep:
            found[key.strip().upper()] = value
    return found


def _records(data: bytes) -> list[dict[str, str]]:
    """The property records of a storage's ``Data`` stream, each a 32-bit length and its text."""
    found: list[dict[str, str]] = []
    at = 0
    while at + 4 <= len(data):
        (length,) = struct.unpack_from("<I", data, at)
        found.append(_fields(data[at + 4 : at + 4 + length]))
        at += 4 + length
    return found


def _pairs(document: PcbDocument) -> tuple[ScopePair, ...]:
    data = b""
    for name, streams in document.storages.items():
        if name.upper() == PAIR_STORAGE.upper():
            data = streams.get("Data", b"")
    found: list[ScopePair] = []
    for fields in _records(data):
        if fields.get("NAME"):
            positive, negative = fields.get("POSITIVENETNAME", ""), fields.get("NEGATIVENETNAME", "")
            found.append(ScopePair(fields["NAME"], positive, negative))
    return tuple(found)


def _designators(document: PcbDocument) -> dict[int, str]:
    """Component index → the designator its designator text shows (``adapter.board``'s reference)."""
    found: dict[int, str] = {}
    for item in document.texts:
        if isinstance(item, TextRecord) and item.prefix.component is not None and item.is_designator:
            found.setdefault(item.prefix.component, item.text)
    return found


def _components(document: PcbDocument) -> tuple[ScopeComponent, ...]:
    pads: dict[int, list[ScopePad]] = {}
    for pad in document.pads:
        if isinstance(pad, PadRecord) and pad.prefix.component is not None:
            smd = pad.prefix.layer != MULTI_LAYER_ID
            pads.setdefault(pad.prefix.component, []).append(ScopePad(pad.x, pad.y, smd))
    texts = _designators(document)
    return tuple(
        ScopeComponent(
            designator=texts.get(index) or record.source_designator or "",
            footprint=record.pattern or "",
            kind=record.record.get("COMPONENTKIND"),
            rotation=record.rotation or 0.0,
            pads=tuple(pads.get(index, ())),
        )
        for index, record in enumerate(document.components)
    )


def scope_document(document: PcbDocument, layers: CopperLayers | None) -> ScopeDocument:
    """The ``ScopeDocument`` of a read PCB document whose board has the copper layers ``layers``."""
    single = [p for p in document.pads if isinstance(p, PadRecord) and p.prefix.layer != MULTI_LAYER_ID]
    plated = {pad.plated for pad in single}
    vias = [v for v in document.vias if isinstance(v, ViaRecord)]
    unit = DISPLAY_UNITS.get(document.board.display_unit) if document.board.display_unit is not None else None
    return ScopeDocument(
        unit="mm" if unit == "mm" else "mil" if unit == "mil" else None,
        layers=None
        if layers is None
        else tuple(ScopeLayer(c.document_name, c.name, c.inner_signal, c.altium_id) for c in layers.layers),
        blind_vias=any((v.start_layer, v.end_layer) != (TOP_ID, BOTTOM_ID) for v in vias),
        nets=tuple(net.name for net in document.nets if net.name),
        pairs=_pairs(document),
        classes=tuple(
            ScopeClass(c.kind, c.name, c.members, bool(c.superclass))
            for c in document.classes
            if c.kind is not None and c.name
        ),
        components=_components(document),
        polygons=tuple(p.name for p in document.polygons if p.name),
        smd_plated=None if len(plated) > 1 else plated == {True},
        smd_holes=any(pad.hole > 0 for pad in single),
    )


__all__ = ["DISPLAY_UNITS", "scope_document"]
