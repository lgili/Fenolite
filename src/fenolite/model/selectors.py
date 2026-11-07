# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""How a rule selector is matched against a rule subject, names compared without regard to letter case.

Moved from fenolite.checks.clearance (change c0462) so that convert, which may not import checks
(capability package-layering), matches Altium rule scopes as the checks do. checks.clearance re-exports
selector_matches.
"""

from __future__ import annotations

import dataclasses

from fenolite.model.rules import CASED_LEAVES, LEAF_OPS, RuleSubject, Selector


def _fold(text: str | None) -> str | None:
    return None if text is None else text.casefold()


def fold_selector(selector: Selector) -> Selector:
    """``selector`` with every leaf value case-folded: names compare without regard to letter case. An
    ``area`` leaf is kept as written: KiCad compares area names with letter case (``H-K-AREA-COND``). A
    ``diff_pair`` leaf keeps its value too, because KiCad compares a pair base with its letter case
    (``H-K-DRU-PAIRSEL``). A ``zone``, ``hole`` or ``pad_type`` leaf is kept too
    (``model.rules.CASED_LEAVES``)."""
    if selector.op in CASED_LEAVES:
        return selector
    if selector.op in LEAF_OPS:
        return dataclasses.replace(selector, value=selector.value.casefold())
    if selector.items:
        return dataclasses.replace(selector, items=tuple(fold_selector(item) for item in selector.items))
    return selector


def fold_subject(subject: RuleSubject) -> RuleSubject:
    return RuleSubject(
        item_kind=subject.item_kind.casefold(),
        net=_fold(subject.net),
        netclass=_fold(subject.netclass),
        ref=_fold(subject.ref),
        layer=_fold(subject.layer),
        areas=subject.areas,
        diff_pair=subject.diff_pair,
        zone=subject.zone,
        hole=subject.hole,
        pad_type=subject.pad_type,
    )


def selector_matches(selector: Selector, subject: RuleSubject) -> bool:
    """Whether ``selector`` selects ``subject``, names compared as the clearance rules compare them: without
    regard to letter case, except an ``area`` leaf and a ``diff_pair`` leaf (``fold_selector``). The
    length stage (``checks.length``) matches its rules with it."""
    return fold_selector(selector).matches(fold_subject(subject))


__all__ = ["fold_selector", "fold_subject", "selector_matches"]
