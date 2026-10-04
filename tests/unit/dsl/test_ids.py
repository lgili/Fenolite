# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ids keyed by names and paths (capability design-model, MODIFIED "Identifier derivation", fourth case;
change c0011)."""

from __future__ import annotations

from fenolite.core.ids import derived_id
from fenolite.dsl import KEYS, Design, Net, Part, connect, to_model
from fenolite.dsl.convert import key_id


def design(order: list[str], extra: str | None = None) -> Design:
    d = Design("t")
    parts = {ref: Part(ref, "Mini:Mini_R") for ref in order}
    if extra:
        parts[extra] = Part(extra, "Mini:Mini_R")
    for ref in order + ([extra] if extra else []):
        d.add(parts[ref])
    connect(Net("A"), *(p["1"] for p in parts.values()))
    return d


def ids(d: Design) -> dict[str, str]:
    model = to_model(d)
    return {c.ref: c.id for c in model.circuit.components} | {n.name: n.id for n in model.circuit.nets}


def test_dsl_ids_ignore_the_seed_and_the_order() -> None:
    assert ids(design(["R1", "R2"])) == ids(design(["R2", "R1"]))
    assert to_model(design(["R1"])).header.id == derived_id("dsn", "dsl", "design")


def test_keys_not_order() -> None:
    assert key_id("component", "power/C1") == derived_id("cmp", "dsl", "component:power/C1")
    assert key_id("pin", "R1", "1") == derived_id("pin", "dsl", "pin:R1:1")
    assert key_id("interface", "power", "VIN/GND") == derived_id("itf", "dsl", "interface:power:VIN/GND")
    assert key_id("net", "GND") == derived_id("net", "dsl", "net:GND")
    assert set(KEYS) == {
        "design", "board", "outline", "rules", "manifest", "module", "component", "pin", "net", "netclass",
        "interface", "layer", "zone", "rule",
    }  # fmt: skip


def test_inserting_a_part_keeps_other_ids() -> None:
    before = ids(design(["R1", "R3"]))
    after = ids(design(["R1", "R3"], extra="R2"))
    assert {k: after[k] for k in before} == before
