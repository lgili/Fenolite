# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""ERC lite: three electrical warnings on a model, for inputs that have no ERC oracle (capability
verification-loop, "ERC lite stage").

The KiCad pipeline does not run them: ``run_checks`` asks KiCad's own ERC instead (``checks.erc``, the stage
``erc.kicad``; change c0062), and the removal that ``REMOVE_IN`` announced is done there. The rules stay as a
function for ``run_document_checks`` (change c0044), which runs them on the built model or on the reading of
a project's schematic documents, where pin electrical types and no-connect marks exist; the caller then
combines ``EVIDENCE`` with the reading's.

The rules follow KiCad's own checks in spirit (the unconnected-pin check of the schematic editor, S-0046),
and their claim is bounded by ``H-K-CHECK-ERC``: a heuristic, so warnings only. Pins of DNP components
are ignored, and so are the pins that ``Circuit.no_connects`` marks as intentionally unconnected (change
c0036): a marked pin is not floating, and a marked pin on a net is ``model.no-connect-on-net``.
"""

from __future__ import annotations

from collections import defaultdict

from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

ERC_RULES = ("output-conflict", "power-undriven", "floating-pin")
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-CHECK-ERC",))
_DRIVERS = frozenset({"output", "power_out"})


def erc_lite(design: Design) -> tuple[Issue, ...]:
    """The ERC lite warnings of ``design``."""
    circuit = design.circuit
    live = {c.id: c for c in circuit.components if not c.dnp}
    pin_types = {(c.id, p.number): p.etype for c in live.values() for p in c.pins}
    powered = {net_id for i in circuit.interfaces if i.kind == "power" for net_id in i.members.values()}
    marked = {(mark.component_id, mark.pin) for mark in circuit.no_connects}
    found: list[Issue] = []
    on_net: set[tuple[str, str]] = set()
    for net in circuit.nets:
        types: defaultdict[str, int] = defaultdict(int)
        for ref in net.members:
            key = (ref.component_id, ref.pin)
            on_net.add(key)
            if key in pin_types and key not in marked:
                types[pin_types[key]] += 1
        if types["output"] + types["power_out"] >= 2:
            found.append(issue("erc.lite.output-conflict", "two or more driving outputs on one net",
                               where=net.name))  # fmt: skip
        if types["power_in"] and not types["power_out"] and net.id not in powered:
            found.append(issue("erc.lite.power-undriven", "a power input without a power output or a power "
                               "interface", where=net.name))  # fmt: skip
    for component in live.values():
        for pin in component.pins:
            key = (component.id, pin.number)
            if pin.etype != "no_connect" and key not in on_net and key not in marked:
                found.append(issue("erc.lite.floating-pin", "a pin on no net",
                                   where=f"{component.ref}-{pin.number}"))  # fmt: skip
    return tuple(found)


def erc_stage(design: Design) -> StageResult:
    found = erc_lite(design)
    summary = {rule: sum(1 for i in found if i.code == f"erc.lite.{rule}") for rule in ERC_RULES}
    return ran("erc.lite", found, EVIDENCE, summary)


__all__ = ["ERC_RULES", "EVIDENCE", "erc_lite", "erc_stage"]
