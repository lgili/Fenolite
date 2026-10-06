# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Property text of the rule and stack-up files: ``KEY=VALUE`` parts joined by ``|`` (change c0042).

``parse_fields`` keeps every part in order, repeated keys included; ``parse_length`` reads a length
written as a decimal number and ``mil`` or ``mm`` (``docs/formats/altium/rule-file.md``,
``stackup-file.md``), exactly as a fraction rounded half to even to the nanometre.
"""

# evidence: see read.project

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from fenolite.core.units import LENGTH_UNITS, Nm, round_half_even_div

LENGTH_UNIT_NAMES = ("mil", "mm")
_LENGTH = re.compile(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))(mil|mm)")


@dataclass(frozen=True, slots=True)
class PropRecord:
    """The ``(key, value)`` pairs of one property text in order (``value`` is ``None`` for a part
    without ``=``) and the text they were read from."""

    fields: tuple[tuple[str, str | None], ...]
    text: str = ""

    def get(self, key: str) -> str | None:
        """The first value of ``key``, or ``None`` when the key is absent or has no value."""
        for name, value in self.fields:
            if name == key:
                return value
        return None

    def keys(self) -> tuple[str, ...]:
        return tuple(name for name, _value in self.fields)


def parse_fields(text: str) -> PropRecord:
    """The parts of ``text`` split on ``|``: a part is a key, its first ``=`` and its value, or a key alone
    (value ``None``). A ``|`` at the very start or end opens or closes the text and gives no part."""
    parts = text.split("|")
    if parts and parts[0] == "" and len(parts) > 1:
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    fields: list[tuple[str, str | None]] = []
    for part in parts:
        key, sep, value = part.partition("=")
        fields.append((key, value if sep else None))
    return PropRecord(tuple(fields), text)


def parse_length(text: str) -> Nm | None:
    """``"6mil"`` → ``152400``; ``"0.035mm"`` → ``35000``. The decimal is converted exactly and rounded
    half to even to the nanometre; ``None`` when ``text`` is not a decimal number followed by ``mil`` or
    ``mm``."""
    match = _LENGTH.fullmatch(text)
    if match is None:
        return None
    value = Fraction(match.group(1)) * LENGTH_UNITS[match.group(2)]
    return round_half_even_div(value.numerator, value.denominator)


__all__ = ["LENGTH_UNIT_NAMES", "PropRecord", "parse_fields", "parse_length"]
