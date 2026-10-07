# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A design that declares no placement rule writes the bytes it wrote before ``RuleSet.proximity`` existed
(change c0113; capability design-model, "Proximity rules in the model").

The recorded digests of the two blink examples are those of ``test_unused_keys.py`` (change c0114), which
this change leaves as it is and which still passes with the new field: no byte of those builds moved.
What is kept here is what makes those bytes stay: the key is left out of every written form when it is
empty, and adding a rule changes ``rules.json`` and nothing else of the model.
"""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest
from _buildhelp import build

from fenolite.dsl import Design, mm, to_model
from fenolite.model import canonical

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
SCRIPTS = ("blink_2layer", "blink_routed")
KEY = "proximity"


def example(name: str) -> tuple[Design, dict[str, object]]:
    scope = runpy.run_path(str(EXAMPLES / name / "design.py"))
    design = scope["design"]
    assert isinstance(design, Design)
    return design, scope


@pytest.mark.parametrize("name", SCRIPTS)
def test_unused_keys_are_not_in_the_model_texts(name: str) -> None:
    design, _ = example(name)
    texts = canonical.dump_texts(to_model(design))
    assert KEY not in json.loads(texts["rules.json"])
    assert f'"{KEY}"' not in "".join(texts.values())


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("name", SCRIPTS)
def test_unused_keys_are_not_in_the_built_cache(name: str, target: int) -> None:
    design, _ = example(name)
    output = build(design, target, project_dir=EXAMPLES / name)
    rules = output.files[".fenolite/rules.json"].decode("utf-8")
    assert KEY not in json.loads(rules)
    again = build(example(name)[0], target, project_dir=EXAMPLES / name)
    assert dict(again.files) == dict(output.files)


@pytest.mark.parametrize("name", SCRIPTS)
def test_unused_keys_change_only_the_rules_layer_when_used(name: str) -> None:
    plain, _ = example(name)
    before = canonical.dump_texts(to_model(plain))
    design, scope = example(name)
    design.near("led", scope["d1"], scope["r1"].pad(2), within=mm(5))  # type: ignore[attr-defined]
    after = canonical.dump_texts(to_model(design))
    assert {file for file in before if before[file] != after[file]} == {"rules.json"}
    rules = json.loads(after["rules.json"])
    assert list(rules)[-1] == KEY and len(rules[KEY]) == 1
    del rules[KEY]
    assert rules == json.loads(before["rules.json"])
