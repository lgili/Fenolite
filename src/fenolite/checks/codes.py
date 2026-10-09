# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes that ``checks`` emits (capability verification-loop, "Check issue codes").

``model.*`` findings and reader codes (``kicad.board.*``, ``kicad.version.*``) pass through unchanged and
are not in this table. Codes of an oracle start with its name, written ``<oracle>`` here; the row
``<oracle>.drc.<type>`` stands for every DRC finding code, whose suffix comes from the tool's own type
(``checks.drc_json.type_code``; "Findings stage issue codes").
The ``copper.*`` codes are those of the copper check (``checks.copper``; "Copper stage issue codes"), which
the build's copper guard emits too.
The last six codes are those of the document check (``checks.documents``; "Document check issue codes",
change c0044): the input of a backend whose project is a set of documents.
The row ``<oracle>.erc.<type>`` stands for every ERC finding code of an oracle (``checks.erc_json``), and
``<oracle>.drc.parity-unchecked`` says that the parity test of a DRC run was asked for and not judged ("ERC
stage issue codes", change c0062). ``type_suffix`` is the one rule that turns a tool's own type into the
last part of a code, for DRC and ERC alike.
The ``parity.*`` codes are those of the parity comparison and its stage (``checks.parity``; "Parity issue
codes", change c0072).
The last two codes report a waiver and a stored exclusion that no longer match a finding ("Waiver and
exclusion issue codes", change c0114); the ``info`` severity of the three copper finding codes is that of a
finding a waiver accepted (``checks.waivers``), which the copper check itself never gives.
The ``placement.*`` codes are those of the placement rules (``checks.placement``; "Placement stage issue
codes", change c0113, and "Height limit issue codes", change c0140); ``place`` and the placement guard of
``build`` report them at most as warnings.
The ``length.*`` codes are those of the length rules stage (``checks.length``; "Length stage issue codes",
change c0106); the governing rule sets the severity of a finding.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ORACLE = "<oracle>"
FINDING = f"{ORACLE}.drc.<type>"
"""The table key of every DRC finding code."""
ERC_FINDING = f"{ORACLE}.erc.<type>"
"""The table key of every ERC finding code."""
_OUTSIDE = re.compile(r"[^a-z0-9-]")
_RUNS = re.compile(r"-{2,}")
ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        "check.read-refused": ("error",),
        "check.cache-unreadable": ("warning",),
        "check.footprint-unresolved": ("error",),
        "check.symbol-unresolved": ("error",),
        "check.rt1-failed": ("error",),
        "check.oracle-failed": ("error",),
        "check.copy-skipped": ("info",),
        "check.report-limit": ("warning",),
        f"{ORACLE}.drc.rules-not-loaded": ("error", "info"),
        f"{ORACLE}.drc.rules-unchecked": ("warning",),
        f"{ORACLE}.drc.parity-unchecked": ("warning",),
        FINDING: ("error", "warning", "info"),
        ERC_FINDING: ("error", "warning", "info"),
        "netlist.assignment-differs": ("error",),
        "netlist.uncovered": ("info",),
        "check.rt2-failed": ("error",),
        "check.rt2-unstable": ("info",),
        "erc.lite.output-conflict": ("warning",),
        "erc.lite.power-undriven": ("warning",),
        "erc.lite.floating-pin": ("warning",),
        "render.failed": ("warning",),
        "copper.short": ("error", "info"),
        "copper.clearance": ("error", "warning", "info"),
        "copper.zone-overlap": ("warning", "info"),
        "copper.keepout": ("error",),
        "copper.rules-incomplete": ("warning",),
        "copper.item-unsupported": ("warning",),
        "copper.clearance-unset": ("info",),
        "zone.unfilled": ("warning",),
        "zone.fill-stale": ("warning",),
        "zone.fill-unchecked": ("info",),
        "check.document-missing": ("warning",),
        "check.rta0-failed": ("error",),
        "check.rta1-failed": ("error",),
        "check.rta1-normalised": ("info",),
        "check.rta2-failed": ("error",),
        "check.rta3-failed": ("error",),
        "check.rta3-unwritten": ("info",),
        "check.roundtrip-unjudged": ("info",),
        "parity.missing-footprint": ("error",),
        "parity.extra-footprint": ("error",),
        "parity.duplicate-footprints": ("error",),
        "parity.net-conflict": ("error",),
        "parity.pin-without-pad": ("error", "warning"),
        "parity.footprint-mismatch": ("warning",),
        "parity.oracle-differs": ("warning",),
        "parity.pad-without-pin": ("info",),
        "check.waiver-unmatched": ("warning",),
        "check.exclusion-stale": ("warning",),
        "placement.too-far": ("error", "warning"),
        "placement.rule-unresolved": ("error",),
        "placement.rule-skipped": ("info",),
        "placement.too-tall": ("error", "warning"),
        "placement.height-unknown": ("warning",),
        "length.out-of-range": ("error", "warning"),
        "length.skew-out-of-range": ("error", "warning"),
        "length.input-missing": ("warning",),
    }
)


def oracle_code(oracle: str, suffix: str) -> str:
    """The code ``<oracle name>.drc.<suffix>``, for example ``kicad.drc.rules-not-loaded``."""
    return f"{oracle}.drc.{suffix}"


def erc_code(oracle: str, suffix: str) -> str:
    """The code ``<oracle name>.erc.<suffix>``, for example ``kicad.erc.pin-not-connected``."""
    return f"{oracle}.erc.{suffix}"


def type_suffix(type: str) -> str:  # noqa: A002 (the report's own key)
    """The last part of a finding code for a tool's own type: lower case, every character outside
    ``[a-z0-9-]`` as ``-``, runs of ``-`` collapsed and the ends trimmed; ``unknown`` when nothing remains."""
    return _RUNS.sub("-", _OUTSIDE.sub("-", type.lower())).strip("-") or "unknown"


def table_key(code: str) -> str:
    """The ``ISSUE_CODES`` key of ``code``: an oracle's ``.drc.`` codes with ``<oracle>`` for its name, and
    ``FINDING`` for every suffix that is not a verdict of the stage; an oracle's ``.erc.`` codes give
    ``ERC_FINDING``."""
    head, sep, _ = code.partition(".erc.")
    if sep and head and "." not in head:
        return ERC_FINDING
    head, sep, rest = code.partition(".drc.")
    if not sep or "." in head:
        return code
    key = f"{ORACLE}.drc.{rest}"
    return key if key in ISSUE_CODES else FINDING


def issue(
    code: str,
    message: str,
    *,
    severity: Severity | None = None,
    where: str = "",
    hint: str = "",
    retryable: bool = False,
) -> Issue:
    """An ``Issue`` of a code of the table, with its only severity unless one of its severities is given."""
    allowed = ISSUE_CODES.get(table_key(code))
    if allowed is None:
        raise KeyError(f"{code!r} is not a check issue code")
    chosen = severity if severity is not None else allowed[0]
    if chosen not in allowed:
        raise ValueError(f"{code!r} has no severity {chosen!r}")
    return Issue(code, chosen, message, where=where, hint=hint, retryable=retryable)


__all__ = [
    "ERC_FINDING",
    "FINDING",
    "ISSUE_CODES",
    "ORACLE",
    "erc_code",
    "issue",
    "oracle_code",
    "table_key",
    "type_suffix",
]
