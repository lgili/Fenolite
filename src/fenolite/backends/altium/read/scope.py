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

import fnmatch
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Literal

from fenolite.model.rules import NO_NET as NO_NET_SELECTOR
from fenolite.model.rules import Selector, SelectorOp, hole_value

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
NET_TIE_KIND = "4"
"""The ``COMPONENTKIND`` of a Net Tie component (``pcb-records.md``, ``H-A-PCBX-NETTIE``)."""
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

RefusalReason = Literal[
    "grammar", "type", "unit", "undefined", "document", "syntax", "object-kind", "via-span", "drill-pair",
    "designator", "package-check", "xsignal", "union", "room-membership", "pad-plated", "hole-zero",
]  # fmt: skip
"""Why a scope is refused: outside the grammar (a function or operator it does not read), a typed reading
that is not a set of objects (``type``), a number whose unit the document does not give (``unit``), a name
the document does not define (``undefined``), a function that reads the document called without one, or a
document without what it reads (``document``), or text that is not a query (``syntax``). Change c0462 adds
the reasons of its functions: a function that returns parent objects only (a polygon, a component, a pair)
in a rule that does not judge them (``object-kind``); a layer function on a board with blind or buried vias
(``via-span``) or a drill pair that is not the whole stack (``drill-pair``); a designator that names more
components than a function selects (``designator``); a package check the document's pads do not decide
(``package-check``); xSignals and unions, which the reader does not read (``xsignal``, ``union``); a room
the document holds, whose membership no neutral leaf selects (``room-membership``); ``PadIsPlated`` on a
board whose pads without a hole are not all plated or all unplated (``pad-plated``); and a hole interval
that holds 0, the hole size of a pad without a hole (``hole-zero``)."""


class Refusal(str):
    """A refused scope: the text says why, ``reason`` is one of ``RefusalReason``."""

    reason: RefusalReason

    def __new__(cls, reason: RefusalReason, message: str) -> Refusal:
        made = super().__new__(cls, message)
        made.reason = reason
        return made


@dataclass(frozen=True, slots=True)
class ScopeLayer:
    """A copper layer of the board: the name the document gives it, its neutral name, whether it is an
    internal signal layer, and its Altium layer id (1 top, 32 bottom)."""

    document_name: str
    name: str
    inner_signal: bool = False
    altium_id: int = 0


@dataclass(frozen=True, slots=True)
class ScopePair:
    """A differential pair of the document (``DifferentialPairs6``): its name and its two nets."""

    name: str
    positive: str
    negative: str


@dataclass(frozen=True, slots=True)
class ScopeClass:
    """A class of ``Classes6``: its kind (0 net, 1 component, 6 differential pair), name and members;
    ``superclass`` holds every object of its kind."""

    kind: int
    name: str
    members: tuple[str, ...] = ()
    superclass: bool = False


@dataclass(frozen=True, slots=True)
class ScopePad:
    """A pad of a component: its centre in file units, and whether it is a surface-mount pad (on one
    layer, not Multi-Layer)."""

    x: int
    y: int
    smd: bool


@dataclass(frozen=True, slots=True)
class ScopeComponent:
    """A component: its designator (the reference the import gives it), its footprint, its
    ``COMPONENTKIND`` text (``None`` without the key), its rotation in degrees and its pads."""

    designator: str
    footprint: str
    kind: str | None = None
    rotation: float = 0.0
    pads: tuple[ScopePad, ...] = ()


ParentKind = Literal["component", "polygon", "pair"]
"""The parent objects a rule may judge: components (Component Clearance, Fanout Control), the polygon of a
Polygon Connect Style record, differential pairs (Differential Pairs Routing)."""


@dataclass(frozen=True, slots=True)
class ScopeDocument:
    """What a scope's functions read from the document its record belongs to (change c0462). ``unit``: the
    unit of a number written without ``AsMils`` or ``AsMM``, when the document gives one; without it only
    the number 0 compares with a length. A field left ``None`` is not known: a function that reads it is
    refused (``document``).

    ``parents``: the parent objects the rule of the scope judges. A function that returns parent objects and
    not their children (``IsComponent``, ``IsNamedPolygon``, ``InDifferentialPairClass`` …) maps only for a
    rule that judges them; for any other rule it is refused (``object-kind``), because the reference does
    not say which primitives such a rule then governs."""

    unit: Literal["mil", "mm"] | None = None
    layers: tuple[ScopeLayer, ...] | None = None
    blind_vias: bool | None = None
    """Whether a via of the document spans less than the whole stack."""
    nets: tuple[str, ...] | None = None
    pairs: tuple[ScopePair, ...] | None = None
    classes: tuple[ScopeClass, ...] | None = None
    components: tuple[ScopeComponent, ...] | None = None
    polygons: tuple[str, ...] | None = None
    """The names of the document's polygons."""
    rooms: tuple[str, ...] | None = None
    """The names of the document's rooms (``read.rooms``, task 2.3)."""
    smd_plated: bool | None = None
    """``True`` when every pad without a hole is plated, ``False`` when none is (or there is none),
    ``None`` when they differ."""
    smd_holes: bool = False
    """Whether a pad on one layer holds a hole size above 0."""
    parents: frozenset[ParentKind] = frozenset()


PARENTS: Mapping[str, frozenset[ParentKind]] = {
    "ComponentClearance": frozenset({"component"}),
    "FanoutControl": frozenset({"component"}),
    "PolygonConnect": frozenset({"polygon"}),
    "DiffPairsRouting": frozenset({"pair"}),
}
"""A rule kind → the parent objects its scopes select (``ScopeDocument.parents``): Component Clearance and
Fanout Control judge components, Polygon Connect Style a polygon, Differential Pairs Routing a pair
(S-1832, S-2212)."""


def for_kind(document: ScopeDocument | None, kind: str | None) -> ScopeDocument | None:
    """``document`` with the parent objects of rule kind ``kind`` (``PARENTS``)."""
    if document is None:
        return None
    return replace(document, parents=PARENTS.get(kind or "", frozenset()))


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


@dataclass(frozen=True, slots=True)
class _Plated:
    """The boolean field ``PadIsPlated``: the pads it is true for and the pads it is false for; an object
    that is no pad is neither."""

    plated: Selector
    unplated: Selector


_Value = _Set | _Number | _String | _Truth | _Field | _Plated


def _kind(value: _Value) -> str:
    if isinstance(value, _Set):
        return "a set of objects"
    if isinstance(value, _Number):
        return "a number"
    if isinstance(value, _Field):
        return f"the number {value.name}"
    if isinstance(value, _Truth):
        return "a boolean string"
    if isinstance(value, _Plated):
        return "the boolean field PadIsPlated"
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
        if truth is not None and isinstance(other, _Plated) and op in ("=", "<>"):
            assert isinstance(truth, _Truth)
            chosen = other.plated if truth.value else other.unplated
            return _Set(chosen if op == "=" else _not(chosen), grouped=True)
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


# --- functions that read the document (change c0462, S-2212) ------------------------------------------

NOTHING = Selector("not", items=(Selector("all"),))
"""The selector of no object: an expansion that matches no object of the document."""
MULTI_LAYER = Selector(
    "or", items=(Selector("item_kind", "via"), Selector("pad_type", "th"), Selector("pad_type", "npth"))
)
"""The objects on Altium's Multi-Layer: vias and pads with a hole (``INFERRED``, ``H-A-RD-PRJ-SCOPE-MULTI``).
An ``On…`` layer check reads an object's Layer property, so it does not return them (S-2212, OnOutside);
``ExistsOnLayer`` does."""
TOP_ID, BOTTOM_ID = 1, 32


def _need(parser: _Parser, name: str, what: str) -> ScopeDocument:
    document = parser.document
    if document is None or getattr(document, what) is None:
        raise _Refused(
            f"{name} reads the document's {what.replace('_', ' ')}, which is not given", "document"
        )
    return document


def _parent(parser: _Parser, name: str, kind: ParentKind) -> None:
    document = parser.document
    if document is None or kind not in document.parents:
        raise _Refused(
            f"{name} returns {kind} objects and not their children (S-2212): it maps only for a rule that "
            f"judges {kind} objects",
            "object-kind",
        )


def _no_arguments(parser: _Parser, name: str) -> None:
    following = parser.peek()
    if following is not None and following.kind == "open":
        raise _Refused(f"{name} takes no argument", "syntax")


def _like(text: str, pattern: str) -> bool:
    """Whether ``text`` matches the Altium pattern ``pattern``: ``*`` and ``?`` are wildcards, and letter
    case does not count (``H-A-RD-PRJ-SCOPE-CASE``)."""
    return fnmatch.fnmatchcase(text.casefold(), _escaped(pattern, True).casefold())


def _any_of(leaves: Sequence[Selector]) -> Selector:
    unique = list(dict.fromkeys(leaves))
    if not unique:
        return NOTHING
    return unique[0] if len(unique) == 1 else Selector("or", items=tuple(unique))


def _layer(layer: ScopeLayer) -> Selector:
    return Selector("layer", _escaped(layer.name, False))


def _on(layers: Sequence[ScopeLayer]) -> Selector:
    """The objects whose Layer property is one of ``layers``: never an object on Multi-Layer."""
    if not layers:
        return NOTHING
    return Selector("and", items=(_any_of([_layer(layer) for layer in layers]), _not(MULTI_LAYER)))


def _layer_function(parser: _Parser, name: str) -> _Value:
    """``OnTopLayer``, ``OnBottomLayer``, ``OnMid``, ``OnOutside`` and ``OnMultiLayer`` (S-2212, "Layer
    Checks")."""
    _no_arguments(parser, name)
    if name == "OnMultiLayer":
        return _Set(MULTI_LAYER, grouped=True)
    layers = _need(parser, name, "layers").layers or ()
    if name == "OnMid":
        return _Set(_on([layer for layer in layers if layer.inner_signal]), grouped=True)
    wanted = {"OnTopLayer": (TOP_ID,), "OnBottomLayer": (BOTTOM_ID,), "OnOutside": (TOP_ID, BOTTOM_ID)}[name]
    found = [layer for layer in layers if layer.altium_id in wanted]
    if len(found) != len(wanted):
        raise _Refused(f"{name}: the board's copper layers hold no layer of id {wanted}", "undefined")
    return _Set(_on(found), grouped=True)


def _exists_on_layer(parser: _Parser, name: str) -> _Value:
    """``ExistsOnLayer('L')`` and ``OnLayer('L')``: the objects on copper layer ``L``, and the objects on
    Multi-Layer, which exist on every copper layer when every via spans the whole stack (S-2212)."""
    (wanted,) = parser.strings(name, many=False)
    document = _need(parser, name, "layers")
    found = [layer for layer in document.layers or () if layer.document_name == wanted]
    if len(found) != 1:
        raise _Refused(
            f"{name} names {wanted!r}, which is no copper layer of the board ({len(found)} match): the "
            "grammar reads copper layers only",
            "undefined",
        )
    if document.blind_vias is not False:
        raise _Refused(
            f"{name}: a via of the document spans part of the stack, and the neutral subject holds no span",
            "via-span",
        )
    return _Set(Selector("or", items=(_layer(found[0]), MULTI_LAYER)), grouped=True)


def _drill_pair(parser: _Parser, name: str) -> _Value:
    """``InDrillLayerPair('A - B')``: the vias whose drill pair is ``A - B`` (S-2212). Exact when every via
    spans the whole stack: the vias for the pair of the top and bottom layers, else none."""
    (wanted,) = parser.strings(name, many=False)
    document = _need(parser, name, "layers")
    if document.blind_vias is not False:
        raise _Refused(f"{name}: a via of the document spans part of the stack", "drill-pair")
    layers = {layer.altium_id: layer.document_name for layer in document.layers or ()}
    if TOP_ID not in layers or BOTTOM_ID not in layers:
        raise _Refused(f"{name}: the board's top or bottom copper layer is not known", "undefined")
    whole = f"{layers[TOP_ID]} - {layers[BOTTOM_ID]}"
    return _Set(
        Selector("item_kind", "via") if wanted.casefold() == whole.casefold() else NOTHING, grouped=True
    )


def _nets_of(pairs: Sequence[ScopePair]) -> Selector:
    """The objects of the nets of ``pairs``: a pair's objects are its two nets' (S-2212)."""
    return _any_of(
        [Selector("net", _escaped(net, False)) for pair in pairs for net in (pair.positive, pair.negative)]
    )


def _pair_function(parser: _Parser, name: str) -> _Value:
    """``InDifferentialPair('P', …)``, ``InAnyDifferentialPair``, ``IsDifferentialPair`` and
    ``InDifferentialPairClass('C')`` (S-2212, "Membership Checks" and "Attribute Checks")."""
    if name == "InDifferentialPair":
        patterns = parser.strings(name, many=True)
        pairs = _need(parser, name, "pairs").pairs or ()
        return _Set(_nets_of([p for p in pairs if any(_like(p.name, pattern) for pattern in patterns)]), True)
    if name == "InAnyDifferentialPair":
        _no_arguments(parser, name)
        return _Set(_nets_of(_need(parser, name, "pairs").pairs or ()), grouped=True)
    if name == "IsDifferentialPair":
        _no_arguments(parser, name)
        _parent(parser, name, "pair")
        return _Set(_nets_of(_need(parser, name, "pairs").pairs or ()), grouped=True)
    (wanted,) = parser.strings(name, many=False)
    _parent(parser, name, "pair")
    document = _need(parser, name, "classes")
    pairs = _need(parser, name, "pairs").pairs or ()
    found = _class(document, name, 6, wanted)
    if found.superclass:
        return _Set(_nets_of(pairs), grouped=True)
    members = {member.casefold() for member in found.members}
    return _Set(_nets_of([pair for pair in pairs if pair.name.casefold() in members]), grouped=True)


def _class(document: ScopeDocument, name: str, kind: int, wanted: str) -> ScopeClass:
    found = [c for c in document.classes or () if c.kind == kind and c.name.casefold() == wanted.casefold()]
    if len(found) != 1:
        raise _Refused(
            f"{name} names the class {wanted!r}, which the document defines {len(found)} times", "undefined"
        )
    return found[0]


def _refs(document: ScopeDocument, name: str, chosen: Sequence[ScopeComponent]) -> Selector:
    """The ``ref`` leaves of the components ``chosen``; refused when a designator also names a component
    that is not chosen, or a chosen component has none."""
    picked = {id(component) for component in chosen}
    leaves: list[Selector] = []
    for component in chosen:
        if not component.designator:
            raise _Refused(f"{name} selects a component without a designator", "designator")
        others = [
            c for c in document.components or ()
            if c.designator.casefold() == component.designator.casefold() and id(c) not in picked
        ]  # fmt: skip
        if others:
            raise _Refused(
                f"{name}: the designator {component.designator!r} also names a component it does not select",
                "designator",
            )
        leaves.append(Selector("ref", _escaped(component.designator, False)))
    return _any_of(leaves)


def _component_function(parser: _Parser, name: str) -> _Value:
    """``HasFootprint('F')`` (components and their children), and the checks that return components only:
    ``IsComponent``, ``IsNetTieComponent``, ``InComponentClass('C')``, ``IsBGA``, ``IsSOIC``, ``IsLCC``
    (S-2212)."""
    if name == "HasFootprint":
        (pattern,) = parser.strings(name, many=False)
        document = _need(parser, name, "components")
        chosen = [c for c in document.components or () if _like(c.footprint, pattern)]
        return _Set(_refs(document, name, chosen), grouped=True)
    wanted = ""
    if name == "InComponentClass":
        (wanted,) = parser.strings(name, many=False)
    else:
        _no_arguments(parser, name)
    _parent(parser, name, "component")
    document = _need(parser, name, "components")
    every = document.components or ()
    if name == "IsComponent":
        chosen = list(every)
    elif name == "IsNetTieComponent":
        unknown = sorted({c.kind for c in every if c.kind not in (None, "0", NET_TIE_KIND)}, key=str)
        if unknown:
            raise _Refused(
                f"{name}: the document holds the component kinds {', '.join(map(str, unknown))}, of which no "
                "permitted source says whether one is Net Tie (In BOM)",
                "undefined",
            )
        chosen = [c for c in every if c.kind == NET_TIE_KIND]
    elif name == "InComponentClass":
        found = _class(_need(parser, name, "classes"), name, 1, wanted)
        members = {member.casefold() for member in found.members}
        chosen = list(every) if found.superclass else [c for c in every if c.designator.casefold() in members]
    else:
        from fenolite.backends.altium.read.packages import PACKAGE_CHECKS, PackageUndecided

        try:
            chosen = [c for c in every if PACKAGE_CHECKS[name](c)]
        except PackageUndecided as undecided:
            raise _Refused(f"{name}: {undecided}", "package-check") from None
    return _Set(_refs(document, name, chosen), grouped=True)


def _pin_count(parser: _Parser, name: str) -> _Value:
    """``CompPinCount``: the number of a component's pads; a comparison returns the components and their
    children (S-2212)."""
    _no_arguments(parser, name)
    document = _need(parser, name, "components")

    def leaf(lo: int | None, hi: int | None) -> Selector:
        chosen = [
            c for c in document.components or ()
            if (lo is None or len(c.pads) >= lo) and (hi is None or len(c.pads) <= hi)
        ]  # fmt: skip
        return _refs(document, name, chosen)

    return _Field(name, leaf, length=False)


def _hole_field(parser: _Parser, name: str) -> _Value:
    """``HoleDiameter`` and ``HoleSize``: the pads and vias whose hole size complies (S-2212, "Fields")."""
    _no_arguments(parser, name)
    document = parser.document
    if document is not None and document.smd_holes:
        raise _Refused(
            f"{name}: a pad on one layer holds a hole size, which the neutral subject does not", "document"
        )

    def leaf(lo: int | None, hi: int | None) -> Selector:
        if lo is None or lo <= 0:
            raise _Refused(
                f"{name}: the interval holds 0, the hole size of a pad without a hole, which the neutral "
                "hole leaf does not hold",
                "hole-zero",
            )
        return Selector("hole", hole_value(lo, hi))

    return _Field(name, leaf)


def _plated(parser: _Parser, name: str) -> _Value:
    """``PadIsPlated``: the pads whose Plated property is set, compared with ``True`` or ``False``
    (S-2212, "Fields"). A pad with a hole is plated by its type; a pad without one by the document."""
    _no_arguments(parser, name)
    document = parser.document
    if document is None:
        raise _Refused(f"{name} reads the document's pads, which are not given", "document")
    if document.smd_plated is None:
        raise _Refused(
            f"{name}: the document's pads without a hole are not all plated or all unplated", "pad-plated"
        )
    th, smd, npth = (Selector("pad_type", kind) for kind in ("th", "smd", "npth"))
    plated = Selector("or", items=(th, smd)) if document.smd_plated else th
    unplated = npth if document.smd_plated else Selector("or", items=(npth, smd))
    return _Plated(plated, unplated)


def _polygon_function(parser: _Parser, name: str) -> _Value:
    """``InNamedPolygon('P')`` (the pour's child primitives and the pour) and ``IsNamedPolygon('P')`` (the
    pour only): the copper of a zone is its children (S-2212)."""
    (wanted,) = parser.strings(name, many=False)
    if name == "IsNamedPolygon":
        _parent(parser, name, "polygon")
    names = _need(parser, name, "polygons").polygons or ()
    found = sorted({n for n in names if n.casefold() == wanted.casefold()})
    if not found:
        raise _Refused(f"{name} names the polygon {wanted!r}, which the document does not hold", "undefined")
    return _Set(_any_of([Selector("zone", _escaped(n, False)) for n in found]), grouped=True)


def _room_function(parser: _Parser, name: str) -> _Value:
    """``WithinRoom('R', …)``: refused. A room the document does not hold is ``undefined``. One it holds
    is ``room-membership``: a pad or a via is in a room by its centre, any other object only when it lies
    wholly within it (S-2212), while the neutral ``area`` leaf selects an object whose copper touches the
    area (``H-K-AREA-COND``), so no leaf selects the objects of a room (task 2.3; the exact mapping needs a
    neutral room membership)."""
    wanted = parser.strings(name, many=True)
    held = {n.casefold() for n in _need(parser, name, "rooms").rooms or ()}
    missing = [w for w in wanted if w.casefold() not in held]
    if missing:
        raise _Refused(f"{name} names the room {missing[0]!r}, which the document does not hold", "undefined")
    raise _Refused(
        f"{name} names the room {wanted[0]!r}: a pad or a via is in a room by its centre and any other "
        "object only wholly within it, and no neutral leaf selects that way",
        "room-membership",
    )


def _refuse(reason: RefusalReason, why: str) -> FunctionHandler:
    def handler(parser: _Parser, name: str) -> _Value:
        raise _Refused(f"{name}: {why}", reason)

    return handler


FUNCTIONS: dict[str, FunctionHandler] = {
    "AsMils": _unit_function,
    "AsMM": _unit_function,
    **dict.fromkeys(("OnTopLayer", "OnBottomLayer", "OnMid", "OnOutside", "OnMultiLayer"), _layer_function),
    "ExistsOnLayer": _exists_on_layer,
    "OnLayer": _exists_on_layer,
    "InDrillLayerPair": _drill_pair,
    **dict.fromkeys(
        ("InDifferentialPair", "InAnyDifferentialPair", "IsDifferentialPair", "InDifferentialPairClass"),
        _pair_function,
    ),
    **dict.fromkeys(
        ("HasFootprint", "IsComponent", "IsNetTieComponent", "InComponentClass", "IsBGA", "IsSOIC", "IsLCC"),
        _component_function,
    ),
    "CompPinCount": _pin_count,
    "HoleDiameter": _hole_field,
    "HoleSize": _hole_field,
    "PadIsPlated": _plated,
    "InNamedPolygon": _polygon_function,
    "IsNamedPolygon": _polygon_function,
    "InxSignal": _refuse("xsignal", "an xSignal runs between two pads, which no neutral leaf holds"),
    "InxSignalClass": _refuse("xsignal", "an xSignal runs between two pads, which no neutral leaf holds"),
    "InNamedUnion": _refuse("union", "the reader does not read the document's unions"),
    "WithinRoom": _room_function,
}
"""The functions of the grammar beyond the membership checks, by name (change c0462)."""
EXPANDED_FUNCTIONS = frozenset(FUNCTIONS) - {"AsMils", "AsMM", "OnMultiLayer"}
"""The functions whose selector is a list read from the document: frozen at import time, so
``fenolite.dsl`` prints a rule that uses one with a comment naming it (design D2 of change c0462)."""


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
    "EXPANDED_FUNCTIONS",
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
    "ScopeClass",
    "ScopeComponent",
    "ScopeLayer",
    "ScopePad",
    "ScopePair",
    "NOTHING",
    "MULTI_LAYER",
    "PARENTS",
    "for_kind",
    "parse_layer_scope",
    "parse_scope",
]
