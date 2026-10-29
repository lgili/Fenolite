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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from fenolite.backends.altium.adapter.units import pcb_length, text_length
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.model.board import Pad
from fenolite.model.rules import Selector

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-PADMASK",))
KIND = "pad-margin"
"""The report kind of a pad whose margin the conversion cannot tell for sure."""
MODE_NONE, MODE_RULE, MODE_MANUAL = 0, 1, 2
MASK_RULE, PASTE_RULE = "SolderMaskExpansion", "PasteMaskExpansion"
SCOPE_ALL = "All"
SCOPED_REASON = (
    "a rule of another scope may govern the pad; its scope is not evaluated, the rule of scope All is used"
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
    if mode == MODE_MANUAL:
        return (pcb_length(units) or None), None
    if mode == MODE_NONE:
        return None, None
    return None, UNKNOWN_REASON


def open_pad(pad: Pad, rules: RuleExpansions) -> tuple[Pad, tuple[str, ...]]:
    """``pad`` with its mask and paste layers by its kind and its margins, and the reasons of its
    ``pad-margin`` rows. A surface pad off the outer copper layers gains nothing."""
    layers = list(pad.layers)
    if pad.kind == "smd":
        extra: Sequence[str] = next((_SIDES[name] for name in pad.layers if name in _SIDES), ())
    else:
        extra = _BOTH_MASKS
    layers += [name for name in extra if name not in layers]
    pairs = _pairs(pad)
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
    "MASK_RULE",
    "PASTE_RULE",
    "RuleExpansion",
    "RuleExpansions",
    "open_pad",
    "rule_expansion",
]
