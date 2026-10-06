# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule records of a PCB document as neutral rules, through the mapper of change c0042 (capability
altium-import, "Rules where they map"; change c0043).

The adapter holds no rule table: ``read.rules.map_rules`` decides what maps. The adapter keeps each mapped
rule and replaces its header: the id and native id of the import's tables, the provenance, and a bag with
``rule_kind``, ``scope1`` and ``scope2``. Unmapped rules are counted per rule kind.
"""

# evidence: see import_evidence

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Sequence

from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.ids import Ids, bag
from fenolite.backends.altium.read.rules import CopperLayers, Field, RuleMapping, map_rules
from fenolite.core.errors import Issue
from fenolite.model.rules import Rule, RuleSet

MAPPER_PER_RULE = "altium.rule.unmapped"
STORAGE = "Rules6"


def _get(fields: Sequence[Field], key: str) -> str:
    return next((value or "" for name, value in fields if name == key), "")


def adopt(
    mapping: RuleMapping,
    records: Sequence[Sequence[Field]],
    ids: Ids,
    *,
    file: str,
    sha256: str,
    issues: list[Issue],
    storage: str = STORAGE,
) -> tuple[Rule, ...]:
    """The rules of ``mapping`` with the import's headers, and its issues summarised into ``issues``: one
    ``altium.import.rule-unmapped`` per rule kind; the mapper's per-rule infos are not forwarded."""
    rules: list[Rule] = []
    for rule, index in zip(mapping.ruleset.rules, mapping.rule_records, strict=True):
        fields = records[index]
        kind, name = _get(fields, "RULEKIND"), _get(fields, "NAME")
        ident, native = ids.native("rul", f"rule:{kind}:{name}:{rule.kind}")
        pairs = [
            ("rule_kind", kind),
            ("scope1", _get(fields, "SCOPE1EXPRESSION")),
            ("scope2", _get(fields, "SCOPE2EXPRESSION")),
        ]
        rules.append(
            dataclasses.replace(
                rule,
                id=ident,
                native_ids=native,
                provenance=ids.provenance(file, sha256, f"{storage}/Data#{index}"),
                ext=bag(pairs),
            )
        )
    issues.extend(found for found in mapping.issues if found.code != MAPPER_PER_RULE)
    by_kind: dict[str, Counter[str]] = {}
    for unmapped in mapping.unmapped:
        by_kind.setdefault(unmapped.kind or "(none)", Counter())[unmapped.reason] += 1
    for kind in sorted(by_kind):
        reasons = by_kind[kind]
        listed = ", ".join(f"{reason} {count}" for reason, count in sorted(reasons.items()))
        issues.append(
            issue(
                "altium.import.rule-unmapped",
                f"{sum(reasons.values())} rule(s) of kind {kind} are not mapped ({listed})",
                f"{storage}/Data",
            )
        )
    return tuple(rules)


def import_rules(
    records: Sequence[Sequence[Field]],
    ids: Ids,
    *,
    file: str,
    sha256: str,
    issues: list[Issue],
    storage: str = STORAGE,
    layers: CopperLayers | None = None,
) -> RuleSet:
    """The rule set of the rule records ``records`` (each a record's whole pair list, ``RuleRecord.fields``
    of c0041): ``map_rules(records, origin=file)`` with the import's ids, provenance and bags. ``layers``
    are the copper layers of the board the records belong to (a PCB document); a rule file has none."""
    mapping = map_rules(records, origin=file, layers=layers)
    rules = adopt(mapping, records, ids, file=file, sha256=sha256, issues=issues, storage=storage)
    ident, native = ids.native("rst", ids.kind)
    return RuleSet(id=ident, native_ids=native, provenance=ids.provenance(file, sha256, storage), rules=rules)


__all__ = ["adopt", "import_rules"]
