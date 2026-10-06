# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Verification evidence: the label grammar, the hypothesis register and the release rule.

Stdlib only; imports nothing from ``fenolite`` but ``core`` (reading Markdown registers needs no model).
"""

from fenolite.verify.evidence import (
    RELEASE_VERIFIED,
    is_release_evidence,
    release_verified,
    report_problems,
)
from fenolite.verify.hypotheses import (
    FAMILIES_HEADER,
    ID_PATTERN,
    REGISTER_HEADER,
    HypothesisRow,
    cited_ids,
    load_families,
    load_register,
    parse_level,
    proposed_ids,
)

__all__ = [
    "FAMILIES_HEADER",
    "ID_PATTERN",
    "REGISTER_HEADER",
    "RELEASE_VERIFIED",
    "HypothesisRow",
    "cited_ids",
    "is_release_evidence",
    "load_families",
    "load_register",
    "parse_level",
    "proposed_ids",
    "release_verified",
    "report_problems",
]
