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

from fenolite.backends.kicad import padnets
from fenolite.backends.kicad.ipcd356 import Ipcd356
from fenolite.core.units import parse_angle, parse_length
from fenolite.geometry import Point
from fenolite.model.board import FootprintInstance
from fenolite.model.circuit import Component
from fenolite.model.design import Design

FULL_TURN = 360_000_000
BOUND = padnets.BOUND_UNITS  # export units per axis
REF_WIDTH, PIN_WIDTH = padnets.REF_WIDTH, padnets.PIN_WIDTH


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


def pad_report(design: Design, export: Ipcd356) -> PadReport:
    """The IPC-D-356 comparison through ``padnets.match_pads`` (c0020 moved the matcher into ``src``)."""
    report = PadReport()
    match = padnets.match_pads(design, export)
    report.vias, report.truncated_keys, report.ambiguous_keys = (
        match.vias,
        match.truncated_keys,
        match.ambiguous_keys,
    )
    report.problems += match.problems
    if not match.pairs:
        return report
    for pair in match.pairs:
        if pair.record.rotation is not None:
            report.r_fields[(pair.stored_angle // 1_000_000, pair.record.rotation)] += 1
    report.matched = len(match.pairs)
    report.problems += _partition_problems(match.pairs)
    return report


def _partition_problems(pairs: tuple[padnets.MatchedPad, ...]) -> list[str]:
    export_to_model: dict[str, set[str | None]] = defaultdict(set)
    model_to_export: dict[str | None, set[str]] = defaultdict(set)
    for pair in pairs:
        export_to_model[pair.record.net].add(pair.pad.net_id)
        model_to_export[pair.pad.net_id].add(pair.record.net)
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
