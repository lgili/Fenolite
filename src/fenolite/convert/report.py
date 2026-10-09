# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The report of a conversion: per kind of model item, what the source holds and what the target keeps,
changes or loses, each change and loss counted under its own reason (capability design-conversion,
"Conversion report" and "Conversion kinds"; change c0159).

``KINDS`` is one vocabulary for every direction: the kinds of the Altium write (``lower.KINDS`` and
``lower.MORE_KINDS``, ``dnp`` among them) and the kinds of the KiCad directions. A lost item of a
``refuse`` kind changes the board that is made or its bill of materials, and needs consent. ``EXPLAINS``
says which differences of the read-back a lost item explains, and where.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from fenolite.model.design import Design

Group = Literal["circuit", "footprint", "copper", "board", "presentation", "project"]
LossClass = Literal["refuse", "report"]
Outcome = Literal["changed", "lost"]
Scope = Literal["ref", "pin", "net", "net-pins", "footprint-nets", "same"]
GROUPS: tuple[Group, ...] = ("circuit", "footprint", "copper", "board", "presentation", "project")


@dataclass(frozen=True, slots=True)
class KindRow:
    """One kind of the vocabulary: its name, its group, and whether a loss of it needs consent."""

    name: str
    group: Group
    loss: LossClass


def _rows(group: Group, refuse: Iterable[str], report: Iterable[str]) -> tuple[KindRow, ...]:
    return (
        *(KindRow(name, group, "refuse") for name in refuse),
        *(KindRow(name, group, "report") for name in report),
    )


KINDS: tuple[KindRow, ...] = (
    *_rows("circuit", ("net", "netclass", "dnp"), ("module", "channel", "pin-pad-map", "pin-pads")),
    *_rows(
        "footprint",
        ("footprint", "pad", "footprint-copper"),
        ("body", "footprint-graphic", "footprint-text", "net-tie"),
    ),
    *_rows(
        "copper",
        ("track", "arc", "via", "zone", "copper-shape", "plane"),
        ("zone-fill", "via-pad-shape", "via-protection"),
    ),
    *_rows(
        "board",
        (),
        (
            "outline",
            "stackup",
            "keep-out",
            "hole",
            "rule",
            "severity",
            "placement-rule",
            "keepout-footprints",
        ),
    ),
    *_rows("presentation", (), ("text", "graphic", "dimension")),
    *_rows("project", (), ("schematic",)),
)
"""The closed vocabulary of kinds, in report order. Every kind that ``lower.LOSS_KINDS`` names and ``dnp``
are ``refuse``; ``schematic`` is a project file, generated (a change) or not converted (a loss)."""
BY_NAME: Mapping[str, KindRow] = MappingProxyType({row.name: row for row in KINDS})
REFUSE: frozenset[str] = frozenset(row.name for row in KINDS if row.loss == "refuse")
SOURCE = "source"
"""Not a kind: the explanation of a difference that the source holds against itself (a reference that
several components share, on both sides alike)."""


@dataclass(frozen=True, slots=True)
class Reason:
    """The items of one kind changed or lost for one reason."""

    reason: str
    outcome: Outcome
    ids: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.ids)

    def to_json(self, *, ids: bool = False) -> dict[str, Any]:
        row: dict[str, Any] = {"reason": self.reason, "outcome": self.outcome, "count": self.count}
        if ids:
            row["ids"] = list(self.ids)
        return row


@dataclass(frozen=True, slots=True)
class ReportRow:
    """One kind: how many items the source holds, how many the target holds as they were (``written``),
    in another form that compares equal (``changed``) or not at all (``lost``), and the reasons."""

    kind: str
    source: int
    written: int
    changed: int
    lost: int
    reasons: tuple[Reason, ...] = ()

    @property
    def group(self) -> Group:
        return BY_NAME[self.kind].group if self.kind in BY_NAME else "board"

    @property
    def loss(self) -> LossClass:
        return BY_NAME[self.kind].loss if self.kind in BY_NAME else "report"

    def ids(self, outcome: Outcome = "lost") -> tuple[str, ...]:
        """The ids of the items of ``outcome``, every reason in order."""
        return tuple(i for reason in self.reasons if reason.outcome == outcome for i in reason.ids)

    def to_json(self, *, ids: bool = False) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "group": self.group,
            "loss": self.loss,
            "source": self.source,
            "written": self.written,
            "changed": self.changed,
            "lost": self.lost,
            "reasons": [reason.to_json(ids=ids) for reason in self.reasons],
        }


Items = Mapping[str, Mapping[str, Iterable[str]]]
"""Kind → reason → the ids of the items (``lower.AltiumInputs.lost``)."""


def _reasons(changed: Mapping[str, Iterable[str]], lost: Mapping[str, Iterable[str]]) -> tuple[Reason, ...]:
    found = [Reason(reason, "changed", tuple(ids)) for reason, ids in changed.items()]
    found += [Reason(reason, "lost", tuple(ids)) for reason, ids in lost.items()]
    return tuple(sorted((r for r in found if r.ids), key=lambda r: (-r.count, r.reason, r.outcome)))


@dataclass(frozen=True, slots=True)
class ConversionReport:
    """The rows of a conversion, in the order of ``KINDS`` (a kind outside the table, which a unit test
    forbids, comes last)."""

    rows: tuple[ReportRow, ...] = ()

    @classmethod
    def of(
        cls,
        *,
        source: Mapping[str, int],
        written: Mapping[str, int] | None = None,
        changed: Items | None = None,
        lost: Items | None = None,
    ) -> ConversionReport:
        """The report of the counts ``source`` (what the source holds, per kind), ``written`` (the
        writer's own count of what it wrote, per kind, where it keeps one) and the items ``changed`` and
        ``lost`` per kind and reason. A kind without a count in ``source`` holds what was written, changed
        and lost; a kind without a count in ``written`` wrote what was neither changed nor lost."""
        written, changed, lost = written or {}, changed or {}, lost or {}
        kinds = set(source) | set(written) | set(changed) | set(lost)
        order = [row.name for row in KINDS] + sorted(kinds - set(BY_NAME))
        rows: list[ReportRow] = []
        for kind in order:
            if kind not in kinds:
                continue
            reasons = _reasons(changed.get(kind, {}), lost.get(kind, {}))
            n_changed = sum(r.count for r in reasons if r.outcome == "changed")
            n_lost = sum(r.count for r in reasons if r.outcome == "lost")
            if kind in source:
                n_source = source[kind]
            else:
                n_source = written.get(kind, 0) + n_changed + n_lost
            n_written = written[kind] if kind in written else max(n_source - n_changed - n_lost, 0)
            if not (n_source or n_written or n_changed or n_lost):
                continue
            rows.append(ReportRow(kind, n_source, n_written, n_changed, n_lost, reasons))
        return cls(tuple(rows))

    def row(self, kind: str) -> ReportRow | None:
        return next((row for row in self.rows if row.kind == kind), None)

    @property
    def lossy(self) -> bool:
        return any(row.lost for row in self.rows)

    @property
    def refused(self) -> tuple[str, ...]:
        """The ``refuse`` kinds with losses, in report order."""
        return tuple(row.kind for row in self.rows if row.lost and row.loss == "refuse")

    def to_json(self, *, ids: bool = False) -> dict[str, Any]:
        """``result.report`` of ``fenolite convert``; the ids of the items only with ``ids``."""
        return {
            "lossy": self.lossy,
            "refused": list(self.refused),
            "rows": [row.to_json(ids=ids) for row in self.rows],
        }


def merge(*reports: ConversionReport) -> ConversionReport:
    """One report of several: the counts of a kind added, its reasons joined (equal reasons as one)."""
    source: dict[str, int] = {}
    written: dict[str, int] = {}
    changed: dict[str, dict[str, list[str]]] = {}
    lost: dict[str, dict[str, list[str]]] = {}
    for report in reports:
        for row in report.rows:
            source[row.kind] = source.get(row.kind, 0) + row.source
            written[row.kind] = written.get(row.kind, 0) + row.written
            for reason in row.reasons:
                into = changed if reason.outcome == "changed" else lost
                into.setdefault(row.kind, {}).setdefault(reason.reason, []).extend(reason.ids)
    return ConversionReport.of(source=source, written=written, changed=changed, lost=lost)


def census(design: Design) -> dict[str, int]:
    """What ``design`` holds per kind, for the kinds that are model entities one by one; the other kinds
    are counted by the writer that touches them."""
    circuit, board, rules = design.circuit, design.board, design.rules
    found: dict[str, int] = {
        "net": len(circuit.nets),
        "netclass": len(circuit.netclasses),
        "dnp": sum(1 for component in circuit.components if component.dnp),
        "module": len(circuit.modules),
        "pin-pad-map": sum(1 for component in circuit.components if component.pin_pad_map),
    }
    if rules is not None:
        found["rule"] = len(rules.rules)
        found["severity"] = len(rules.severities)
        found["placement-rule"] = len(rules.proximity) + len(rules.heights)
    if board is not None:
        footprints = board.footprints
        copper = [g for fp in footprints for g in fp.graphics if g.layer.endswith(".Cu")]
        found.update(
            {
                "footprint": len(footprints),
                "pad": sum(len(fp.pads) for fp in footprints),
                "body": sum(len(fp.bodies) for fp in footprints),
                "footprint-copper": len(copper),
                "net-tie": sum(1 for fp in footprints if fp.net_ties),
                "track": len(board.tracks),
                "arc": len(board.arcs),
                "via": len(board.vias),
                "zone": len(board.zones),
                "zone-fill": sum(1 for zone in board.zones if zone.fills),
                "keep-out": len(board.keepouts),
                "keepout-footprints": sum(1 for keepout in board.keepouts if keepout.no_footprints),
                "hole": len(board.holes),
                "stackup": int(board.stackup is not None),
                "text": len(board.texts),
                "dimension": len(board.dimensions),
            }
        )
    return {kind: count for kind, count in found.items() if count}


LEVEL5: tuple[str, ...] = (
    "route-missing",
    "route-connectivity",
    "route-vias",
    "route-length",
    "route-stub",
    "route-unjudged",
)
"""The difference kinds of level 5, located at a net."""
AT_REF: tuple[str, ...] = (
    "component-missing",
    "value",
    "dnp",
    "pin-missing",
    "net",
    "footprint-missing",
    "footprint-name",
    "pad-missing",
    "pad-kind",
    "pad-shape",
    "pad-size",
    "pad-drill",
    "pad-position",
    "pad-rotation",
    "pad-copper",
    "side",
    "position",
    "rotation",
)
"""The difference kinds of levels 1 to 4, located at a reference or at one of its pins."""


@dataclass(frozen=True, slots=True)
class Explains:
    """A lost item of ``kind`` explains a difference of one of ``differences`` located in ``scope``:
    ``ref`` its reference or a pin of it, ``pin`` its own ``REF-PIN``, ``net`` its net, ``net-pins`` a pin
    on its net, ``footprint-nets`` the net of a pad of its footprint, ``same`` a difference whose two sides
    hold the same value (the source's own, kind ``SOURCE``)."""

    kind: str
    differences: tuple[str, ...]
    scope: Scope


EXPLAINS: tuple[Explains, ...] = (
    Explains("footprint", AT_REF, "ref"),
    Explains("footprint", LEVEL5, "footprint-nets"),
    Explains("pad", ("pad-missing", "pin-missing"), "pin"),
    Explains("pad", LEVEL5, "net"),
    Explains("track", LEVEL5, "net"),
    Explains("arc", LEVEL5, "net"),
    Explains("via", LEVEL5, "net"),
    Explains("zone", LEVEL5, "net"),
    Explains("net", ("net",), "net-pins"),
    Explains("net", LEVEL5, "net"),
    Explains("dnp", ("dnp",), "ref"),
    Explains("footprint-copper", LEVEL5, "footprint-nets"),
    Explains("net-tie", LEVEL5, "footprint-nets"),
    Explains(SOURCE, ("ref-ambiguous",), "same"),
)
"""The closed table of which differences a lost item explains. A lost pad explains only its own
``pad-missing`` and ``pin-missing`` and the level-5 kinds of its net, not every difference at its pin."""


def _prefixes(where: str, separator: str) -> Iterable[str]:
    """``where`` and each of its prefixes that ends before ``separator``."""
    yield where
    index = where.find(separator)
    while index >= 0:
        yield where[:index]
        index = where.find(separator, index + 1)


class Explainer:
    """The places that the lost items of ``report`` explain, located in ``design``, the design the
    direction wrote (its ids are those of the report)."""

    def __init__(self, design: Design, report: ConversionReport) -> None:
        circuit, board = design.circuit, design.board
        refs = {component.id: component.ref for component in circuit.components}
        net_names = {net.id: net.name for net in circuit.nets}
        footprints = board.footprints if board is not None else ()
        by_footprint = {fp.id: fp for fp in footprints}
        pad_place: dict[str, tuple[str, str, str | None]] = {}
        footprint_of_graphic: dict[str, str] = {}
        for fp in footprints:
            ref = refs.get(fp.component_id, "")
            for pad in fp.pads:
                pad_place[pad.id] = (ref, pad.number, pad.net_id)
            for graphic in fp.graphics:
                footprint_of_graphic[graphic.id] = fp.id
        nets_of_items: dict[str, str | None] = {}
        if board is not None:
            for item in (*board.tracks, *board.arcs, *board.vias, *board.zones):
                nets_of_items[item.id] = item.net_id

        def fp_nets(fp_id: str | None) -> set[str]:
            fp = by_footprint.get(fp_id or "")
            if fp is None:
                return set()
            return {net_names[p.net_id] for p in fp.pads if p.net_id and p.net_id in net_names}

        self._places: dict[tuple[str, Scope], set[str]] = {}
        for row in report.rows:
            ids = row.ids("lost")
            if not ids:
                continue
            kind = row.kind
            if kind in ("footprint", "net-tie"):
                fps = [by_footprint[i] for i in ids if i in by_footprint]
                self._add(kind, "ref", {refs.get(fp.component_id, "") for fp in fps})
                self._add(kind, "footprint-nets", {net for fp in fps for net in fp_nets(fp.id)})
            elif kind == "pad":
                placed = [pad_place[i] for i in ids if i in pad_place]
                self._add(kind, "pin", {f"{ref}-{number}" for ref, number, _ in placed})
                self._add(kind, "net", {net_names[n] for _, _, n in placed if n and n in net_names})
            elif kind in ("track", "arc", "via", "zone"):
                found = (nets_of_items.get(i) for i in ids)
                self._add(kind, "net", {net_names[n] for n in found if n is not None and n in net_names})
            elif kind == "net":
                lost = set(ids)
                names = {net_names[i] for i in lost if i in net_names}
                self._add(kind, "net", names)
                self._add(
                    kind,
                    "net-pins",
                    {f"{ref}-{number}" for ref, number, n in pad_place.values() if n in lost and number},
                )
            elif kind == "dnp":
                self._add(kind, "ref", {refs[i] for i in ids if i in refs})
            elif kind == "footprint-copper":
                holders = {footprint_of_graphic.get(i) for i in ids}
                self._add(kind, "footprint-nets", {net for fp_id in holders for net in fp_nets(fp_id)})

    def _add(self, kind: str, scope: Scope, places: set[str]) -> None:
        places.discard("")
        if places:
            self._places.setdefault((kind, scope), set()).update(places)

    def explain(self, kind: str, where: str, a: str, b: str) -> str | None:
        """The lost kind that explains a difference of ``kind`` at ``where`` with the values ``a`` and
        ``b``, or ``None``."""
        for row in EXPLAINS:
            if kind not in row.differences:
                continue
            if row.scope == "same":
                if a == b and a:
                    return row.kind
                continue
            places = self._places.get((row.kind, row.scope))
            if not places:
                continue
            if row.scope in ("ref", "pin", "net-pins"):
                candidates = _prefixes(where, "-") if row.scope == "ref" else (where,)
            else:
                candidates = _prefixes(where, ":")
            if any(candidate in places for candidate in candidates):
                return row.kind
        return None


__all__ = [
    "AT_REF",
    "BY_NAME",
    "EXPLAINS",
    "GROUPS",
    "KINDS",
    "LEVEL5",
    "REFUSE",
    "SOURCE",
    "ConversionReport",
    "Explainer",
    "Explains",
    "Group",
    "KindRow",
    "LossClass",
    "Outcome",
    "Reason",
    "ReportRow",
    "Scope",
    "census",
    "merge",
]
