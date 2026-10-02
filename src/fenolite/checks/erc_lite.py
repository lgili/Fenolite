# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""ERC lite: three electrical warnings on a built model until ``sch erc`` replaces them (capability
verification-loop, "ERC lite stage").

The rules follow KiCad's own checks in spirit (the unconnected-pin check of the schematic editor, S-0046),
and their claim is bounded by ``H-K-CHECK-ERC``: a heuristic, so warnings only. Pins of DNP components
are ignored. ``check_removal`` makes the suite fail from 0.2 on, when the stage must go.
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
REMOVE_IN = (0, 2)
_DRIVERS = frozenset({"output", "power_out"})


def check_removal(version: str) -> None:
    """Raise ``RuntimeError`` once ``version`` reaches ``REMOVE_IN``: ``erc.lite`` must then be removed."""
    parts: list[int] = []
    for piece in version.split(".")[:2]:
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    if tuple(parts) >= REMOVE_IN:
        raise RuntimeError(f"erc.lite is due for removal at REMOVE_IN {REMOVE_IN} (version {version})")


def erc_lite(design: Design) -> tuple[Issue, ...]:
    """The ERC lite warnings of ``design``."""
    circuit = design.circuit
    live = {c.id: c for c in circuit.components if not c.dnp}
    pin_types = {(c.id, p.number): p.etype for c in live.values() for p in c.pins}
    powered = {net_id for i in circuit.interfaces if i.kind == "power" for net_id in i.members.values()}
    found: list[Issue] = []
    on_net: set[tuple[str, str]] = set()
    for net in circuit.nets:
        types: defaultdict[str, int] = defaultdict(int)
        for ref in net.members:
            key = (ref.component_id, ref.pin)
            on_net.add(key)
            if key in pin_types:
                types[pin_types[key]] += 1
        if types["output"] + types["power_out"] >= 2:
            found.append(issue("erc.lite.output-conflict", "two or more driving outputs on one net",
                               where=net.name))  # fmt: skip
        if types["power_in"] and not types["power_out"] and net.id not in powered:
            found.append(issue("erc.lite.power-undriven", "a power input without a power output or a power "
                               "interface", where=net.name))  # fmt: skip
    for component in live.values():
        for pin in component.pins:
            if pin.etype != "no_connect" and (component.id, pin.number) not in on_net:
                found.append(issue("erc.lite.floating-pin", "a pin on no net",
                                   where=f"{component.ref}-{pin.number}"))  # fmt: skip
    return tuple(found)


def erc_stage(design: Design) -> StageResult:
    found = erc_lite(design)
    summary = {rule: sum(1 for i in found if i.code == f"erc.lite.{rule}") for rule in ERC_RULES}
    return ran("erc.lite", found, EVIDENCE, summary)


__all__ = ["ERC_RULES", "EVIDENCE", "REMOVE_IN", "check_removal", "erc_lite", "erc_stage"]
