# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule records of a PCB document as neutral rules, through the mapper of change c0042 (capability
altium-import, "Rules where they map"; change c0043).

The adapter holds no rule table: ``read.rules.map_rules`` decides what maps. The adapter keeps each mapped
rule and replaces its header: the id and native id of the import's tables, the provenance, and a bag with
``rule_kind``, ``scope1`` and ``scope2``, and the pairs the mapper added beside the record text (the cell
of a cell rule, the entries of a matrix that no rule holds; change c0130). Unmapped rules are counted per
rule kind. The Polygon Connect Style records, which no model rule holds, are kept on the board as text
(``connect_texts``, change c0215).
"""

# evidence: see import_evidence

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Sequence

from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.ids import Ids, bag
from fenolite.backends.altium.read.rules import (
    BACKEND,
    CELL_PAIR,
    WRITTEN_KINDS,
    CopperLayers,
    Field,
    RuleMapping,
    map_rules,
)
from fenolite.backends.altium.read.scope import ScopeDocument
from fenolite.core.errors import Issue
from fenolite.model.rules import Rule, RuleSet

MAPPER_PER_RULE = frozenset({"altium.rule.unmapped", "altium.rule.applies-to-nothing"})
"""The per-record infos of the mapper: the import counts their records by kind and reason instead."""
RECORD_PAIR = "record"
STORAGE = "Rules6"


POLYGON_CONNECT = "PolygonConnect"
"""The rule kind of Polygon Connect Style records (``connectstyle.RULE_KIND``), which the model holds no
rule of: the board keeps them as ``polygon_connect`` pairs (change c0215)."""


def connect_texts(records: Sequence[Sequence[Field]]) -> tuple[str, ...]:
    """The Polygon Connect Style records among ``records`` (the field lists of a document's rules), each as
    the text of the board's ``polygon_connect`` pair: its keys from ``RULEKIND`` on, ``KEY=VALUE`` joined by
    ``|``. Enabled or not, in record order."""
    found: list[str] = []
    for fields in records:
        keys = [key for key, _ in fields]
        if "RULEKIND" not in keys or _get(fields, "RULEKIND") != POLYGON_CONNECT:
            continue
        found.append("|".join(f"{key}={value or ''}" for key, value in fields[keys.index("RULEKIND") :]))
    return tuple(found)


KEPT_RULE = "kept_rule"
KEPT_RECORD = "kept_record"
STACKED = ("HoleToHoleClearance", "ALLOWSTACKEDMICROVIAS", "TRUE")
"""A Hole To Hole Clearance that allows stacked micro vias maps, and the lowering writes the key ``FALSE``:
its record is kept (change c0424)."""


def kept_indexes(records: Sequence[Sequence[Field]], mapping: RuleMapping) -> frozenset[int]:
    """The records that give no rule which ``rulemap.lower`` writes again in its own form (change c0424):
    a record the mapper does not map (any reason), a record of a kind outside ``read.rules.WRITTEN_KINDS``,
    and a Hole To Hole Clearance with stacked micro vias allowed. A Polygon Connect Style record is not among
    them (the board keeps it as ``polygon_connect``), nor a record without ``RULEKIND``."""
    unmapped = {item.index for item in mapping.unmapped}
    found: set[int] = set()
    for index, fields in enumerate(records):
        kind = _get(fields, "RULEKIND")
        if not kind or kind == POLYGON_CONNECT:
            continue
        stacked = kind == STACKED[0] and _get(fields, STACKED[1]) == STACKED[2]
        if index in unmapped or kind not in WRITTEN_KINDS or stacked:
            found.add(index)
    return frozenset(found)


def kept_text(number: int, fields: Sequence[Field]) -> str:
    """The ``kept_rule`` text of a record: its kind number, ``|``, and its pairs from ``RULEKIND`` on as
    ``KEY=VALUE`` (a key without value alone) joined by ``|``."""
    keys = [key for key, _value in fields]
    start = keys.index("RULEKIND")
    return f"{number}|" + "|".join(
        key if value is None else f"{key}={value}" for key, value in fields[start:]
    )


def kept_fields(text: str) -> tuple[int, tuple[tuple[str, str], ...]]:
    """The kind number and the pairs of a ``kept_rule`` text (``kept_text``), as the writer takes them: a
    key written without a value gets the empty value."""
    number, _bar, rest = text.partition("|")
    pairs: list[tuple[str, str]] = []
    for part in rest.split("|"):
        key, _equals, value = part.partition("=")
        pairs.append((key, value))
    return int(number), tuple(pairs)


def _mapper_pairs(rule: Rule) -> tuple[tuple[str, str], ...]:
    held = rule.ext.get(BACKEND)
    return tuple((key, str(value)) for key, value in held.payload) if held is not None else ()


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
    kept: frozenset[int] = frozenset(),
) -> tuple[Rule, ...]:
    """The rules of ``mapping`` with the import's headers, and its issues summarised into ``issues``: one
    ``altium.import.rule-unmapped`` per rule kind; the mapper's per-rule infos are not forwarded. A rule of
    a record of ``kept`` holds the pair ``kept_record`` (change c0424)."""
    rules: list[Rule] = []
    for rule, index in zip(mapping.ruleset.rules, mapping.rule_records, strict=True):
        fields = records[index]
        kind, name = _get(fields, "RULEKIND"), _get(fields, "NAME")
        more = [pair for pair in _mapper_pairs(rule) if pair[0] != RECORD_PAIR]
        cell = "".join(f":{value}" for key, value in more if key == CELL_PAIR)
        ident, native = ids.native("rul", f"rule:{kind}:{name}:{rule.kind}{cell}")
        pairs = [
            ("rule_kind", kind),
            ("scope1", _get(fields, "SCOPE1EXPRESSION")),
            ("scope2", _get(fields, "SCOPE2EXPRESSION")),
            *more,
            *([(KEPT_RECORD, "1")] if index in kept else []),
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
    issues.extend(found for found in mapping.issues if found.code not in MAPPER_PER_RULE)
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
    numbers: Sequence[int] = (),
    kept: list[str] | None = None,
    document: ScopeDocument | None = None,
) -> RuleSet:
    """The rule set of the rule records ``records`` (each a record's whole pair list, ``RuleRecord.fields``
    of c0041): ``map_rules(records, origin=file)`` with the import's ids, provenance and bags. ``layers``
    are the copper layers of the board the records belong to (a PCB document); a rule file has none. With
    ``kept`` (a PCB document, whose record kind numbers are ``numbers``) the ``kept_rule`` texts of the
    records ``kept_indexes`` names are appended to it, in record order (change c0424). ``document`` is what
    the scope functions of change c0462 read from the PCB document (``read.scopedoc.scope_document``)."""
    mapping = map_rules(records, origin=file, layers=layers, document=document)
    held = kept_indexes(records, mapping) if kept is not None else frozenset[int]()
    if kept is not None:
        kept.extend(kept_text(numbers[index], records[index]) for index in sorted(held))
    rules = adopt(mapping, records, ids, file=file, sha256=sha256, issues=issues, storage=storage, kept=held)
    ident, native = ids.native("rst", ids.kind)
    return RuleSet(id=ident, native_ids=native, provenance=ids.provenance(file, sha256, storage), rules=rules)


__all__ = [
    "KEPT_RECORD",
    "KEPT_RULE",
    "adopt",
    "import_rules",
    "kept_fields",
    "kept_indexes",
    "kept_text",
]
