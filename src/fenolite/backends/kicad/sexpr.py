# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad S-expression syntax: a spelling-preserving parser, two printers and tree equality.

Written from ``docs/formats/kicad/sexpr.md`` only. Atoms keep their exact text (quotes included for
strings); decoding happens on demand. The parser is iterative (no recursion, ``MAX_DEPTH`` enforced)
and every rejection raises ``FormatError`` with the file, the byte offset in the UTF-8 encoding of the
input and the locator of the innermost open list.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Literal

from fenolite.core.errors import FormatError
from fenolite.core.units import round_half_even_div

MAX_DEPTH = 256
XY_WRAP_COLUMNS = 99

_NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_NUMBER_PARTS = re.compile(r"(-?)(\d*)(?:\.(\d*))?(?:[eE]([-+]?\d+))?")
_STRING = re.compile(r'"(?:[^"\\\r\n]|\\[^\r\n])*"')
_STRING_PREFIX = re.compile(r'"(?:[^"\\\r\n]|\\[^\r\n])*')
_UNQUOTED = re.compile(r'[^ \t\r\n()"][^ \t\r\n()]*')
_WS = re.compile(r"[ \t\r\n]*")
_TOKEN = re.compile(
    r"(?P<ws>[ \t\r\n]+)"
    r"|(?P<open>\()"
    r"|(?P<close>\))"
    r'|(?P<str>"(?:[^"\\\r\n]|\\[^\r\n])*")(?![^ \t\r\n()])'
    r'|(?P<atom>[^ \t\r\n()"][^ \t\r\n()]*)'
    r"|(?P<bad>.)",
    re.DOTALL,
)
_SIMPLE_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
_OCTAL = "01234567"
_HEX = "0123456789abcdefABCDEF"
_MAX_EXPONENT = 400


class AtomKind(StrEnum):
    SYMBOL = "symbol"
    STRING = "string"
    NUMBER = "number"


def _classify(text: str) -> AtomKind | None:
    """The kind of ``text`` if it is exactly one lexical atom, else ``None``."""
    if text.startswith('"'):
        return AtomKind.STRING if _STRING.fullmatch(text) else None
    if not _UNQUOTED.fullmatch(text):
        return None
    return AtomKind.NUMBER if _NUMBER.fullmatch(text) else AtomKind.SYMBOL


def _decode(body: str) -> str:
    if "\\" not in body:
        return body
    out: list[str] = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c != "\\" or i + 1 >= n:
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1]
        if nxt in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[nxt])
            i += 2
        elif nxt in _OCTAL:
            j = i + 1
            while j < n and j < i + 4 and body[j] in _OCTAL:
                j += 1
            out.append(chr(int(body[i + 1 : j], 8)))
            i = j
        elif nxt == "x" and i + 3 < n and body[i + 2] in _HEX and body[i + 3] in _HEX:
            out.append(chr(int(body[i + 2 : i + 4], 16)))
            i += 4
        else:
            out.append("\\" + nxt)  # unknown escape: kept as written
            i += 2
    return "".join(out)


def _encode(value: str) -> str:
    out = ['"']
    for c in value:
        code = ord(c)
        if c == '"':
            out.append('\\"')
        elif c == "\\":
            out.append("\\\\")
        elif c == "\n":
            out.append("\\n")
        elif c == "\r":
            out.append("\\r")
        elif code == 0:
            raise ValueError("NUL cannot be written in a KiCad string")
        elif code < 0x20 and c != "\t":
            out.append(f"\\{code:03o}")
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


@dataclass(frozen=True, slots=True)
class Atom:
    """One atom exactly as written; ``kind`` follows from the lexical form of ``text``."""

    text: str
    kind: AtomKind

    def __post_init__(self) -> None:
        kind = _classify(self.text) if isinstance(self.text, str) else None  # pyright: ignore[reportUnnecessaryIsInstance]
        if kind is None:
            raise ValueError(f"not a single KiCad atom: {self.text!r}")
        if kind != self.kind:
            raise ValueError(f"atom {self.text!r} reads as {kind.value}, not {self.kind}")
        _set(self, "kind", kind)

    @property
    def value(self) -> str:
        """The decoded value: escapes resolved for strings, the text itself otherwise."""
        if self.kind == AtomKind.STRING:
            return _decode(self.text[1:-1])
        return self.text

    def to_nm(self, *, exact: bool = True) -> int:
        """A millimetre number as integer nanometres (integer arithmetic; half-even when inexact)."""
        if self.kind != AtomKind.NUMBER:
            raise ValueError(f"{self.text!r} is not a number")
        match = _NUMBER_PARTS.fullmatch(self.text)
        if match is None:  # pragma: no cover - NUMBER atoms always match
            raise ValueError(f"{self.text!r} is not a number")
        sign, whole, frac, exponent = match.group(1), match.group(2), match.group(3) or "", match.group(4)
        digits = int((whole or "0") + frac)
        scale = (int(exponent) if exponent else 0) - len(frac) + 6
        if abs(scale) > _MAX_EXPONENT:
            raise ValueError(f"{self.text!r} is out of range")
        if sign:
            digits = -digits
        if scale >= 0:
            return digits * 10**scale
        divisor = 10**-scale
        if exact and digits % divisor:
            raise ValueError(f"{self.text!r} mm is not a whole number of nanometres")
        return round_half_even_div(digits, divisor)

    def to_int(self) -> int:
        if self.kind != AtomKind.NUMBER or not re.fullmatch(r"-?\d+", self.text):
            raise ValueError(f"{self.text!r} is not an integer")
        return int(self.text)

    @classmethod
    def symbol(cls, name: str) -> Atom:
        return cls(name, AtomKind.SYMBOL)

    @classmethod
    def string(cls, value: str) -> Atom:
        """A quoted string written as KiCad writes it (see ``docs/formats/kicad/sexpr.md``)."""
        return _atom(_encode(value), AtomKind.STRING)

    @classmethod
    def from_nm(cls, nm: int) -> Atom:
        """Millimetres with at most 6 decimals, no exponent, no trailing zeros or dot."""
        if type(nm) is not int:
            raise TypeError(f"nm must be an int, got {nm!r}")
        whole, frac = divmod(abs(nm), 1_000_000)
        text = str(whole) + (f".{frac:06d}".rstrip("0") if frac else "")
        return _atom(("-" if nm < 0 else "") + text, AtomKind.NUMBER)

    @classmethod
    def integer(cls, n: int) -> Atom:
        if type(n) is not int:
            raise TypeError(f"n must be an int, got {n!r}")
        return _atom(str(n), AtomKind.NUMBER)


_new = object.__new__
_set = object.__setattr__


def _atom(text: str, kind: AtomKind) -> Atom:
    """Unchecked constructor: the caller guarantees that ``kind`` is the lexical kind of ``text``."""
    atom = _new(Atom)
    _set(atom, "text", text)
    _set(atom, "kind", kind)
    return atom


@dataclass(frozen=True, slots=True)
class Node:
    """A list: a head atom and ordered children. ``offset`` (bytes) is not part of equality."""

    head: Atom
    children: tuple[Node | Atom, ...] = ()
    offset: int | None = field(default=None, compare=False)
    comments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.children) is not tuple:
            _set(self, "children", tuple(self.children))
        if type(self.comments) is not tuple:
            _set(self, "comments", tuple(self.comments))

    @property
    def name(self) -> str:
        return self.head.value

    def atoms(self) -> tuple[Atom, ...]:
        return tuple(c for c in self.children if type(c) is Atom)

    def nodes(self, name: str | None = None) -> tuple[Node, ...]:
        return tuple(c for c in self.children if type(c) is Node and (name is None or c.name == name))

    def find(self, name: str) -> Node | None:
        for c in self.children:
            if type(c) is Node and c.name == name:
                return c
        return None

    def with_children(self, children: Iterable[Node | Atom]) -> Node:
        return replace(self, children=tuple(children))


def _node(head: Atom, children: tuple[Node | Atom, ...], offset: int) -> Node:
    node = _new(Node)
    _set(node, "head", head)
    _set(node, "children", children)
    _set(node, "offset", offset)
    _set(node, "comments", ())
    return node


# --- parsing --------------------------------------------------------------------------------------


class _Frame:
    """An open list while parsing: its head (once read), children so far, byte offset, char index."""

    __slots__ = ("children", "head", "offset", "start")

    def __init__(self, offset: int, start: int) -> None:
        self.head: Atom | None = None
        self.children: list[Node | Atom] = []
        self.offset = offset
        self.start = start


def _locator(stack: list[_Frame]) -> str:
    """Locator of the innermost open list that has a head."""
    parts: list[str] = []
    parent: list[Node | Atom] | None = None
    for frame in stack:
        if frame.head is None:
            break
        name = frame.head.value
        if parent is None:
            parts.append(f"/{name}")
        else:
            index = sum(1 for c in parent if isinstance(c, Node) and c.name == name)
            parts.append(f"/{name}[{index}]")
        parent = frame.children
    return "".join(parts)


class _Parser:
    __slots__ = ("ascii", "file", "fragment", "text")

    def __init__(self, text: str, file: str, *, fragment: bool) -> None:
        self.text = text
        self.file = file
        self.fragment = fragment
        self.ascii = text.isascii()

    def byte(self, i: int) -> int:
        return i if self.ascii else len(self.text[:i].encode("utf-8", "surrogatepass"))

    def error(self, message: str, i: int, stack: list[_Frame] | None = None) -> FormatError:
        return FormatError(message, file=self.file, locator=_locator(stack or []), offset=self.byte(i))

    def bad_string(self, i: int, stack: list[_Frame]) -> FormatError:
        text = self.text
        closed = _STRING.match(text, i)
        if closed is not None:  # a well-formed string followed directly by another atom
            return self.error("atom directly after a closing quote", closed.end(), stack)
        end = _STRING_PREFIX.match(text, i).end()  # type: ignore[union-attr]
        if end < len(text) and text[end] == "\\":
            end += 1
        if end >= len(text):
            return self.error("unterminated string", i, stack)
        if text[end] == "\n":
            return self.error("newline inside string", end, stack)
        return self.error("carriage return inside string", end, stack)

    def comments(self, pos: int) -> tuple[tuple[str, ...], int]:
        """Skip whitespace and ``#`` lines before the root; return them and the root position."""
        text, n = self.text, len(self.text)
        found: list[str] = []
        while True:
            pos = _WS.match(text, pos).end()  # type: ignore[union-attr]
            if pos >= n:
                raise self.error("empty input: no root list", n)
            c = text[pos]
            if c == "(":
                return tuple(found), pos
            if c == "#" and not self.fragment:
                start = text.rfind("\n", 0, pos) + 1
                eol = text.find("\n", pos)
                eol = n if eol < 0 else eol
                found.append(text[start:eol].rstrip("\r"))
                pos = eol
                continue
            if c == "﻿" and pos == 0:
                raise self.error("byte-order mark before the root list", 0)
            raise self.error("content before the root list", pos)

    def parse(self) -> Node | Atom:
        text, n = self.text, len(self.text)
        if self.fragment:
            pos = _WS.match(text, 0).end()  # type: ignore[union-attr]
            if pos >= n:
                raise self.error("empty fragment", n)
            if text[pos] != "(":
                return self.fragment_atom(pos)
            comments: tuple[str, ...] = ()
        else:
            comments, pos = self.comments(0)
        root, end = self.parse_list(pos)
        rest = _WS.match(text, end).end()  # type: ignore[union-attr]
        if rest < n:
            what = "more than one element" if self.fragment else "content after the root list"
            raise self.error(what, rest)
        if comments:
            _set(root, "comments", comments)
        return root

    def fragment_atom(self, pos: int) -> Atom:
        text, n = self.text, len(self.text)
        match = _TOKEN.match(text, pos)
        assert match is not None
        group = match.lastgroup
        if group not in ("str", "atom"):
            if text[pos] == '"':
                raise self.bad_string(pos, [])
            raise self.error(f"unexpected {text[pos]!r}", pos)
        end = match.end()
        if _WS.match(text, end).end() < n:  # type: ignore[union-attr]
            raise self.error("more than one element", _WS.match(text, end).end())  # type: ignore[union-attr]
        token = match.group()
        if group == "str":
            return _atom(token, AtomKind.STRING)
        return _atom(token, AtomKind.NUMBER if _NUMBER.fullmatch(token) else AtomKind.SYMBOL)

    def parse_list(self, pos: int) -> tuple[Node, int]:
        text = self.text
        ascii_text = self.ascii
        cache: dict[str, Atom] = {}
        stack: list[_Frame] = []
        counted_char, counted_byte = 0, 0
        number = _NUMBER.fullmatch
        for m in _TOKEN.finditer(text, pos):
            group = m.lastgroup
            if group == "ws":
                continue
            if group == "open":
                start = m.start()
                if stack and stack[-1].head is None:
                    raise self.error("list starting with a list", start, stack)
                if len(stack) >= MAX_DEPTH:
                    raise self.error(f"nesting deeper than MAX_DEPTH ({MAX_DEPTH})", start, stack)
                if ascii_text:
                    offset = start
                else:
                    counted_byte += len(text[counted_char:start].encode("utf-8", "surrogatepass"))
                    counted_char = start
                    offset = counted_byte
                stack.append(_Frame(offset, start))
            elif group == "close":
                frame = stack[-1]
                head = frame.head
                if head is None:
                    raise self.error("empty list ()", frame.start, stack)
                stack.pop()
                node = _node(head, tuple(frame.children), frame.offset)
                if stack:
                    stack[-1].children.append(node)
                else:
                    return node, m.end()
            elif group == "str" or group == "atom":
                token = m.group()
                atom = cache.get(token)
                if atom is None:
                    if group == "str":
                        kind = AtomKind.STRING
                    else:
                        kind = AtomKind.NUMBER if number(token) else AtomKind.SYMBOL
                    atom = cache[token] = _atom(token, kind)
                frame = stack[-1]
                if frame.head is None:
                    frame.head = atom
                else:
                    frame.children.append(atom)
            else:
                start = m.start()
                if text[start] == '"':
                    raise self.bad_string(start, stack)
                raise self.error(f"unexpected character {text[start]!r}", start, stack)  # pragma: no cover
        raise self.error(f"unbalanced parentheses: {len(stack)} list(s) not closed", len(text), stack)


def parse(text: str, *, file: str = "") -> Node:
    """Parse a whole file (one root list, optional ``#`` lines before it)."""
    result = _Parser(text, file, fragment=False).parse()
    assert isinstance(result, Node)
    return result


def parse_bytes(data: bytes, *, file: str = "") -> Node:
    """Parse UTF-8 bytes; invalid UTF-8 and a byte-order mark are rejected with their offset."""
    if data.startswith(b"\xef\xbb\xbf"):
        raise FormatError("byte-order mark before the root list", file=file, offset=0)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FormatError("invalid UTF-8", file=file, offset=exc.start) from exc
    return parse(text, file=file)


def load(path: str | os.PathLike[str]) -> Node:
    return parse_bytes(Path(path).read_bytes(), file=os.fspath(path))


def parse_fragment(text: str, *, file: str = "") -> Node | Atom:
    """Exactly one list or one atom, with optional surrounding whitespace and no comments."""
    return _Parser(text, file, fragment=True).parse()


# --- printing -------------------------------------------------------------------------------------


def _check_comments(node: Node, depth: int) -> None:
    if node.comments and depth:
        raise ValueError(f"comments on a nested node {node.name!r}; only the root may carry comments")


def _compact(node: Node, depth: int, out: list[str]) -> None:
    if depth > MAX_DEPTH:
        raise ValueError(f"tree deeper than MAX_DEPTH ({MAX_DEPTH})")
    _check_comments(node, depth)
    out.append("(" + node.head.text)
    for child in node.children:
        if type(child) is Atom:
            out.append(" " + child.text)
        else:
            out.append(" ")
            _compact(child, depth + 1, out)  # type: ignore[arg-type]
    out.append(")")


def _atoms_only(node: Node) -> bool:
    return all(type(c) is Atom for c in node.children)


def _one_line(node: Node) -> str:
    return "(" + " ".join([node.head.text, *(c.text for c in node.children)]) + ")"  # type: ignore[union-attr]


def _kicad(node: Node, depth: int, lines: list[str]) -> None:
    if depth > MAX_DEPTH:
        raise ValueError(f"tree deeper than MAX_DEPTH ({MAX_DEPTH})")
    _check_comments(node, depth)
    indent = "\t" * depth
    children = node.children
    count = len(children)
    first = 0
    while first < count and type(children[first]) is Atom:
        first += 1
    head_line = indent + "(" + " ".join([node.head.text, *(c.text for c in children[:first])])  # type: ignore[union-attr]
    if first == count:
        lines.append(head_line + ")")
        return
    lines.append(head_line)
    inner = indent + "\t"
    packing = node.head.text == "pts"
    current: int | None = None  # index in ``lines`` of the open xy line
    for child in children[first:]:
        if type(child) is Atom:
            lines.append(inner + child.text)
            current = None
            continue
        sub: Node = child  # type: ignore[assignment]
        if packing and sub.head.text == "xy" and _atoms_only(sub):
            _check_comments(sub, depth + 1)
            text = _one_line(sub)
            if current is not None and len(lines[current]) < XY_WRAP_COLUMNS:
                lines[current] += " " + text
            else:
                lines.append(inner + text)
                current = len(lines) - 1
            continue
        current = None
        _kicad(sub, depth + 1, lines)
    lines.append(indent + ")")


def dumps(x: Node | Atom, *, style: Literal["kicad", "compact"] = "kicad") -> str:
    """KiCad 10 layout (``"kicad"``) or one line (``"compact"``); atoms give their text."""
    if style not in ("kicad", "compact"):
        raise ValueError(f"unknown style {style!r} (use 'kicad' or 'compact')")
    if isinstance(x, Atom):
        return x.text
    if style == "compact":
        out: list[str] = []
        _compact(x, 0, out)
        return "".join(out)
    for comment in x.comments:
        if "\n" in comment or "\r" in comment or not comment.lstrip(" \t").startswith("#"):
            raise ValueError(f"invalid root comment {comment!r}: one line starting with '#'")
    lines: list[str] = list(x.comments)
    _kicad(x, 0, lines)
    return "\n".join(lines) + "\n"


def canonical(text: str, *, file: str = "") -> str:
    """Fenolite's canonical print of a KiCad S-expression text: ``dumps(parse(text))``.

    No atom changes, so the result parses tree-equal to ``text``, and printing it again gives the same
    bytes. The parser's ``FormatError`` and the printer's ``ValueError`` (comments below the root) are
    raised unchanged. This is Fenolite's layout, not a claim about the bytes KiCad writes.
    """
    return dumps(parse(text, file=file))


def first_line_difference(a: str, b: str) -> int | None:
    """The number, from 1, of the first line at which two texts differ; ``None`` for equal texts."""
    if a == b:
        return None
    lines_a, lines_b = a.split("\n"), b.split("\n")
    for number, (x, y) in enumerate(zip(lines_a, lines_b, strict=False), start=1):
        if x != y:
            return number
    return min(len(lines_a), len(lines_b)) + 1


# --- equality and locators ------------------------------------------------------------------------


def tree_equal(a: Node, b: Node) -> bool:
    """Heads, atom texts and kinds, child order and root comments; offsets and layout are ignored."""
    return a == b


def _child_locators(parent: str, node: Node) -> Iterator[tuple[str, Node]]:
    seen: dict[str, int] = {}
    for child in node.children:
        if type(child) is Node:
            name = child.name  # type: ignore[union-attr]
            index = seen.get(name, 0)
            seen[name] = index + 1
            yield f"{parent}/{name}[{index}]", child  # type: ignore[misc]


def walk(node: Node) -> Iterator[tuple[str, Node]]:
    """``(locator, node)`` for every node in document order, the root first."""
    stack: list[tuple[str, Node]] = [(f"/{node.name}", node)]
    while stack:
        locator, current = stack.pop()
        yield locator, current
        stack.extend(reversed(list(_child_locators(locator, current))))


def first_difference(a: Node, b: Node) -> str | None:
    """Locator of the first node that differs, or ``None`` for tree-equal nodes."""
    stack: list[tuple[str, Node, Node]] = [(f"/{a.name}", a, b)]
    while stack:
        locator, x, y = stack.pop()
        if x.head != y.head or x.comments != y.comments or len(x.children) != len(y.children):
            return locator
        pairs: list[tuple[str, Node, Node]] = []
        seen: dict[str, int] = {}
        for cx, cy in zip(x.children, y.children, strict=True):
            if type(cx) is not type(cy):
                return locator
            if type(cx) is Atom:
                if cx != cy:
                    return locator
                continue
            nx: Node = cx  # type: ignore[assignment]
            ny: Node = cy  # type: ignore[assignment]
            if nx.head != ny.head:
                return locator
            index = seen.get(nx.name, 0)
            seen[nx.name] = index + 1
            pairs.append((f"{locator}/{nx.name}[{index}]", nx, ny))
        stack.extend(reversed(pairs))
    return None


__all__ = [
    "MAX_DEPTH",
    "Atom",
    "AtomKind",
    "Node",
    "canonical",
    "dumps",
    "first_difference",
    "first_line_difference",
    "load",
    "parse",
    "parse_bytes",
    "parse_fragment",
    "tree_equal",
    "walk",
]
