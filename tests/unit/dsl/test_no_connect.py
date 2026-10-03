# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""No-connect marks of the DSL (capability design-dsl, "No-connect marks in the DSL"; change c0036)."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, Net, Part, connect, no_connect, to_model
from fenolite.model.circuit import PinRef


def one_part() -> tuple[Design, Part]:
    d, u1 = Design("t"), Part("U1", "Mini:Mini_QFP32_IC")
    d.add(u1)
    return d, u1


def _id(d: Design, ref: str) -> str:
    return next(c.id for c in to_model(d).circuit.components if c.ref == ref)


def test_marks_in_the_model() -> None:
    d, u1 = one_part()
    no_connect(u1[12], u1[11], u1["11"])
    circuit = to_model(d).circuit
    u1_id = _id(d, "U1")
    assert circuit.no_connects == (PinRef(u1_id, "11"), PinRef(u1_id, "12"))
    assert circuit.components[0].pins == () and circuit.nets == ()
    assert u1.no_connects == {"11", "12"}


def test_marking_a_connected_designator() -> None:
    d, u1 = one_part()
    en = Net("EN")
    connect(en, u1[11])
    with pytest.raises(DslError, match=r"U1 11 .*EN"):
        no_connect(u1[11])
    model = to_model(d)
    assert model.circuit.no_connects == ()
    assert model.circuit.nets[0].members == (PinRef(_id(d, "U1"), "11"),)


def test_connecting_a_marked_designator() -> None:
    d, u1 = one_part()
    en = Net("EN")
    no_connect(u1[11])
    with pytest.raises(DslError, match=r"U1 11"):
        connect(en, u1[11])
    assert u1.connections == {} and "EN" not in d.nets
    assert to_model(d).circuit.no_connects == (PinRef(_id(d, "U1"), "11"),)


def test_a_refused_call_marks_nothing() -> None:
    d, u1 = one_part()
    connect(Net("EN"), u1[11])
    with pytest.raises(DslError):
        no_connect(u1[12], u1[11])
    assert u1.no_connects == set() and to_model(d).circuit.no_connects == ()


@pytest.mark.parametrize("bad", ["U1.11", 11, None])
def test_not_a_pin_handle(bad: object) -> None:
    with pytest.raises(DslError, match="no_connect"):
        no_connect(bad)  # type: ignore[arg-type]


def test_a_part_is_not_a_pin_handle() -> None:
    _, u1 = one_part()
    with pytest.raises(DslError):
        no_connect(u1)  # type: ignore[arg-type]
    assert u1.no_connects == set()


def test_no_arguments_does_nothing() -> None:
    d, _ = one_part()
    no_connect()
    assert to_model(d).circuit.no_connects == ()


def test_several_parts_in_one_call_and_name_designators() -> None:
    d, u1 = one_part()
    r1 = Part("R1", "Mini:Mini_R")
    d.add(r1)
    no_connect(u1["TP"], r1[2])
    assert to_model(d).circuit.no_connects == tuple(
        sorted((PinRef(_id(d, "U1"), "TP"), PinRef(_id(d, "R1"), "2")))
    )


def test_a_mark_follows_its_part() -> None:
    d = Design("t")
    early, never = Part("U1", "Mini:Mini_QFP32_IC"), Part("U2", "Mini:Mini_QFP32_IC")
    no_connect(early[3], never[4])
    d.add(early)
    late = Part("U3", "Mini:Mini_QFP32_IC")
    d.add(late)
    no_connect(late[5])
    assert to_model(d).circuit.no_connects == tuple(
        sorted((PinRef(_id(d, "U1"), "3"), PinRef(_id(d, "U3"), "5")))
    )


def test_re_export() -> None:
    import fenolite.dsl

    assert no_connect.__module__ == "fenolite.dsl.part"
    assert "no_connect" in fenolite.dsl.__all__ and not hasattr(Part, "no_connect")
