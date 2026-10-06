# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed grammar of rule scopes (capability altium-project-reader, "Closed scope grammar", c0042).

``parse_scope`` turns a scope query into a neutral ``Selector`` only when the query is inside a small
closed grammar (``docs/formats/altium/rule-file.md``, "Closed scope grammar"); any other query gives a
string that says why, so that no scope is approximated. One parenthesis level holds one kind of
operator, because no permitted source states the precedence (S-0296).

``parse_layer_scope`` reads the two layer conditions of change c0125 (``rule-file.md``, "Layer scopes of
Clearance"): they name layers of a board, so they give no selector; ``read.rules`` maps them with the
copper layers of the board a record belongs to.
"""

# evidence: see import_evidence, read.project

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from fenolite.model.rules import Selector, SelectorOp

LEAF_FUNCTIONS: dict[str, SelectorOp] = {"InNet": "net", "InNetClass": "netclass", "InComponent": "ref"}
"""Membership functions with one quoted value, and the neutral selector each gives."""
ITEM_KINDS: dict[str, str] = {"IsTrack": "track", "IsVia": "via", "IsPad": "pad"}
"""Object-type checks without arguments, and the neutral item kind each selects."""
AND_OPERATORS = ("And", "&&")
OR_OPERATORS = ("Or", "||")
NOT_OPERATOR = "Not"
GLOB_CHARACTERS = ("*", "?", "[", "]")
INNER_SIGNAL = "OnMid"
"""The layer check that is true for an object on an internal signal layer (S-0555)."""
EXISTS_ON_LAYER = "ExistsOnLayer"
"""The membership check that is true for an object that exists on the named layer, an object on
Multi-Layer included (S-0556)."""

_TOKEN = re.compile(
    r"\s*(?:(?P<string>'[^']*')|(?P<op>&&|\|\|)|(?P<open>\()|(?P<close>\))"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<other>\S))"
)


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str


class _Refused(Exception):
    """The query is outside the grammar; the message says why."""


def _tokens(text: str) -> list[_Token]:
    found: list[_Token] = []
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:  # only spaces are left
            break
        kind = match.lastgroup or "other"
        found.append(_Token(kind, match.group(kind)))
        position = match.end()
    return found


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self.tokens = tokens
        self.position = 0

    def peek(self) -> _Token | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self) -> _Token:
        token = self.peek()
        if token is None:
            raise _Refused("the query ends where an operand is expected")
        self.position += 1
        return token

    def at_level_end(self) -> bool:
        token = self.peek()
        return token is None or token.kind == "close"

    def level(self) -> Selector:
        token = self.peek()
        if token is not None and token.text == NOT_OPERATOR:
            self.take()
            operand = self.operand()
            if not self.at_level_end():
                raise _Refused(
                    "Not must be the whole of its parenthesis level: the precedence of Not, And and Or "
                    "is not stated, so put the operand of Not and the rest in parentheses"
                )
            return Selector("not", items=(operand,))
        items = [self.operand()]
        kind: Literal["and", "or"] | None = None
        while not self.at_level_end():
            token = self.take()
            current: Literal["and", "or"]
            if token.text in AND_OPERATORS:
                current = "and"
            elif token.text in OR_OPERATORS:
                current = "or"
            else:
                raise _Refused(f"text left over at {token.text!r}: an operator And or Or is expected")
            if kind is not None and current != kind:
                raise _Refused(
                    "the query mixes the operators And and Or at one parenthesis level; their precedence "
                    "is not stated, so each level must hold one kind of operator"
                )
            kind = current
            following = self.peek()
            if following is not None and following.text == NOT_OPERATOR:
                raise _Refused(
                    f"the query mixes Not with {'And' if kind == 'and' else 'Or'} at one parenthesis level; "
                    "put Not and its operand in parentheses"
                )
            items.append(self.operand())
        if kind is None:
            return items[0]
        return Selector(kind, items=tuple(items))

    def operand(self) -> Selector:
        token = self.take()
        if token.kind == "open":
            inner = self.level()
            closing = self.peek()
            if closing is None or closing.kind != "close":
                raise _Refused("a parenthesis is not closed")
            self.take()
            return inner
        if token.kind == "string":
            raise _Refused(f"a quoted value {token.text} stands where an operand is expected")
        if token.kind != "name":
            raise _Refused(f"the text {token.text!r} is outside the closed grammar")
        name = token.text
        if name == "All":
            raise _Refused("All stands below the top level; it is accepted only as the whole scope")
        if name in (NOT_OPERATOR, *AND_OPERATORS, *OR_OPERATORS):
            raise _Refused(f"the operator {name} stands where an operand is expected")
        if name in ITEM_KINDS:
            return Selector("item_kind", ITEM_KINDS[name])
        if name in LEAF_FUNCTIONS:
            return Selector(LEAF_FUNCTIONS[name], self.argument(name))
        if name.startswith("On"):
            raise _Refused(
                f"the layer function {name} is not mapped: it needs the board's layer names, "
                "which only the import maps"
            )
        raise _Refused(f"the function {name} is outside the closed grammar")

    def argument(self, name: str) -> str:
        opening = self.take()
        if opening.kind != "open":
            raise _Refused(f"{name} must be followed by one quoted value in parentheses")
        value = self.take()
        if value.kind != "string":
            if value.text == "'":
                raise _Refused(f"the value of {name} holds an unclosed quote '")
            raise _Refused(f"{name} takes one quoted value")
        closing = self.take()
        if closing.kind != "close":
            if closing.kind == "string" or closing.text == "'":
                raise _Refused(f"the value of {name} holds a quote ', which a neutral value cannot hold")
            raise _Refused(f"{name} takes one quoted value")
        text = value.text[1:-1]
        if not text:
            raise _Refused(f"the value of {name} is empty")
        for character in GLOB_CHARACTERS:
            if character in text:
                raise _Refused(
                    f"the value of {name} holds the character {character}: a neutral value is a glob, "
                    "and Altium's own wildcard rules are not stated"
                )
        return text


@dataclass(frozen=True, slots=True)
class LayerScope:
    """A scope that is one layer condition: ``inner`` for ``OnMid``, else the layer names of
    ``ExistsOnLayer('…')`` or of a disjunction of such terms, as written and in written order."""

    inner: bool = False
    names: tuple[str, ...] = ()


def parse_layer_scope(text: str) -> LayerScope | None:
    """The layer condition that is the whole scope ``text``, or ``None`` for any other scope: ``OnMid``,
    ``ExistsOnLayer('<name>')``, or such terms joined by ``Or``; one pair of parentheses may enclose the
    whole. Nothing else is read here: a layer condition joined with another function stays outside the
    grammar (``parse_scope`` says why)."""
    tokens = _tokens(text)
    if len(tokens) >= 2 and tokens[0].kind == "open" and tokens[-1].kind == "close":
        tokens = tokens[1:-1]
    if [(token.kind, token.text) for token in tokens] == [("name", INNER_SIGNAL)]:
        return LayerScope(inner=True)
    names: list[str] = []
    position = 0
    while True:
        term = tokens[position : position + 4]
        if [token.kind for token in term] != ["name", "open", "string", "close"]:
            return None
        if term[0].text != EXISTS_ON_LAYER or len(term[2].text) < 3:
            return None
        names.append(term[2].text[1:-1])
        position += 4
        if position == len(tokens):
            return LayerScope(names=tuple(names))
        if tokens[position].text not in OR_OPERATORS:
            return None
        position += 1


def parse_scope(text: str) -> Selector | str:
    """The neutral selector of the scope query ``text``, or a string that says why ``text`` is outside the
    closed grammar of ``rule-file.md``. ``All`` is accepted only as the whole query."""
    if text.strip() == "All":
        return Selector("all")
    parser = _Parser(_tokens(text))
    try:
        if parser.peek() is None:
            return "the scope is empty"
        selector = parser.level()
        left = parser.peek()
        if left is not None:
            raise _Refused(f"text left over at {left.text!r}")
    except _Refused as refused:
        return str(refused)
    return selector


__all__ = [
    "AND_OPERATORS",
    "EXISTS_ON_LAYER",
    "GLOB_CHARACTERS",
    "INNER_SIGNAL",
    "ITEM_KINDS",
    "LEAF_FUNCTIONS",
    "NOT_OPERATOR",
    "OR_OPERATORS",
    "LayerScope",
    "parse_layer_scope",
    "parse_scope",
]
