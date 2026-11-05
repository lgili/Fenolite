# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The integrity check of an Altium PCB document (capability altium-edit, "Integrity check"; change c0241,
design Decision 4): the faults of the index tables that the native tool may refuse, read-only.

Each rule is a function of the decoded document. A finding names the stream, the record's position and the
rule's row of ``docs/hypotheses.md``. Its severity is ``error`` when that row is in ``CONFIRMED`` and
``warning`` otherwise; no row is confirmed until its Part J phase B case passes
(``docs/evidence/altium-edit.md``), so every finding is a warning today.

The parameter rules (``H-A-INTEG-PARAMCOUNT``, ``H-A-INTEG-PARAMORPHAN``) have no form to check: phase A
found ``PrimitiveParameters`` empty in every saved file (``docs/formats/altium/pcb-document.md``, "Edit
observations"), and no public source gives the form of a group. A document whose storage holds data gives one
``altium.integrity.parameters-unjudged`` note instead of a judgement.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from types import MappingProxyType

from fenolite.backends.altium.models3d import model_records
from fenolite.backends.altium.pcbrecords import LAYER_NAMES, V7_LAYERS, layer_text
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.cfb import CompoundFile
from fenolite.backends.altium.read.pcb import SPLIT_PLANE_POLYGON, PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, RegionRecord
from fenolite.backends.altium.read.pcbprops import parse_blocks
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level

STAGE = "altium.integrity"
"""The name of the check stage (``fenolite check DOC --stages altium.integrity``)."""
RULES: Mapping[str, str] = MappingProxyType(
    {
        "altium.integrity.subpoly-gap": "H-A-INTEG-SUBPOLY",
        "altium.integrity.pour-index-twice": "H-A-INTEG-POURINDEX",
        "altium.integrity.unique-id-twice": "H-A-INTEG-ID",
        "altium.integrity.unique-id-index": "H-A-EDIT-DELETE",
        "altium.integrity.parameters-unjudged": "H-A-INTEG-PARAMCOUNT",
        "altium.integrity.model-unused": "H-A-INTEG-MODEL",
        "altium.integrity.model-missing": "H-A-INTEG-MODEL",
        "altium.integrity.layer-fields": "H-A-INTEG-LAYER",
    }
)
"""Each finding code and the row of ``docs/hypotheses.md`` it cites."""
CONFIRMED: frozenset[str] = frozenset()
"""The rows a recorded Part J phase B case confirmed; a finding of one of them is an ``error``. Empty: phase
B has not run (c0241, task 4.2)."""
INTEGRITY_ISSUE_CODES: Mapping[str, Severity | tuple[Severity, ...]] = MappingProxyType(
    {
        **{code: ("error", "warning") for code in RULES if code != "altium.integrity.parameters-unjudged"},
        "altium.integrity.parameters-unjudged": "info",
    }
)
"""Code → the severities it takes."""
HYPOTHESES = tuple(sorted(set(RULES.values()) | {"H-A-INTEG-PARAMORPHAN"}))
EVIDENCE = Evidence(Level.INFERRED, hypotheses=HYPOTHESES)
"""``INFERRED``: no rule is confirmed by the kit yet."""
_ID_TABLES = (
    ("UniqueIDPrimitiveInformation", "entry"),
    ("Components6", "component"),
    ("Polygons6", "polygon"),
    ("Rules6", "rule"),
)


def _finding(code: str, message: str, where: str) -> Issue:
    row = RULES[code]
    severity: Severity = (
        "info"
        if code == "altium.integrity.parameters-unjudged"
        else "error"
        if row in CONFIRMED
        else "warning"
    )
    hint = f"rule of {row}" + ("" if row in CONFIRMED else " (not confirmed by the kit: a warning)")
    return Issue(code, severity, message, where, hint)


# --- rules -------------------------------------------------------------------------------------------


def _polygon_label(doc: PcbDocument, index: int) -> str:
    if 0 <= index < len(doc.polygons):
        return f"polygon {index} ({doc.polygons[index].name!r})"
    return f"polygon {index}"


def subpoly_gaps(doc: PcbDocument) -> Iterator[Issue]:
    """``H-A-INTEG-SUBPOLY``: the poured regions of one polygon whose ``SUBPOLYINDEX`` numbers skip a value
    below their highest (``pcb-pour.md``: the pieces of a polygon carry 0 to n − 1)."""
    numbers: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for position, region in enumerate(doc.regions):
        if not isinstance(region, RegionRecord):
            continue
        polygon = region.prefix.polygon
        text = region.properties.get("SUBPOLYINDEX")
        if polygon is None or polygon == SPLIT_PLANE_POLYGON or text is None:
            continue
        try:
            value = int(text)
        except ValueError:
            continue
        if value >= 0:
            numbers[polygon].append((value, position))
    for polygon, found in sorted(numbers.items()):
        held = {value for value, _ in found}
        missing = sorted(set(range(max(held) + 1)) - held)
        if missing:
            positions = ", ".join(f"#{p}" for _, p in sorted(found, key=lambda item: item[1]))
            values = ", ".join(str(v) for v, _ in sorted(found, key=lambda item: item[1]))
            yield _finding(
                "altium.integrity.subpoly-gap",
                f"the pieces of {_polygon_label(doc, polygon)} hold SUBPOLYINDEX {values}, without "
                f"{', '.join(map(str, missing))} (Regions6 records {positions})",
                f"Regions6/Data#{found[0][1]}",
            )


def pour_index_twice(doc: PcbDocument) -> Iterator[Issue]:
    """``H-A-INTEG-POURINDEX``: two polygons with one ``POURINDEX``."""
    held: dict[int, list[int]] = defaultdict(list)
    for position, polygon in enumerate(doc.polygons):
        if polygon.pour_index is not None:
            held[polygon.pour_index].append(position)
    for value, positions in sorted(held.items()):
        if len(positions) > 1:
            names = ", ".join(_polygon_label(doc, p) for p in positions)
            yield _finding(
                "altium.integrity.pour-index-twice",
                f"{names} hold POURINDEX {value}",
                f"Polygons6/Data#{positions[1]}",
            )


def _pad_label(doc: PcbDocument, index: int) -> str:
    pad = doc.pads[index] if 0 <= index < len(doc.pads) else None
    if not isinstance(pad, PadRecord):
        return f"pad {index}"
    owner = pad.prefix.component
    if owner is not None and 0 <= owner < len(doc.components):
        return f"pad {index} ({doc.components[owner].source_designator}.{pad.name})"
    return f"pad {index} ({pad.name})"


def unique_ids(doc: PcbDocument) -> Iterator[Issue]:
    """``H-A-INTEG-ID``: one unique id held twice within the entries of ``UniqueIDPrimitiveInformation``, the
    components, the polygons or the rules; and (``H-A-EDIT-DELETE``) an entry whose ``PRIMITIVEINDEX`` names
    no pad."""
    sources: dict[str, Sequence[tuple[int, str]]] = {}
    entries = doc.parts.get("UniqueIDPrimitiveInformation", ((), b""))[0]
    records = parse_blocks(b"".join(entries), where="UniqueIDPrimitiveInformation")[0]
    rows: list[tuple[int, str]] = []
    for position, record in enumerate(records):
        value = record.get("UNIQUEID")
        if value:
            rows.append((position, value))
        index = record.get("PRIMITIVEINDEX")
        kind = (record.get("PRIMITIVEOBJECTID") or "").upper()
        if kind == "PAD" and index is not None and index.isdigit() and int(index) >= len(doc.pads):
            yield _finding(
                "altium.integrity.unique-id-index",
                f"entry {position} names pad {index}; the document holds {len(doc.pads)} pads",
                f"UniqueIDPrimitiveInformation/Data#{position}",
            )
    sources["UniqueIDPrimitiveInformation"] = rows
    sources["Components6"] = [(i, c.unique_id) for i, c in enumerate(doc.components) if c.unique_id]
    sources["Polygons6"] = [
        (i, value) for i, p in enumerate(doc.polygons) if (value := p.record.get("UNIQUEID"))
    ]
    sources["Rules6"] = [(i, value) for i, r in enumerate(doc.rules) if (value := r.record.get("UNIQUEID"))]
    for storage, kind in _ID_TABLES:
        held: dict[str, list[int]] = defaultdict(list)
        for position, value in sources[storage]:
            if value.strip():  # a blank id names nothing (one public document holds two)
                held[value.strip().upper()].append(position)
        for value, positions in sorted(held.items()):
            if len(positions) < 2:
                continue
            if storage == "UniqueIDPrimitiveInformation":
                pads = [int(i) for p in positions if (i := records[p].get("PRIMITIVEINDEX") or "").isdigit()]
                named = " and ".join(_pad_label(doc, pad) for pad in pads) or "entries"
                message = f"{named} share the unique id {value} in UniqueIDPrimitiveInformation"
            else:
                held_by = ", ".join(f"#{p}" for p in positions)
                message = f"{kind}s {held_by} of {storage} share the unique id {value}"
            yield _finding("altium.integrity.unique-id-twice", message, f"{storage}/Data#{positions[1]}")


def parameters(compound: CompoundFile) -> Iterator[Issue]:
    """``H-A-INTEG-PARAMCOUNT`` and ``H-A-INTEG-PARAMORPHAN``: not judged (module docstring)."""
    path = "PrimitiveParameters/Data"
    if path in compound and compound.read(path):
        yield _finding(
            "altium.integrity.parameters-unjudged",
            "PrimitiveParameters holds data; the form of its groups is not known, so their counts and owners "
            "are not checked",
            path,
        )


def models(compound: CompoundFile) -> Iterator[Issue]:
    """``H-A-INTEG-MODEL``: an entry of ``Models/Data`` whose ``ID`` no body names, and a body with
    ``MODEL.MODELTYPE=1`` whose ``MODELID`` the store does not hold (``pcb-bodies.md``)."""
    store = model_records(compound.read("Models/Data")) if "Models/Data" in compound else ()
    ids = {record.get("ID", "").upper(): n for n, record in enumerate(store) if record.get("ID")}
    named: set[str] = set()
    for storage, shape_based in (("ComponentBodies6", False), ("ShapeBasedComponentBodies6", True)):
        path = f"{storage}/Data"
        if path not in compound:
            continue
        for body in read_bodies(compound.read(path), shape_based=shape_based, storage=storage):
            model = body.model_id.upper()
            if not body.framed or not model:
                continue
            named.add(model)
            if body.properties.get("MODEL.MODELTYPE") == "1" and model not in ids:
                yield _finding(
                    "altium.integrity.model-missing",
                    f"body {body.index} names the model {body.model_id}, which Models/Data does not hold",
                    f"{path}#{body.index}",
                )
    for model, position in sorted(ids.items(), key=lambda item: item[1]):
        if model not in named:
            yield _finding(
                "altium.integrity.model-unused",
                f"model entry {position} ({store[position].get('NAME', '')!r}) is named by no body",
                f"Models/Data#{position}",
            )


def _v7_id(text: str) -> int | None:
    """The layer id a ``V7_LAYER`` text names, ``None`` when it names none the layer byte can hold."""
    wanted = text.strip().upper()
    for layer, name in V7_LAYERS.items():
        if name == wanted:
            return layer
    for layer in range(1, 33):
        try:
            if layer_text(layer) == wanted:
                return layer
        except ValueError:
            continue
    return None


def layer_fields(doc: PcbDocument) -> Iterator[Issue]:
    """``H-A-INTEG-LAYER``: a region whose layer byte and ``V7_LAYER`` key name different layers. A
    ``V7_LAYER`` that names a layer the byte cannot hold (a mechanical layer above 16) is not compared."""
    for storage, items in (("Regions6", doc.regions), ("ShapeBasedRegions6", doc.shape_regions)):
        for position, region in enumerate(items):
            if not isinstance(region, RegionRecord):
                continue
            text = region.properties.get("V7_LAYER")
            if not text:
                continue
            named = _v7_id(text)
            if named is None or named == region.prefix.layer:
                continue
            byte = LAYER_NAMES.get(region.prefix.layer, f"layer {region.prefix.layer}")
            yield _finding(
                "altium.integrity.layer-fields",
                f"region {position} lies on {byte} by its layer byte and on {LAYER_NAMES[named]} by "
                f"V7_LAYER={text}",
                f"{storage}/Data#{position}",
            )


# --- the check ---------------------------------------------------------------------------------------


def check_document(doc: PcbDocument, compound: CompoundFile) -> tuple[Issue, ...]:
    """Every finding of the rules on ``doc``, read from ``compound``, in rule order."""
    return (
        *subpoly_gaps(doc),
        *pour_index_twice(doc),
        *unique_ids(doc),
        *parameters(compound),
        *models(compound),
        *layer_fields(doc),
    )


def check_pcbdoc(data: bytes, *, file: str = "") -> tuple[Issue, ...]:
    """The findings of ``check_document`` on the PCB document ``data``; the reader's errors are raised."""
    from fenolite.backends.altium.read.cfb import open_compound

    compound = open_compound(data, file=file)
    return check_document(read_pcbdoc(compound, file=file), compound)


__all__ = [
    "CONFIRMED",
    "EVIDENCE",
    "HYPOTHESES",
    "INTEGRITY_ISSUE_CODES",
    "RULES",
    "STAGE",
    "check_document",
    "check_pcbdoc",
]
