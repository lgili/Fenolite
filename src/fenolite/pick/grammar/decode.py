# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Decode: an MPN read back into its parameters (change c0263, ``docs/picking.md``, "Families with
ordering codes").

The MPN is parsed left to right against each family, in code-point order of the family ids: a literal must
match, a code field takes the one code that starts at the position (its codes are prefix-free, so there is
at most one), a fixed-width value field takes its width and decodes the canonical spelling, an ``rkm`` field
takes the one spelling of the family's domain that starts there. What is left after the last field is the
opaque ``suffix`` of a ``tail = "opaque"`` family, kept unread; for ``tail = "none"`` it fails the parse.
A parse gives every attribute, the value and ``in_matrix``; no parse gives ``family.decode-no-match`` with
the position and the field that failed, per family whose literal prefix matched.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.partquery import VALUE_UNITS
from fenolite.pick.grammar.codes import EVIDENCE, issue, label_evidence
from fenolite.pick.grammar.expand import Candidate, admitted, value_domain
from fenolite.pick.grammar.schema import GrammarFamily
from fenolite.pick.grammar.valuecodes import WIDTHS, decode_value, encode_value
from fenolite.pick.rows import value_text

TAIL = re.compile(r"[A-Z0-9#/-]+")
"""The characters an opaque tail may hold."""


@dataclass(frozen=True, slots=True)
class Decoded:
    """One full parse: the candidate (with its ``suffix``), whether the validity matrix admits it, and its
    evidence."""

    candidate: Candidate
    in_matrix: bool
    evidence: Evidence

    def as_json(self) -> dict[str, object]:
        """``mpn``, ``family``, ``device``, ``manufacturer``, ``value``, every attribute as written, the codes
        by field, ``suffix``, ``in_matrix`` and ``evidence``."""
        found = self.candidate
        texts = found.code_texts()
        return {
            "mpn": found.mpn + found.suffix,
            "family": found.family.id,
            "device": found.device,
            "manufacturer": found.family.manufacturer,
            "value": value_text(VALUE_UNITS[found.family.kind], found.value),
            **{name: texts[name] for name in sorted(texts)},
            "codes": dict(found.codes),
            "suffix": found.suffix or None,
            "in_matrix": self.in_matrix,
            "evidence": self.evidence.label(),
        }


@dataclass(frozen=True, slots=True)
class Failure:
    """Where the parse of an MPN by a family stopped: the character ``position`` (from 0) and the field
    (``end`` for characters left after the last field)."""

    family: str
    position: int
    field: str


@dataclass(frozen=True, slots=True)
class DecodeResult:
    """The full parses of one MPN, the failures of the families whose literal prefix matched, and the
    findings."""

    mpn: str
    decoded: tuple[Decoded, ...]
    failures: tuple[Failure, ...]
    issues: tuple[Issue, ...]


def _spellings(family: GrammarFamily) -> tuple[str, ...]:
    value_field = family.value_field
    assert value_field is not None
    found = (encode_value(value_field.scheme, value, value_field.scale) for value in value_domain(family))
    return tuple(sorted({text for text in found if text is not None}))


def parse_mpn(family: GrammarFamily, mpn: str) -> Candidate | Failure:
    """The candidate of the one parse of ``mpn`` by ``family`` (``suffix`` set for an opaque tail), or where
    the parse failed."""
    value_field = family.value_field
    if value_field is None:
        return Failure(family.id, 0, "pattern")
    position = 0
    codes: list[tuple[str, str]] = []
    value = None
    for kind, text in family.tokens:
        if kind == "literal":
            if not mpn.startswith(text, position):
                return Failure(family.id, position, f"literal {text}")
            position += len(text)
            continue
        item = family.fields.get(text)
        if item is None:
            return Failure(family.id, position, text)
        rest = mpn[position:]
        if item.is_value:
            width = WIDTHS.get(item.scheme)
            if width is not None:
                spelled = rest[:width]
            else:
                spelled = next((found for found in _spellings(family) if rest.startswith(found)), "")
            value = decode_value(item.scheme, spelled, item.scale) if spelled else None
            if value is None:
                return Failure(family.id, position, text)
            codes.append((text, spelled))
            position += len(spelled)
            continue
        found = next((code.code for code in item.codes if rest.startswith(code.code)), None)
        if found is None:
            return Failure(family.id, position, text)
        codes.append((text, found))
        position += len(found)
    suffix = mpn[position:]
    if suffix and (family.tail != "opaque" or not TAIL.fullmatch(suffix)):
        return Failure(family.id, position, "end")
    assert value is not None
    return Candidate(family, mpn[:position], tuple(codes), value, suffix)


def decode(mpn: str, families: Sequence[GrammarFamily]) -> DecodeResult:
    """Decode ``mpn`` against every family of ``families`` in id order."""
    decoded: list[Decoded] = []
    failures: list[Failure] = []
    for family in sorted(families, key=lambda item: item.id):
        found = parse_mpn(family, mpn)
        if isinstance(found, Failure):
            if mpn.startswith(family.literal_prefix):
                failures.append(found)
            continue
        value_field = family.value_field
        assert value_field is not None
        codes = {name: code for name, code in found.codes if name != value_field.name}
        in_matrix = admitted(family, codes, found.value)
        evidence = Evidence.combine(EVIDENCE, label_evidence(family.evidence))
        if found.suffix:
            evidence = Evidence(Level.UNVERIFIED, hypotheses=evidence.hypotheses)
        decoded.append(Decoded(found, in_matrix, evidence))
    issues: list[Issue] = []
    if not decoded:
        detail = "; ".join(
            f"{item.family} fails at position {item.position}, field {item.field}" for item in failures
        )
        issues.append(
            issue(
                "family.decode-no-match",
                f"{mpn}: no family parses it"
                + (f" ({detail})" if detail else "; no family's literal prefix matches"),
                mpn,
                "check the MPN, or add or complete the family's grammar",
            )
        )
    elif len(decoded) > 1:
        names = " and ".join(item.candidate.family.id for item in decoded)
        issues.append(
            issue(
                "family.decode-ambiguous",
                f"{mpn}: parsed by {names}",
                mpn,
                "make the families' literal prefixes or codes distinct",
            )
        )
    for item in decoded:
        if not item.in_matrix:
            issues.append(
                issue(
                    "family.decode-outside-matrix",
                    f"{mpn}: parses in {item.candidate.family.id} outside its validity matrix; the grammar "
                    "may be incomplete, or the part may not exist",
                    mpn,
                )
            )
        if item.candidate.suffix:
            issues.append(
                issue(
                    "family.suffix-opaque",
                    f"{mpn}: the tail {item.candidate.suffix} is kept unread; it may change what the other "
                    "fields mean, so the decode is UNVERIFIED",
                    mpn,
                )
            )
    return DecodeResult(mpn, tuple(decoded), tuple(failures), tuple(issues))


__all__ = ["TAIL", "DecodeResult", "Decoded", "Failure", "decode", "parse_mpn"]
