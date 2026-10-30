# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The finding codes of grammar families and their evidence (change c0263; ``docs/cli-contract.md``,
"family")."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "family.ambiguous-code": "error",
        "family.pattern-field": "error",
        "family.matrix-unknown-code": "error",
        "family.value-unencodable": "error",
        "family.prefer-missing": "error",
        "family.source-missing": "error",
        "family.decode-no-match": "error",
        "family.decode-ambiguous": "error",
        "family.expansion-limit": "error",
        "family.matrix-empty-row": "warning",
        "family.decode-outside-matrix": "warning",
        "family.suffix-opaque": "info",
    }
)
"""Code → severity of every finding of ``fenolite.pick.grammar``; ``fenolite explain`` explains each."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-FAMILY-ROUNDTRIP",))
"""The evidence of lint, expansion, encode and decode: decode ∘ encode is the identity on every expanded
MPN of the authored grammars and on every canonical value of each scheme (property tests). A reply
combines it with each family's own label (lowest wins); a decode with an opaque tail is ``UNVERIFIED``."""


def label_evidence(label: str) -> Evidence:
    """The ``Evidence`` of a record's label (``ORACLE-VERIFIED(kicad)``, ``INFERRED``, …); a label this
    version does not know is ``UNVERIFIED``."""
    if label.startswith("ORACLE-VERIFIED(") and label.endswith(")"):
        return Evidence(Level.ORACLE_VERIFIED, oracle=label[len("ORACLE-VERIFIED(") : -1])
    if label.startswith("ALTIUM-VERIFIED(kit"):
        return Evidence(Level.ALTIUM_VERIFIED_KIT)
    if label.startswith("ALTIUM-VERIFIED(author-report"):
        return Evidence(Level.ALTIUM_VERIFIED_AUTHOR_REPORT)
    try:
        return Evidence(Level(label))
    except ValueError:
        return Evidence(Level.UNVERIFIED)


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    """The finding ``code`` with its severity of ``ISSUE_CODES``."""
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


__all__ = ["EVIDENCE", "ISSUE_CODES", "issue", "label_evidence"]
