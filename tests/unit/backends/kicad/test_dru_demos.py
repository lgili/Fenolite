# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The demo custom-rules files read and written again (capability corpus-policy, "Project and rules
corpus rows"; change c0010): every cached ``dru`` row is read with ``read_rules``, written with
``write_rules(…, target=10)`` and read again equal. Items are named by their manifest id only."""

from __future__ import annotations

import dataclasses

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.kicad.dru import read_rules, write_rules
from fenolite.model.rules import RuleSet

pytestmark = pytest.mark.needs_corpus
ROWS = [i for i in manifest_items("project") if i.path.suffix == ".kicad_dru"]


def plain(ruleset: RuleSet) -> RuleSet:
    return dataclasses.replace(
        ruleset, provenance=None, rules=tuple(dataclasses.replace(r, provenance=None) for r in ruleset.rules)
    )


@pytest.mark.parametrize("item", ROWS, ids=lambda i: i.id)
def test_demo_rules_round_trip(item: CorpusItem) -> None:
    text = require(item).read_text(encoding="utf-8")
    ruleset = read_rules(text, file=item.id)
    assert plain(read_rules(write_rules(ruleset, target=10))) == plain(ruleset), item.id
