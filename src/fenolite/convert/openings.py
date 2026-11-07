# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Mask and paste openings of pads imported from Altium, for a KiCad target (capability design-conversion,
"Mask and paste of imported pads"; change c0223; facts: ``docs/formats/altium/import.md``, "Pads and
padstacks", and ``docs/formats/altium/pcb-records.md``, "Pad").

The Altium reader keeps each pad's paste and solder-mask mode and expansion in its ``altium`` bag (``paste``
and ``mask``, ``<mode>,<expansion in units>``, only when the mode is not "from the rules"). The modes are
0 none, 1 from the rules and 2 manual. A rule expansion comes from the document's ``PasteMaskExpansion``
and ``SolderMaskExpansion`` records. Nothing is read from a file here: the caller gives the rule records.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import itertools
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fenolite.backends.altium.adapter.units import pcb_length, text_length
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.model.board import Pad
from fenolite.model.rules import PAD_TYPE_OF, RuleSubject, Selector

if TYPE_CHECKING:
    from fenolite.backends.altium.read.scope import ScopeDocument

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-PADMASK",))
KIND = "pad-margin"
"""The report kind of a pad whose margin the conversion cannot tell for sure."""
MODE_NONE, MODE_RULE, MODE_MANUAL = 0, 1, 2
MASK_RULE, PASTE_RULE = "SolderMaskExpansion", "PasteMaskExpansion"
SCOPE_ALL = "All"
SCOPED_REASON = (
    "a rule whose scope Fenolite cannot judge for the pad comes first; the next rule that selects the pad is "
    "used"
)
UNKNOWN_REASON = "the pad's expansion mode is not one of none, rules and manual: no margin"
_SIDES = {"F.Cu": ("F.Paste", "F.Mask"), "B.Cu": ("B.Paste", "B.Mask")}
_BOTH_MASKS = ("F.Mask", "B.Mask")


@dataclass(frozen=True, slots=True)
class RuleExpansion:
    """The expansion that the rules give a pad of one kind (mask or paste): ``value`` from the enabled rule
    of scope ``All`` that comes first (``None`` without one), and whether an enabled rule of another scope
    comes before it (``scoped``)."""

    value: Nm | None = None
    scoped: bool = False


@dataclass(frozen=True, slots=True)
class RuleExpansions:
    mask: RuleExpansion = RuleExpansion()
    paste: RuleExpansion = RuleExpansion()


def _selects_no_pad(selector: Selector) -> bool:
    """Whether ``selector`` is false for every pad: an object-type check of another kind (``IsVia``,
    ``IsTrack``), a conjunction with such a term, or a disjunction of such terms only."""
    if selector.op == "item_kind":
        return selector.value != "pad"
    if selector.op == "and":
        return any(_selects_no_pad(item) for item in selector.items)
    if selector.op == "or":
        return all(_selects_no_pad(item) for item in selector.items)
    return False


def _governs_no_pad(scope: str) -> bool:
    """Whether a rule of scope ``scope`` cannot govern a pad: the scope is inside the closed grammar of
    ``docs/formats/altium/rule-file.md`` and selects no pad (``IsVia`` before the ``All`` rule of a mask
    expansion is the common case)."""
    from fenolite.backends.altium.read.scope import parse_scope

    selector = parse_scope(scope)
    return not isinstance(selector, str) and _selects_no_pad(selector)


def rule_expansion(records: Iterable[Mapping[str, str]], kind: str) -> RuleExpansion:
    """The ``RuleExpansion`` of the rule records (``RULEKIND``, ``ENABLED``, ``PRIORITY``,
    ``SCOPE1EXPRESSION``, ``EXPANSION``) of ``kind``, ``MASK_RULE`` or ``PASTE_RULE``. A rule whose scope
    selects no pad (``IsVia``) is left out: it cannot govern a pad, so it makes no ``pad-margin`` row."""
    rows: list[tuple[int, str, Nm | None]] = []
    for record in records:
        if record.get("RULEKIND") != kind or record.get("ENABLED", "TRUE").upper() != "TRUE":
            continue
        if _governs_no_pad(record.get("SCOPE1EXPRESSION", "")):
            continue
        try:
            priority = int(record.get("PRIORITY", "0"))
        except ValueError:
            priority = 0
        found = text_length(record.get("EXPANSION"))
        scope = record.get("SCOPE1EXPRESSION", "").strip()
        rows.append((priority, scope, None if found is None else found[0]))
    rows.sort(key=lambda row: row[0])
    for index, (_, scope, value) in enumerate(rows):
        if scope == SCOPE_ALL:
            return RuleExpansion(value, scoped=index > 0)
    return RuleExpansion(None, scoped=bool(rows))


@dataclass(frozen=True, slots=True)
class ViaRule:
    """The solder-mask rule that governs the vias (change c0445): ``value`` and ``from_hole``
    (``SOLDERMASKFROMHOLE``: the expansion is measured from the edge of the hole) of the first enabled
    ``SolderMaskExpansion`` record, by priority, of scope ``IsVia`` or ``All`` (``None`` without one), and
    whether an enabled record of another scope that may select vias comes before it (``scoped``)."""

    value: Nm | None = None
    from_hole: bool = False
    scoped: bool = False


VIA_MODE_RULE, VIA_MODE_MANUAL = 1, 2
"""The solder-mask cache states of a via record at 66 (``pcb-copper.md``, "Via"): its expansion from the
rules, and its own expansion (a tented side, change c0166). State 0 is read as the rules."""
VIA_SCOPES = ("All", "IsVia")


def _selects_no_via(selector: Selector) -> bool:
    if selector.op == "item_kind":
        return selector.value != "via"
    if selector.op == "and":
        return any(_selects_no_via(item) for item in selector.items)
    if selector.op == "or":
        return all(_selects_no_via(item) for item in selector.items)
    return False


def via_rule(records: Iterable[Mapping[str, str]]) -> ViaRule:
    """The ``ViaRule`` of the rule records (``RULEKIND``, ``ENABLED``, ``PRIORITY``, ``SCOPE1EXPRESSION``,
    ``EXPANSION``, ``SOLDERMASKFROMHOLE``). A record whose scope selects no via (``IsPad``) is left out."""
    from fenolite.backends.altium.read.scope import parse_scope

    rows: list[tuple[int, Mapping[str, str]]] = []
    for record in records:
        if record.get("RULEKIND") != MASK_RULE or record.get("ENABLED", "TRUE").upper() != "TRUE":
            continue
        selector = parse_scope(record.get("SCOPE1EXPRESSION", ""))
        if not isinstance(selector, str) and _selects_no_via(selector):
            continue
        try:
            priority = int(record.get("PRIORITY", "0"))
        except ValueError:
            priority = 0
        rows.append((priority, record))
    rows.sort(key=lambda row: row[0])
    for index, (_, record) in enumerate(rows):
        if record.get("SCOPE1EXPRESSION", "").strip() in VIA_SCOPES:
            found = text_length(record.get("EXPANSION"))
            return ViaRule(
                None if found is None else found[0],
                record.get("SOLDERMASKFROMHOLE", "FALSE").upper() == "TRUE",
                scoped=index > 0,
            )
    return ViaRule(None, scoped=bool(rows))


def via_margin(diameter: Nm, drill: Nm, state: int, expansion: Nm, rule: ViaRule) -> Nm | None:
    """The growth of a via's mask opening beyond its copper (change c0445): its own ``expansion`` in the
    manual state, else the rule's, measured from the hole when the rule says so; ``None`` without a rule."""
    if state == VIA_MODE_MANUAL:
        return expansion
    if rule.value is None:
        return None
    return (drill - diameter) // 2 + rule.value if rule.from_hole else rule.value


@dataclass(frozen=True, slots=True)
class ExpansionRule:
    """One enabled expansion record (change c0462, design D6): its priority (1 governs), its scope as
    written, its selector (``None``: a scope ``read.scope.parse_scope`` does not read), its expansion and,
    for a solder-mask record, whether the expansion is measured from the hole (``SOLDERMASKFROMHOLE``)."""

    priority: int
    scope: str
    selector: Selector | None
    value: Nm | None
    from_hole: bool = False


def expansion_rules(
    records: Iterable[Mapping[str, str]], kind: str, document: ScopeDocument | None = None
) -> tuple[ExpansionRule, ...]:
    """The enabled records of ``kind`` (``MASK_RULE`` or ``PASTE_RULE``) as ``ExpansionRule`` in the order of
    Altium's priority (the first governs), each scope read with the records' ``document``."""
    from fenolite.backends.altium.read.scope import parse_scope

    rows: list[ExpansionRule] = []
    for record in records:
        if record.get("RULEKIND") != kind or record.get("ENABLED", "TRUE").upper() != "TRUE":
            continue
        try:
            priority = int(record.get("PRIORITY", "0"))
        except ValueError:
            priority = 0
        scope = record.get("SCOPE1EXPRESSION", "").strip()
        selector = parse_scope(scope, document=document)
        found = text_length(record.get("EXPANSION"))
        rows.append(
            ExpansionRule(
                priority,
                scope,
                selector if isinstance(selector, Selector) else None,
                None if found is None else found[0],
                record.get("SOLDERMASKFROMHOLE", "FALSE").upper() == "TRUE",
            )
        )
    return tuple(sorted(rows, key=lambda row: row.priority))


_NONE = Selector("not", items=(Selector("all"),))


def _unknown(selector: Selector, subject: RuleSubject) -> set[Selector]:
    """The leaves of ``selector`` the conversion cannot judge for ``subject``: a room (``area``: the
    conversion places no object in a room), and a layer while the object spans the layers."""
    if selector.op == "area" or (selector.op == "layer" and subject.layer is None):
        return {selector}
    found: set[Selector] = set()
    for item in selector.items:
        found |= _unknown(item, subject)
    return found


MAX_UNKNOWN = 8
"""The most unknown leaves whose every truth value is tried (``_decided``); a scope with more is unread."""


def _assigned(selector: Selector, values: Mapping[Selector, bool]) -> Selector:
    if selector in values:
        return Selector("all") if values[selector] else _NONE
    if selector.items:
        return dataclasses.replace(selector, items=tuple(_assigned(item, values) for item in selector.items))
    return selector


def _decided(selector: Selector, subject: RuleSubject) -> bool | None:
    """Whether ``selector`` selects ``subject``, ``None`` when it depends on a leaf the conversion cannot
    judge (``_unknown``): every truth value of those leaves is tried, and one answer for all decides it.
    ``OnLayer('Bottom Layer')`` holds the vias and the pads with a hole by its own terms, so it decides them
    without their layer."""
    from fenolite.model.selectors import selector_matches

    unknown = sorted(_unknown(selector, subject), key=lambda leaf: (leaf.op, leaf.value))
    if len(unknown) > MAX_UNKNOWN:
        return None
    found = {
        selector_matches(_assigned(selector, dict(zip(unknown, bits, strict=True))), subject)
        for bits in itertools.product((False, True), repeat=len(unknown))
    }
    return found.pop() if len(found) == 1 else None


@dataclass(frozen=True, slots=True)
class Governed:
    """The expansion record that governs one pad or via (``governing_expansion``): its value and
    ``from_hole`` (``None``: no record selects it), and ``unread``, the scope of a record before it that
    Fenolite cannot judge for the object, ``""`` when there is none."""

    value: Nm | None = None
    from_hole: bool = False
    unread: str = ""


def _with_classes(selector: Selector, classes: Collection[str]) -> Selector:
    """``selector`` with each ``netclass`` leaf decided by ``classes``, the names (case-folded) of every
    net class that holds the subject's net: an Altium net may be in several classes, the neutral subject
    names one."""
    if selector.op == "netclass":
        wanted = selector.value.casefold()
        return Selector("all") if any(fnmatch.fnmatchcase(name, wanted) for name in classes) else _NONE
    if selector.items:
        return dataclasses.replace(
            selector, items=tuple(_with_classes(item, classes) for item in selector.items)
        )
    return selector


def governing_expansion(
    rules: Sequence[ExpansionRule], subject: RuleSubject, classes: Collection[str] | None = None
) -> Governed:
    """The first record of ``rules`` whose scope selects ``subject``, names compared without case, as the
    clearance rules compare them. A record whose scope is outside the grammar, or that selects the object or
    not by a leaf the conversion cannot judge (a room, or a layer of a through-hole pad or a via, which span
    the layers; ``_decided``), may govern it: its scope is kept in ``unread`` and the next record that
    selects the object gives the value. ``classes`` (case-folded) are the net classes of the document that
    hold the subject's net; without them a ``netclass`` leaf compares ``subject.netclass``."""
    unread = ""
    for rule in rules:
        selector = rule.selector
        if selector is not None and classes is not None:
            selector = _with_classes(selector, classes)
        selects = None if selector is None else _decided(selector, subject)
        if selects is None:
            unread = unread or rule.scope
        elif selects:
            return Governed(rule.value, rule.from_hole, unread)
    return Governed(None, False, unread)


def pad_subject(
    pad: Pad,
    copper: Collection[str],
    net: str | None = None,
    netclass: str | None = None,
    ref: str | None = None,
    diff_pair: str | None = None,
) -> RuleSubject:
    """The subject of ``pad`` for an expansion record: a surface pad on its one layer of ``copper`` (the
    copper layer names of its board), a pad with a hole on none, with its finished hole."""
    layers = [name for name in pad.layers if name in copper]
    surface = pad.kind == "smd"
    return RuleSubject(
        "pad",
        net=net,
        netclass=netclass,
        ref=ref,
        layer=layers[0] if surface and len(layers) == 1 else None,
        diff_pair=diff_pair,
        hole=None if surface or not pad.drill else pad.drill,
        pad_type=PAD_TYPE_OF.get(pad.kind),
    )


def pad_expansions(
    mask: Sequence[ExpansionRule],
    paste: Sequence[ExpansionRule],
    subject: RuleSubject,
    classes: Collection[str] | None = None,
) -> RuleExpansions:
    """The ``RuleExpansions`` of one pad: each the value of the record that governs it, ``scoped`` when a
    record Fenolite cannot judge for it comes first."""
    found = [governing_expansion(rules, subject, classes) for rules in (mask, paste)]
    return RuleExpansions(*(RuleExpansion(one.value, scoped=bool(one.unread)) for one in found))


def via_governing(
    mask: Sequence[ExpansionRule], subject: RuleSubject, classes: Collection[str] | None = None
) -> ViaRule:
    """The ``ViaRule`` of one via: the solder-mask record that governs it (``governing_expansion``)."""
    found = governing_expansion(mask, subject, classes)
    return ViaRule(found.value, found.from_hole, scoped=bool(found.unread))


def _pairs(pad: Pad) -> dict[str, str]:
    bag = pad.ext.get("altium")
    return dict(bag.payload) if bag is not None else {}


def _margin(text: str | None, rule: RuleExpansion) -> tuple[Nm | None, str | None]:
    """The margin of one opening and the reason of a ``pad-margin`` row (``None``: none)."""
    if text is None:  # the reader leaves the mode out when it is "from the rules"
        if rule.scoped:
            return (rule.value or None), SCOPED_REASON
        return (rule.value or None), None
    mode_text, _, expansion = text.partition(",")
    try:
        mode, units = int(mode_text), int(expansion or "0")
    except ValueError:
        return None, UNKNOWN_REASON
    if mode == MODE_MANUAL:  # a manual 0 is an override too (change c0440): it is written, not inherited
        return pcb_length(units), None
    if mode == MODE_NONE:
        return None, None
    return None, UNKNOWN_REASON


def source_pairs(pad: Pad) -> dict[str, str]:
    """The ``mask`` and ``paste`` entries of the Altium bag of a pad as read, for ``open_pad``: the
    conversion empties every bag before it opens the pads (change c0440)."""
    return {key: value for key, value in _pairs(pad).items() if key in ("mask", "paste")}


def open_pad(
    pad: Pad, rules: RuleExpansions, pairs: Mapping[str, str] | None = None
) -> tuple[Pad, tuple[str, ...]]:
    """``pad`` with its mask and paste layers by its kind and its margins, and the reasons of its
    ``pad-margin`` rows. A surface pad off the outer copper layers gains nothing. ``pairs`` are the pad's
    ``source_pairs`` when its own bag is already emptied (change c0440); ``None`` reads its bag."""
    layers = list(pad.layers)
    if pad.kind == "smd":
        extra: Sequence[str] = next((_SIDES[name] for name in pad.layers if name in _SIDES), ())
    else:
        extra = _BOTH_MASKS
    layers += [name for name in extra if name not in layers]
    pairs = _pairs(pad) if pairs is None else pairs
    mask, mask_why = _margin(pairs.get("mask"), rules.mask)
    reasons = [why for why in (mask_why,) if why]
    paste: Nm | None = None
    if any(name.endswith(".Paste") for name in layers):
        paste, paste_why = _margin(pairs.get("paste"), rules.paste)
        reasons += [why for why in (paste_why,) if why and why not in reasons]
    opened = dataclasses.replace(pad, layers=tuple(layers), mask_margin=mask, paste_margin=paste)
    return opened, tuple(reasons)


__all__ = [
    "EVIDENCE",
    "KIND",
    "ExpansionRule",
    "Governed",
    "expansion_rules",
    "governing_expansion",
    "pad_expansions",
    "pad_subject",
    "via_governing",
    "MASK_RULE",
    "PASTE_RULE",
    "RuleExpansion",
    "RuleExpansions",
    "ViaRule",
    "open_pad",
    "rule_expansion",
    "source_pairs",
    "via_margin",
    "via_rule",
]
