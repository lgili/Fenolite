# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The model of a board against ``kicad-cli pcb export pos`` and ``pcb export ipcd356`` (change c0009).

Placements compare exactly (``--units mm`` prints 6 decimals, 1 nm). Pads compare relative to a
reference pad within ±2 export units per axis: each IPC-D-356 value is quantised to 2540 nm and the
export origin is unknown (S-0019). The export truncates references to 6 characters and pins to 4.
"""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.backends.kicad.ipcd356 import Ipcd356, Ipcd356Record
from fenolite.core.units import parse_angle, parse_length
from fenolite.geometry import Point, Transform
from fenolite.model.board import FootprintInstance, Pad
from fenolite.model.circuit import Component
from fenolite.model.design import Design

FULL_TURN = 360_000_000
BOUND = 2  # export units per axis
REF_WIDTH, PIN_WIDTH = 6, 4


@dataclass(frozen=True)
class PosRow:
    """One placement row in the file frame (Y down): reference, position, rotation mod 360°, side."""

    ref: str
    position: Point
    rotation: int
    side: str


def read_pos(text: str) -> list[PosRow]:
    """``pcb export pos --format csv --units mm``: ``Ref,Val,Package,PosX,PosY,Rot,Side``."""
    rows: list[PosRow] = []
    for row in csv.DictReader(io.StringIO(text)):
        x = parse_length(row["PosX"], default_unit="mm")
        y = -parse_length(row["PosY"], default_unit="mm")
        rotation = parse_angle(row["Rot"], default_unit="deg") % FULL_TURN
        rows.append(PosRow(row["Ref"], Point(x, y), rotation, row["Side"].strip()))
    return rows


def _component(design: Design, fp: FootprintInstance) -> Component:
    found = design.by_id[fp.component_id]
    assert isinstance(found, Component)
    return found


def placements(design: Design) -> list[PosRow]:
    """The model's footprints as placement rows, without those excluded from position files."""
    board = design.board
    assert board is not None
    return [
        PosRow(_component(design, fp).ref, fp.position, fp.rotation % FULL_TURN, fp.side)
        for fp in board.footprints
        if "exclude_from_pos_files" not in fp.attributes
    ]


def pos_problems(design: Design, rows: list[PosRow]) -> list[str]:
    """Differences between the export and the model, compared as multisets per reference."""
    exported: dict[str, Counter[PosRow]] = defaultdict(Counter)
    for row in rows:
        exported[row.ref][row] += 1
    modelled: dict[str, Counter[PosRow]] = defaultdict(Counter)
    for row in placements(design):
        modelled[row.ref][row] += 1
    problems: list[str] = []
    for ref in sorted(set(exported) | set(modelled)):
        if exported[ref] != modelled[ref]:
            only_export = list((exported[ref] - modelled[ref]).elements())[:1]
            only_model = list((modelled[ref] - exported[ref]).elements())[:1]
            problems.append(f"{ref}: export {only_export}, model {only_model}")
    return problems


def bottom_rotations(design: Design, rows: list[PosRow]) -> list[tuple[int, int]]:
    """``(stored angle, exported angle)`` in degrees for bottom footprints with a unique reference."""
    board = design.board
    assert board is not None
    by_ref: dict[str, list[FootprintInstance]] = defaultdict(list)
    for fp in board.footprints:
        by_ref[_component(design, fp).ref].append(fp)
    pairs: list[tuple[int, int]] = []
    for row in rows:
        fps = by_ref.get(row.ref, [])
        if row.side == "bottom" and len(fps) == 1:
            pairs.append((fps[0].rotation // 1_000_000, row.rotation // 1_000_000))
    return pairs


@dataclass
class PadReport:
    """The outcome of the IPC-D-356 comparison and the counts the census records."""

    problems: list[str] = field(default_factory=lambda: [])
    vias: int = 0
    truncated_keys: int = 0
    ambiguous_keys: int = 0
    matched: int = 0
    r_fields: Counter[tuple[int, int]] = field(default_factory=lambda: Counter())


@dataclass(frozen=True)
class _ModelPad:
    key: tuple[str, str]
    ref: str
    pad: Pad
    absolute: Point
    stored_angle: int


def _model_pads(design: Design) -> list[_ModelPad]:
    board = design.board
    assert board is not None
    found: list[_ModelPad] = []
    for fp in board.footprints:
        ref = _component(design, fp).ref
        placement = Transform.placement(fp.position, fp.rotation)
        for pad in fp.pads:
            stored = (pad.rotation + fp.rotation) % FULL_TURN
            key = (ref[:REF_WIDTH], pad.number[:PIN_WIDTH])
            found.append(_ModelPad(key, ref, pad, placement.apply(pad.position), stored))
    return found


def _export_frame(point: Point, unit_nm: int) -> tuple[Fraction, Fraction]:
    """File frame (nm, Y down) to export units (Y up), before the unknown origin."""
    return Fraction(point.x, unit_nm), Fraction(-point.y, unit_nm)


def pad_report(design: Design, export: Ipcd356) -> PadReport:
    report = PadReport()
    unit = export.unit_nm
    records = [r for r in export.records if not (r.ref == "VIA" and r.pin == "")]
    report.vias = len(export.records) - len(records)
    by_key: dict[tuple[str, str], list[_ModelPad]] = defaultdict(list)
    for model_pad in _model_pads(design):
        by_key[model_pad.key].append(model_pad)
    record_keys = Counter((r.ref, r.pin) for r in records)
    report.ambiguous_keys = sum(1 for k, n in record_keys.items() if n > 1 or len(by_key.get(k, [])) > 1)
    report.truncated_keys = sum(
        1 for pads in by_key.values() for p in pads if len(p.ref) > REF_WIDTH or len(p.pad.number) > PIN_WIDTH
    )
    unique = [
        r for r in records if record_keys[(r.ref, r.pin)] == 1 and len(by_key.get((r.ref, r.pin), [])) == 1
    ]
    if unique:
        anchors = [(unique[0], by_key[(unique[0].ref, unique[0].pin)][0])]
    else:  # no unique key: try each pad of the first record's key as the reference
        first = next((r for r in records if by_key.get((r.ref, r.pin))), None)
        anchors = [(first, pad) for pad in by_key[(first.ref, first.pin)]] if first is not None else []
    if not anchors:
        report.problems.append("no record matches a model pad key")
        return report
    attempts = [_match(records, by_key, anchor, unit) for anchor in anchors]
    pairs, problems = next((a for a in attempts if not a[1]), attempts[0])
    report.problems += problems
    for record, model_pad in pairs:
        if record.rotation is not None:
            report.r_fields[(model_pad.stored_angle // 1_000_000, record.rotation)] += 1
    report.matched = len(pairs)
    report.problems += _partition_problems(pairs)
    return report


def _match(
    records: list[Ipcd356Record],
    by_key: dict[tuple[str, str], list[_ModelPad]],
    anchor: tuple[Ipcd356Record, _ModelPad],
    unit: int,
) -> tuple[list[tuple[Ipcd356Record, _ModelPad]], list[str]]:
    """Pair every record with a distinct pad of its key, positions relative to ``anchor``."""
    reference, reference_pad = anchor
    ref_x, ref_y = _export_frame(reference_pad.absolute, unit)
    origin = (reference.x - ref_x, reference.y - ref_y)
    taken: set[int] = set()
    pairs: list[tuple[Ipcd356Record, _ModelPad]] = []
    problems: list[str] = []
    for record in records:
        best: tuple[Fraction, _ModelPad] | None = None
        for candidate in by_key.get((record.ref, record.pin), []):
            if id(candidate) in taken:
                continue
            x, y = _export_frame(candidate.absolute, unit)
            dx, dy = abs(record.x - origin[0] - x), abs(record.y - origin[1] - y)
            if dx <= BOUND and dy <= BOUND and (best is None or dx + dy < best[0]):
                best = (dx + dy, candidate)
        if best is None:
            problems.append(f"{record.ref} pin {record.pin}: no model pad within the bound")
            continue
        taken.add(id(best[1]))
        pairs.append((record, best[1]))
    return pairs, problems


def _partition_problems(pairs: list[tuple[Ipcd356Record, _ModelPad]]) -> list[str]:
    export_to_model: dict[str, set[str | None]] = defaultdict(set)
    model_to_export: dict[str | None, set[str]] = defaultdict(set)
    for record, model_pad in pairs:
        export_to_model[record.net].add(model_pad.pad.net_id)
        model_to_export[model_pad.pad.net_id].add(record.net)
    problems = [
        f"export net {net!r} spans {len(ids)} model nets"
        for net, ids in export_to_model.items()
        if len(ids) > 1
    ]
    problems += [
        f"model net {nid} spans export nets {sorted(nets)}"
        for nid, nets in model_to_export.items()
        if len(nets) > 1
    ]
    return problems
