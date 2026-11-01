# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
# evidence: see reader
"""An independent small S-expression subset, documented in formats/librepcb/library.md.

No backend parser is imported. Unknown escapes and unbalanced/oversized inputs fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DecimalException

MAX_BYTES = 8 * 1024 * 1024
MAX_TOKENS = 250_000
MAX_DEPTH = 64


class Invalid(ValueError):
    """Outside the supported library subset."""


@dataclass(frozen=True, slots=True)
class Node:
    head: str
    values: tuple[str | Node, ...] = ()

    @property
    def atoms(self) -> tuple[str, ...]:
        return tuple(v for v in self.values if isinstance(v, str))

    def children(self, head: str) -> tuple[Node, ...]:
        return tuple(v for v in self.values if isinstance(v, Node) and v.head == head)

    def child(self, head: str) -> Node | None:
        found = self.children(head)
        if len(found) > 1:
            raise Invalid(f"duplicate {head}")
        return found[0] if found else None

    def text(self, head: str, default: str = "") -> str:
        node = self.child(head)
        if node is None:
            return default
        if len(node.atoms) != 1 or len(node.values) != 1:
            raise Invalid(f"{head}: expected one atom")
        return node.atoms[0]


def parse(text: str) -> Node:
    """Parse one bounded list without eval, imports, comments or recovery guessing."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise Invalid("element exceeds byte limit")
    stack: list[list[str | Node]] = []
    roots: list[Node] = []
    i = 0
    tokens = 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
            continue
        tokens += 1
        if tokens > MAX_TOKENS:
            raise Invalid("element exceeds token limit")
        if c == "(":
            if len(stack) >= MAX_DEPTH:
                raise Invalid("element exceeds nesting limit")
            stack.append([])
            i += 1
        elif c == ")":
            if not stack:
                raise Invalid("unmatched closing parenthesis")
            values = stack.pop()
            if not values or not isinstance(values[0], str):
                raise Invalid("list needs an atom head")
            node = Node(values[0], tuple(values[1:]))
            if stack:
                stack[-1].append(node)
            else:
                roots.append(node)
            i += 1
        else:
            if not stack:
                raise Invalid("atom outside root list")
            if c == '"':
                i += 1
                out: list[str] = []
                while i < len(text) and text[i] != '"':
                    c = text[i]
                    if c == "\\":
                        i += 1
                        if i == len(text) or text[i] not in {'"', "\\", "n", "r", "t"}:
                            raise Invalid("unsupported string escape")
                        c = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}[text[i]]
                    elif ord(c) < 32:
                        raise Invalid("unescaped control character")
                    out.append(c)
                    i += 1
                if i == len(text):
                    raise Invalid("unterminated string")
                i += 1
                atom = "".join(out)
                if i < len(text) and not (text[i].isspace() or text[i] in "()"):
                    raise Invalid("string needs a token boundary")
            else:
                start = i
                while i < len(text) and not (text[i].isspace() or text[i] in "()"):
                    if text[i] in {'"', ";", "#", "\\"} or ord(text[i]) < 32:
                        raise Invalid("unsupported atom character or comment")
                    i += 1
                atom = text[start:i]
            stack[-1].append(atom)
    if stack:
        raise Invalid("unclosed list")
    if len(roots) != 1:
        raise Invalid("expected one root list")
    return roots[0]


def quantity(text: str, *, angle: bool = False) -> int:
    """Exactly convert decimal mm/degrees to integer nm/microdegrees."""
    try:
        value = Decimal(text) * 1_000_000
    except DecimalException:
        raise Invalid(f"invalid {'angle' if angle else 'length'} {text!r}") from None
    if not value.is_finite() or value != value.to_integral_value() or abs(value) > 10**15:
        raise Invalid(f"nonintegral or excessive {'microdegrees' if angle else 'nm'}: {text}")
    return int(value)
