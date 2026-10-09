# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The impedance table for the fabricator (capability manufacturing-exports, "Impedance table for the
fabricator"; user guide ``docs/impedance.md``; change c0105).

One row per impedance target and layer, from the model only: no tool runs and nothing is written here.
``fenolite impedance`` adds the estimates of ``analysis.impedance`` and plans the CSV file.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, format_length
from fenolite.exports.assembly import CsvOptions
from fenolite.exports.assembly import render_csv as render_table
from fenolite.model.board import Stackup
from fenolite.model.design import Design
from fenolite.model.rules import ImpedanceKind

COLUMNS: tuple[str, ...] = (
    "target",
    "kind",
    "structure",
    "layer",
    "references",
    "ohms",
    "tolerance_percent",
    "width_mm",
    "gap_mm",
    "heights_mm",
    "epsilon_r",
    "classes",
    "nets",
)
"""The CSV header of the table."""
ESTIMATE_COLUMNS: tuple[str, ...] = ("estimate_ohms", "suggested_width_mm")
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "impedance.none": "info",
        "impedance.no-stackup": "warning",
        "impedance.estimate-unsupported": "info",
        "impedance.mixed-dielectric": "info",
        "impedance.out-of-range": "warning",
        "impedance.off-target": "warning",
    }
)
"""The closed table of the codes of the impedance table and of ``fenolite impedance``."""
EVIDENCE = Evidence(Level.INFERRED)
"""The table itself is mechanical: it copies the model. Its level is the level of the design's source,
which ``fenolite impedance`` combines with this one (``INFERRED`` for a built project, the read's for a
KiCad project)."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


@dataclass(frozen=True, slots=True)
class ImpedanceRow:
    """One row: a target on one layer, with the heights to each reference and the permittivity from the
    board's stack-up when it has one."""

    target: str
    kind: ImpedanceKind
    structure: str
    layer: str
    references: tuple[str, ...]
    ohms: str
    tolerance_percent: str
    width: Nm
    gap: Nm | None
    heights: tuple[Nm, ...] | None
    epsilon_r: str
    classes: tuple[str, ...]
    nets: tuple[str, ...]


def copper_layers(design: Design) -> tuple[str, ...]:
    """The copper layers of the board, top to bottom."""
    if design.board is None:
        return ()
    ordered = sorted(design.board.layers, key=lambda layer: layer.ordinal)
    return tuple(layer.name for layer in ordered if layer.kind == "copper")


def structure_of(copper: Sequence[str], layer: str, references: Sequence[str]) -> str:
    """``microstrip`` for one reference on an outer layer, ``stripline`` for two references on an inner
    layer, else ``""``."""
    if not copper or layer not in copper:
        return ""
    outer = layer in (copper[0], copper[-1])
    if outer and len(references) == 1:
        return "microstrip"
    if not outer and len(references) == 2:
        return "stripline"
    return ""


def _between(stackup: Stackup, layer: str, reference: str) -> tuple[int, set[str]] | None:
    names = [entry.name for entry in stackup.layers]
    if layer not in names or reference not in names or layer == reference:
        return None
    first, second = sorted((names.index(layer), names.index(reference)))
    entries = [entry for entry in stackup.between(names[first], names[second]) if entry.kind == "dielectric"]
    return sum(entry.thickness for entry in entries), {entry.epsilon_r for entry in entries}


def impedance_table(design: Design) -> tuple[ImpedanceRow, ...]:
    """One row per impedance target and layer of ``design``, sorted by target name, then in stack order."""
    targets = design.rules.impedance if design.rules is not None else ()
    classes = {c.id: c.name for c in design.circuit.netclasses}
    copper = copper_layers(design)
    rank = {name: index for index, name in enumerate(copper)}
    stackup = design.board.stackup if design.board is not None else None
    rows: list[ImpedanceRow] = []
    for target in sorted(targets, key=lambda t: t.name):
        names = tuple(classes.get(i, i) for i in target.netclass_ids)
        nets = tuple(sorted(n.name for n in design.circuit.nets if n.netclass_id in target.netclass_ids))
        for row in sorted(target.layers, key=lambda r: rank.get(r.layer, len(rank))):
            heights: tuple[Nm, ...] | None = None
            epsilon = ""
            if stackup is not None:
                found = [_between(stackup, row.layer, ref) for ref in row.references]
                if all(f is not None for f in found):
                    heights = tuple(f[0] for f in found if f is not None)
                    values = set[str]().union(*(f[1] for f in found if f is not None))
                    epsilon = next(iter(values)) if len(values) == 1 else ""
            rows.append(
                ImpedanceRow(
                    target=target.name,
                    kind=target.kind,
                    structure=structure_of(copper, row.layer, row.references),
                    layer=row.layer,
                    references=row.references,
                    ohms=target.ohms,
                    tolerance_percent=target.tolerance_percent,
                    width=row.width,
                    gap=row.gap,
                    heights=heights,
                    epsilon_r=epsilon,
                    classes=names,
                    nets=nets,
                )
            )
    return tuple(rows)


def millimetres(nm: Nm | None) -> str:
    """The exact millimetre text of ``nm`` (``200_000`` → ``0.2``), ``""`` for ``None``."""
    return "" if nm is None else format_length(nm, "mm")[: -len("mm")]


def milliohm_text(mohm: int | None) -> str:
    """Milliohms as exact ohm text (``50_763`` → ``50.763``), ``""`` for ``None``."""
    if mohm is None:
        return ""
    whole, part = divmod(mohm, 1000)
    return f"{whole}.{part:03d}".rstrip("0").rstrip(".") if part else str(whole)


def cells(row: ImpedanceRow) -> list[str]:
    """The text of one row in ``COLUMNS`` order."""
    return [
        row.target,
        row.kind,
        row.structure,
        row.layer,
        " ".join(row.references),
        row.ohms,
        row.tolerance_percent,
        millimetres(row.width),
        millimetres(row.gap),
        "" if row.heights is None else " ".join(millimetres(h) for h in row.heights),
        row.epsilon_r,
        " ".join(row.classes),
        " ".join(row.nets),
    ]


def render_csv(
    rows: Sequence[ImpedanceRow], estimates: Sequence[tuple[int | None, Nm | None]] | None = None
) -> bytes:
    """The table as CSV bytes through ``assembly.render_csv``; with ``estimates`` (one ``(milliohms,
    suggested width)`` per row) the two estimate columns follow."""
    header = list(COLUMNS)
    lines = [cells(row) for row in rows]
    if estimates is not None:
        header += ESTIMATE_COLUMNS
        lines = [
            [*line, milliohm_text(mohm), millimetres(width)]
            for line, (mohm, width) in zip(lines, estimates, strict=True)
        ]
    return render_table(header, lines, CsvOptions())


__all__ = [
    "COLUMNS",
    "ESTIMATE_COLUMNS",
    "EVIDENCE",
    "ISSUE_CODES",
    "ImpedanceRow",
    "cells",
    "copper_layers",
    "impedance_table",
    "issue",
    "millimetres",
    "milliohm_text",
    "render_csv",
    "structure_of",
]
