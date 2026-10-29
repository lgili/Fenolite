# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The corners of the test rig (change c0253; capability electrical-contracts, "Rig corners";
``docs/contracts.md``, "The rig and its corners").

A rig supply's voltage is a range, and the worst case over it stays the verdict of every row. In addition,
each row and expectation whose value reads a rig supply is evaluated at every corner: each of the design's
supplies at its minimum or at its maximum, all combinations, named like ``bench=max,aux=min``. A corner pins
the supplies to exact values and keeps every other input a range. Corners never change a verdict: an
expression that is not monotone can fail between two corners. With more than ``MAX_SUPPLIES`` supplies the
corners are not evaluated.
"""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Mapping

from fenolite.model.circuit import ValueRange
from fenolite.model.rules import ContractSet, RigSupply

MAX_SUPPLIES = 6
"""The most rig supplies whose corners are evaluated (64 corners)."""
TOO_MANY = "too-many-supplies"


def supplies(contracts: ContractSet | None) -> tuple[str, ...]:
    """The names of the rig supplies, in name order."""
    if contracts is None:
        return ()
    return tuple(sorted(e.name for e in contracts.rig if isinstance(e, RigSupply)))


def corners(contracts: ContractSet | None) -> tuple[Mapping[str, str], ...] | None:
    """Every corner of the rig supplies (supply name → ``min`` or ``max``), in a fixed order; ``()`` without
    a supply, ``None`` with more than ``MAX_SUPPLIES``."""
    names = supplies(contracts)
    if len(names) > MAX_SUPPLIES:
        return None
    if not names:
        return ()
    return tuple(
        dict(zip(names, ends, strict=True)) for ends in itertools.product(("min", "max"), repeat=len(names))
    )


def name(corner: Mapping[str, str]) -> str:
    """``bench=max,aux=min``: each supply and its end, in name order."""
    return ",".join(f"{supply}={corner[supply]}" for supply in sorted(corner))


def pinned(contracts: ContractSet, corner: Mapping[str, str]) -> ContractSet:
    """``contracts`` with each rig supply's voltage pinned to the end ``corner`` names."""
    elements = []
    for element in contracts.rig:
        if isinstance(element, RigSupply) and element.name in corner:
            voltage = element.voltage
            first, other = (
                (voltage.low, voltage.high) if corner[element.name] == "min" else (voltage.high, voltage.low)
            )
            end = first if first is not None else other
            exact = ValueRange("volt", end, None, end)
            elements.append(dataclasses.replace(element, voltage=exact))
        else:
            elements.append(element)
    return dataclasses.replace(contracts, rig=tuple(elements))


__all__ = ["MAX_SUPPLIES", "TOO_MANY", "corners", "name", "pinned", "supplies"]
