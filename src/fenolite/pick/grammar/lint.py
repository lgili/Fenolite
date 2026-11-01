# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The static lint of a grammar family (change c0263, ``docs/picking.md``, "Families with ordering
codes").

The lint proves, without enumerating the family, that every MPN parses one way: no code of a field is a
proper prefix of another (a value field of a fixed-width scheme is prefix-free by construction; an ``rkm``
field is checked over the family's domain), so the concatenation of fields and fixed literals decodes left
to right without backtracking. It also checks the pattern against the fields, the matrix codes, that every
value of the domain can be spelled, the ``prefer`` code of each ordering field and the sources of the
numeric attributes.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from fenolite.core.errors import Issue, Severity
from fenolite.core.partquery import VALUE_UNITS
from fenolite.pick.grammar.codes import issue
from fenolite.pick.grammar.expand import value_domain
from fenolite.pick.grammar.schema import NUMERIC_UNITS, GrammarFamily, MatrixRow
from fenolite.pick.grammar.valuecodes import WIDTHS, encode_value
from fenolite.pick.rows import value_text

SOURCED: tuple[str, ...] = ("tolerance", *NUMERIC_UNITS)
"""The numeric code attributes whose source a family must name, beside ``value``."""


def prefix_pairs(texts: Iterable[str]) -> list[tuple[str, str]]:
    """Every ``(a, b)`` of ``texts`` where ``a`` is a proper prefix of ``b``, in code-point order."""
    ordered = sorted(set(texts))
    pairs: list[tuple[str, str]] = []
    for index, first in enumerate(ordered):
        for second in ordered[index + 1 :]:
            if not second.startswith(first):
                break  # in code-point order, the strings that start with ``first`` follow it directly
            pairs.append((first, second))
    return pairs


def _pattern(family: GrammarFamily) -> list[Issue]:
    found: list[Issue] = []
    placeholders = family.placeholders
    for name in sorted({name for name in placeholders if name not in family.fields}):
        found.append(
            issue(
                "family.pattern-field",
                f"{family.id}: the placeholder {{{name}}} names no field",
                f"pattern.{name}",
            )
        )
    for name, count in sorted(Counter(placeholders).items()):
        if count > 1:
            found.append(
                issue(
                    "family.pattern-field",
                    f"{family.id}: the field {name} appears {count} times in the pattern",
                    f"pattern.{name}",
                )
            )
    for name in family.fields:
        if name not in placeholders:
            found.append(
                issue(
                    "family.pattern-field",
                    f"{family.id}: the field {name} has no placeholder in the pattern",
                    f"fields.{name}",
                    f"add {{{name}}} to the pattern, or remove the field",
                )
            )
    values = [name for name, item in family.fields.items() if item.is_value]
    if len(values) != 1:
        found.append(
            issue(
                "family.pattern-field",
                f"{family.id}: {len(values)} value fields ({', '.join(values) or 'none'}); exactly one "
                "field has a scheme",
                "fields",
            )
        )
    return found


def _ambiguous(family: GrammarFamily) -> list[Issue]:
    found: list[Issue] = []
    for name, item in family.fields.items():
        if item.is_value:
            if item.scheme in WIDTHS:
                continue
            texts = [encode_value(item.scheme, value, item.scale) for value in value_domain(family)]
            spelled = [text for text in texts if text is not None]
        else:
            spelled = [code.code for code in item.codes]
        for first, second in prefix_pairs(spelled):
            found.append(
                issue(
                    "family.ambiguous-code",
                    f"{family.id}: in the field {name}, the code {first} is a proper prefix of {second}",
                    f"fields.{name}",
                    "make the codes of a field prefix-free, or split the family or the field",
                )
            )
    return found


def _matrix(family: GrammarFamily, rows: Iterable[MatrixRow], table: str) -> list[Issue]:
    found: list[Issue] = []
    for row in rows:
        for name, allowed in row.codes.items():
            item = family.fields[name]
            for code in allowed:
                if item.code(code) is None:
                    found.append(
                        issue(
                            "family.matrix-unknown-code",
                            f"{family.id}: [[{table}]] row {row.index} names the code {code}, which "
                            f"the field {name} lacks",
                            f"{table}[{row.index}].{name}",
                        )
                    )
    return found


def _unencodable(family: GrammarFamily) -> list[Issue]:
    value_field = family.value_field
    if value_field is None:
        return []
    found: list[Issue] = []
    for row in family.valid:
        missing = [
            value
            for value in value_domain(family, (row,))
            if encode_value(value_field.scheme, value, value_field.scale) is None
        ]
        if missing:
            unit = VALUE_UNITS[family.kind]
            shown = ", ".join(value_text(unit, value) for value in missing[:5])
            found.append(
                issue(
                    "family.value-unencodable",
                    f"{family.id}: [[valid]] row {row.index} admits {len(missing)} value(s) that "
                    f"{value_field.scheme} in {value_field.unit} cannot spell ({shown})",
                    f"valid[{row.index}].{value_field.name}",
                    "cut the row's span to what the scheme can spell, or change the field's unit",
                )
            )
    return found


def _prefer(family: GrammarFamily) -> list[Issue]:
    found: list[Issue] = []
    for name, item in family.fields.items():
        if item.role != "ordering":
            continue
        if not item.prefer or item.code(item.prefer) is None:
            found.append(
                issue(
                    "family.prefer-missing",
                    f"{family.id}: the ordering field {name} "
                    + (
                        f"prefers {item.prefer}, which is not one of its codes"
                        if item.prefer
                        else "names no prefer"
                    ),
                    f"fields.{name}.prefer",
                    "name the code encode uses, one of the field's codes",
                )
            )
    return found


def _sources(family: GrammarFamily) -> list[Issue]:
    stated = {
        attribute
        for item in family.fields.values()
        for code in item.codes
        for attribute in code.attributes
        if attribute in SOURCED
    }
    needed = sorted(stated) + ["value"]
    if family.sources:
        return []
    return [
        issue(
            "family.source-missing",
            f"{family.id}: the attribute {name} names no source",
            f"sources.{name}",
            "list the datasheet in sources, or give sources.<attribute>",
        )
        for name in needed
        if not family.sources_by.get(name)
    ]


def _empty(family: GrammarFamily) -> list[Issue]:
    found: list[Issue] = []
    for row in family.valid:
        named_known = all(
            any(family.fields[name].code(code) is not None for code in allowed)
            for name, allowed in row.codes.items()
        )
        if named_known and (family.value_field is None or value_domain(family, (row,))):
            continue
        found.append(
            issue(
                "family.matrix-empty-row",
                f"{family.id}: [[valid]] row {row.index} admits no combination",
                f"valid[{row.index}]",
            )
        )
    return found


def lint_family(family: GrammarFamily) -> list[Issue]:
    """Every finding of ``family``: errors first in check order, then warnings."""
    found = [
        *_pattern(family),
        *_ambiguous(family),
        *_matrix(family, family.valid, "valid"),
        *_matrix(family, family.exclude, "exclude"),
        *_unencodable(family),
        *_prefer(family),
        *_sources(family),
        *_empty(family),
    ]
    order: dict[Severity, int] = {"error": 0, "warning": 1, "info": 2}
    return sorted(found, key=lambda item: order[item.severity])


def errors(family: GrammarFamily) -> list[Issue]:
    """The error findings of ``family``: a family with any is not used to pick or decode."""
    return [found for found in lint_family(family) if found.severity == "error"]


__all__ = ["SOURCED", "errors", "lint_family", "prefix_pairs"]
