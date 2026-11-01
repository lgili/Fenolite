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
    FREE_FIELDS,
    KIND_LEVELS,
    KINDS,
    SCHEMATIC_LEVEL,
    Difference,
    Excluded,
    Frame,
    LevelId,
    LevelResult,
)
from fenolite.core.errors import FormatError

SCHEMA = 1
Attribution = Literal["importer", "undecided", "fenolite", "upstream", "tool"]
ATTRIBUTIONS: tuple[Attribution, ...] = ("importer", "undecided")
"""The attributions of a rule of an exclusion file."""
ACCEPTED_ATTRIBUTIONS: tuple[Attribution, ...] = ("fenolite", "upstream", "tool", "undecided")
"""The attributions of an accepted difference of a provenance file: a limit of Fenolite, something odd in
the original, a behaviour of the original's tool, or not decided yet."""
ACCEPTED_REQUIRED = ("id", "level", "kind", "where", "reason", "attribution", "decided")
ACCEPTED_OPTIONAL = ("field",)
ROOT_KEYS = frozenset({"schema", "profile"})
PROFILE_KEYS = frozenset({"name", "tool", "tool_version", "frame", "tolerance_nm", "tolerance_udeg", "rule"})
RULE_REQUIRED = ("id", "level", "kind", "where", "attribution", "reason", "hypothesis")
RULE_OPTIONAL = ("field", "corpus")
PROFILE_OPTIONAL = ("rule", "tolerance_ppm")


@dataclass(frozen=True, slots=True)
class Rule:
    """One known difference: every difference of ``level`` and ``kind`` (and ``field``, when given) whose
    ``where`` matches the glob. ``attribution`` says who makes the change: the ``importer`` when a public
    source or the tool's report shows it, ``undecided`` when no source says which side is right."""

    id: str
    level: LevelId
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
    tolerance_ppm: int = 0


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


def check_kind(level: LevelId, kind: str, field: str, where: str, file: str) -> None:
    """``FormatError`` when ``kind`` is no kind of ``level``, or names no ``field`` of that name (a kind whose
    field column is a placeholder takes any dotted field)."""
    if level not in KIND_LEVELS.get(kind, ()):
        raise FormatError(f"{where}: {kind!r} is not a kind of level {level}", file=file)
    if not field:
        return
    fields = {name for found, other, name in KINDS if found == level and other == kind}
    if field not in fields and not fields & FREE_FIELDS:
        raise FormatError(f"{where}: {kind!r} has no field {field!r}", file=file)


def _rule(table: Mapping[str, Any], seen: set[str], profile: str, file: str) -> Rule:
    ident = table.get("id")
    where = f"rule {ident!r} of profile {profile!r}" if isinstance(ident, str) else f"a rule of {profile!r}"
    _keys(table, RULE_REQUIRED, RULE_OPTIONAL, where, file)
    ident = _text(table, "id", where, file)
    if ident in seen:
        raise FormatError(f"{where}: the id is used twice", file=file)
    seen.add(ident)
    level = table["level"] if table["level"] == SCHEMATIC_LEVEL else _count(table, "level", where, file)
    kind = _text(table, "kind", where, file)
    field = table.get("field", "")
    if not isinstance(field, str):
        raise FormatError(f"{where}: field is a string", file=file)
    check_kind(level, kind, field, where, file)
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
        _keys(table, sorted(PROFILE_KEYS - {"rule"}), PROFILE_OPTIONAL, where, file)
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
                tolerance_ppm=_count(table, "tolerance_ppm", where, file) if "tolerance_ppm" in table else 0,
            )
        )
    return tuple(profiles)


def accepted_rules(entries: object, *, file: str = "") -> tuple[Rule, ...]:
    """The exclusion rules of the accepted differences of a provenance file (the list
    ``fidelity.accepted``): each entry of ``id``, ``level``, ``kind``, ``where`` (a glob), optional ``field``,
    ``reason``, ``attribution`` (one of ``ACCEPTED_ATTRIBUTIONS``) and ``decided`` becomes a ``Rule`` that
    keeps its reason and attribution. ``FormatError`` names the entry for a missing or unknown key, a kind of
    another level, a repeated id or a value of the wrong type."""
    if not isinstance(entries, list):
        raise FormatError("fidelity.accepted is a list of entries", file=file)
    rules: list[Rule] = []
    seen: set[str] = set()
    for index, raw in enumerate(cast(list[object], entries)):
        if not isinstance(raw, dict):
            raise FormatError(f"fidelity.accepted[{index}] is an object", file=file)
        table = cast(dict[str, Any], raw)
        ident = table.get("id")
        where = f"accepted entry {ident!r}" if isinstance(ident, str) else f"fidelity.accepted[{index}]"
        _keys(table, ACCEPTED_REQUIRED, ACCEPTED_OPTIONAL, where, file)
        ident = _text(table, "id", where, file)
        if ident in seen:
            raise FormatError(f"{where}: the id is used twice", file=file)
        seen.add(ident)
        level = table["level"]
        if level != SCHEMATIC_LEVEL and (type(level) is not int or level < 1):
            raise FormatError(f"{where}: level is an integer of 1 to 8 or {SCHEMATIC_LEVEL!r}", file=file)
        kind = _text(table, "kind", where, file)
        field = table.get("field", "")
        if not isinstance(field, str):
            raise FormatError(f"{where}: field is a string", file=file)
        check_kind(level, kind, field, where, file)
        attribution = _text(table, "attribution", where, file)
        if attribution not in ACCEPTED_ATTRIBUTIONS:
            raise FormatError(f"{where}: attribution is one of {', '.join(ACCEPTED_ATTRIBUTIONS)}", file=file)
        _text(table, "decided", where, file)
        rules.append(
            Rule(
                id=ident,
                level=level,
                kind=kind,
                where=_text(table, "where", where, file),
                attribution=attribution,
                reason=_text(table, "reason", where, file),
                hypothesis="",
                field=field,
            )
        )
    return tuple(rules)


def _is_prefix(prefix: str, version: str) -> bool:
    """Whether ``prefix`` starts ``version`` at a dot boundary: ``10.0`` matches ``10.0.6``, not ``10.01``."""
    return version == prefix or version.startswith(prefix + ".")


def select_profile(profiles: Sequence[Profile], name: str, tool_version: str) -> Profile | None:
    """The profile called ``name`` whose ``tool_version`` is the longest prefix of ``tool_version`` at a dot
    boundary, or ``None``."""
    found = [p for p in profiles if p.name == name and _is_prefix(p.tool_version, tool_version)]
    return max(found, key=lambda p: len(p.tool_version)) if found else None


def apply_rules(result: LevelResult, rules: Sequence[Rule]) -> LevelResult:
    """``result`` with each difference and each notice that a rule matches moved to ``excluded``; the first
    matching rule, in the given order, wins."""
    excluded: list[Excluded] = list(result.excluded)

    def kept(found: Sequence[Difference]) -> tuple[Difference, ...]:
        left: list[Difference] = []
        for difference in found:
            rule = next((r for r in rules if r.matches(difference)), None)
            if rule is None:
                left.append(difference)
            else:
                excluded.append(Excluded(difference, rule.id, rule.reason))
        return tuple(left)

    differences, notices = kept(result.differences), kept(result.notices)
    return replace(result, differences=differences, notices=notices, excluded=tuple(excluded))


__all__ = [
    "ACCEPTED_ATTRIBUTIONS",
    "ATTRIBUTIONS",
    "SCHEMA",
    "Attribution",
    "Profile",
    "Rule",
    "accepted_rules",
    "apply_rules",
    "check_kind",
    "load_profiles",
    "select_profile",
]
