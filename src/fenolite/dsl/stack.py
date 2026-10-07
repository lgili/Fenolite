# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The entries of a stack-up in a design script (``docs/dsl.md``, "Stack-up"; change c0101).

``Design.stackup()`` takes them from the top face of the board to its bottom face:
``silkscreen()``, ``mask()``, ``copper()``, ``core()`` and ``prepreg()``. Every number is the script's:
Fenolite supplies no thickness, material, dielectric constant or finish. This module imports the
standard library, ``fenolite.core``, ``fenolite.model`` and the DSL's own errors and lengths.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm
from fenolite.model.design import PLAIN_DECIMAL

EntryKind = Literal["silkscreen", "mask", "copper", "core", "prepreg"]
DIELECTRICS: tuple[EntryKind, ...] = ("core", "prepreg")
PRESETS: tuple[str, ...] = ()
"""The names of the packaged presets, in code-point order. None ships: the presets of fabricator pages
are an open task of change c0101 (its tasks, 9.1)."""


@dataclass(frozen=True, slots=True)
class StackEntry:
    """One entry of a script stack-up. ``epsilon_r`` and ``loss_tangent`` are plain decimal texts or
    empty; ``thickness`` is 0 for a silkscreen."""

    kind: EntryKind
    thickness: Nm = 0
    material: str = ""
    epsilon_r: str = ""
    loss_tangent: str = ""
    color: str = ""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise DslError(f"{name} must be a string without surrounding blanks, not {value!r}")
    return value


def _decimal(value: object, name: str, *, positive: bool) -> str:
    """``value`` as the shortest plain decimal text; ``""`` for ``None``."""
    if value is None:
        return ""
    bound = "above 0" if positive else "at least 0"
    problem = DslError(
        f"{name}: {value!r} is not an int, a Fraction or a plain decimal text {bound} "
        "(no float, no sign, no exponent)"
    )
    if isinstance(value, bool) or isinstance(value, float):
        raise problem
    if isinstance(value, int):
        number = Fraction(value)
    elif isinstance(value, Fraction):
        number = value
    elif isinstance(value, str) and PLAIN_DECIMAL.fullmatch(value):
        number = Fraction(value)
    else:
        raise problem
    if number < 0 or (positive and number == 0):
        raise problem
    denominator = number.denominator
    for prime in (2, 5):
        while denominator % prime == 0:
            denominator //= prime
    if denominator != 1:
        raise DslError(f"{name}: {value!r} is not a terminating decimal")
    digits = 0
    while (number * 10**digits).denominator != 1:
        digits += 1
    whole = int(number * 10**digits)
    text = str(whole).rjust(digits + 1, "0")
    return text if digits == 0 else f"{text[:-digits]}.{text[-digits:]}"


def _thickness(value: object, name: str, *, positive: bool) -> Nm:
    found = as_nm(value, name=name)
    if found < 0 or (positive and found == 0):
        raise DslError(f"{name}: the thickness must be {'above 0' if positive else 'at least 0'}")
    return found


def _entry(
    kind: EntryKind,
    thickness: object,
    material: object,
    epsilon_r: object,
    loss_tangent: object,
    color: object,
) -> StackEntry:
    name = f"stack.{kind}()"
    return StackEntry(
        kind,
        _thickness(thickness, name, positive=kind != "mask"),
        _text(material, f"{name}: material"),
        _decimal(epsilon_r, f"{name}: epsilon_r", positive=True),
        _decimal(loss_tangent, f"{name}: loss_tangent", positive=False),
        _text(color, f"{name}: color"),
    )


def silkscreen(*, color: str = "") -> StackEntry:
    """A silkscreen, above the top mask or below the bottom one; it has no thickness."""
    return StackEntry("silkscreen", color=_text(color, "stack.silkscreen(): color"))


def mask(
    thickness: object,
    *,
    material: str = "",
    epsilon_r: object = None,
    loss_tangent: object = None,
    color: str = "",
) -> StackEntry:
    """A solder mask of ``thickness`` (a DSL length, at least 0)."""
    return _entry("mask", thickness, material, epsilon_r, loss_tangent, color)


def copper(thickness: object) -> StackEntry:
    """A copper layer of ``thickness`` (a DSL length above 0); it takes the next copper name of the
    board."""
    return StackEntry("copper", _thickness(thickness, "stack.copper()", positive=True))


def core(
    thickness: object,
    *,
    material: str = "",
    epsilon_r: object = None,
    loss_tangent: object = None,
    color: str = "",
) -> StackEntry:
    """A core of ``thickness`` (a DSL length above 0) between two copper layers. ``epsilon_r`` and
    ``loss_tangent`` are an ``int``, a ``Fraction`` or a decimal text, never a float."""
    return _entry("core", thickness, material, epsilon_r, loss_tangent, color)


def prepreg(
    thickness: object,
    *,
    material: str = "",
    epsilon_r: object = None,
    loss_tangent: object = None,
    color: str = "",
) -> StackEntry:
    """A prepreg sheet, with the arguments of ``core``; several in one gap are the sheets of one
    dielectric."""
    return _entry("prepreg", thickness, material, epsilon_r, loss_tangent, color)


def preset(name: str) -> tuple[StackEntry, ...]:
    """The entries of the packaged preset ``name``; ``DslError`` listing ``PRESETS`` for an unknown
    name."""
    raise DslError(f"unknown stack-up preset {name!r}; the presets are {list(PRESETS)}")


__all__ = [
    "DIELECTRICS",
    "PRESETS",
    "EntryKind",
    "StackEntry",
    "copper",
    "core",
    "mask",
    "prepreg",
    "preset",
    "silkscreen",
]
