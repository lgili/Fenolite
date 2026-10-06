# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Specctra syntax: nested lists of words and quoted strings (capability specctra-dsn, "Specctra
syntax"; facts: ``docs/formats/specctra/dsn.md``, "Syntax").

``parse`` reads a text into an ``SNode`` tree and ``dumps`` prints a tree. Both follow the file's own
``parser`` section: ``(string_quote <char>)`` names the quote character and ``(space_in_quoted_tokens on)``
lets a quoted string hold blanks. Before any declaration the quote character is ``"`` (a choice of this
reader) and a blank ends a string. The format has no escape, so a name holding the quote character or a
line end cannot be written; ``dumps`` raises ``ValueError`` for one.
"""

# evidence: see dsn, ses

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.core.errors import FormatError

DEFAULT_QUOTE = '"'
QUOTE_CHARS = ("'", '"', "$")
"""The quote characters a ``parser`` section may declare."""
STRING_QUOTE = "string_quote"
SPACE_IN_QUOTED = "space_in_quoted_tokens"
INDENT = "  "
_BLANK = " \t\r\n\f\v"
_NEVER_IN_A_WORD = frozenset(_BLANK + "();'")
_NUMBER = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)")


@dataclass(frozen=True, slots=True)
class SNode:
    """A list: its keyword and its members in file order, each a word (``str``) or a list.

    ``offset`` is the byte offset of the opening parenthesis in the text that was read; it takes no part in
    equality, so a tree equals the tree read back from its printed text.
    """

    head: str
    items: tuple[SNode | str, ...] = ()
    offset: int = field(default=0, compare=False)

    @property
    def words(self) -> tuple[str, ...]:
        """The members that are words, in order."""
        return tuple(item for item in self.items if isinstance(item, str))

    @property
    def lists(self) -> tuple[SNode, ...]:
        """The members that are lists, in order."""
        return tuple(item for item in self.items if isinstance(item, SNode))

    def all(self, head: str) -> tuple[SNode, ...]:
        """The member lists whose keyword is ``head``, in order."""
        return tuple(item for item in self.lists if item.head == head)

    def first(self, head: str) -> SNode | None:
        """The first member list whose keyword is ``head``, or ``None``."""
        return next((item for item in self.lists if item.head == head), None)


class _Reader:
    def __init__(self, text: str, file: str) -> None:
        self.text = text
        self.file = file
        self.pos = 0
        self.quote = DEFAULT_QUOTE
        self.spaces = False

    def offset(self, pos: int) -> int:
        return len(self.text[:pos].encode("utf-8"))

    def error(self, message: str, pos: int) -> FormatError:
        return FormatError(message, file=self.file, offset=self.offset(pos))

    def skip_blank(self) -> None:
        text, n = self.text, len(self.text)
        while self.pos < n and text[self.pos] in _BLANK:
            self.pos += 1

    def word(self) -> str:
        """The word or quoted string at the cursor."""
        text, n, start = self.text, len(self.text), self.pos
        if text[start] == self.quote:
            end = start + 1
            while end < n and text[end] != self.quote:
                if not self.spaces and text[end] in _BLANK:
                    # blanks are not allowed in quoted strings here: the blank ends the string
                    self.pos = end
                    return text[start + 1 : end]
                end += 1
            if end >= n:
                raise self.error("a quoted string is not closed", start)
            self.pos = end + 1
            return text[start + 1 : end]
        end = start
        while end < n and text[end] not in _BLANK and text[end] not in "()":
            end += 1
        self.pos = end
        return text[start:end]

    def node(self) -> SNode:
        """The list whose opening parenthesis is at the cursor."""
        text, n, start = self.text, len(self.text), self.pos
        self.pos += 1
        self.skip_blank()
        if self.pos >= n:
            raise self.error("a list is not closed", start)
        if text[self.pos] in "()":
            raise self.error("a list must start with a keyword", self.pos)
        head = self.word()
        items: list[SNode | str] = []
        if head == STRING_QUOTE:
            self.skip_blank()
            if self.pos < n and text[self.pos] != ")":
                items.append(text[self.pos])
                self.pos += 1
        while True:
            self.skip_blank()
            if self.pos >= n:
                raise self.error("a list is not closed", start)
            char = text[self.pos]
            if char == ")":
                self.pos += 1
                break
            items.append(self.node() if char == "(" else self.word())
        node = SNode(head, tuple(items), self.offset(start))
        self.declare(node, start)
        return node

    def declare(self, node: SNode, pos: int) -> None:
        """Apply a ``string_quote`` or ``space_in_quoted_tokens`` list that just closed."""
        if node.head == STRING_QUOTE:
            if len(node.items) != 1 or node.items[0] not in QUOTE_CHARS:
                raise self.error(f"string_quote needs one of {' '.join(QUOTE_CHARS)}", pos)
            self.quote = str(node.items[0])
        elif node.head == SPACE_IN_QUOTED:
            if node.items not in (("on",), ("off",)):
                raise self.error("space_in_quoted_tokens needs on or off", pos)
            self.spaces = node.items == ("on",)


def parse(text: str, *, file: str = "") -> SNode:
    """The tree of a design or session text: exactly one list.

    Raises ``FormatError`` with a byte offset for an unbalanced parenthesis, a quoted string that is not
    closed, a list without a keyword, a malformed quote declaration, or text outside the one list.
    """
    reader = _Reader(text, file)
    reader.skip_blank()
    if reader.pos >= len(text):
        raise reader.error("the text holds no list", reader.pos)
    if text[reader.pos] != "(":
        raise reader.error("the text must start with a list", reader.pos)
    node = reader.node()
    reader.skip_blank()
    if reader.pos < len(text):
        raise reader.error("text after the end of the list", reader.pos)
    return node


def is_word(text: str, *, quote: str = DEFAULT_QUOTE) -> bool:
    """Whether ``text`` can be written without quotes when ``quote`` is the quote character."""
    return bool(text) and not any(char in _NEVER_IN_A_WORD or char == quote for char in text)


def writable(text: str, *, quote: str = DEFAULT_QUOTE) -> bool:
    """Whether ``text`` can be written at all with blanks allowed in quoted strings: it holds neither the
    quote character nor a line end."""
    return quote not in text and "\n" not in text and "\r" not in text


class _Printer:
    def __init__(self) -> None:
        self.quote = DEFAULT_QUOTE
        self.spaces = False

    def atom(self, text: str) -> str:
        if is_word(text, quote=self.quote):
            return text
        if not writable(text, quote=self.quote):
            raise ValueError(f"the Specctra syntax cannot carry the name {text!r}")
        if not self.spaces and any(char in _BLANK for char in text):
            raise ValueError(f"the name {text!r} holds a blank before (space_in_quoted_tokens on)")
        return f"{self.quote}{text}{self.quote}"

    def node(self, node: SNode, depth: int, out: list[str]) -> None:
        pad = INDENT * depth
        if node.head == STRING_QUOTE and len(node.items) == 1 and node.items[0] in QUOTE_CHARS:
            out.append(f"{pad}({STRING_QUOTE} {node.items[0]})")
            self.quote = str(node.items[0])
            return
        line = f"{pad}({self.atom(node.head)}"
        index = 0
        items = node.items
        while index < len(items) and isinstance(items[index], str):
            line += f" {self.atom(str(items[index]))}"
            index += 1
        if index == len(items):
            out.append(line + ")")
        else:
            out.append(line)
            for item in items[index:]:
                if isinstance(item, SNode):
                    self.node(item, depth + 1, out)
                else:
                    out.append(f"{pad}{INDENT}{self.atom(item)}")
            out.append(f"{pad})")
        if node.head == SPACE_IN_QUOTED and items in (("on",), ("off",)):
            self.spaces = items == ("on",)


def dumps(node: SNode) -> str:
    """The text of a tree: a list without member lists on one line, the others one member list per line.

    Words are quoted when they must be, with the quote character the tree itself declares (``"`` before a
    declaration). Raises ``ValueError`` for a name the syntax cannot carry at its place in the tree.
    """
    out: list[str] = []
    _Printer().node(node, 0, out)
    return "\n".join(out) + "\n"


def number(text: str, *, file: str = "", offset: int | None = None) -> Fraction:
    """The exact value of a decimal number; ``FormatError`` for anything else (exponents included)."""
    if not _NUMBER.fullmatch(text):
        raise FormatError(f"not a number: {text!r}", file=file, offset=offset)
    return Fraction(text)


__all__ = [
    "DEFAULT_QUOTE",
    "QUOTE_CHARS",
    "SNode",
    "dumps",
    "is_word",
    "number",
    "parse",
    "writable",
]
