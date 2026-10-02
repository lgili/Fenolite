# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lowering the model's rules to a KiCad custom-rules file, and its net classes to the project file.

Facts and Fenolite choices: ``docs/formats/kicad/rules.md`` and ``docs/formats/kicad/project.md``.
``lower_rules`` writes the rules of the user's ``RuleSet`` and nothing else (Fenolite ships no
requirement values), in priority order, with generated names, through ``dru.write_rules``, so target
gating and the self-check are shared. ``lower_netclass`` writes one model ``NetClass`` as a project
class entry, from the ``Default`` entry of the project being written.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Mapping, Sequence
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
from fenolite.model.rules import Rule, RuleSet

EVIDENCE = Evidence(
    Level.KICAD_VERIFIED, hypotheses=("H-K-DRU-DIALECT", "H-K-DRU-ORDER", "H-K-DRU-COND", "H-K-DRU-KIND")
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
    }
)
"""Model ``NetClass`` field → project class key."""
FLOOR_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "clearance": "min_clearance",
        "track_width": "min_track_width",
        "via_diameter": "min_via_diameter",
        "via_drill": "min_through_hole_diameter",
    }
)
"""Model ``NetClass`` field → its floor in ``board.design_settings.rules``."""


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
    the name and the four modelled values written; every other key is kept.

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


__all__ = [
    "EVIDENCE",
    "FLOOR_KEYS",
    "NETCLASS_KEYS",
    "LoweredRules",
    "lower_netclass",
    "lower_rules",
    "lowered_names",
    "millimetres",
]
