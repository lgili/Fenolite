# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The checks of ``fenolite ready`` that are not oracle stages (capability verification-loop, "Shared
readiness definitions" to "Readiness issue codes"; change c0098; ``docs/cli-contract.md``, "ready").

``fenolite ready`` gathers six checks in one reply, each a ``StageResult`` as ``check`` gives its stages:
``nets.open`` (the open connections of ``analysis.connectivity``, which the command computes and hands in
as ``OpenNet`` rows, since ``checks`` may not import ``analysis``), ``erc.kicad`` and ``drc.kicad`` (the
stages of ``check``, run unchanged), and three rules judged here on the design: pins left unconnected
without a no-connect mark, power nets with neither a declared track width nor a zone, and parts without a
footprint or a value. The rules are Fenolite's own definitions (``H-G-READY-RULES``), so their evidence is
``INFERRED``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.checks.clearance import DEFAULT_CLASS
from fenolite.checks.stages import StageResult, ran
from fenolite.checks.validate import footprint_issue, unresolved_footprints
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Component, Pin, power_interface_nets
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject

READY_CHECKS: tuple[str, ...] = (
    "nets.open",
    "erc.kicad",
    "drc.kicad",
    "pins.unconnected",
    "power.nets",
    "parts.fields",
)
"""The checks of ``fenolite ready``, in the order they are reported."""
ORACLE_CHECKS: tuple[str, ...] = ("erc.kicad", "drc.kicad")
"""The checks that are stages of ``check`` and need ``kicad-cli``."""
READY_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "ready.net-open": "error",
        "ready.pin-unconnected": "error",
        "ready.power-net-unsized": "error",
        "ready.part-value-missing": "error",
        "ready.check-skipped": "warning",
    }
)
"""The closed table of the codes that ``fenolite ready`` adds ("Readiness issue codes")."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-READY-RULES",))
"""The level of the three rules: Fenolite's definitions, which no tool computes."""
POWER_PIN_TYPES = frozenset({"power_in", "power_out"})
"""The pin types that make a net a power net when no interface names it."""


def issue(code: str, message: str, *, where: str = "") -> Issue:
    """An ``Issue`` of a code of ``READY_ISSUE_CODES``, with its severity; ``KeyError`` for another code."""
    return Issue(code, READY_ISSUE_CODES[code], message, where=where)


def _mm(nm: int) -> str:
    return f"{nm / 1_000_000:.3f} mm"


@dataclass(frozen=True, slots=True)
class OpenNet:
    """A net with open connections: its name, their number, and the shortest of them (``a`` and ``b`` are
    the ``where`` texts of its two ends, ``shortest`` its length in nanometres)."""

    name: str
    connections: int
    shortest: int
    a: str
    b: str


def open_stage(nets: Sequence[OpenNet], *, evidence: Evidence, issues: Iterable[Issue] = ()) -> StageResult:
    """``nets.open``: one ``ready.net-open`` per row of ``nets``, plus ``issues`` (those of the query and of
    the board read), with ``summary`` ``{nets, connections}``."""
    found = [
        issue(
            "ready.net-open",
            f"{net.connections} open connection{'s' if net.connections != 1 else ''}; the shortest joins "
            f"{net.a} and {net.b} ({_mm(net.shortest)})",
            where=net.name,
        )
        for net in nets
        if net.connections
    ]
    summary = {"nets": len(found), "connections": sum(net.connections for net in nets)}
    return ran("nets.open", [*found, *issues], evidence, summary)


def unconnected_pins(
    design: Design, *, flagged: Collection[tuple[str, str]] = ()
) -> tuple[tuple[Component, Pin], ...]:
    """The pins of parts that are not DNP, whose type is not ``no_connect``, that ``Circuit.no_connects``
    does not mark and ``flagged`` (pairs of component id and pin number) does not hold, and that are on no
    net or the only member of their net, in circuit order."""
    circuit = design.circuit
    marked = {(mark.component_id, mark.pin) for mark in circuit.no_connects}
    size: dict[tuple[str, str], int] = {}
    for net in circuit.nets:
        members = {(ref.component_id, ref.pin) for ref in net.members}
        for key in members:
            size[key] = max(size.get(key, 0), len(members))
    skip = marked | set(flagged)
    return tuple(
        (component, pin)
        for component in circuit.components
        if not component.dnp
        for pin in component.pins
        if pin.etype != "no_connect"
        and (component.id, pin.number) not in skip
        and size.get((component.id, pin.number), 0) <= 1
    )


def pins_stage(design: Design, *, flagged: Collection[tuple[str, str]] = ()) -> StageResult:
    """``pins.unconnected``: one ``ready.pin-unconnected`` per pin of ``unconnected_pins``."""
    found = [
        issue(
            "ready.pin-unconnected",
            "a pin on no net, or alone on its net, without a no-connect mark",
            where=f"{component.ref}-{pin.number}",
        )
        for component, pin in unconnected_pins(design, flagged=flagged)
    ]
    return ran("pins.unconnected", found, EVIDENCE, {"pins": len(found)})


@dataclass(frozen=True, slots=True)
class PowerNet:
    """A power net: its name, why it is one (``interface`` or ``pin-type``), its declared width
    (``class:<name>``, ``rule:<name>`` or ``None``) and the number of zones of the board on it."""

    net: str
    source: str
    width: str | None
    zones: int

    def to_json(self) -> dict[str, object]:
        return {"net": self.net, "source": self.source, "width": self.width, "zones": self.zones}


def _width(intent: Design, net_name: str, netclass_id: str | None) -> str | None:
    netclass = next((c for c in intent.circuit.netclasses if c.id == netclass_id), None)
    class_name = netclass.name if netclass is not None else DEFAULT_CLASS
    if netclass is not None and netclass.name != DEFAULT_CLASS and netclass.track_width is not None:
        return f"class:{netclass.name}"
    if intent.rules is None:
        return None
    subject = RuleSubject("track", net=net_name, netclass=class_name)
    for rule in intent.rules.rules:
        if (
            rule.kind == "track_width"
            and rule.severity != "ignore"
            and rule.selector_a.op != "all"
            and rule.selector_a.matches(subject)
        ):
            return f"rule:{rule.name}"
    return None


def power_nets(intent: Design, *, board: Design) -> tuple[PowerNet, ...]:
    """One row per power net of ``intent``, sorted by name: a net that an interface of kind ``power`` names,
    else a net with a ``power_in`` or ``power_out`` member pin. Its width comes from the classes and rules
    of ``intent``, and its zones from ``board``, matched by net name."""
    circuit = intent.circuit
    declared = power_interface_nets(circuit)
    types = {(c.id, p.number): p.etype for c in circuit.components for p in c.pins}
    zone_nets = Counter[str]()
    if board.board is not None:
        names = {net.id: net.name for net in board.circuit.nets}
        for zone in board.board.zones:
            if zone.net_id is not None and zone.net_id in names:
                zone_nets[names[zone.net_id]] += 1
    rows: dict[str, PowerNet] = {}
    for net in circuit.nets:
        if net.id in declared:
            source = "interface"
        elif any(types.get((ref.component_id, ref.pin)) in POWER_PIN_TYPES for ref in net.members):
            source = "pin-type"
        else:
            continue
        rows.setdefault(net.name, PowerNet(net.name, source, _width(intent, net.name, net.netclass_id),
                                           zone_nets[net.name]))  # fmt: skip
    return tuple(rows[name] for name in sorted(rows))


def power_stage(intent: Design, *, board: Design) -> StageResult:
    """``power.nets``: one ``ready.power-net-unsized`` per power net with no declared width and no zone."""
    rows = power_nets(intent, board=board)
    found = [
        issue(
            "ready.power-net-unsized",
            f"a power net ({row.source}) with no track width of its own class or of a rule, and no zone",
            where=row.net,
        )
        for row in rows
        if row.width is None and row.zones == 0
    ]
    return ran("power.nets", found, EVIDENCE, {"nets": [row.to_json() for row in rows]})


def parts_stage(design: Design) -> StageResult:
    """``parts.fields``: ``check.footprint-unresolved`` for each part of ``unresolved_footprints`` and
    ``ready.part-value-missing`` for each part that is not DNP and has an empty value."""
    footprints = [footprint_issue(component) for component in unresolved_footprints(design)]
    values = [
        issue("ready.part-value-missing", "a part without a value", where=component.ref)
        for component in design.circuit.components
        if not component.dnp and not component.value.strip()
    ]
    summary = {"footprint": len(footprints), "value": len(values)}
    return ran("parts.fields", [*footprints, *values], EVIDENCE, summary)


def skipped_check(name: str, reason: str) -> StageResult:
    """A check that did not run: ``skipped`` with ``reason``, holding its one ``ready.check-skipped``."""
    found = issue("ready.check-skipped", f"{name} did not run ({reason})", where=name)
    return StageResult(name, "skipped", Evidence(), (found,), reason=reason)


__all__ = [
    "EVIDENCE",
    "ORACLE_CHECKS",
    "POWER_PIN_TYPES",
    "READY_CHECKS",
    "READY_ISSUE_CODES",
    "OpenNet",
    "PowerNet",
    "issue",
    "open_stage",
    "parts_stage",
    "pins_stage",
    "power_nets",
    "power_stage",
    "skipped_check",
    "unconnected_pins",
]
