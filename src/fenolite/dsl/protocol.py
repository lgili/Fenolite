# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed protocol limit bundles. Every numeric value is supplied by the user."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import Interface
from fenolite.dsl.part import PinHandle
from fenolite.dsl.timing import Delay, Loss
from fenolite.dsl.topology import Topology, chain, node, number
from fenolite.model.pairs import PAIR_ROLES
from fenolite.model.rules import PlacementSeverity, ProtocolSkew
from fenolite.model.rules import Topology as ModelTopology

if TYPE_CHECKING:
    from fenolite.dsl.design import Design


def _validate(bundle: Usb2 | Clock) -> None:
    if all(value is None for value in (bundle.delay_min, bundle.delay_max, bundle.skew_max, bundle.loss_max)):
        raise DslError("a protocol bundle needs at least one user-supplied limit")
    if any(
        value is not None and not isinstance(value, Delay)  # pyright: ignore[reportUnnecessaryIsInstance]
        for value in (bundle.delay_min, bundle.delay_max, bundle.skew_max)
    ):
        raise DslError("protocol delay and skew limits must be Delay values")
    if bundle.loss_max is not None and not isinstance(bundle.loss_max, Loss):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError("protocol loss_max must be a Loss")
    if (
        bundle.delay_min is not None
        and bundle.delay_max is not None
        and bundle.delay_min.fs > bundle.delay_max.fs
    ):
        raise DslError("protocol delay_min exceeds delay_max")
    if bundle.severity not in ("error", "warning"):
        raise DslError("protocol severity is error or warning")


@dataclass(frozen=True, slots=True, kw_only=True)
class Usb2:
    """User limits for a USB2 or DiffPair interface; no protocol numbers are shipped."""

    delay_min: Delay | None = None
    delay_max: Delay | None = None
    skew_max: Delay | None = None
    loss_max: Loss | None = None
    severity: PlacementSeverity = "error"

    def __post_init__(self) -> None:
        _validate(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class Clock:
    """User delay, skew and loss limits for an ordered clock topology."""

    delay_min: Delay | None = None
    delay_max: Delay | None = None
    skew_max: Delay | None = None
    loss_max: Loss | None = None
    severity: PlacementSeverity = "error"

    def __post_init__(self) -> None:
        _validate(self)


def constrain(design: Design, target: object, bundle: object) -> None:
    if isinstance(bundle, Clock):
        if not isinstance(target, Topology) or target.design is not design:
            raise DslError("constrain(): Clock requires a topology of this design")
        parents = {edge.a for edge in target.to_model().edges}
        leaves = tuple(pin for pin in target.pins if node(pin) not in parents)
        if bundle.skew_max is not None and len(leaves) < 2:
            raise DslError("constrain(): Clock skew needs two or more leaves")
        for end in leaves:
            if bundle.delay_min is not None or bundle.delay_max is not None:
                target.delay(
                    target.pins[0], end, min=bundle.delay_min, max=bundle.delay_max, severity=bundle.severity
                )
            if bundle.loss_max is not None:
                target.loss(target.pins[0], end, max=bundle.loss_max, severity=bundle.severity)
        if bundle.skew_max is not None:
            target.skew(*leaves, max=bundle.skew_max, severity=bundle.severity)
        return
    if not isinstance(bundle, Usb2) or not isinstance(target, Interface) or target.kind not in PAIR_ROLES:
        raise DslError("constrain(): Usb2 requires a USB2 or DiffPair interface; Clock requires a topology")
    if any(interface is target for interface, _ in design.protocol_bindings):
        raise DslError(f"constrain(): interface {target.name!r} is constrained twice")
    design.register_interface(target)
    design.protocol_bindings.append((target, bundle))


def expand(design: Design) -> tuple[tuple[ModelTopology, ...], tuple[ProtocolSkew, ...]]:
    """Expand each two-terminal differential member independently; no fictional cross-net tree edge."""
    topologies: list[ModelTopology] = []
    skews: list[ProtocolSkew] = []
    for interface, bundle in sorted(design.protocol_bindings, key=lambda row: row[0].name):
        names: list[str] = []
        for role in PAIR_ROLES[interface.kind]:
            net = interface.members[role]
            pins = tuple(
                sorted(
                    (
                        PinHandle(part, number(PinHandle(part, designator)))
                        for part in design.parts.values()
                        for designator, connected in part.connections.items()
                        if connected is net
                    ),
                    key=node,
                )
            )
            if len(pins) != 2:
                raise DslError(
                    f"constrain(): {interface.name}.{role} needs exactly two connected pins; "
                    "declare a topology for a bus with branches"
                )
            name = f"protocol:{interface.name}:{role}"
            if name in design.topologies:
                raise DslError(f"constrain(): topology name {name!r} is already used")
            tree = Topology(design, name, (chain(pins[0], pins[1]),))
            if bundle.delay_min is not None or bundle.delay_max is not None:
                tree.delay(*pins, min=bundle.delay_min, max=bundle.delay_max, severity=bundle.severity)
            if bundle.loss_max is not None:
                tree.loss(*pins, max=bundle.loss_max, severity=bundle.severity)
            topologies.append(tree.to_model())
            names.append(name)
        if bundle.skew_max is not None:
            skews.append(
                ProtocolSkew(interface.name, (names[0], names[1]), bundle.skew_max.fs, bundle.severity)
            )  # type: ignore[arg-type]
    return tuple(topologies), tuple(skews)


__all__ = ["Clock", "Usb2", "constrain", "expand"]
