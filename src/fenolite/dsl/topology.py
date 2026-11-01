# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ordered pad trees and user-declared bridges through series parts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from fenolite.core.ids import derived_id
from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Part, PinHandle
from fenolite.dsl.timing import Delay, Loss
from fenolite.dsl.units import as_nm
from fenolite.model.rules import Topology as ModelTopology
from fenolite.model.rules import TopologyConstraint, TopologyEdge

if TYPE_CHECKING:
    from fenolite.dsl.design import Design


def number(pin: PinHandle) -> str:
    device = pin.part.device
    if device is not None:
        function = next((found for found in device.pins if found.function == pin.designator), None)
        if function is not None:
            if len(function.pins) != 1:
                raise DslError(f"topology pin {pin.part.label}-{pin.designator} names several pins")
            return function.pins[0]
    return pin.designator


def node(pin: PinHandle) -> str:
    return f"{pin.part.label}-{number(pin)}"


def _canonical(pin: PinHandle) -> PinHandle:
    return PinHandle(pin.part, number(pin))


def _targets(value: object) -> tuple[PinHandle, ...]:
    items: tuple[object, ...] = cast(tuple[object, ...], value) if isinstance(value, tuple) else (value,)
    if not items or not all(isinstance(pin, PinHandle) for pin in items):
        raise DslError("a topology chain takes a pin or a non-empty tuple of pins")
    return tuple(_canonical(cast(PinHandle, pin)) for pin in items)


@dataclass(frozen=True, slots=True)
class Chain:
    """Edges recorded by ``a >> b >> c`` or ``a >> (b, c)``; branching is terminal."""

    edges: tuple[tuple[PinHandle, PinHandle], ...]
    tail: PinHandle | None

    def __rshift__(self, value: object) -> Chain:
        if self.tail is None:
            raise DslError("a fan-out is terminal; start a new chain at the branch pin")
        targets = _targets(value)
        if self.tail in targets:
            raise DslError(f"topology chain has a cycle at {node(self.tail)}")
        return Chain(
            self.edges + tuple((self.tail, pin) for pin in targets), targets[0] if len(targets) == 1 else None
        )


def chain(start: PinHandle, value: object) -> Chain:
    start = _canonical(start)
    return Chain((), start) >> value


@dataclass(frozen=True, slots=True)
class _Constraint:
    kind: str
    ends: tuple[PinHandle, ...] = ()
    low: int | None = None
    high: int | None = None
    severity: str = "error"


class Topology:
    """A design's ordered tree; delay(), skew(), loss(), stub() and order() add limits."""

    def __init__(self, design: Design, name: str, chains: tuple[Chain, ...]) -> None:
        self.design = design
        self.name = name
        self.edges = tuple(edge for chain in chains for edge in chain.edges)
        self.pins = tuple(dict.fromkeys(pin for edge in self.edges for pin in edge))
        self.constraints: list[_Constraint] = []
        if not self.pins:
            raise DslError(f"topology {name!r} needs at least one chain")
        for pin in self.pins:
            if pin.part.design is not design:
                raise DslError(f"topology {name!r}: {pin.part.label} is not in this design")
        self.to_model()  # validate at the user's call, before registering anything

    def _add(
        self, kind: str, ends: tuple[object, ...], low: int | None, high: int | None, severity: str
    ) -> None:
        if severity not in ("error", "warning"):
            raise DslError("topology severity is 'error' or 'warning'")
        pins = tuple(_canonical(pin) for pin in ends if isinstance(pin, PinHandle))
        if len(pins) != len(ends) or any(pin not in self.pins for pin in pins):
            raise DslError(f"topology {self.name!r}: constraint ends must be pins of this tree")
        constraint = _Constraint(kind, pins, low, high, severity)
        self.constraints.append(constraint)
        try:
            self.to_model()
        except DslError:
            self.constraints.pop()
            raise

    def delay(
        self,
        a: PinHandle,
        b: PinHandle,
        *,
        min: Delay | None = None,
        max: Delay | None = None,
        severity: str = "error",
    ) -> None:  # noqa: A002
        """Limit delay from ``a`` to ``b`` in fs(), ps() or ns(); min rounds down, max rounds up."""
        if any(value is not None and not isinstance(value, Delay) for value in (min, max)):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError("topology.delay(): limits must be Delay values")
        self._add("delay", (a, b), None if min is None else min.fs, None if max is None else max.fs, severity)

    def skew(self, *ends: PinHandle, max: Delay, severity: str = "error") -> None:
        """Limit the difference of delays from this tree's root to the given ends."""
        if not isinstance(max, Delay):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError("topology.skew(): max must be a Delay")
        self._add("skew", ends, None, max.fs, severity)

    def loss(self, a: PinHandle, b: PinHandle, *, max: Loss, severity: str = "error") -> None:
        """Limit path loss in mdb() or db(), using the user's loss inputs at their stated frequency."""
        if not isinstance(max, Loss):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError("topology.loss(): max must be a Loss")
        self._add("loss", (a, b), None, max.mdb, severity)

    def stub(self, *, max: object, severity: str = "error") -> None:
        """Limit an unlisted copper branch's centre-line length in mm(), mil(), inch() or nm()."""
        self._add("stub", (), None, as_nm(max, name="topology.stub(): max"), severity)

    def order(self, *, severity: str = "error") -> None:
        """Require copper to visit each chain's pads in its declared order, without loops."""
        self._add("order", (), None, None, severity)

    def _bridge(self, a: PinHandle, b: PinHandle) -> tuple[int, int] | None:
        if a.part is not b.part:
            return None
        x, y = sorted((number(a), number(b)))
        declared = self.design.bridges.get((a.part, x, y))
        if declared is not None:
            return declared
        if a.part.device is not None:
            for bridge in a.part.device.bridges:
                mapped = tuple(number(a.part[end]) for end in bridge.between)
                if sorted(mapped) == [x, y]:
                    return bridge.delay_fs, bridge.loss_mdb
        return None

    def to_model(self) -> ModelTopology:
        def net(pin: PinHandle) -> str | None:
            found = pin.part.connections.get(pin.designator)
            if found is None:
                found = next(
                    (
                        value
                        for designator, value in pin.part.connections.items()
                        if number(PinHandle(pin.part, designator)) == number(pin)
                    ),
                    None,
                )
            return None if found is None else found.name

        edges: list[TopologyEdge] = []
        missing: list[str] = []
        for a, b in self.edges:
            bridge = self._bridge(a, b)
            if bridge is not None:
                edges.append(TopologyEdge(node(a), node(b), "bridge", delay_fs=bridge[0], loss_mdb=bridge[1]))
            elif net(a) is not None and net(a) == net(b):
                edges.append(TopologyEdge(node(a), node(b), net=net(a) or ""))
            else:
                raise DslError(
                    f"topology {self.name!r}: {node(a)} and {node(b)} must share a net or a bridge"
                )
        # Join separate chains only through pins of the same series component. An undeclared bridge
        # remains an explicit failed input, so build can report topology.bridge-missing as a finding.
        reached = {node(self.pins[0])}
        while True:
            previous = set(reached)
            reached.update(edge.b for edge in edges if edge.a in reached)
            if reached == previous:
                break
        while len(reached) < len(self.pins):
            candidate = next(
                (
                    (a, b)
                    for a in self.pins
                    for b in self.pins
                    if node(a) in reached
                    and node(b) not in reached
                    and a.part is b.part
                    and not any(edge.b == node(b) for edge in edges)
                ),
                None,
            )
            if candidate is None:
                break
            a, b = candidate
            bridge = self._bridge(a, b)
            if bridge is None:
                missing.append(a.part.label)
                bridge = (0, 0)
            edges.append(TopologyEdge(node(a), node(b), "bridge", delay_fs=bridge[0], loss_mdb=bridge[1]))
            while True:
                previous = set(reached)
                reached.update(edge.b for edge in edges if edge.a in reached)
                if reached == previous:
                    break
        constraints: list[TopologyConstraint] = []
        for spec in self.constraints:
            values: dict[str, object] = {
                "kind": spec.kind,
                "ends": tuple(node(pin) for pin in spec.ends),
                "severity": spec.severity,
            }
            if spec.kind == "delay":
                values.update(min_fs=spec.low, max_fs=spec.high)
            elif spec.kind == "skew":
                values["max_fs"] = spec.high
            elif spec.kind == "loss":
                values["max_mdb"] = spec.high
            elif spec.kind == "stub":
                values["max_nm"] = spec.high
            try:
                constraints.append(TopologyConstraint(**values))  # type: ignore[arg-type]
            except ValueError as error:
                raise DslError(f"topology {self.name!r}: {error}") from None
        try:
            return ModelTopology(
                id=derived_id("top", "dsl", f"topology:{self.name}"),
                name=self.name,
                nodes=tuple(node(pin) for pin in self.pins),
                edges=tuple(edges),
                constraints=tuple(constraints),
                missing_bridges=tuple(sorted(set(missing))),
            )
        except ValueError as error:
            raise DslError(
                f"topology {self.name!r} ({', '.join(node(pin) for pin in self.pins)}): {error}"
            ) from None


def declare(design: Design, name: str, chains: tuple[object, ...]) -> Topology:
    if not isinstance(name, str) or not name or name in design.topologies:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"topology(): name {name!r} is empty or declared twice")
    if not all(isinstance(chain, Chain) for chain in chains):
        raise DslError("topology(): give chains made with pin >> pin")
    result = Topology(design, name, chains)  # type: ignore[arg-type]
    design.topologies[name] = result
    return result


def bridge(design: Design, part: Part, a: str | int, b: str | int, delay: object, loss: object) -> None:
    if not isinstance(part, Part) or part.design is not design:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError("bridge(): give a part of this design")
    x, y = sorted((number(part[a]), number(part[b])))
    if x == y:
        raise DslError("bridge(): pins must differ")
    if delay is not None and not isinstance(delay, Delay):
        raise DslError("bridge(): delay must be a Delay")
    if loss is not None and not isinstance(loss, Loss):
        raise DslError("bridge(): loss must be a Loss")
    key = (part, x, y)
    if key in design.bridges:
        raise DslError("bridge(): bridge is declared twice")
    design.bridges[key] = (0 if delay is None else delay.fs, 0 if loss is None else loss.mdb)


__all__ = ["Chain", "Topology", "bridge", "chain", "declare", "node", "number"]
