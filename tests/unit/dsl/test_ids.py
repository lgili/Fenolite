# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ids keyed by names and paths (capability design-model, MODIFIED "Identifier derivation", fourth case;
change c0011)."""

from __future__ import annotations

from fenolite.core.ids import derived_id
from fenolite.dsl import KEYS, Design, Net, Part, connect, mm, to_model
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
        "interface", "layer", "zone", "rule", "stackup", "stack_layer", "area", "text", "graphic",
        "dimension", "impedance",
    }  # fmt: skip


def test_inserting_a_part_keeps_other_ids() -> None:
    before = ids(design(["R1", "R3"]))
    after = ids(design(["R1", "R3"], extra="R2"))
    assert {k: after[k] for k in before} == before


def test_board_items_ids_from_names_and_keys() -> None:
    """Scenario "Area and drawing ids from names and keys" (change c0103)."""
    square = [(mm(0), mm(0)), (mm(10), mm(0)), (mm(10), mm(10))]
    models = []
    for reverse in (False, True):
        d = Design("items")
        d.board(mm(50), mm(30))
        calls = [
            lambda d=d: d.rule_area("ANT", square, forbid=("tracks",)),
            lambda d=d: d.rule_area("HV", square),
            lambda d=d: d.text("rev", "REV A", (mm(2), mm(2))),
            lambda d=d: d.dimension("width", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-5)),
        ]
        for call in reversed(calls) if reverse else calls:
            call()
        models.append(to_model(d))
    for model in models:
        board = model.board
        assert board is not None
        assert [k.id for k in board.keepouts] == [
            derived_id("kpo", "dsl", "area:ANT"), derived_id("kpo", "dsl", "area:HV")
        ]  # fmt: skip
        assert board.texts[0].id == derived_id("txt", "dsl", "text:rev")
        assert board.dimensions[0].id == derived_id("dim", "dsl", "dimension:width")
    assert models[0].board == models[1].board
    assert KEYS["area"] == ("kpo", "area:<area name>") and KEYS["text"] == ("txt", "text:<drawing key>")
    assert KEYS["graphic"] == ("gfx", "graphic:<drawing key>")
    assert KEYS["dimension"] == ("dim", "dimension:<drawing key>")
    assert key_id("area", "ANT") == derived_id("kpo", "dsl", "area:ANT")
