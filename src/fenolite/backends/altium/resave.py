# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Spellings of one value in Altium property text (capability file-safety, "Resave differences of Altium
documents"; facts: ``docs/formats/altium/pcb-read.md``, "Resave differences"; change c0207).

Two property values are one value when both decode, by the same rule, to the same value in the format's
units: mil text in units of 1/10 000 mil, rounded half to even; a decimal number (an angle in scientific
form included) exactly; a boolean (``TRUE``/``T``, ``FALSE``/``F``). A key that holds free text (a name, a
text, a designator, a description, a path or an id) is never decoded: ``1.0`` and ``1`` are two pad names.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from fenolite.backends.altium.read.pcbprops import parse_bool, parse_mil
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-RD-RESAVE",))
FREE_TEXT_SUFFIXES = (
    "NAME",
    "TEXT",
    "DESIGNATOR",
    "DESCRIPTION",
    "COMMENT",
    "PATTERN",
    "PATH",
    "UNIQUEID",
    "GUID",
    "IDENTIFIER",
    "REFERENCE",
    "LIBRARY",
)
"""Keys that end with one of these (any case, after a ``#<k>`` repeat suffix is removed) hold free text."""
_DECIMAL = re.compile(r"\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*")


def _text(value: object) -> str | None:
    if isinstance(value, bytes):
        try:
            return value.decode("ascii")
        except UnicodeDecodeError:
            return None
    return value if isinstance(value, str) else None


def free_text(key: str) -> bool:
    """Whether the property ``key`` holds free text, which is compared as written."""
    name = key.partition("#")[0].upper()
    return name.endswith(FREE_TEXT_SUFFIXES)


def _decimal(text: str) -> Decimal | None:
    if _DECIMAL.fullmatch(text) is None:
        return None
    try:
        return Decimal(text.strip())
    except InvalidOperation:  # pragma: no cover - the pattern admits only valid decimals
        return None


def same_value(key: str, a: object, b: object) -> bool:
    """Whether two spellings of the property ``key`` decode to one value (see the module's rules). Equal
    spellings are one value; a free-text key and a value that is not ASCII text are compared as written."""
    if a == b:
        return True
    left, right = _text(a), _text(b)
    if left is None or right is None or free_text(key):
        return False
    mil_a, mil_b = parse_mil(left), parse_mil(right)
    if mil_a is not None and mil_b is not None:
        return round(mil_a) == round(mil_b)  # half to even, in units of 1/10 000 mil
    number_a, number_b = _decimal(left), _decimal(right)
    if number_a is not None and number_b is not None:
        return number_a == number_b
    flag_a, flag_b = parse_bool(left), parse_bool(right)
    return flag_a is not None and flag_a == flag_b


__all__ = ["EVIDENCE", "FREE_TEXT_SUFFIXES", "free_text", "same_value"]
