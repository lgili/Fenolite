# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The export kind ``altium-rul``: the rules of a project as an Altium rule file (capability
manufacturing-exports, "Altium rule file export"; change c0084; user guide ``docs/exports.md``).

No tool runs. The rules are those of the project's own rules file, lowered by
``backends.altium.rulemap.lower``; a rule that has no exact Altium form is named in the result with its
reason, and never written approximately. Altium's PCB Rules editor imports the file into a board.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.core.evidence import Evidence
from fenolite.model.rules import Rule

KIND = "altium-rul"
SUFFIX = ".RUL"


@dataclass(frozen=True, slots=True)
class RuleFileExport:
    """The file of one export: its name, its bytes (empty when no rule is written), the rules written and
    the rules that are not, each as ``{kind, selector}`` (the first with ``rule``, the record's name; the
    second with ``reason``), and the evidence."""

    path: str
    data: bytes
    written: tuple[dict[str, str], ...]
    not_lowered: tuple[dict[str, str], ...]
    evidence: Evidence


def export_rules(rules: Sequence[Rule], *, stem: str) -> RuleFileExport:
    """``<stem>.RUL`` for ``rules``: the bytes of ``rulemap.write_rule_file`` and what was written."""
    from fenolite.backends.altium import rulemap  # a backend is imported only when the kind is asked for

    lowered = rulemap.lower(rules)
    written = tuple(
        {"kind": rule.kind, "selector": rulemap.rule_selector(rule), "rule": record.name}
        for record in lowered.records
        for rule in record.rules
    )
    refused = tuple(
        {"kind": item.kind, "selector": item.selector, "reason": item.reason} for item in lowered.not_lowered
    )
    data = rulemap.write_rule_file(rules, name=stem)
    return RuleFileExport(f"{stem}{SUFFIX}", data, written, refused, rulemap.EVIDENCE)


__all__ = ["KIND", "SUFFIX", "RuleFileExport", "export_rules"]
