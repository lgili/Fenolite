# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Role copper in the DSL: ``design.role_copper(...)`` (change c0243, decision 9; capability design-dsl,
"Role copper in the DSL"; ``docs/dsl.md``, "Role copper").

The call checks its arguments and records plain data. The build resolves it after the roles, the script
copper and the generated records, with the planner that ``fenolite build`` gives it
(``fenolite.roles.copper``), for both targets. ``role_copper(design)`` returns the record or ``None``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, cast

from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm

if TYPE_CHECKING:
    from fenolite.dsl.design import Design

KINDS: tuple[str, ...] = ("power", "switch_node", "ground", "high_voltage")
"""The role kinds whose copper the call generates."""
CONNECTIONS: tuple[str, ...] = ("solid", "thermal", "thru_hole_only", "none")
GROUND_FILLS: tuple[str, ...] = ("reference", "all")


@dataclass(frozen=True, slots=True)
class RoleCopperIntent:
    """The record of ``design.role_copper(...)``: plain data, lengths in nanometres, ``temp_rise`` in
    millikelvin, ``widen`` in per mille, ``requirements`` a path relative to the script's folder."""

    kinds: tuple[str, ...] = KINDS
    layers: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {})
    ground_layers: tuple[str, ...] | None = None
    ground_fill: str = "reference"
    connection: Mapping[str, str] = field(default_factory=lambda: {})
    stitch_pitch: Nm | None = None
    temp_rise: int | None = None
    widen: int | None = None
    corridors: bool = True
    keep: tuple[str, ...] = ()
    regenerate: tuple[str, ...] = ()
    requirements: str | None = None


def _strings(value: object, what: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise DslError(f"role_copper(): {what} must be a sequence of names, not {value!r}")
    items = tuple(cast("Sequence[object]", value))
    if not all(isinstance(item, str) and item for item in items):
        raise DslError(f"role_copper(): {what} must hold non-empty names, not {value!r}")
    return cast("tuple[str, ...]", items)


def _kind(name: str, what: str) -> str:
    if name not in KINDS:
        raise DslError(f"role_copper(): {what}: {name!r} is not one of {', '.join(KINDS)}")
    return name


def _layers(design: Design, value: object, what: str) -> tuple[str, ...]:
    names = _strings(value, what)
    held = design.copper_layers
    for name in names:
        if name not in held:
            raise DslError(
                f"role_copper(): {what}: the board has no copper layer {name!r} ({', '.join(held)})"
            )
    return names


def _rise(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise DslError(
            f"role_copper(): temp_rise is a rise in kelvin (an int or a decimal string), not {value!r}"
        )
    try:
        kelvin = Decimal(str(value))
    except InvalidOperation:
        raise DslError(f"role_copper(): temp_rise {value!r} is not a number of kelvin") from None
    millikelvin = kelvin * 1000
    if millikelvin <= 0 or millikelvin != millikelvin.to_integral_value():
        raise DslError(f"role_copper(): temp_rise must be above 0 with at most three decimals, not {value!r}")
    return int(millikelvin)


def record_role_copper(
    design: Design,
    *,
    kinds: object,
    layers: object,
    ground_layers: object,
    ground_fill: object,
    connection: object,
    stitch_pitch: object,
    temp_rise: object,
    widen: object,
    corridors: object,
    keep: object,
    regenerate: object,
    requirements: object,
) -> None:
    """Check the arguments of ``design.role_copper`` and record them."""
    if design.role_copper_intent is not None:
        raise DslError("role_copper() is called twice; call it once with every option")
    if design.outline_path is None:
        raise DslError("role_copper(): call board() first")
    chosen_kinds = tuple(_kind(name, "kinds") for name in _strings(kinds, "kinds"))
    if not chosen_kinds:
        raise DslError("role_copper(): kinds is empty")
    by_kind: dict[str, tuple[str, ...]] = {}
    if layers is not None:
        if not isinstance(layers, Mapping):
            raise DslError(f"role_copper(): layers maps a kind to its layers, not {layers!r}")
        for name, value in cast("Mapping[object, object]", layers).items():
            by_kind[_kind(str(name), "layers")] = _layers(design, value, f"layers[{name!r}]")
    grounds = None if ground_layers is None else _layers(design, ground_layers, "ground_layers")
    if ground_fill not in GROUND_FILLS:
        raise DslError(f"role_copper(): ground_fill {ground_fill!r} is not one of {', '.join(GROUND_FILLS)}")
    modes: dict[str, str] = {}
    if connection is not None:
        if not isinstance(connection, Mapping):
            raise DslError(f"role_copper(): connection maps a kind to a mode, not {connection!r}")
        for name, mode in cast("Mapping[object, object]", connection).items():
            if mode not in CONNECTIONS:
                raise DslError(f"role_copper(): connection {mode!r} is not one of {', '.join(CONNECTIONS)}")
            modes[_kind(str(name), "connection")] = cast(str, mode)
    pitch = None
    if stitch_pitch is not None:
        pitch = as_nm(stitch_pitch, name="role_copper(): stitch_pitch")
        if pitch <= 0:
            raise DslError("role_copper(): stitch_pitch must be above 0")
    if widen is not None and (isinstance(widen, bool) or not isinstance(widen, int) or widen < 1000):
        raise DslError(f"role_copper(): widen is a per mille of at least 1000, not {widen!r}")
    if not isinstance(corridors, bool):
        raise DslError(f"role_copper(): corridors must be a bool, not {corridors!r}")
    if requirements is not None and (not isinstance(requirements, str) or not requirements):
        raise DslError(
            f"role_copper(): requirements is the path of a requirements file, not {requirements!r}"
        )
    design.role_copper_intent = RoleCopperIntent(
        kinds=chosen_kinds,
        layers=by_kind,
        ground_layers=grounds,
        ground_fill=cast(str, ground_fill),
        connection=modes,
        stitch_pitch=pitch,
        temp_rise=_rise(temp_rise),
        widen=widen,
        corridors=corridors,
        keep=_strings(keep, "keep"),
        regenerate=_strings(regenerate, "regenerate"),
        requirements=requirements,
    )


def role_copper(design: Design) -> RoleCopperIntent | None:
    """The record of ``design.role_copper(...)``, or ``None`` when the script does not call it."""
    return design.role_copper_intent


__all__ = ["CONNECTIONS", "GROUND_FILLS", "KINDS", "RoleCopperIntent", "role_copper"]
