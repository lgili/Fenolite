# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact, non-negative femtoseconds and milli-decibels, without floating point."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from fenolite.dsl.errors import DslError


def _whole(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise DslError(f"{name} holds a non-negative integer, not {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class Delay:
    """An exact non-negative delay in integer femtoseconds; use fs(), ps() or ns()."""

    fs: int

    def __post_init__(self) -> None:
        _whole(self.fs, "Delay")


@dataclass(frozen=True, slots=True)
class Loss:
    """An exact non-negative loss in integer milli-decibels; use mdb() or db()."""

    mdb: int

    def __post_init__(self) -> None:
        _whole(self.mdb, "Loss")


def _scaled(value: int | str, scale: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"{name} takes an int or decimal text, not {value!r}")
    text = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise DslError(f"{name}: expected non-negative decimal text, not {value!r}")
    exact = Fraction(text) * scale
    if exact.denominator != 1:
        raise DslError(f"{name}: {value!r} is below the integer unit precision")
    return exact.numerator


def fs(value: int | str) -> Delay:
    """``value`` femtoseconds, exactly; floats and fractional femtoseconds are refused."""
    return Delay(_scaled(value, 1, "fs()"))


def ps(value: int | str) -> Delay:
    """``value`` picoseconds, exactly (ps("12.5") is 12 500 fs)."""
    return Delay(_scaled(value, 1_000, "ps()"))


def ns(value: int | str) -> Delay:
    """``value`` nanoseconds, exactly (ns("1.2") is 1 200 000 fs)."""
    return Delay(_scaled(value, 1_000_000, "ns()"))


def mdb(value: int | str) -> Loss:
    """``value`` milli-decibels, exactly; no loss figure is supplied by Fenolite."""
    return Loss(_scaled(value, 1, "mdb()"))


def db(value: int | str) -> Loss:
    """``value`` decibels, exactly (db("1.5") is 1 500 mdB)."""
    return Loss(_scaled(value, 1_000, "db()"))


__all__ = ["Delay", "Loss", "db", "fs", "mdb", "ns", "ps"]
