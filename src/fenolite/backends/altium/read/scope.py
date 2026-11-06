# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed grammar of rule scopes (capability altium-project-reader, "Closed scope grammar", changes
c0042 and c0462).

``parse_scope`` turns a scope query into a neutral ``Selector`` only when the query is inside a closed
grammar (``docs/formats/altium/rule-file.md``, "Closed scope grammar"); any other query gives a
``Refusal``, a string that says why, so that no scope is approximated. The grammar follows the order of
precedence of Altium's query language (S-2211): brackets, then ``Not``, then ``^ * / Div Mod And``, then
``+ - Or Xor``, then the comparisons, then ``&& ||``; equal levels go from left to right. The parse is typed:
a value is a set of objects (a selector), a number, a string or a field of the objects, and a query whose
typed reading is not a set of objects is refused, naming the operator, never re-bracketed.

``parse_layer_scope`` reads the two layer conditions of change c0125 (``rule-file.md``, "Layer scopes of
Clearance"): they name layers of a board, so they give no selector; ``read.rules`` maps them with the
copper layers of the board a record belongs to.
"""

# evidence: see import_evidence, read.project

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from fenolite.model.rules import NO_NET as NO_NET_SELECTOR
from fenolite.model.rules import Selector, SelectorOp

LEAF_FUNCTIONS: dict[str, SelectorOp] = {"InNet": "net", "InNetClass": "netclass", "InComponent": "ref"}
"""Membership functions of quoted values, and the neutral selector each gives (S-2212): ``InNet`` and
``InComponent`` take one or more names, each of which may hold Altium's wildcards ``*`` and ``?``;
``InNetClass`` takes one class name, compared as written."""
WILDCARD_FUNCTIONS = frozenset({"InNet", "InComponent"})
"""The functions whose values hold Altium's wildcards (S-2212, "Membership Checks": ``InNet('V*')`` returns
the nets whose names start with V)."""
NO_NET = "No Net"
"""The net name ``InNet`` takes for the objects without a net (``rule-file.md``, "Closed scope grammar";
``H-A-RD-PRJ-SCOPE-NONET``, change c0409): ``InNet('No Net')`` is ``model.rules.NO_NET``."""
ANY_NET = "InAnyNet"
"""The attribute check, without an argument, that is true for an object of a net or a primitive of one: ``Not
InAnyNet`` returns the objects without a net (S-1680; change c0420, B7). It is ``net *``, so ``Not InAnyNet``
is ``model.rules.NO_NET``."""
ITEM_KINDS: dict[str, str] = {
    "IsTrack": "track",
    "IsVia": "via",
    "IsPad": "pad",
    "InPolygon": "zone",
    "InPoly": "zone",
}
"""Object-type checks without arguments, and the neutral item kind each selects. ``InPolygon`` (alias
``InPoly``) is the attribute check that a Clearance rule names for the copper of a pour (``pcb-pour.md``
I3; S-1702, change c0412); with an argument it stays outside the grammar."""
AND_OPERATORS = ("And", "&&")
OR_OPERATORS = ("Or", "||")
NOT_OPERATOR = "Not"
GLOB_CHARACTERS = ("*", "?", "[", "]")
ALTIUM_WILDCARDS = ("*", "?")
"""Altium's two wildcard characters (S-2211, "Wild Card Characters")."""
INNER_SIGNAL = "OnMid"
"""The layer check that is true for an object on an internal signal layer (S-0555)."""
EXISTS_ON_LAYER = "ExistsOnLayer"
"""The membership check that is true for an object that exists on the named layer, an object on
Multi-Layer included (S-0556)."""
UNIT_NM: dict[str, int] = {"mil": 25_400, "mm": 1_000_000}
"""Nanometres per unit of ``AsMils`` and ``AsMM`` (S-2212)."""

KEYWORDS: dict[str, str] = {
    word.casefold(): word
    for word in ("And", "Or", "Not", "Xor", "Div", "Mod", "Between", "Like", "True", "False")
}
"""The operator words and boolean strings by their letters in any case, and the spelling the grammar holds
(change c0377 for And, Or and Not; ``H-A-RD-PRJ-SCOPE-CASE``, ``INFERRED``)."""
SPELLED: dict[str, str] = {"and": "And", "or": "Or", "not": "Not"}
"""The three operators that change c0377 read in any letter case (kept for its callers)."""

LEVELS: dict[str, int] = {
    "&&": 1, "||": 1,
    "=": 2, "<>": 2, "<": 2, ">": 2, "<=": 2, ">=": 2, "Between": 2, "Like": 2,
    "+": 3, "-": 3, "Or": 3, "Xor": 3,
    "^": 4, "*": 4, "/": 4, "Div": 4, "Mod": 4, "And": 4,
}  # fmt: skip
"""The binary operators by binding level, loosest first (S-2211); ``Not`` binds tighter than all of them."""
COMPARISONS = frozenset({"=", "<>", "<", ">", "<=", ">="})
ARITHMETIC = frozenset({"+", "-", "^", "*", "/", "Div", "Mod"})
LOGIC: dict[str, Literal["and", "or", "xor"]] = {
    "&&": "and",
    "And": "and",
    "||": "or",
    "Or": "or",
    "Xor": "xor",
}

RefusalReason = Literal["grammar", "type", "unit", "undefined", "document", "syntax"]
"""Why a scope is refused: outside the grammar (a function or operator it does not read), a typed reading
that is not a set of objects (``type``), a number whose unit the document does not give (``unit``), a name
the document does not define (``undefined``), a function that reads the document called without one
(``document``), or text that is not a query (``syntax``)."""


class Refusal(str):
    """A refused scope: the text says why, ``reason`` is one of ``RefusalReason``."""

    reason: RefusalReason

    def __new__(cls, reason: RefusalReason, message: str) -> Refusal:
        made = super().__new__(cls, message)
        made.reason = reason
        return made


@dataclass(frozen=True, slots=True)
class ScopeDocument:
    """What a scope's functions read from the document its record belongs to (change c0462). ``unit``: the
    unit of a number written without ``AsMils`` or ``AsMM``, when the document gives one; without it only
    the number 0 compares with a length."""

    unit: Literal["mil", "mm"] | None = None


_TOKEN = re.compile(
    r"\s*(?:(?P<string>'[^']*')|(?P<number>[0-9]+(?:\.[0-9]+)?)"
    r"|(?P<op>&&|\|\||<>|<=|>=|[=<>+\-*/^,])|(?P<open>\()|(?P<close>\))"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<other>\S))"
)


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str


class _Refused(Exception):
    """The query is outside the grammar; ``reason`` and the message say why."""

    def __init__(self, message: str, reason: RefusalReason = "grammar") -> None:
        super().__init__(message)
        self.reason: RefusalReason = reason


def _tokens(text: str) -> list[_Token]:
    found: list[_Token] = []
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:  # only spaces are left
            break
        kind = match.lastgroup or "other"
        word = match.group(kind)
        if kind == "name":
            word = KEYWORDS.get(word.casefold(), word)
        found.append(_Token(kind, word))
        position = match.end()
    return found


# --- typed values ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Set:
    """A set of objects. ``grouped``: written in brackets or given by one function, so an operator next
    to it does not merge into it."""

    selector: Selector
    grouped: bool = False


@dataclass(frozen=True, slots=True)
class _Number:
    value: Decimal


@dataclass(frozen=True, slots=True)
class _String:
    text: str


@dataclass(frozen=True, slots=True)
class _Truth:
    """The boolean string ``True`` or ``False``, written bare or quoted (S-2211, "Boolean Strings")."""

    value: bool


@dataclass(frozen=True, slots=True)
class _Field:
    """A numeric field of the objects (change c0462, task 3): ``leaf`` gives the selector of the objects
    whose value lies in the closed interval of nanometres (``None``: open). ``unit`` is the unit
    ``AsMils``/``AsMM`` gives; ``length``: a length, else a count."""

    name: str
    leaf: Callable[[int | None, int | None], Selector]
    length: bool = True
    unit: str | None = None


_Value = _Set | _Number | _String | _Truth | _Field


def _kind(value: _Value) -> str:
    if isinstance(value, _Set):
        return "a set of objects"
    if isinstance(value, _Number):
        return "a number"
    if isinstance(value, _Field):
        return f"the number {value.name}"
    if isinstance(value, _Truth):
        return "a boolean string"
    return "a string"


def _flat(op: Literal["and", "or"], items: Sequence[_Set]) -> Selector:
    """``op`` of ``items``, an ungrouped operand of the same ``op`` merged into it."""
    found: list[Selector] = []
    for item in items:
        if not item.grouped and item.selector.op == op:
            found.extend(item.selector.items)
        else:
            found.append(item.selector)
    return Selector(op, items=tuple(found))


def _not(selector: Selector) -> Selector:
    return Selector("not", items=(selector,))


def _escaped(text: str, wildcards: bool) -> str:
    """The neutral glob (``fnmatch``) of an Altium value: Altium's ``*`` and ``?`` stay wildcards where the
    function takes them; every other glob character is escaped, so it matches itself."""
    out: list[str] = []
    for character in text:
        if character in ALTIUM_WILDCARDS and wildcards:
            out.append(character)
        elif character in GLOB_CHARACTERS:
            out.append(f"[{character}]")
        else:
            out.append(character)
    return "".join(out)


FunctionHandler = Callable[["_Parser", str], _Value]
"""A function of the grammar: it reads its own arguments from the parser, after its name."""


class _Parser:
    def __init__(self, tokens: list[_Token], document: ScopeDocument | None) -> None:
        self.tokens = tokens
        self.position = 0
        self.document = document

    def peek(self, ahead: int = 0) -> _Token | None:
        at = self.position + ahead
        return self.tokens[at] if at < len(self.tokens) else None

    def take(self) -> _Token:
        token = self.peek()
        if token is None:
            raise _Refused("the query ends where an operand is expected", "syntax")
        self.position += 1
        return token

    def binary(self) -> str | None:
        token = self.peek()
        if token is None or token.kind not in ("op", "name"):
            return None
        return token.text if token.text in LEVELS else None

    def expression(self, floor: int = 1, *, stop_and: bool = False) -> _Value:
        """Precedence climbing: the operand, then each binary operator of level ``floor`` or tighter, left
        to right. ``stop_and``: an ``And`` ends the expression (the bound of ``Between … And …``)."""
        left = self.unary()
        while True:
            op = self.binary()
            if op is None or LEVELS[op] < floor or (stop_and and op == "And"):
                return left
            self.take()
            if op == "Between":
                low = self.expression(LEVELS["Between"] + 1, stop_and=True)
                word = self.take()
                if word.text != "And":
                    raise _Refused("Between must be followed by a bound, And and a bound", "syntax")
                high = self.expression(LEVELS["Between"] + 1, stop_and=stop_and)
                left = self.between(left, low, high)
                continue
            right = self.expression(LEVELS[op] + 1, stop_and=stop_and)
            left = self.combine(op, left, right)

    def unary(self) -> _Value:
        token = self.peek()
        if token is not None and token.text == NOT_OPERATOR:
            self.take()
            operand = self.unary()
            if not isinstance(operand, _Set):
                raise _Refused(f"the operator Not takes a set of objects, not {_kind(operand)}", "type")
            return _Set(_not(operand.selector))
        if token is not None and token.text == "-" and token.kind == "op":
            self.take()
            operand = self.unary()
            if not isinstance(operand, _Number):
                raise _Refused(f"the sign - takes a number, not {_kind(operand)}", "type")
            return _Number(-operand.value)
        return self.primary()

    def combine(self, op: str, left: _Value, right: _Value) -> _Value:
        if op in LOGIC:
            if not (isinstance(left, _Set) and isinstance(right, _Set)):
                raise _Refused(
                    f"the operator {op} joins {_kind(left)} and {_kind(right)}: it binds as Altium's order "
                    "of precedence gives it (S-2211), and the query is not re-bracketed",
                    "type",
                )
            logic = LOGIC[op]
            if logic == "xor":
                a, b = left.selector, right.selector
                both = (Selector("and", items=(a, _not(b))), Selector("and", items=(_not(a), b)))
                return _Set(Selector("or", items=both), grouped=True)
            return _Set(_flat(logic, (left, right)))
        if op in COMPARISONS:
            return self.compare(op, left, right)
        if op in ARITHMETIC:
            raise _Refused(f"the arithmetic operator {op} is outside the closed grammar")
        raise _Refused(f"the operator {op} is outside the closed grammar")

    def compare(self, op: str, left: _Value, right: _Value) -> _Value:
        truth = right if isinstance(right, _Truth) else left if isinstance(left, _Truth) else None
        other = left if truth is right else right
        if truth is not None and isinstance(other, _Set) and op in ("=", "<>"):
            assert isinstance(truth, _Truth)
            keep = truth.value == (op == "=")
            return _Set(other.selector if keep else _not(other.selector), grouped=other.grouped or not keep)
        if isinstance(left, _Field) and isinstance(right, _Number):
            return _Set(self.interval(left, op, right), grouped=True)
        if isinstance(left, _Number) and isinstance(right, _Field):
            mirrored = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}.get(op, op)
            return _Set(self.interval(right, mirrored, left), grouped=True)
        raise _Refused(
            f"the comparison {op} of {_kind(left)} with {_kind(right)} is outside the grammar", "type"
        )

    def nanometres(self, field_: _Field, number: _Number) -> int:
        if not field_.length:
            if number.value != number.value.to_integral_value():
                raise _Refused(f"{field_.name} is a count, compared with {number.value}", "type")
            return int(number.value)
        unit = field_.unit or (self.document.unit if self.document is not None else None)
        if number.value == 0:
            return 0
        if unit is None:
            raise _Refused(
                f"the number {number.value} compared with {field_.name} has no unit: the document does not "
                "give the unit of the query, and no AsMils or AsMM names one",
                "unit",
            )
        scaled = number.value * UNIT_NM[unit]
        if scaled != scaled.to_integral_value():
            raise _Refused(f"{number.value} {unit} is not a whole number of nanometres", "unit")
        return int(scaled)

    def interval(self, field_: _Field, op: str, number: _Number) -> Selector:
        value = self.nanometres(field_, number)
        if op == "=":
            return field_.leaf(value, value)
        if op == "<>":
            return _not(field_.leaf(value, value))
        bounds = {">": (value + 1, None), ">=": (value, None), "<": (None, value - 1), "<=": (None, value)}
        return field_.leaf(*bounds[op])

    def between(self, subject: _Value, low: _Value, high: _Value) -> _Value:
        if not (isinstance(subject, _Field) and isinstance(low, _Number) and isinstance(high, _Number)):
            raise _Refused(
                f"Between compares {_kind(subject)} with {_kind(low)} and {_kind(high)}: outside the grammar",
                "type",
            )
        return _Set(subject.leaf(self.nanometres(subject, low), self.nanometres(subject, high)), grouped=True)

    def primary(self) -> _Value:
        token = self.take()
        if token.kind == "open":
            inner = self.expression()
            closing = self.peek()
            if closing is None or closing.kind != "close":
                raise _Refused("a parenthesis is not closed", "syntax")
            self.take()
            return _Set(inner.selector, grouped=True) if isinstance(inner, _Set) else inner
        if token.kind == "string":
            body = token.text[1:-1]
            if body in ("True", "False"):
                return _Truth(body == "True")
            return _String(body)
        if token.kind == "number":
            try:
                return _Number(Decimal(token.text))
            except InvalidOperation:  # pragma: no cover - the token pattern holds digits only
                raise _Refused(f"the number {token.text} does not read", "syntax") from None
        if token.kind != "name":
            raise _Refused(f"the text {token.text!r} is outside the closed grammar", "syntax")
        name = token.text
        if name in ("True", "False"):
            return _Truth(name == "True")
        if name == "All":
            raise _Refused("All stands below the top level; it is accepted only as the whole scope")
        if name in LEVELS or name == NOT_OPERATOR:
            raise _Refused(f"the operator {name} stands where an operand is expected", "syntax")
        if name in ITEM_KINDS:
            return _Set(Selector("item_kind", ITEM_KINDS[name]))
        if name == ANY_NET:
            return _Set(Selector("net", "*"))
        if name in LEAF_FUNCTIONS:
            return self.membership(name)
        handler = FUNCTIONS.get(name)
        if handler is not None:
            return handler(self, name)
        if name.startswith("On"):
            raise _Refused(
                f"the layer function {name} is not mapped: it needs the board's layer names, "
                "which only the import maps"
            )
        raise _Refused(f"the function {name} is outside the closed grammar")

    def strings(self, name: str, *, many: bool) -> list[str]:
        """The quoted values of ``name(…)``: one, or one or more separated by commas with ``many``."""
        if self.peek() is None:
            raise _Refused("the query ends where an operand is expected", "syntax")
        opening = self.take()
        if opening.kind != "open":
            raise _Refused(f"{name} must be followed by quoted values in parentheses", "syntax")
        found: list[str] = []
        while True:
            value = self.take()
            if value.kind != "string":
                if value.text == "'":
                    raise _Refused(f"the value of {name} holds an unclosed quote '", "syntax")
                raise _Refused(f"{name} takes quoted values", "syntax")
            following = self.take()
            if following.kind == "string" or following.text == "'":
                raise _Refused(f"the value of {name} holds a quote ', which a neutral value cannot hold")
            text = value.text[1:-1]
            if not text:
                raise _Refused(f"the value of {name} is empty", "syntax")
            found.append(text)
            if following.kind == "close":
                return found
            if following.text != "," or not many:
                raise _Refused(f"{name} takes {'quoted values' if many else 'one quoted value'}", "syntax")

    def membership(self, name: str) -> _Set:
        values = self.strings(name, many=name in WILDCARD_FUNCTIONS)
        op = LEAF_FUNCTIONS[name]
        leaves = [
            NO_NET_SELECTOR
            if name == "InNet" and value == NO_NET
            else Selector(op, _escaped(value, name in WILDCARD_FUNCTIONS))
            for value in values
        ]
        if len(leaves) == 1:
            return _Set(leaves[0])
        return _Set(Selector("or", items=tuple(leaves)), grouped=True)


def _unit_function(parser: _Parser, name: str) -> _Value:
    """``AsMils(field)`` and ``AsMM(field)``: the field with its unit (S-2212, "Membership Checks")."""
    opening = parser.take()
    if opening.kind != "open":
        raise _Refused(f"{name} must be followed by a field in parentheses", "syntax")
    inner = parser.expression()
    closing = parser.take()
    if closing.kind != "close":
        raise _Refused(f"{name} takes one field", "syntax")
    if not isinstance(inner, _Field) or not inner.length:
        raise _Refused(f"{name} takes a length field, not {_kind(inner)}", "type")
    return _Field(inner.name, inner.leaf, True, "mil" if name == "AsMils" else "mm")


FUNCTIONS: dict[str, FunctionHandler] = {"AsMils": _unit_function, "AsMM": _unit_function}
"""The functions of the grammar beyond the membership checks, by name (change c0462)."""


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


def parse_scope(text: str, *, document: ScopeDocument | None = None) -> Selector | Refusal:
    """The neutral selector of the scope query ``text``, or a ``Refusal`` that says why ``text`` is outside
    the closed grammar of ``rule-file.md``. ``All`` is accepted only as the whole query. ``document`` gives
    what the functions read from the record's document (``ScopeDocument``)."""
    if text.strip() == "All":
        return Selector("all")
    parser = _Parser(_tokens(text), document)
    try:
        if parser.peek() is None:
            return Refusal("syntax", "the scope is empty")
        value = parser.expression()
        left = parser.peek()
        if left is not None:
            raise _Refused(f"text left over at {left.text!r}", "syntax")
        if not isinstance(value, _Set):
            raise _Refused(f"the query gives {_kind(value)}, not a set of objects", "type")
    except _Refused as refused:
        return Refusal(refused.reason, str(refused))
    return value.selector


__all__ = [
    "ALTIUM_WILDCARDS",
    "AND_OPERATORS",
    "ANY_NET",
    "EXISTS_ON_LAYER",
    "FUNCTIONS",
    "GLOB_CHARACTERS",
    "INNER_SIGNAL",
    "ITEM_KINDS",
    "LEAF_FUNCTIONS",
    "NOT_OPERATOR",
    "OR_OPERATORS",
    "UNIT_NM",
    "WILDCARD_FUNCTIONS",
    "LayerScope",
    "Refusal",
    "ScopeDocument",
    "parse_layer_scope",
    "parse_scope",
]
