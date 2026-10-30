# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the DSL cannot express (change c0275, design decision 10): every item of the source that no
emitted call writes, counted by kind, with up to three examples.

The emitter reports what it leaves out while it writes; this module adds the board's root items that the
KiCad reader keeps as opaque fragments (a ``group``, a ``generated`` item, an image…), the model items
that no emitter writes yet, and maps each kind to the self-check differences it explains. The kinds that
change c0277 makes expressible (verbatim items, groups, holes, dimensions…) stay here until it is merged;
then each of its items removes its row.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.sexpr import Node
from fenolite.checks.equivalence.model import LevelId
from fenolite.core.errors import Issue
from fenolite.importer.codes import issue
from fenolite.model.base import Opaque
from fenolite.model.design import Design

INFRASTRUCTURE = frozenset(
    {"general", "paper", "setup", "net", "title_block", "embedded_fonts", "embedded_files"}
)
"""Root fragments of a board file that hold settings, not items: the build writes its own. The net table of
a KiCad 9 board is one (the nets come from the pads), and the title block, which the model holds and the
emitter writes as ``design.title_block()``."""
EXPLAINS: Mapping[str, tuple[tuple[int, str], ...]] = {
    "dnp": ((1, "dnp"),),
    "copper-without-net": ((5, "*"),),
    "zero-length-track": ((5, "*"),),
    "degenerate-arc": ((5, "*"),),
    "via-protection": ((5, "*"),),
    "via-span": ((5, "*"),),
    "pad-net-conflict": ((2, "*"), (5, "*")),
    "duplicate-ref": ((1, "ref-ambiguous"), (5, "*")),
    "footprint-ref": ((1, "component-missing"), (1, "ref-ambiguous"), (5, "*")),
    "footprint": ((1, "component-missing"), (5, "*")),
}
"""Each kind → the (level, difference kind) it explains in the self-check; ``*`` is any kind."""


@dataclass(frozen=True, slots=True)
class Unexpressed:
    """One kind of item no DSL call expresses: the count and up to three examples."""

    kind: str
    count: int
    examples: tuple[str, ...] = ()

    def as_json(self) -> dict[str, object]:
        return {"kind": self.kind, "count": self.count, "examples": list(self.examples)}


@dataclass
class Ledger:
    """What the emitter leaves out, by kind, as it writes, and the board items it does not write because
    the tool that fills the board draws them again (``regenerated``, by kind; change c0277)."""

    counts: Counter[str] = field(default_factory=lambda: Counter[str]())
    examples: dict[str, list[str]] = field(default_factory=lambda: {})
    regenerated: Counter[str] = field(default_factory=lambda: Counter[str]())
    teardrops_lost: int = 0
    """Vias and footprints left out that hold teardrop settings (their teardrops would not come back)."""

    def add(self, kind: str, example: str = "", count: int = 1) -> None:
        self.counts[kind] += count
        shown = self.examples.setdefault(kind, [])
        if example and len(shown) < 3 and example not in shown:
            shown.append(example)

    def rows(self) -> tuple[Unexpressed, ...]:
        return tuple(
            Unexpressed(kind, count, tuple(self.examples.get(kind, ())))
            for kind, count in sorted(self.counts.items())
            if count
        )


TEARDROP_REGENERATED = "padvia"
"""The type of a teardrop zone that the filling tool draws again from the teardrop settings of the pad or via
it joins, which the code keeps: the pads' in their vendored footprints, the vias' in their tables."""


def _root_heads(design: Design) -> Iterable[str]:
    """The head of each opaque root item of the board; a teardrop zone is ``teardrop`` with its type
    (``teardrop:padvia``), or ``teardrop`` when it states none."""
    board = design.board
    if board is None or "kicad" not in board.ext:
        return
    for slot in slotlib.from_ext(board.ext["kicad"]):
        if isinstance(slot, Opaque):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name not in INFRASTRUCTURE:
                attr = child.find("attr") if child.name == "zone" else None
                drop = attr.find("teardrop") if attr is not None else None
                if drop is None:
                    yield child.name
                    continue
                kind = drop.find("type")
                atoms = kind.atoms() if kind is not None else ()
                yield f"teardrop:{atoms[0].value}" if len(atoms) == 1 else "teardrop"


def scan(design: Design, ledger: Ledger) -> None:
    """Add the board's opaque root items and the model items no emitter writes to ``ledger``. A teardrop
    zone of the type ``TEARDROP_REGENERATED`` is counted as regenerated, unless teardrop settings were lost: a
    via's that could not be read (``teardrop-setting``), or a left-out via's or footprint's
    (``ledger.teardrops_lost``); then every teardrop zone is unexpressed."""
    settings_lost = ledger.counts["teardrop-setting"] > 0 or ledger.teardrops_lost > 0
    for head in _root_heads(design):
        if head == f"teardrop:{TEARDROP_REGENERATED}" and not settings_lost:
            ledger.regenerated["teardrop"] += 1
        elif head.startswith("teardrop"):
            ledger.add("teardrop", head)
        else:
            ledger.add(head, head)
    board = design.board
    if board is None:
        return
    for hole in board.holes:
        ledger.add("hole", hole.id)
    for dimension in board.dimensions:
        ledger.add("dimension", f"{dimension.kind} on {dimension.layer}")
    for component in design.circuit.components:
        if component.dnp:
            ledger.add("dnp", component.ref)
    for footprint in board.footprints:
        if footprint.net_ties:
            ledger.add("net-tie", footprint.lib_ref)


def lossy_issues(rows: Iterable[Unexpressed]) -> tuple[Issue, ...]:
    """One ``import.item-unexpressed`` warning per kind (with ``--allow-lossy``)."""
    return tuple(
        issue(
            "import.item-unexpressed",
            f"{row.count} item(s) of kind {row.kind} cannot be expressed in the DSL and are left out"
            + (f" (for example {', '.join(row.examples)})" if row.examples else ""),
            where=row.kind,
            hint="change c0277 adds verbatim items for what the DSL does not say",
        )
        for row in rows
    )


def explained(level: LevelId, kind: str, rows: Iterable[Unexpressed]) -> bool:
    """Whether a self-check difference of ``kind`` at ``level`` is explained by an unexpressed kind."""
    for row in rows:
        for at, what in EXPLAINS.get(row.kind, ()):
            if at == level and what in ("*", kind):
                return True
    return False


def regenerated_issues(ledger: Ledger) -> tuple[Issue, ...]:
    """One ``import.teardrops-regenerated`` (info) when teardrop zones were left to the filling tool."""
    count = ledger.regenerated["teardrop"]
    if not count:
        return ()
    return (
        issue(
            "import.teardrops-regenerated",
            f"{count} teardrop zone(s) are not written: KiCad draws them again from the teardrop settings "
            "of the pads and vias, which the code keeps, when it fills the board",
            where="teardrop",
            hint="run fenolite fill on the built board to draw them",
        ),
    )


__all__ = [
    "EXPLAINS",
    "INFRASTRUCTURE",
    "TEARDROP_REGENERATED",
    "Ledger",
    "Unexpressed",
    "explained",
    "lossy_issues",
    "regenerated_issues",
    "scan",
]
