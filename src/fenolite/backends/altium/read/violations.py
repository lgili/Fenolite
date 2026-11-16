# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium's own DRC results: the violations a PCB document stores and the ``.drc`` text report (change c0498,
design D1 and D2).

A document saved after a DRC holds one property-text record per violation in a ``T<Kind>Violation``
storage, and the waived ones in ``WaivedViolations`` (``docs/formats/altium/pcb-records.md``, "DRC
violations"; ``H-A-DRC-STORED``, census of seven public rows). A record names its rule by its position in
``Rules6`` and each primitive by its kind and its position in the storage of that kind, which is the
locator the import gives the item. A pad is named ``REF-PIN``, as the copper check names it. The text report
names primitives by description only (``H-A-DRC-TXT``, ``INFERRED``): each line keeps ``primitives=()``, its
first coordinate pair as the location and the line as the message.
"""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.backends.altium.read.cfb import CompoundFile, read_compound
from fenolite.backends.altium.read.pcbprops import parse_blocks
from fenolite.backends.altium.read.proptext import parse_length
from fenolite.backends.base import NativeFinding, NativeViolations
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

STORED_EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-A-DRC-STORED",))
REPORT_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-DRC-TXT",))
UNKNOWN = "altium.read.violations-unknown"
WAIVED = "WaivedViolations"
STORAGES: dict[str, str] = {
    "Pad": "Pads6",
    "Via": "Vias6",
    "Track": "Tracks6",
    "Arc": "Arcs6",
    "Text": "Texts6",
    "Fill": "Fills6",
    "Region": "Regions6",
}
"""The primitive kinds a violation names and the storage each indexes (``PRIMnID``, ``PRIMnINDEX``)."""
EDGE = "edge"
"""The name of the board outline (``Board`` index 0) in a violation, as the copper check's edge."""
_VIOLATION = re.compile(r"T([A-Za-z0-9]+)Violation")
REPORT_KINDS: tuple[tuple[str, str], ...] = (
    ("Silk To Solder Mask", "SilkToSolderMaskClearance"),
    ("Silk To Silk", "SilkToSilkClearance"),
    ("Silk to Silk", "SilkToSilkClearance"),
    ("Silk To Board Region", "SilkToBoardRegionClearance"),
    ("Board Outline Clearance", "BoardOutlineClearance"),
    ("Short-Circuit", "ShortCircuit"),
    ("Short Circuit", "ShortCircuit"),
    ("Clearance Constraint", "Clearance"),
    ("Width Constraint", "Width"),
    ("Hole To Hole Clearance", "HoleToHoleClearance"),
    ("Hole Size Constraint", "HoleSize"),
    ("Minimum Solder Mask Sliver", "MinimumSolderMaskSliver"),
    ("Height Constraint", "Height"),
    ("Un-Routed Net Constraint", "UnRoutedNet"),
)
"""Constraint names of the text report's ``Processing Rule`` lines and the rule kind each names
(``H-A-DRC-TXT``): the first that the line holds wins."""
_POINT = re.compile(r"\(\s*(-?[0-9.]+(?:mil|mm))\s*,\s*(-?[0-9.]+(?:mil|mm))\s*\)")


def _unknown(message: str, where: str) -> Issue:
    return Issue(UNKNOWN, "warning", message, where=where)


def _count(compound: CompoundFile, storage: str) -> int:
    path = f"{storage}/Header"
    data = compound.read(path) if path in compound else b""
    return int.from_bytes(data[:4], "little") if len(data) >= 4 else 0


def _pads(design: Design) -> dict[str, str]:
    """``Pads6/Data#n`` → ``REF-PIN`` of each pad of a component of ``design``."""
    board = design.board
    if board is None:
        return {}
    refs = {c.id: c.ref for c in design.circuit.components}
    found: dict[str, str] = {}
    for footprint in board.footprints:
        ref = refs.get(footprint.component_id, "")
        for pad in footprint.pads:
            if pad.provenance is not None and pad.provenance.locator and ref:
                found[pad.provenance.locator] = f"{ref}-{pad.number}"
    return found


def _location(x: str | None, y: str | None) -> Point | None:
    nx, ny = parse_length(x or ""), parse_length(y or "")
    return None if nx is None or ny is None else Point(nx, -ny)  # the model's Y points down


def stored_violations(path: str | Path, design: Design) -> NativeViolations:
    """The violations stored in the PCB document ``path``, whose import is ``design`` (``H-A-DRC-STORED``).
    A waived violation (one of ``WaivedViolations`` naming the same rule and primitives) is marked. A record
    without ``RULEINDEX`` or a named primitive, or a storage whose record count differs from its ``Header``,
    gives ``altium.read.violations-unknown`` and is left out."""
    compound = read_compound(path)
    rules = [dict(fields) for fields in _rule_fields(compound)]
    pads = _pads(design)
    counts = {storage: _count(compound, storage) for storage in STORAGES.values()}
    issues: list[Issue] = []

    def named(kind: str | None, index: str | None) -> tuple[str | None, bool]:
        if kind == "Board" and index == "0":
            return EDGE, False
        storage = STORAGES.get(kind or "")
        if storage is None or index is None or not index.isdigit():
            return None, False
        locator = f"{storage}/Data#{int(index)}"
        return pads.get(locator, locator), int(index) >= counts[storage]

    def records(storage: str) -> list[dict[str, str]]:
        path = f"{storage}/Data"
        data = compound.read(path) if path in compound else b""
        blocks, trailing, problems = parse_blocks(data, where=path)
        if trailing or problems or len(blocks) != _count(compound, storage):
            issues.append(_unknown(f"{storage} holds {len(blocks)} whole record(s) for a Header count of "
                                   f"{_count(compound, storage)}", storage))  # fmt: skip
        return [dict(block.fields) for block in blocks]

    def primitives(record: dict[str, str], key: str) -> tuple[tuple[str, ...], bool] | None:
        names: list[str] = []
        stale = False
        for n in ("1", "2"):
            name, missing = named(record.get(f"PRIM{n}{key}"), record.get(f"PRIM{n}INDEX"))
            if name is None and record.get(f"PRIM{n}{key}") is None:
                continue
            if name is None:
                return None
            names.append(name)
            stale = stale or missing
        return tuple(sorted(names)), stale

    waived: set[tuple[str, tuple[str, ...]]] = set()
    if f"{WAIVED}/Data" in compound:
        for number, record in enumerate(records(WAIVED)):
            held = primitives(record, "KIND")
            if held is not None and record.get("RULEINDEX", "").isdigit():
                waived.add((record["RULEINDEX"], held[0]))
            else:
                issues.append(_unknown("a waived violation names no rule or an unknown primitive kind",
                                       f"{WAIVED}/Data#{number}"))  # fmt: skip
    found: list[NativeFinding] = []
    for storage in sorted({name.split("/", 1)[0] for name in compound.streams()}):
        match = _VIOLATION.fullmatch(storage)
        if match is None:
            continue
        for number, record in enumerate(records(storage)):
            held = primitives(record, "ID")
            index = record.get("RULEINDEX", "")
            if held is None or not index.isdigit() or not held[0]:
                issues.append(_unknown("a violation names no rule or an unknown primitive kind",
                                       f"{storage}/Data#{number}"))  # fmt: skip
                continue
            rule = rules[int(index)] if int(index) < len(rules) else {}
            found.append(
                NativeFinding(
                    kind=rule.get("RULEKIND")
                    or match.group(1),  # TMinSolderMaskSliver… is MinimumSolderMaskSliver
                    rule=rule.get("NAME", ""),
                    primitives=held[0],
                    at=_location(record.get("LOCATION1.X"), record.get("LOCATION1.Y")),
                    message=record.get("DESCRIPTION", ""),
                    waived=(index, held[0]) in waived,
                    stale=held[1] or int(index) >= len(rules),
                )
            )
    found.sort(key=lambda f: (f.kind, f.primitives, f.message))
    return NativeViolations(tuple(found), tuple(issues), STORED_EVIDENCE, "stored" if found else "")


def _rule_fields(compound: CompoundFile) -> tuple[tuple[tuple[str, str], ...], ...]:
    from fenolite.backends.altium.read.pcb import read_rule_fields

    return read_rule_fields(compound)


def holds_violations(path: str | Path) -> bool:
    """Whether the PCB document ``path`` holds a violation storage with a record."""
    compound = read_compound(path)
    storages = {name.split("/", 1)[0] for name in compound.streams()}
    return any(_VIOLATION.fullmatch(s) and _count(compound, s) > 0 for s in storages)


def report_kind(line: str) -> str:
    """The rule kind a ``Processing Rule`` line names, else ``""``."""
    return next((kind for name, kind in REPORT_KINDS if name in line), "")


def report_violations(report: str | Path, design: Design) -> NativeViolations:
    """The violations of Altium's ``.drc`` text report (``H-A-DRC-TXT``, ``INFERRED``): one per line that
    starts with ``Violation`` or names primitives, under the last ``Processing Rule`` line. ``design`` is
    taken for the signature of ``stored_violations``; the report's lines are not matched to items."""
    del design
    text = Path(report).read_text(encoding="utf-8", errors="replace")
    kind = rule = ""
    found: list[NativeFinding] = []
    issues: list[Issue] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("Processing Rule"):
            rule = line.split(":", 1)[1].strip() if ":" in line else line
            kind = report_kind(rule)
            continue
        if not rule or not line.startswith("Violation "):
            continue
        if not kind:
            issues.append(_unknown(f"the rule {rule!r} names no known kind", f"line {number}"))
        point = _POINT.search(line)
        at = _location(point.group(1), point.group(2)) if point is not None else None
        found.append(NativeFinding(kind=kind or "unknown", rule=rule, primitives=(), at=at, message=line))
    return NativeViolations(tuple(found), tuple(issues), REPORT_EVIDENCE, "report")


__all__ = [
    "EDGE",
    "REPORT_EVIDENCE",
    "STORED_EVIDENCE",
    "UNKNOWN",
    "holds_violations",
    "report_kind",
    "report_violations",
    "stored_violations",
]
