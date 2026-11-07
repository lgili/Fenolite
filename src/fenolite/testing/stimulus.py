# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed outside-world inputs for an isolated block (change c0270)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from fenolite.dsl.quantity import Quantity, Range
from fenolite.testing.design import TestingError

if TYPE_CHECKING:
    from fenolite.dsl.block import BlockDef, BlockInstance
    from fenolite.dsl.design import Design
    from fenolite.dsl.portnets import PortHandle, PortNet


def _amount(value: object, unit: str, port: str) -> Range:
    found = value.as_range() if isinstance(value, Quantity) else value
    if not isinstance(found, Range) or found.unit != unit:
        raise TestingError(f"stimulus {port}: expected a quantity or range in {unit}, got {value!r}")
    return found


@dataclass(frozen=True, slots=True)
class Source:
    voltage: Range
    current: Range | None = None


@dataclass(frozen=True, slots=True)
class Draw:
    current: Range


def source(voltage: object, current: object = None) -> Source:
    """The voltage and optional available current of a rig supply."""
    return Source(
        _amount(voltage, "volt", "source voltage"),
        None if current is None else _amount(current, "ampere", "source current"),
    )


def draw(current: object) -> Draw:
    """The current a rig sink draws from a port."""
    return Draw(_amount(current, "ampere", "draw current"))


def _port(instance: BlockInstance, name: str) -> PortHandle | PortNet:
    ports = instance.module.ports
    head, dot, member = name.partition(".")
    if head not in ports:
        raise TestingError(f"unknown stimulus port {name!r}; ports: {', '.join(sorted(ports))}")
    port = ports[head]
    if dot:
        if len(port.members) == 1 or member not in port.members:
            raise TestingError(
                f"stimulus port {name!r}: {head} has members {', '.join(port.members)}; "
                "a single-net port is named without a member"
            )
        return port.members[member]
    if port.main() is None:
        raise TestingError(f"stimulus port {name!r}: name a member of {', '.join(port.members)}")
    return port


@dataclass(frozen=True, slots=True)
class Stimulus:
    """Immutable port inputs; resolved against the actual parameterised block before building."""

    ports: Mapping[str, Source | Draw]
    ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ports", MappingProxyType(dict(self.ports)))

    def reference(self, instance: BlockInstance) -> str:
        for name in self.ports:
            _port(instance, name)
        if self.ref is not None:
            _port(instance, self.ref)
            value = self.ports.get(self.ref)
            if value is not None and (
                isinstance(value, Draw) or value.voltage.low != value.voltage.high or value.voltage.low != 0
            ):
                raise TestingError(f"stimulus reference {self.ref}: its input must be exactly 0 V")
            return self.ref
        zero = [
            name
            for name, value in self.ports.items()
            if isinstance(value, Source) and value.voltage.low == value.voltage.high == 0
        ]
        if len(zero) == 1:
            return zero[0]
        if len(zero) > 1:
            raise TestingError(f"stimulus reference is ambiguous: {', '.join(sorted(zero))}; give ref=")
        grounds = [name for name, port in instance.module.ports.items() if port.kind == "ground"]
        if len(grounds) == 1:
            return grounds[0]
        raise TestingError(
            f"stimulus needs one reference; Ground candidates: {', '.join(sorted(grounds)) or '(none)'}; "
            f"ports: {', '.join(sorted(instance.module.ports))}; give ref="
        )

    def validate(self, block: BlockDef, params: Mapping[str, object]) -> None:
        """Validate without allocating a folder or running a build."""
        from fenolite.dsl.design import Design
        from fenolite.dsl.errors import DslError

        try:
            instance = Design("stimulus_preflight").use(block, "dut", **params)
            self.reference(instance)
        except DslError as error:
            raise TestingError(str(error)) from error

    def apply(self, design: Design, instance: BlockInstance) -> None:
        from fenolite.dsl.contracts import sink, supply

        reference = self.reference(instance)
        ret = _port(instance, reference)
        for name, value in sorted(self.ports.items()):
            if name == reference:
                if (
                    isinstance(value, Draw)
                    or value.voltage.low != value.voltage.high
                    or value.voltage.low != 0
                ):
                    raise TestingError(f"stimulus reference {name}: its input must be exactly 0 V")
                continue
            target = _port(instance, name)
            label = f"stim_{name.replace('.', '_')}"
            element = (
                sink(target, ret, current=value.current, name=label)
                if isinstance(value, Draw)
                else supply(target, ret, voltage=value.voltage, current=value.current, name=label)
            )
            design.rig(element)


def stimulus(
    mapping: Mapping[str, object] | None = None, /, *, ref: str | None = None, **ports: object
) -> Stimulus:
    """State port voltages, supplies and loads; interface members use mapping keys such as ``BUS.sda``."""
    given = dict(mapping or {})
    overlap = given.keys() & ports.keys()
    if overlap:
        raise TestingError(f"stimulus port stated twice: {', '.join(sorted(overlap))}")
    given.update(ports)
    if ref is not None and (not isinstance(ref, str) or not ref):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TestingError("stimulus ref is a port name")
    values: dict[str, Source | Draw] = {}
    for name, value in given.items():
        if not isinstance(name, str) or not name:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TestingError(f"stimulus port is a nonempty name, got {name!r}")
        values[name] = value if isinstance(value, Source | Draw) else Source(_amount(value, "volt", name))
    return Stimulus(MappingProxyType(values), ref)


__all__ = ["Stimulus", "draw", "source", "stimulus"]
