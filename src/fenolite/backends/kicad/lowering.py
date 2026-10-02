# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lowering the model's rules to a KiCad custom-rules file.

Facts and Fenolite choices: ``docs/formats/kicad/rules.md``. ``lower_rules`` writes the rules of the
user's ``RuleSet`` and nothing else (Fenolite ships no requirement values), in priority order, with
generated names, through ``dru.write_rules``, so target gating and the self-check are shared.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from fenolite.backends.base import WriteResult
from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.dru import write_rules
from fenolite.backends.kicad.versions import DEFAULT_TARGET
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.rules import Rule, RuleSet

EVIDENCE = Evidence(
    Level.KICAD_VERIFIED, hypotheses=("H-K-DRU-DIALECT", "H-K-DRU-ORDER", "H-K-DRU-COND", "H-K-DRU-KIND")
)
"""Settled on ``kicad-cli`` 9.0.9 and 10.0.6 by the rules oracle (``tests/kicad/rules/``)."""
LoweredRules = WriteResult
"""``lower_rules`` returns the board writer's neutral result, ``WriteResult(text, issues)``."""


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


__all__ = ["EVIDENCE", "LoweredRules", "lower_rules", "lowered_names"]
