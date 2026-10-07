# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Corpus boards for the board reader tests: the manifest rows and one cached read per session."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from _corpus import CorpusItem, manifest_items

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import versions
from fenolite.backends.kicad import via_protection as vialib
from fenolite.backends.kicad.pcb import ZONE_SETTING_FIELDS, read_board
from fenolite.backends.kicad.sexpr import AtomKind, Node, dumps, load, walk
from fenolite.core.errors import Issue
from fenolite.geometry import Arc, GeometryError, Point, Segment
from fenolite.geometry.errors import OPEN_CONTOUR
from fenolite.geometry.polygon import assemble_rings
from fenolite.model.base import Modeled, Opaque
from fenolite.model.board import Zone
from fenolite.model.design import Design

BOARD_ITEMS: list[CorpusItem] = [i for i in manifest_items("rt0") if i.path.suffix == ".kicad_pcb"]
MALFORMED_ITEMS: list[CorpusItem] = [i for i in manifest_items("malformed") if i.path.suffix == ".kicad_pcb"]


def readable(item: CorpusItem) -> bool:
    """True when the board's header is at or above the read floor (KiCad 8.0)."""
    return versions.detect_version(load(item.path)) >= versions.READ_FLOOR[versions.FileKind.BOARD]


def is_readable_row(item: CorpusItem) -> bool:
    """Decided from the manifest alone: the demo rows are 8.0+, the third-party rows are older."""
    return item.origin == "kicad-demos"


READABLE_ITEMS = [i for i in BOARD_ITEMS if is_readable_row(i)]
OLD_ITEMS = [i for i in BOARD_ITEMS if not is_readable_row(i)]


@cache
def read(path: Path) -> tuple[Design, tuple[Issue, ...]]:
    """The design read from ``path`` and the reader's issues (read once per test session)."""
    issues: list[Issue] = []
    design = read_board(path, issues=issues)
    return design, tuple(issues)


# --- census (counts only: origins, manifest ids, head chains and codes, never content) -------------

_INDEX = re.compile(r"\[\d+\]")
_DECIMALS = re.compile(r"\.(\d+)")


@dataclass(frozen=True)
class Entry:
    """One board for the census: its origin and id, the parsed tree, the design and the reader issues."""

    origin: str
    id: str
    root: Node
    design: Design
    issues: tuple[Issue, ...]


def entry(item: CorpusItem) -> Entry:
    design, issues = read(item.path)
    return Entry(item.origin, item.id, load(item.path), design, issues)


def context(locator: str) -> str:
    return _INDEX.sub("", locator.removeprefix("/kicad_pcb/")) or "kicad_pcb"


def _per_origin(counts: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {origin: dict(sorted(c.items())) for origin, c in sorted(counts.items())}


def census_numbers(entries: Iterable[Entry]) -> dict[str, Any]:
    """Numbers the reader kept opaque as inexact, and every over-precise atom of the files, by context."""
    reader: dict[str, Counter[str]] = {}
    atoms: dict[str, Counter[str]] = {}
    for e in entries:
        found = reader.setdefault(e.origin, Counter())
        for issue in e.issues:
            if issue.code in ("kicad.board.inexact-length", "kicad.board.inexact-angle"):
                found[f"{issue.code.rsplit('.', 1)[1]}:{context(issue.where)}"] += 1
        precise = atoms.setdefault(e.origin, Counter())
        for locator, node in walk(e.root):
            for atom in node.atoms():
                if atom.kind != AtomKind.NUMBER:
                    continue
                decimals = _DECIMALS.search(atom.text)
                if "e" in atom.text.lower():
                    precise[f"exponent:{context(locator)}"] += 1
                elif decimals is not None and len(decimals.group(1)) > 6:
                    precise[f"over-6-decimals:{context(locator)}"] += 1
    return {"reader_inexact": _per_origin(reader), "over_precise_atoms": _per_origin(atoms)}


def census_kept_opaque(entries: Iterable[Entry]) -> dict[str, Any]:
    reasons: dict[str, Counter[str]] = {}
    for e in entries:
        found = reasons.setdefault(e.origin, Counter())
        for issue in e.issues:
            if issue.code == "kicad.board.kept-opaque":
                message = re.sub(r"'[^']*'", "'…'", issue.message)
                found[f"{context(issue.where)}: {message}"] += 1
    return _per_origin(reasons)


def census_uuids(entries: Iterable[Entry]) -> dict[str, dict[str, int]]:
    """uuid values repeated inside one file, per board and head (``H-K-PCB-UUID``)."""
    repeats: dict[str, dict[str, int]] = {}
    for e in entries:
        values: Counter[str] = Counter()
        heads: dict[str, set[str]] = {}
        for _, node in walk(e.root):
            uuid = node.find("uuid")
            if uuid is not None and uuid.atoms():
                value = uuid.atoms()[0].value
                values[value] += 1
                heads.setdefault(value, set()).add(node.name)
        per_head: Counter[str] = Counter()
        for value, count in values.items():
            if count > 1:
                per_head["+".join(sorted(heads[value]))] += count - 1
        if per_head:
            repeats[e.id] = dict(per_head)
    return repeats


ZONE_SETTING_CHILDREN = ("connect_pads", "min_thickness", "fill")
_PAD_CONNECTS = frozenset(f"(zone_connect {n})" for n in range(4))


def _setting_slots(zone: Zone) -> dict[str, str]:
    """``Modeled`` or ``Opaque`` per setting child that the zone holds, by head."""
    fields = {ZONE_SETTING_FIELDS[head]: head for head in ZONE_SETTING_CHILDREN}
    out: dict[str, str] = {}
    for slot in slotlib.from_ext(zone.ext["kicad"]):
        if isinstance(slot, Modeled):
            if slot.field in fields:
                out[fields[slot.field]] = "Modeled"
        else:
            head = slot.fragment[1:].split(" ", 1)[0].rstrip(")")
            if head in ZONE_SETTING_CHILDREN:
                out[head] = "Opaque"
    return out


def _protection_form(node: Node) -> str:
    """The protection children of a via or of ``setup``, as written, joined; ``""`` without any."""
    return " ".join(dumps(c, style="compact") for c in node.nodes() if c.name in vialib.FEATURE_FIELDS)


def census_via_protection(entries: Iterable[Entry]) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Per origin: boards by the protection children of their ``setup``, vias, vias with protection
    children by the form of those children, and the vias whose read protection holds a value (change
    c0112). The second value lists the protection children that the reader kept as opaque slots, by board
    id and locator."""
    counts: dict[str, Counter[str]] = {}
    problems: list[str] = []
    for e in entries:
        assert e.design.board is not None
        found = counts.setdefault(e.origin, Counter())
        setup = e.root.find("setup")
        found[f"setup: {(_protection_form(setup) if setup is not None else '') or 'no child'}"] += 1
        for node in e.root.nodes("via"):
            found["vias"] += 1
            form = _protection_form(node)
            if form:
                found["vias_with_children"] += 1
                found[f"via: {form}"] += 1
        for via in e.design.board.vias:
            if via.protection != type(via.protection)():
                found["vias_with_values"] += 1
            for slot in slotlib.from_ext(via.ext["kicad"]):
                if isinstance(slot, Opaque):
                    child = slotlib.opaque_child(slot)
                    if isinstance(child, Node) and child.name in vialib.FEATURE_FIELDS:
                        found[f"opaque:{child.name}"] += 1
                        locator = via.provenance.locator if via.provenance is not None else ""
                        problems.append(f"{e.id} {locator} {child.name}")
    return _per_origin(counts), problems


def census_zone_settings(entries: Iterable[Entry]) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Per origin: zones, zones whose three setting children are modelled slots, opaque setting children
    by head and the reader's reason, and pads by the slot kind of their ``zone_connect``
    (``H-K-ZONE-FORM``). The second value lists the zones with an opaque setting child, by board id and
    locator."""
    counts: dict[str, Counter[str]] = {}
    problems: list[str] = []
    for e in entries:
        assert e.design.board is not None
        found = counts.setdefault(e.origin, Counter())
        reasons = {
            i.where: re.sub(r"'[^']*'", "'…'", i.message)
            for i in e.issues
            if i.code == "kicad.board.kept-opaque"
        }
        for zone in e.design.board.zones:
            found["zones"] += 1
            kinds = _setting_slots(zone)
            if all(kinds.get(head) == "Modeled" for head in ZONE_SETTING_CHILDREN):
                found["zones_modelled"] += 1
            if zone.filled:
                found["zones_filled"] += 1
            if zone.filled and not zone.fills:
                found["zones_filled_without_polygons"] += 1
            if zone.locked:
                found["zones_locked"] += 1
            locator = zone.provenance.locator if zone.provenance is not None else ""
            for head in ZONE_SETTING_CHILDREN:
                kind = kinds.get(head)
                if kind is None:
                    found[f"absent:{head}"] += 1
                elif kind == "Opaque":
                    reason = reasons.get(f"{locator}/{head}[0]", "no reason reported")
                    found[f"opaque:{head}: {reason}"] += 1
                    problems.append(f"{e.id} {context(locator)} {head}: {reason}")
        for fp in e.design.board.footprints:
            for pad in fp.pads:
                if pad.zone_connection is not None:
                    found[f"pads_zone_connect:{pad.zone_connection}"] += 1
                for slot in slotlib.from_ext(pad.ext["kicad"]):
                    if isinstance(slot, Opaque) and slot.fragment.startswith("(zone_connect"):
                        found["pads_zone_connect_opaque"] += 1
                        if slot.fragment in _PAD_CONNECTS:
                            problems.append(f"{e.id} pad {pad.number}: {slot.fragment} is opaque")
    return _per_origin(counts), problems


def census_zones(entries: Iterable[Entry]) -> tuple[dict[str, int], list[str]]:
    """Opaque zone outlines per origin (``H-K-PCB-ZONE``), and the zones that break the rule."""
    counts: Counter[str] = Counter()
    problems: list[str] = []
    for e in entries:
        assert e.design.board is not None
        flagged = {
            i.where.rsplit("/polygon", 1)[0] for i in e.issues if i.code == "kicad.board.zone-outline-opaque"
        }
        counts[e.origin] += len(flagged)
        for zone in (*e.design.board.zones, *e.design.board.keepouts):
            if zone.provenance is None or zone.provenance.locator not in flagged:
                continue
            slots = slotlib.from_ext(zone.ext["kicad"])
            polygons = [s for s in slots if isinstance(s, Opaque) and s.fragment.startswith("(polygon ")]
            if zone.outline != () or not polygons:
                problems.append(f"{e.id}: {zone.provenance.locator}")
    return dict(counts), problems


def census_fields(entries: Iterable[Entry]) -> dict[str, Any]:
    """Footprint fields per origin (change c0030): fields, the properties that stay projected slots of
    their footprint, the field children kept opaque, and the kept-opaque reasons inside fields."""
    counts: dict[str, Counter[str]] = {}
    reasons: dict[str, Counter[str]] = {}
    for e in entries:
        assert e.design.board is not None
        found = counts.setdefault(e.origin, Counter())
        for footprint in e.design.board.footprints:
            found["footprints"] += 1
            found["fields"] += len(footprint.fields)
            for slot in slotlib.from_ext(footprint.ext["kicad"]):
                if isinstance(slot, Opaque) and slot.fragment.startswith("(property"):
                    found["properties kept as footprint slots"] += 1
            for field in footprint.fields:
                found[f"name:{field.name}" if field.name in ("Reference", "Value") else "name:other"] += 1
                found["hidden"] += not field.visible
                found["mirrored"] += field.mirrored
                found["without thickness"] += field.thickness is None
                found["justified"] += (field.h_justify, field.v_justify) != ("center", "center")
                for slot in slotlib.from_ext(field.ext["kicad"]):
                    if isinstance(slot, Opaque) and slot.fragment.startswith("("):
                        found[f"opaque child:{slot.fragment[1:].split(' ', 1)[0].rstrip(')')}"] += 1
        why = reasons.setdefault(e.origin, Counter())
        for issue in e.issues:
            if issue.code == "kicad.board.kept-opaque" and "/property[" in issue.where:
                message = re.sub(r"'[^']*'", "'…'", issue.message)
                why[f"{context(issue.where)}: {message}"] += 1
    return {"counts": _per_origin(counts), "kept_opaque": _per_origin(reasons)}


def census_validation(entries: Iterable[Entry]) -> dict[str, dict[str, int]]:
    """``Design.validate()`` findings by code and severity, per origin (counted, not asserted)."""
    found: dict[str, Counter[str]] = {}
    for e in entries:
        counts = found.setdefault(e.origin, Counter())
        counts.update(f"{i.code}:{i.severity}" for i in e.design.validate())
    return _per_origin(found)


def census_headers(entries: Iterable[Entry]) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    for e in entries:
        parts: list[str] = []
        for head in ("version", "generator", "generator_version"):
            child = e.root.find(head)
            parts.append(child.atoms()[0].value if child is not None and child.atoms() else "-")
        headers.setdefault(" ".join(parts), []).append(e.id)
    return headers


def census_pintypes(entries: Iterable[Entry]) -> dict[str, dict[str, int]]:
    values: dict[str, Counter[str]] = {}
    for e in entries:
        counts = values.setdefault(e.origin, Counter())
        for _, node in walk(e.root):
            if node.name == "pad":
                pintype = node.find("pintype")
                if pintype is not None and pintype.atoms():
                    counts[pintype.atoms()[0].value] += 1
    return _per_origin(values)


# --- Edge.Cuts outlines (c0020; H-G-EDGE-EXACT): counts and gap sizes only ---------------------------

GAP_BUCKETS = ((1_000, "gap-up-to-1um"), (10_000, "gap-up-to-10um"))
EDGE_ITEM_HEADS = frozenset({"fp_line", "fp_arc", "fp_rect", "fp_poly", "fp_circle", "fp_curve"})


def gap_bucket(gap_nm: int) -> str:
    return next((name for limit, name in GAP_BUCKETS if gap_nm <= limit), "gap-larger")


def edge_pieces(design: Design) -> tuple[list[Segment | Arc], int, int]:
    """The root graphics on ``edge`` layers as pieces, with the counts of circles (rings by themselves)
    and of zero-length pieces (left out)."""
    board = design.board
    assert board is not None
    edge = {layer.name for layer in board.layers if layer.kind == "edge"}
    pieces: list[Segment | Arc] = []
    circles = zero = 0
    for graphic in board.graphics:
        if graphic.layer not in edge:
            continue
        points = graphic.points
        if graphic.kind == "circle":
            circles += 1
            continue
        if graphic.kind == "arc" and len(points) == 3:
            found: list[Segment | Arc] = [Arc(points[0], points[1], points[2])]
        elif graphic.kind == "rect" and len(points) == 2:
            (x0, y0), (x1, y1) = (points[0].x, points[0].y), (points[1].x, points[1].y)
            corners = (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))
            found = [Segment(a, b) for a, b in zip(corners, (*corners[1:], corners[0]), strict=True)]
        elif graphic.kind == "polygon":
            found = [Segment(a, b) for a, b in zip(points, (*points[1:], points[0]), strict=True)]
        else:
            found = [Segment(a, b) for a, b in zip(points, points[1:], strict=False)]
        for piece in found:
            if piece.start == piece.end:
                zero += 1
            else:
                pieces.append(piece)
    return pieces, circles, zero


def smallest_gap(pieces: list[Segment | Arc]) -> int | None:
    """The smallest distance between two loose endpoints, in whole nanometres rounded up."""
    uses = Counter(p for piece in pieces for p in (piece.start, piece.end))
    loose = sorted(p for p, n in uses.items() if n == 1)
    best: int | None = None
    for i, a in enumerate(loose):
        for b in loose[i + 1 :]:
            d2 = (a.x - b.x) ** 2 + (a.y - b.y) ** 2
            gap = math.isqrt(d2 - 1) + 1 if d2 else 0
            best = gap if best is None else min(best, gap)
    return best


def outline_outcome(design: Design) -> dict[str, Any]:
    """What ``assemble_rings`` makes of one board's root edge graphics; never raises on the outcome."""
    pieces, circles, zero = edge_pieces(design)
    outcome: dict[str, Any] = {"pieces": len(pieces), "circles": circles, "zero_length": zero}
    if not pieces:
        return outcome | {"result": "no-pieces"}
    try:
        return outcome | {"result": "chained", "rings": len(assemble_rings(pieces))}
    except GeometryError as error:
        outcome |= {"result": error.code}
        if error.code == OPEN_CONTOUR:
            gap = smallest_gap(pieces)
            outcome |= {"gap_nm": gap, "bucket": "gap-none" if gap is None else gap_bucket(gap)}
        return outcome


def footprint_edge_items(root: Node) -> int:
    """Edge items inside footprints: counted only, because their children stay opaque."""
    count = 0
    for _, node in walk(root):
        if node.name in EDGE_ITEM_HEADS:
            layer = node.find("layer")
            if layer is not None and layer.atoms() and layer.atoms()[0].value == "Edge.Cuts":
                count += 1
    return count


def census_outline(entries: Iterable[Entry]) -> dict[str, dict[str, int]]:
    """Per origin: boards by outcome, gap buckets of the open contours, and the counted-only items."""
    found: dict[str, Counter[str]] = {}
    for e in entries:
        counts = found.setdefault(e.origin, Counter())
        outcome = outline_outcome(e.design)
        counts["boards"] += 1
        counts[f"boards:{outcome['result']}"] += 1
        if "bucket" in outcome:
            counts[f"boards:{outcome['bucket']}"] += 1
        counts["rings"] += outcome.get("rings", 0)
        counts["circles"] += outcome["circles"]
        counts["zero-length-pieces"] += outcome["zero_length"]
        counts["footprint-edge-items"] += footprint_edge_items(e.root)
    return _per_origin(found)


# --- demo boards with their project files (c0068): the copper censuses --------------------------------


def checked_items() -> tuple[CorpusItem, ...]:
    """The cached, readable, non-heavy demo boards."""
    return tuple(i for i in READABLE_ITEMS if i.path.is_file() and not i.heavy)


def project_of(item: CorpusItem) -> Path | None:
    """The cached project file of a demo board: the ``project`` row of the same tag and file stem."""
    tag = item.id.rsplit("-pcb-", 1)[0]
    for row in manifest_items("project"):
        if row.id.startswith(f"{tag}-pro-") and row.path.stem == item.path.stem and row.path.is_file():
            return row.path
    return None
