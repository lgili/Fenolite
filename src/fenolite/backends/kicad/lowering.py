# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lowering the model's rules to a KiCad custom-rules file, and its net classes to the project file.

Facts and Fenolite choices: ``docs/formats/kicad/rules.md`` and ``docs/formats/kicad/project.md``.
``lower_rules`` writes the rules of the user's ``RuleSet`` and nothing else (Fenolite ships no
requirement values), in priority order, with generated names, through ``dru.write_rules``, so target
gating and the self-check are shared. ``lower_netclass`` writes one model ``NetClass`` as a project
class entry, from the ``Default`` entry of the project being written. ``lower_minimums`` derives the
board-setup minimums of the project from the board-wide rules, and ``class_conflicts`` reports class
clearances that a board-wide clearance rule overrides or leaves above it (``project.md``, "Board-setup
minimums").
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Collection, Mapping, Sequence
from types import MappingProxyType

from fenolite.backends.base import WriteResult
from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.dru import write_rules
from fenolite.backends.kicad.proerrors import project_issue
from fenolite.backends.kicad.versions import DEFAULT_TARGET
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, format_length
from fenolite.model.circuit import NetClass
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

EVIDENCE = Evidence(
    Level.KICAD_VERIFIED,
    hypotheses=("H-K-DRU-DIALECT", "H-K-DRU-ORDER", "H-K-DRU-COND", "H-K-DRU-KIND", "H-K-DRU-PAIR"),
)
"""Settled on ``kicad-cli`` 9.0.9 and 10.0.6 by the rules oracle (``tests/kicad/rules/``)."""
LoweredRules = WriteResult
"""``lower_rules`` returns the board writer's neutral result, ``WriteResult(text, issues)``."""
NETCLASS_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "clearance": "clearance",
        "track_width": "track_width",
        "via_diameter": "via_diameter",
        "via_drill": "via_drill",
        "diff_pair_width": "diff_pair_width",
        "diff_pair_gap": "diff_pair_gap",
        "diff_pair_via_gap": "diff_pair_via_gap",
    }
)
"""Model ``NetClass`` field → project class key. The three pair values are defaults of KiCad's router and
no DRC limits; a pair gap below the class clearance lowers the clearance inside a pair of the class
(``H-K-PRO-PAIR``)."""
FLOOR_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "clearance": "min_clearance",
        "track_width": "min_track_width",
        "via_diameter": "min_via_diameter",
        "via_drill": "min_through_hole_diameter",
    }
)
"""Model ``NetClass`` field → its floor in ``board.design_settings.rules``."""


MINIMUM_KEYS: Mapping[int, Mapping[RuleKind, str]] = MappingProxyType(
    {
        major: MappingProxyType(
            {
                "clearance": "min_clearance",
                "track_width": "min_track_width",
                "via_diameter": "min_via_diameter",
                "hole_size": "min_through_hole_diameter",
                "edge_clearance": "min_copper_edge_clearance",
            }
        )
        for major in (9, 10)
    }
)
"""Target major → rule kind in normal form → its key in ``board.design_settings.rules``
(``H-K-PRO-MIN-KEYS``; pinned to the probe files)."""
FLOOR_OVER_RULES: Mapping[str, frozenset[int]] = MappingProxyType(
    {key: frozenset[int]() for key in MINIMUM_KEYS[10].values()}
)
"""Minimum key → the majors on which that minimum governs a custom rule with a lower ``min``. Empty:
on ``kicad-cli`` 9.0.9 and 10.0.6 a board-wide custom rule governs below every minimum
(``H-K-PRO-MIN-RULE`` refuted, ``H-K-PRO-MIN-RULE-2``; pinned to the probe files)."""
RULES_OVER_CLASSES: frozenset[int] = frozenset({9, 10})
"""The majors on which a board-wide custom clearance rule governs the items of a class with a larger
clearance (``H-K-PRO-MIN-CLASS``, measured on 9.0.9 and 10.0.6; pinned to the probe files)."""
_ALL = Selector("all")


def lowered_names(rules: Sequence[Rule]) -> tuple[str, ...]:
    """``fenolite_<priority>_<slug>`` for each rule in emission order; a repeated name gets ``_2``, ``_3``…

    A rule with several layers is written once per layer, with ``_<layer slug>`` appended; those names
    count as used too.
    """
    used: set[str] = set()
    names: list[str] = []
    for rule in rules:
        base = f"fenolite_{rule.priority}_{rulemap.slug(rule.name)}"

        def expanded(name: str, rule: Rule = rule) -> list[str]:
            if len(rule.layers) < 2:
                return [name]
            return [f"{name}_{rulemap.slug(layer)}" for layer in rule.layers]

        name, k = base, 1
        while any(n in used for n in expanded(name)):
            k += 1
            name = f"{base}_{k}"
        used.update(expanded(name))
        names.append(name)
    return tuple(names)


def lower_rules(ruleset: RuleSet, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False) -> LoweredRules:
    """The rules file text of ``ruleset`` for KiCad ``target``.0, in priority order (priority 1 last).

    Errors raise ``dru.RulesLossError`` (FEN-7001) with every issue; warnings and infos are returned.
    """
    bag = ruleset.ext.get("kicad")
    if bag is not None and any(key.startswith("slot:") for key, _ in bag.payload):
        raise ValueError(
            "this rule set was read from a rules file; "
            "write it with write_rules, which keeps its order and names"
        )
    ordered = rulemap.rule_order(ruleset.rules)
    renamed = tuple(
        dataclasses.replace(rule, name=name, ext={})
        for rule, name in zip(ordered, lowered_names(ordered), strict=True)
    )
    issues: list[Issue] = []
    text = write_rules(
        dataclasses.replace(ruleset, ext={}, rules=renamed),
        target=target,
        allow_lossy=allow_lossy,
        issues=issues,
    )
    return WriteResult(text, tuple(issues))


def millimetres(nm: Nm) -> JsonNumber:
    """The exact millimetre text of ``nm`` as a JSON number (``2_000_000`` → ``2``)."""
    return JsonNumber(format_length(nm, "mm")[: -len("mm")])


def lower_netclass(
    cls: NetClass,
    *,
    base: JsonObject,
    floors: Mapping[str, Nm],
    issues: list[Issue] | None = None,
) -> JsonObject:
    """A project class entry for ``cls``: a copy of ``base`` (the project's ``Default`` entry) with
    the name and the seven modelled values written; every other key is kept.

    A value below its floor gives ``kicad.project.below-floor`` and is still written, because the floor
    governs (``H-K-PRO-FLOOR``); a description gives ``kicad.project.unlowered-field``.
    """
    found = issues if issues is not None else []
    entry: JsonObject = copy.deepcopy(base)
    entry["name"] = cls.name
    for field, key in NETCLASS_KEYS.items():
        value: Nm | None = getattr(cls, field)
        if value is None:
            continue
        entry[key] = millimetres(value)
        floor = floors.get(field)
        if floor is not None and value < floor:
            found.append(
                project_issue(
                    "kicad.project.below-floor",
                    f"class {cls.name!r}: {field} {millimetres(value).text} mm is below "
                    f"{FLOOR_KEYS[field]} {millimetres(floor).text} mm; the board-setup minimum governs",
                    where=f"/net_settings/classes/{cls.name}",
                    hint="raise the class value, or lower the minimum in Board Setup",
                )
            )
    if cls.description:
        found.append(
            project_issue(
                "kicad.project.unlowered-field",
                f"class {cls.name!r}: the description has no project key and is not written",
                where=f"/net_settings/classes/{cls.name}",
            )
        )
    return entry


def is_board_wide(rule: Rule) -> bool:
    """True when the normal form of ``rule`` selects every item: ``all``, no B side and no layers."""
    form = rulemap.normal_form(rule)
    return form.selector_a == _ALL and form.selector_b is None and not form.layers


def _of_kind(ruleset: RuleSet | None, kind: RuleKind) -> list[tuple[Rule, Rule]]:
    """``(rule, normal form)`` of every modelled rule whose normal form has ``kind``, in KiCad's order."""
    if ruleset is None:
        return []
    pairs = [(rule, rulemap.normal_form(rule)) for rule in rulemap.rule_order(ruleset.rules)]
    return [(rule, form) for rule, form in pairs if form.kind == kind]


def _governing(pairs: Sequence[tuple[Rule, Rule]]) -> int | None:
    """The index of the last board-wide rule of ``pairs``, which governs every item they select."""
    found = [i for i, (rule, _) in enumerate(pairs) if is_board_wide(rule)]
    return found[-1] if found else None


def governing_rule(ruleset: RuleSet | None, kind: RuleKind) -> Rule | None:
    """The board-wide rule of ``kind`` (normal form) that KiCad applies last, if any."""
    pairs = _of_kind(ruleset, kind)
    index = _governing(pairs)
    return None if index is None else pairs[index][0]


def _mm(nm: Nm) -> str:
    return millimetres(nm).text


def lower_minimums(
    ruleset: RuleSet | None,
    *,
    target: int,
    current: Mapping[str, Nm],
    issues: list[Issue] | None = None,
) -> dict[str, Nm]:
    """The board-setup minimums that the project for ``target`` must hold, from the board-wide rules.

    Per kind, the governing board-wide rule is the last one in KiCad's order. With severity ``error``
    and a ``min``, its key gets the least ``min`` of it and of the later rules of its kind. ``current``
    holds the minimums in force; a rule below a minimum that is not written is reported where the
    minimum governs rules (``FLOOR_OVER_RULES``).
    """
    if target not in MINIMUM_KEYS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {tuple(MINIMUM_KEYS)}")
    found = issues if issues is not None else []
    minimums: dict[str, Nm] = {}
    for kind, key in MINIMUM_KEYS[target].items():
        pairs = _of_kind(ruleset, kind)
        index = _governing(pairs)
        later = pairs if index is None else pairs[index:]
        if index is not None:
            rule = pairs[index][0]
            if rule.severity == "error" and rule.min is not None:
                minimums[key] = min(form.min for _, form in later if form.min is not None)
                continue
            reason = f"severity {rule.severity}" if rule.severity != "error" else "no min"
            found.append(
                project_issue(
                    "kicad.project.minimum-kept",
                    f"rule {rule.name!r} governs {kind} on the whole board but has {reason}; "
                    f"{key} is kept as it is",
                    where=rule.id,
                )
            )
        floor = current.get(key)
        if floor is None or target not in FLOOR_OVER_RULES.get(key, frozenset()):
            continue
        for rule, form in later:
            if form.min is not None and form.min < floor:
                found.append(
                    project_issue(
                        "kicad.project.rule-below-minimum",
                        f"rule {rule.name!r}: {kind} min {_mm(form.min)} mm is below {key} "
                        f"{_mm(floor)} mm, which KiCad applies instead",
                        where=rule.id,
                        hint=f"a board-wide {kind} rule with severity error lets Fenolite lower {key}",
                    )
                )
    return minimums


def class_conflicts(
    ruleset: RuleSet | None,
    *,
    target: int,
    clearances: Mapping[str, Nm],
    model_names: Collection[str],
    issues: list[Issue] | None = None,
) -> None:
    """Report the class clearances that KiCad does not combine with the governing board-wide clearance
    rule as the design states them (``RULES_OVER_CLASSES``); clearance only."""
    found = issues if issues is not None else []
    pairs = _of_kind(ruleset, "clearance")
    index = _governing(pairs)
    if index is None:
        return
    rule = pairs[index][0]
    if rule.min is None:
        return
    limit = rule.min
    if target in RULES_OVER_CLASSES:
        for name in sorted(clearances):
            value = clearances[name]
            if value <= limit or (name == "Default" and name not in model_names):
                continue
            restored = any(
                form.selector_a == Selector("netclass", name)
                and form.selector_b is None
                and not form.layers
                and form.min is not None
                and form.min >= value
                for _, form in pairs[index + 1 :]
            )
            if not restored:
                found.append(
                    project_issue(
                        "kicad.project.class-shadowed",
                        f"class {name!r}: clearance {_mm(value)} mm is above the board-wide rule "
                        f"{rule.name!r} ({_mm(limit)} mm), which KiCad applies to its items instead",
                        where=f"/net_settings/classes/{name}",
                        hint=f"add a clearance rule on netclass {name} with min {_mm(value)} mm after it",
                    )
                )
        return
    default = clearances.get("Default")
    if "Default" not in model_names and default is not None and default > limit:
        found.append(
            project_issue(
                "kicad.project.default-over-rule",
                f"the Default class clearance {_mm(default)} mm keeps unclassed nets above the "
                f"board-wide rule {rule.name!r} ({_mm(limit)} mm)",
                where="/net_settings/classes/Default",
                hint=f"a model class Default with clearance {_mm(limit)} mm lowers it",
            )
        )


__all__ = [
    "EVIDENCE",
    "FLOOR_KEYS",
    "FLOOR_OVER_RULES",
    "MINIMUM_KEYS",
    "NETCLASS_KEYS",
    "RULES_OVER_CLASSES",
    "LoweredRules",
    "class_conflicts",
    "governing_rule",
    "is_board_wide",
    "lower_minimums",
    "lower_netclass",
    "lower_rules",
    "lowered_names",
    "millimetres",
]
