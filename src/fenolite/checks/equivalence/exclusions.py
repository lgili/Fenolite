# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exclusion profiles: known differences as data (capability design-equivalence, "Exclusion lists").

A profile is a named list of rules for one tool version line, with the frame and the tolerances the
comparison runs under. A rule matches differences by level, kind, an optional field and a glob over
``where``. A matched difference is moved to the level's ``excluded`` list; it stays in the output and
never fails a comparison. This module knows the file format and no tool.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from fnmatch import fnmatchcase
from typing import Any, Literal, cast

from fenolite.checks.equivalence.model import (
    FRAMES,
    KIND_LEVELS,
    KINDS,
    Difference,
    Excluded,
    Frame,
    LevelResult,
)
from fenolite.core.errors import FormatError

SCHEMA = 1
Attribution = Literal["importer", "undecided"]
ATTRIBUTIONS: tuple[Attribution, ...] = ("importer", "undecided")
ROOT_KEYS = frozenset({"schema", "profile"})
PROFILE_KEYS = frozenset({"name", "tool", "tool_version", "frame", "tolerance_nm", "tolerance_udeg", "rule"})
RULE_REQUIRED = ("id", "level", "kind", "where", "attribution", "reason", "hypothesis")
RULE_OPTIONAL = ("field", "corpus")


@dataclass(frozen=True, slots=True)
class Rule:
    """One known difference: every difference of ``level`` and ``kind`` (and ``field``, when given) whose
    ``where`` matches the glob. ``attribution`` says who makes the change: the ``importer`` when a public
    source or the tool's report shows it, ``undecided`` when no source says which side is right."""

    id: str
    level: int
    kind: str
    where: str
    attribution: Attribution
    reason: str
    hypothesis: str
    field: str = ""
    corpus: tuple[str, ...] = ()

    def matches(self, difference: Difference) -> bool:
        return (
            difference.level == self.level
            and difference.kind == self.kind
            and (not self.field or difference.field == self.field)
            and fnmatchcase(difference.where, self.where)
        )


@dataclass(frozen=True, slots=True)
class Profile:
    """The rules of one tool version line, with the frame and the tolerances of the comparison."""

    name: str
    tool: str
    tool_version: str
    frame: Frame
    tolerance_nm: int
    tolerance_udeg: int
    rules: tuple[Rule, ...] = ()


def _text(table: Mapping[str, Any], key: str, where: str, file: str) -> str:
    value = table[key]
    if not isinstance(value, str) or not value:
        raise FormatError(f"{where}: {key} is a non-empty string", file=file)
    return value


def _count(table: Mapping[str, Any], key: str, where: str, file: str) -> int:
    value = table[key]
    if type(value) is not int or value < 0:
        raise FormatError(f"{where}: {key} is a non-negative integer", file=file)
    return value


def _keys(
    table: Mapping[str, Any], required: Sequence[str], optional: Sequence[str], where: str, file: str
) -> None:
    missing = [key for key in required if key not in table]
    if missing:
        raise FormatError(f"{where}: missing {', '.join(missing)}", file=file)
    unknown = sorted(set(table) - set(required) - set(optional))
    if unknown:
        raise FormatError(f"{where}: unknown key {', '.join(unknown)}", file=file)


def _rule(table: Mapping[str, Any], seen: set[str], profile: str, file: str) -> Rule:
    ident = table.get("id")
    where = f"rule {ident!r} of profile {profile!r}" if isinstance(ident, str) else f"a rule of {profile!r}"
    _keys(table, RULE_REQUIRED, RULE_OPTIONAL, where, file)
    ident = _text(table, "id", where, file)
    if ident in seen:
        raise FormatError(f"{where}: the id is used twice", file=file)
    seen.add(ident)
    level = _count(table, "level", where, file)
    kind = _text(table, "kind", where, file)
    if level not in KIND_LEVELS.get(kind, ()):
        raise FormatError(f"{where}: {kind!r} is not a kind of level {level}", file=file)
    field = table.get("field", "")
    if not isinstance(field, str):
        raise FormatError(f"{where}: field is a string", file=file)
    if field and (level, kind, field) not in KINDS:
        raise FormatError(f"{where}: {kind!r} has no field {field!r}", file=file)
    attribution = _text(table, "attribution", where, file)
    if attribution not in ATTRIBUTIONS:
        raise FormatError(f"{where}: attribution is one of {', '.join(ATTRIBUTIONS)}", file=file)
    corpus = table.get("corpus", [])
    if not isinstance(corpus, list) or not all(isinstance(row, str) for row in cast(list[object], corpus)):
        raise FormatError(f"{where}: corpus is a list of corpus row ids", file=file)
    return Rule(
        id=ident,
        level=level,
        kind=kind,
        where=_text(table, "where", where, file),
        attribution=attribution,
        reason=_text(table, "reason", where, file),
        hypothesis=_text(table, "hypothesis", where, file),
        field=field,
        corpus=tuple(cast(list[str], corpus)),
    )


def load_profiles(text: str, *, file: str = "") -> tuple[Profile, ...]:
    """The profiles of an exclusion file, in file order. ``FormatError`` names the file and the rule for a
    missing or unknown key, a kind of another level, a duplicate rule id or a value of the wrong type."""
    try:
        root = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not a TOML document: {error}", file=file) from None
    unknown = sorted(set(root) - ROOT_KEYS)
    if unknown:
        raise FormatError(f"unknown key {', '.join(unknown)}", file=file)
    if root.get("schema") != SCHEMA or type(root.get("schema")) is not int:
        raise FormatError(f"schema must be {SCHEMA}", file=file)
    tables = root.get("profile", [])
    if not isinstance(tables, list):
        raise FormatError("profile is an array of tables ([[profile]])", file=file)
    profiles: list[Profile] = []
    seen: set[str] = set()
    for table in cast(list[Mapping[str, Any]], tables):
        if not isinstance(table, dict):
            raise FormatError("profile is an array of tables ([[profile]])", file=file)
        name = table.get("name")
        where = f"profile {name!r}"
        _keys(table, sorted(PROFILE_KEYS - {"rule"}), ("rule",), where, file)
        frame = _text(table, "frame", where, file)
        if frame not in FRAMES:
            raise FormatError(f"{where}: frame is one of {', '.join(FRAMES)}", file=file)
        rules = table.get("rule", [])
        if not isinstance(rules, list):
            raise FormatError(f"{where}: rule is an array of tables ([[profile.rule]])", file=file)
        name = _text(table, "name", where, file)
        profiles.append(
            Profile(
                name=name,
                tool=_text(table, "tool", where, file),
                tool_version=_text(table, "tool_version", where, file),
                frame=frame,
                tolerance_nm=_count(table, "tolerance_nm", where, file),
                tolerance_udeg=_count(table, "tolerance_udeg", where, file),
                rules=tuple(_rule(rule, seen, name, file) for rule in cast(list[Mapping[str, Any]], rules)),
            )
        )
    return tuple(profiles)


def _is_prefix(prefix: str, version: str) -> bool:
    """Whether ``prefix`` starts ``version`` at a dot boundary: ``10.0`` matches ``10.0.6``, not ``10.01``."""
    return version == prefix or version.startswith(prefix + ".")


def select_profile(profiles: Sequence[Profile], name: str, tool_version: str) -> Profile | None:
    """The profile called ``name`` whose ``tool_version`` is the longest prefix of ``tool_version`` at a dot
    boundary, or ``None``."""
    found = [p for p in profiles if p.name == name and _is_prefix(p.tool_version, tool_version)]
    return max(found, key=lambda p: len(p.tool_version)) if found else None


def apply_rules(result: LevelResult, rules: Sequence[Rule]) -> LevelResult:
    """``result`` with each difference that a rule matches moved to ``excluded``; the first matching rule,
    in the given order, wins."""
    kept: list[Difference] = []
    excluded: list[Excluded] = list(result.excluded)
    for difference in result.differences:
        rule = next((r for r in rules if r.matches(difference)), None)
        if rule is None:
            kept.append(difference)
        else:
            excluded.append(Excluded(difference, rule.id, rule.reason))
    return replace(result, differences=tuple(kept), excluded=tuple(excluded))


__all__ = [
    "ATTRIBUTIONS",
    "SCHEMA",
    "Attribution",
    "Profile",
    "Rule",
    "apply_rules",
    "load_profiles",
    "select_profile",
]
