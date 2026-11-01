# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The printer of emitted code (change c0275, design decision 4): a fixed subset of Python, calls with
keyword arguments, tuples, dicts, integers and strings, in the style ``ruff format`` keeps at line length
110 (no template engine, no ``ast.unparse``).

An expression is written on one line when it fits; else it is exploded, one element per line with a
trailing comma, which ``ruff format`` keeps (its magic trailing comma). Integers of five digits or more
are grouped by ``_`` in threes, as a reviewer reads nanometres.
"""

from __future__ import annotations

import keyword
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction

LINE = 110
"""The line length of emitted code (``ruff format --line-length 110``)."""
INDENT = "    "
NM_PER_MM = 1_000_000
UDEG_PER_DEG = 1_000_000
_NAME = re.compile(r"[^a-z0-9_]+")


@dataclass(frozen=True, slots=True)
class Raw:
    """An atom written as given: a name, a number or a string literal."""

    text: str


@dataclass(frozen=True, slots=True)
class Tup:
    """A tuple of expressions."""

    items: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class Dct:
    """A dict of string keys to expressions, in the given order."""

    items: tuple[tuple[str, Expr], ...]


@dataclass(frozen=True, slots=True)
class Call:
    """``func(args..., name=value...)``."""

    func: str
    args: tuple[Expr, ...] = ()
    kwargs: tuple[tuple[str, Expr], ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Sub:
    """``name[key]``: an item of a mapping or a part's pin."""

    name: str
    key: Expr


Expr = Raw | Tup | Dct | Call | Sub


def string(text: str) -> str:
    """``text`` as a Python string literal as ``ruff format`` writes it: double quotes unless the text holds
    more double quotes than single quotes; backslashes and control characters escaped."""
    quote = "'" if text.count('"') > text.count("'") else '"'
    out = [quote]
    for char in text:
        code = ord(char)
        if char == "\\":
            out.append("\\\\")
        elif char == quote:
            out.append("\\" + char)
        elif char == "\n":
            out.append("\\n")
        elif char == "\t":
            out.append("\\t")
        elif char == "\r":
            out.append("\\r")
        elif code < 0x20 or code == 0x7F:
            out.append(f"\\x{code:02x}")
        else:
            out.append(char)
    out.append(quote)
    return "".join(out)


def integer(value: int) -> str:
    """``value`` with ``_`` between groups of three digits once it has five digits or more."""
    digits = str(abs(value))
    if len(digits) >= 5:
        groups: list[str] = []
        while digits:
            groups.insert(0, digits[-3:])
            digits = digits[:-3]
        digits = "_".join(groups)
    return f"-{digits}" if value < 0 else digits


def decimal(value: int, unit: int) -> str:
    """``value / unit`` as the shortest exact decimal: ``250000, 10**6`` gives ``0.25``."""
    sign = "-" if value < 0 else ""
    whole, rest = divmod(abs(value), unit)
    fraction = f"{rest:0{len(str(unit)) - 1}d}".rstrip("0") if rest else ""
    return f"{sign}{whole}.{fraction}" if fraction else f"{sign}{whole}"


def length(nm: int) -> Call:
    """``mm("…")`` of a length in nanometres, exact."""
    return Call("mm", (Raw(string(decimal(nm, NM_PER_MM))),))


def angle(udeg: int) -> Raw:
    """An angle in microdegrees: whole degrees as an integer, else the exact decimal string."""
    if udeg % UDEG_PER_DEG == 0:
        return Raw(str(udeg // UDEG_PER_DEG))
    return Raw(string(decimal(udeg, UDEG_PER_DEG)))


def area_mm2(nm2: int) -> Raw:
    """An area in square nanometres as the exact ``"…mm2"`` string the DSL reads."""
    value = Fraction(nm2, NM_PER_MM * NM_PER_MM)
    text = decimal(nm2, NM_PER_MM * NM_PER_MM) if value.denominator != 1 else str(value.numerator)
    return Raw(string(f"{text}mm2"))


def text(value: str) -> Raw:
    return Raw(string(value))


def number(value: int) -> Raw:
    return Raw(integer(value))


def identifier(seed: str, taken: set[str], *, prefix: str = "n") -> str:
    """A Python name made from ``seed``: lower case, ``[a-z0-9_]``, not a keyword, not in ``taken`` (a
    suffix ``_2``, ``_3``… makes it unique); it is added to ``taken``."""
    base = _NAME.sub("_", seed.lower()).strip("_") or prefix
    if base[0].isdigit():
        base = f"{prefix}{base}" if prefix.endswith("_") else f"{prefix}_{base}"
    if keyword.iskeyword(base) or keyword.issoftkeyword(base):
        base = f"{base}_"
    name, index = base, 2
    while name in taken:
        name = f"{base}_{index}"
        index += 1
    taken.add(name)
    return name


def flat(expr: Expr) -> str:
    """``expr`` on one line."""
    if isinstance(expr, Raw):
        return expr.text
    if isinstance(expr, Sub):
        return f"{expr.name}[{flat(expr.key)}]"
    if isinstance(expr, Tup):
        inner = ", ".join(flat(item) for item in expr.items)
        return f"({inner},)" if len(expr.items) == 1 else f"({inner})"
    if isinstance(expr, Dct):
        return "{" + ", ".join(f"{string(k)}: {flat(v)}" for k, v in expr.items) + "}"
    parts = [flat(arg) for arg in expr.args] + [f"{name}={flat(value)}" for name, value in expr.kwargs]
    return f"{expr.func}({', '.join(parts)})"


def _elements(expr: Expr) -> tuple[str, str, list[tuple[str, Expr]]] | None:
    """The opening and closing text and the elements (prefix, expression) of an expression that can be
    exploded; ``None`` for an atom."""
    if isinstance(expr, Tup):
        return "(", ")", [("", item) for item in expr.items]
    if isinstance(expr, Dct):
        return "{", "}", [(f"{string(k)}: ", v) for k, v in expr.items]
    if isinstance(expr, Call):
        items: list[tuple[str, Expr]] = [("", arg) for arg in expr.args]
        items += [(f"{name}=", value) for name, value in expr.kwargs]
        return f"{expr.func}(", ")", items
    return None


def lines(expr: Expr, depth: int = 0, prefix: str = "", suffix: str = "") -> list[str]:
    """The lines of ``prefix + expr + suffix`` at indentation ``depth``: one line when it fits in ``LINE``
    columns, else exploded with a trailing comma, recursively."""
    pad = INDENT * depth
    one = f"{pad}{prefix}{flat(expr)}{suffix}"
    parts = _elements(expr)
    if len(one) <= LINE or parts is None or not parts[2]:
        return [one]
    opening, closing, items = parts
    out = [f"{pad}{prefix}{opening}"]
    for item_prefix, item in items:
        out += lines(item, depth + 1, item_prefix, ",")
    out.append(f"{pad}{closing}{suffix}")
    return out


def statement(expr: Expr, depth: int = 0, *, target: str = "") -> list[str]:
    """An expression statement, or the assignment ``target = expr``."""
    return lines(expr, depth, f"{target} = " if target else "")


def comment_block(texts: Sequence[str]) -> list[str]:
    """Each text as a ``#`` comment line."""
    return [f"# {line}".rstrip() for line in texts]


__all__ = [
    "LINE",
    "Call",
    "Dct",
    "Expr",
    "Raw",
    "Sub",
    "Tup",
    "angle",
    "area_mm2",
    "comment_block",
    "decimal",
    "flat",
    "identifier",
    "integer",
    "length",
    "lines",
    "number",
    "statement",
    "string",
    "text",
]
