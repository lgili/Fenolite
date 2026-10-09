# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Impedance targets in the DSL (capability design-dsl, "Impedance targets in the DSL"; change c0105)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from _zdesign import zdesign

from fenolite import dsl
from fenolite.dsl import USB2, Design, DiffPair, DslError, Net, mm, ohm, to_model, trace
from fenolite.dsl.convert import key_id
from fenolite.model.rules import Rule, Selector, TraceGeometry


def _usb() -> tuple[Design, USB2]:
    d = Design("z")
    usb_p, usb_n = Net("USB_P"), Net("USB_N")
    d.rules.netclass("USB90", clearance=mm(0.2), nets=(usb_p, usb_n))
    return d, USB2(usb_p, usb_n, name="USB")


def _se() -> Design:
    d = Design("z")
    d.rules.netclass("SE50", nets=(Net("CLK"), Net("CLK2")))
    return d


def _rules(d: Design) -> dict[str, Rule]:
    rules = to_model(d).rules
    assert rules is not None
    return {rule.name: rule for rule in rules.rules}


SE_TRACES = (trace("F.Cu", refs="In1.Cu", width=mm(0.35)), trace("B.Cu", refs="In2.Cu", width=mm(0.35)))


def test_trace_is_reexported() -> None:
    assert dsl.trace is trace and "trace" in dsl.__all__


def test_call_single_ended_target_on_a_class() -> None:
    d = _se()
    d.rules.minimum(track_width=mm(0.1))
    d.rules.impedance("SE50", ohms=ohm(50), netclass="SE50", layers=SE_TRACES)
    model = to_model(d)
    assert model.rules is not None
    (target,) = model.rules.impedance
    assert (target.name, target.kind, target.ohms, target.tolerance_percent) == ("SE50", "single", "50", "")
    assert target.id == key_id("impedance", "SE50")
    assert target.netclass_ids == (key_id("netclass", "SE50"),)
    assert target.layers == (
        TraceGeometry("F.Cu", ("In1.Cu",), 350_000),
        TraceGeometry("B.Cu", ("In2.Cu",), 350_000),
    )
    names = [rule.name for rule in model.rules.rules]
    assert names == ["min_track_width", "track_width_SE50_F.Cu", "track_width_SE50_B.Cu"]
    for rule, layer in zip(model.rules.rules[1:], ("F.Cu", "B.Cu"), strict=True):
        assert rule.kind == "track_width" and rule.layers == (layer,)
        assert rule.min == rule.opt == rule.max == 350_000
        assert (rule.priority, rule.severity) == (1, "error")
        assert rule.selector_a == Selector("netclass", "SE50")


def test_call_pair_target() -> None:
    d, usb = _usb()
    d.rules.impedance(
        "USB90",
        ohms=90,
        pair=usb,
        tolerance=10,
        layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.2), gap=mm(0.15)),),
    )
    model = to_model(d)
    assert model.rules is not None
    (target,) = model.rules.impedance
    assert (target.kind, target.tolerance_percent) == ("differential", "10")
    assert target.netclass_ids == (key_id("netclass", "USB90"),)
    rules = _rules(d)
    assert rules["track_width_USB90_F.Cu"].min == 200_000
    gap = rules["diff_pair_gap_USB90_F.Cu"]
    assert gap.min == gap.opt == gap.max == 150_000 and gap.layers == ("F.Cu",)
    assert gap.kind == "diff_pair_gap" and gap.selector_a == Selector("netclass", "USB90")
    assert "USB" in d.interfaces


def test_two_gaps() -> None:
    d, usb = _usb()
    d.rules.impedance(
        "USB90",
        ohms=90,
        pair=usb,
        layers=(
            trace("In2.Cu", refs=("B.Cu", "In1.Cu"), width=mm(0.15), gap=mm(0.2)),
            trace("F.Cu", refs="In1.Cu", width=mm(0.2), gap=mm(0.15)),
        ),
    )
    rules = _rules(d)
    assert (rules["diff_pair_gap_USB90_F.Cu"].min, rules["diff_pair_gap_USB90_F.Cu"].layers) == (
        150_000,
        ("F.Cu",),
    )
    inner = rules["diff_pair_gap_USB90_In2.Cu"]
    assert inner.min == inner.opt == inner.max == 200_000 and inner.layers == ("In2.Cu",)
    assert all(rule.layers for rule in rules.values())
    model = to_model(d)
    assert model.rules is not None
    assert [row.layer for row in model.rules.impedance[0].layers] == ["F.Cu", "In2.Cu"]
    assert model.rules.impedance[0].layers[1].references == ("In1.Cu", "B.Cu")


def test_call_decimal_ohms_text() -> None:
    d = _se()
    d.rules.impedance("SE50", ohms=ohm("42.5"), netclass="SE50", tolerance="7.50", layers=SE_TRACES)
    model = to_model(d)
    assert model.rules is not None
    assert (model.rules.impedance[0].ohms, model.rules.impedance[0].tolerance_percent) == ("42.5", "7.5")


def _call(d: Design, **changes: object) -> None:
    arguments: dict[str, object] = {"ohms": ohm(50), "netclass": "SE50", "layers": SE_TRACES, **changes}
    d.rules.impedance(str(arguments.pop("name", "SE50")), **arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"ohms": 50.0}, "50.0"),
        ({"ohms": "fifty"}, "not a positive number"),
        ({"ohms": 0}, "above 0"),
        ({"ohms": True}, "not a positive number"),
        ({"ohms": mm(1)}, "not a positive number"),
        ({"tolerance": 100}, "below 100"),
        ({"tolerance": 2.5}, "float"),
        ({"name": ""}, "non-empty"),
        ({"netclass": None}, "one of the two"),
        ({"pair": "USB"}, "one of the two"),
        ({"layers": ()}, "non-empty"),
        ({"layers": ("F.Cu",)}, "not a trace()"),
        ({"layers": (SE_TRACES[0], SE_TRACES[0])}, "given twice"),
        (
            {"layers": (SE_TRACES[0], trace("B.Cu", refs="In2.Cu", width=mm(0.3), gap=mm(0.1)))},
            "some traces only",
        ),
        ({"priority": -1}, "priority"),
    ],
)
def test_call_refused(changes: dict[str, object], words: str) -> None:
    d = _se()
    with pytest.raises(DslError, match=words.replace("(", r"\(").replace(")", r"\)")):
        _call(d, **changes)
    assert d.rules.impedance_targets == {}


def test_call_name_twice() -> None:
    d = _se()
    _call(d)
    with pytest.raises(DslError, match="twice"):
        _call(d)


@pytest.mark.parametrize(
    "make",
    [
        lambda: trace("F.Cu", refs=("In1.Cu", "In1.Cu"), width=mm(0.2)),
        lambda: trace("F.Cu", refs=("In1.Cu", "In2.Cu", "B.Cu"), width=mm(0.2)),
        lambda: trace("F.Cu", refs="F.Cu", width=mm(0.2)),
        lambda: trace("F.Cu", refs="In1.Cu", width=0),
        lambda: trace("F.Cu", refs="In1.Cu", width=mm(0)),
        lambda: trace("F.Cu", refs="In1.Cu", width=mm(0.2), gap=mm(0)),
        lambda: trace("", refs="In1.Cu", width=mm(0.2)),
    ],
)
def test_call_trace_refused(make: Callable[[], object]) -> None:
    with pytest.raises(DslError):
        make()


def test_call_pair_without_a_gap() -> None:
    d, usb = _usb()
    with pytest.raises(DslError, match="F.Cu has no gap"):
        d.rules.impedance("USB90", ohms=90, pair=usb, layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.2)),))
    assert d.rules.impedance_targets == {}


def test_pair_across_two_classes() -> None:
    d = Design("z")
    p, n = Net("D_P"), Net("D_N")
    d.rules.netclass("A", nets=(p,))
    d.rules.netclass("B", nets=(n,))
    pair = DiffPair(p, n, name="D")
    d.rules.impedance(
        "D", ohms=100, pair=pair, layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.2), gap=mm(0.2)),)
    )
    with pytest.raises(DslError, match=r"pair D.*A, B"):
        to_model(d)


def test_unknown_class_in_to_model() -> None:
    d = Design("z")
    d.rules.impedance("X", ohms=50, netclass="NOPE", layers=SE_TRACES)
    with pytest.raises(DslError, match="NOPE"):
        to_model(d)


def test_derived_name_taken() -> None:
    d = _se()
    d.rules.rule("track_width_SE50_F.Cu", "track_width", min=mm(0.1))
    _call(d)
    with pytest.raises(DslError, match="named like another rule"):
        to_model(d)


def test_two_classes_in_one_target() -> None:
    d = _se()
    d.rules.netclass("SE50B", nets=(Net("CLK3"),))
    _call(d, netclass=("SE50", "SE50B"))
    rule = _rules(d)["track_width_SE50_F.Cu"]
    assert rule.selector_a == Selector(
        "or", items=(Selector("netclass", "SE50"), Selector("netclass", "SE50B"))
    )


def test_bench_design_converts() -> None:
    model = to_model(zdesign())
    assert model.rules is not None
    assert [t.name for t in model.rules.impedance] == ["SE50", "USB90"]
    assert model.board is not None and model.board.stackup is not None
    assert model.board.stackup.impedance_controlled
    assert [i for i in model.validate() if i.code == "model.impedance-invalid"] == []
