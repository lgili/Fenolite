# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fate of every rule record of an Altium board in a conversion to KiCad (capability design-conversion,
"Fate of every Altium rule record" and "Limits the KiCad rule cannot take"; change c0424).

Each record is written (KiCad holds it as it is), changed (KiCad holds it in another form, for a stated
reason), kept (KiCad cannot hold it: a declared format limit, and the model keeps the record for an Altium
write, ``adapter.rules.kept_indexes``), or lost (a malformed record only). ``lower_rules`` gives the neutral
rules theirs; ``record_fates`` gives one to each kept record that gave no neutral rule and to each Polygon
Connect Style record. The reasons are ``CHANGED``, ``KEPT`` and ``DISABLED``;
``docs/formats/altium/rule-file.md``, "Fates in a conversion", is the table.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet

if TYPE_CHECKING:
    from fenolite.backends.altium.read.rules import CopperLayers
    from fenolite.convert.altium_to_kicad import Ledger

KIND = "rule"
CHANGED: Mapping[str, str] = MappingProxyType(
    {
        "ComponentClearance": (
            "an Altium Component Clearance is written as a KiCad courtyard clearance: Altium measures the "
            "components' 3D bodies or boundaries, with a vertical gap that KiCad does not hold"
        ),
        "DiffPairsRouting": (
            "an Altium Differential Pairs Routing rule is written as KiCad's pair gap and uncoupled length: "
            "its per-layer widths are not written, and KiCad checks the gap that Altium routes to"
        ),
        "HoleToHoleClearance": (
            "an Altium Hole To Hole Clearance that allows stacked micro vias is written without the "
            "allowance, which KiCad does not hold"
        ),
    }
)
"""Altium kind → why its mapped rule is written in another form."""
STACKED_ONLY = frozenset({"HoleToHoleClearance"})
"""The kinds of ``CHANGED`` whose rule is changed only when it came from a kept record (stacked micro vias
allowed); with the key ``FALSE`` it is written as it is."""
MARGINS = (
    "the first enabled Altium {kind} rule of scope All is written as the margins of the pads that follow "
    "the rule"
)
SHORTS = (
    "an Altium Short Circuit rule of scope All that allows no short is KiCad's own check of shorting items, "
    "which KiCad always runs"
)
CONNECT = (
    "an Altium Polygon Connect Style rule is written as the connection, thermal gap and spoke width of each "
    "zone and pad it governs (change c0409)"
)
KEPT_PREFIX = "kept for an Altium write: "
KEPT: Mapping[str, str] = MappingProxyType(
    {
        "Height": "KiCad's rules have no component height constraint",
        "PlaneClearance": "the conversion gives an internal plane no zone: no KiCad item takes the clearance",
        "PlaneConnect": "the conversion gives an internal plane no zone: no KiCad item takes the connection",
        "MinimumSolderMaskSliver": "Fenolite's model and KiCad writer hold no minimum solder mask web",
        "NetAntennae": "KiCad's check of dangling tracks takes no tolerance",
        "SilkToSolderMaskClearance": "KiCad's one silkscreen clearance is not split by what it measures to",
        "SilkToBoardRegionClearance": "KiCad's rules have no silkscreen to board region clearance",
        "PolygonConnect": "the record cannot be read, so no zone or pad takes its style",
    }
)
"""Altium kind → why KiCad cannot hold it; another kind takes ``NO_RULE``."""
NO_RULE = "KiCad has no rule of this kind"
NOT_MAPPED = "the rule does not map onto a KiCad rule"
DISABLED = "the rule is disabled in the source; KiCad has no disabled rule that leaves the next one in force"
MALFORMED = "the rule record has no kind or no name"


def kept_reason(kind: str, *, enabled: bool = True, mapped_kind: bool = False) -> str:
    """The reason of a kept record of ``kind``: disabled, a kind of ``KEPT``, a mappable kind whose record
    does not map, or ``NO_RULE``."""
    if not enabled:
        return KEPT_PREFIX + DISABLED
    if kind in KEPT:
        return KEPT_PREFIX + KEPT[kind]
    return KEPT_PREFIX + (NOT_MAPPED if mapped_kind else NO_RULE)


def _bag(rule: Rule) -> dict[str, str]:
    held = rule.ext.get("altium")
    return {str(key): str(value) for key, value in held.payload} if held is not None else {}


def _problems(rules: RuleSet, rule: Rule, target: int) -> list[tuple[str, str]]:
    """The code and message of each warning and error of the KiCad lowering of ``rule`` alone: those it
    returns, those its refusal (``RulesLossError``) carries, or the message of another refusal."""
    from fenolite.backends.kicad.dru import RulesLossError
    from fenolite.backends.kicad.lowering import lower_rules as lower
    from fenolite.core.errors import FenoliteError

    try:
        found = lower(dataclasses.replace(rules, rules=(rule,)), target=target, allow_lossy=True).issues
    except RulesLossError as error:
        found = tuple(error.issues)
    except (FenoliteError, ValueError) as error:
        return [("", str(error))]
    return [(issue.code, issue.message) for issue in found if issue.severity in ("warning", "error")]


def lower_rules(rules: RuleSet, target: int, ledger: Ledger, source: RuleSet | None = None) -> RuleSet:
    """The neutral rules of ``rules`` that the KiCad lowering writes, each alone; the Altium bag of each is
    read from the rule of the same id in ``source`` (the rules as imported, before the target's model drops
    the bags), else from the rule itself. A rule refused only for a
    limit its KiCad constraint does not take is written without that limit and is ``changed``; the model of
    the source keeps the limit. A refused rule of a kept record is ``kept``; another refused rule is lost, as
    before."""
    from fenolite.backends.kicad.rulemap import LIMIT_ORDER, LIMITS

    bags = {rule.id: _bag(rule) for rule in source.rules} if source is not None else {}
    written: list[Rule] = []
    for rule in rules.rules:
        bag = bags.get(rule.id) or _bag(rule)
        kept = bag.get("kept_record") == "1"
        altium_kind = bag.get("rule_kind", "")
        problems = _problems(rules, rule, target)
        left_out: tuple[str, ...] = ()
        if problems and all(code == "rules.unsupported-limit" for code, _ in problems):
            left_out = tuple(
                name
                for name in LIMIT_ORDER
                if getattr(rule, name) is not None and name not in LIMITS[rule.kind]
            )
            if left_out:
                rule = dataclasses.replace(rule, **{name: None for name in left_out})
                problems = _problems(rules, rule, target)
        if problems:
            if kept:
                ledger.keep(KIND, rule.id, kept_reason(altium_kind, mapped_kind=True))
            else:
                reasons = "; ".join(message for _, message in problems)
                ledger.drop(KIND, rule.id, f"the target cannot write this imported rule: {reasons}")
            continue
        written.append(rule)
        if left_out:
            limits = " and ".join(f"'{name}'" for name in left_out)
            ledger.change(
                KIND,
                rule.id,
                f"KiCad's {rule.kind} constraint takes no {limits} limit: the others are written, and the "
                "model keeps it",
            )
        elif altium_kind in CHANGED and (altium_kind not in STACKED_ONLY or kept):
            ledger.change(KIND, rule.id, CHANGED[altium_kind])
    return dataclasses.replace(rules, rules=tuple(written))


def _pairs(design: Design, key: str) -> list[str]:
    board = design.board
    held = board.ext.get("altium") if board is not None else None
    return [str(text) for name, text in (held.payload if held is not None else ()) if name == key]


def record_fates(design: Design, ledger: Ledger) -> int:
    """The fates of the kept records of the source ``design`` that gave no neutral rule, and of its Polygon
        Connect Style records; the number of records given a fate, which the report adds to the source count
        of ``rule``. The first enabled Solder Mask or Paste Mask Expansion record of scope ``All`` is changed
        (the pads' margins, ``openings``), and so is a Short Circuit record of scope ``All`` that allows no
    short (KiCad's own check); a record without kind or name is lost; every other one is kept."""
    from fenolite.backends.altium.adapter.layers import copper_layers_of
    from fenolite.backends.altium.adapter.rules import KEPT_RULE, kept_fields
    from fenolite.backends.altium.connectstyle import connect_fields, read_connect_style
    from fenolite.backends.altium.read.rules import RULE_KIND_MAP

    rules = design.rules.rules if design.rules is not None else ()
    sources = {(_bag(rule).get("rule_kind", ""), rule.name.split("/")[0]) for rule in rules}
    margins: set[str] = set()
    layers = copper_layers_of(design.board.layers) if design.board is not None else None
    count = 0
    records = [dict(kept_fields(text)[1]) for text in _pairs(design, KEPT_RULE)]
    records += [dict(connect_fields(text)) for text in _pairs(design, "polygon_connect")]
    for fields in sorted(records, key=lambda f: (f.get("RULEKIND", ""), _priority(f))):
        kind, name = fields.get("RULEKIND", ""), fields.get("NAME", "")
        if (kind, name) in sources:
            continue  # the record gave neutral rules: ``lower_rules`` gave them their fates
        count += 1
        ident = f"{kind}:{name}"
        enabled = fields.get("ENABLED") == "TRUE"
        if not kind or not name:
            ledger.drop(KIND, ident, MALFORMED)
        elif (
            kind in ("SolderMaskExpansion", "PasteMaskExpansion")
            and enabled
            and kind not in margins
            and _all(fields)
        ):
            margins.add(kind)
            ledger.change(KIND, ident, MARGINS.format(kind=kind))
        elif kind == "PolygonConnect" and enabled and _read_style(fields, read_connect_style):
            ledger.change(KIND, ident, CONNECT)
        elif kind == "ShortCircuit" and enabled and fields.get("ALLOWED") == "FALSE" and _all(fields):
            ledger.change(KIND, ident, SHORTS)
        elif enabled and kind in RULE_KIND_MAP and _maps_to_nothing(fields, layers):
            pass  # a Routing Layers record that disallows no layer of the board: KiCad needs no rule
        else:
            ledger.keep(KIND, ident, kept_reason(kind, enabled=enabled, mapped_kind=kind in RULE_KIND_MAP))
    return count


def _read_style(fields: Mapping[str, str], read: Callable[..., object]) -> bool:
    """Whether the Polygon Connect Style record reads into a style that a pour takes."""
    style = read(list(fields.items()))
    return style is not None and not getattr(style, "reason", "")


def _priority(fields: Mapping[str, str]) -> int:
    text = fields.get("PRIORITY", "")
    return int(text) if text.isascii() and text.isdigit() else 0


def _all(fields: Mapping[str, str]) -> bool:
    return (
        fields.get("SCOPE1EXPRESSION", "").strip() == "All"
        and fields.get("SCOPE2EXPRESSION", "All").strip() == "All"
    )


def _maps_to_nothing(fields: Mapping[str, str], layers: CopperLayers | None) -> bool:
    """Whether the mapper maps the record, alone, onto no rule (a Routing Layers record that disallows no
    copper layer of the board): the mapper decides, as it did for the import."""
    from fenolite.backends.altium.read.rules import map_rules

    mapping = map_rules([list(fields.items())], origin="kept", layers=layers)
    return not mapping.unmapped and not mapping.ruleset.rules


__all__ = [
    "CHANGED",
    "DISABLED",
    "KEPT",
    "MALFORMED",
    "CONNECT",
    "NO_RULE",
    "SHORTS",
    "kept_reason",
    "lower_rules",
    "record_fates",
]
