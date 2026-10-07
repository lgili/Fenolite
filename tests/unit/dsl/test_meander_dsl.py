# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Meanders in the DSL (capability design-dsl, "Meanders in the DSL"; change c0106): what a script records
and what is refused at the call."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import (
    Design,
    DslError,
    MeanderIntent,
    Net,
    Part,
    arc_to,
    connect,
    copper,
    meanders,
    mm,
    to_model,
)


def _pair() -> Design:
    design = Design("pair")
    design.board(mm(60), mm(40))
    u1 = Part("U1", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
    j1 = Part("J1", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
    design.add(u1, j1)
    usb_p, usb_n = Net("USB_P"), Net("USB_N")
    connect(usb_p, u1[1], j1[1])
    connect(usb_n, u1[2], j1[2])
    design.track("usb_p", u1.pad(1), (mm(12), mm(8)), (mm(40), mm(8)), j1.pad(1))
    design.track("usb_n", u1.pad(2), (mm(12), mm(12)), (mm(40), mm(12)), j1.pad(2))
    return design


def test_record_a_meander_on_a_pair() -> None:
    design = _pair()
    before = to_model(design)
    design.meander("n_tune", track="usb_n", segment=1, match="usb_p", amplitude=mm(0.5), pitch=mm(0.4))
    assert meanders(design) == (
        MeanderIntent("n_tune", "usb_n", 1, 500_000, 400_000, None, "usb_p", "left", None),
    )  # fmt: skip
    assert to_model(design) == before  # a meander is not a model object
    assert [intent.key for intent in copper(design)] == ["usb_n", "usb_p"]
    design.meander(
        "a_tune", track="usb_p", segment=0, target=mm(40), amplitude=mm(1), pitch=mm(1), side="right",
        margin=mm(0),
    )  # fmt: skip
    found = meanders(design)
    assert [m.key for m in found] == ["a_tune", "n_tune"]  # key order
    assert found[0] == MeanderIntent("a_tune", "usb_p", 0, 1_000_000, 1_000_000, 40_000_000, None, "right", 0)
    assert all(type(v) is int for m in found for v in (m.amplitude, m.pitch, m.segment))


def test_malformed_meanders_fail_at_the_call() -> None:
    design = _pair()
    with pytest.raises(DslError, match="nope"):
        design.meander("m1", track="nope", segment=0, target=mm(30), amplitude=mm(1), pitch=mm(1))
    with pytest.raises(DslError, match="segment 5"):
        design.meander("m2", track="usb_n", segment=5, target=mm(30), amplitude=mm(1), pitch=mm(1))
    with pytest.raises(DslError, match="either target"):
        design.meander("m3", track="usb_n", segment=1, amplitude=mm(1), pitch=mm(1))
    with pytest.raises(DslError, match="either target"):
        design.meander(
            "m4", track="usb_n", segment=1, target=mm(30), match="usb_p", amplitude=mm(1), pitch=mm(1)
        )
    assert meanders(design) == ()


def test_every_other_refusal() -> None:
    design = _pair()
    good = {"track": "usb_n", "segment": 1, "target": mm(30), "amplitude": mm(1), "pitch": mm(1)}
    for key in ("bad key", "usb_n"):  # not a copper key; the key of a copper intent
        with pytest.raises(DslError, match="copper key"):
            design.meander(key, **good)  # type: ignore[arg-type]
    for change in (
        {"segment": -1},
        {"segment": True},
        {"segment": 3},
        {"amplitude": mm(0)},
        {"pitch": mm(-1)},
        {"margin": mm(-1)},
        {"target": mm(0)},
        {"target": None, "match": "usb_n"},  # itself
        {"target": None, "match": "nope"},
        {"side": "up"},
    ):
        with pytest.raises(DslError):
            design.meander("m", **{**good, **change})  # type: ignore[arg-type]
    design.meander("m", **good)  # type: ignore[arg-type]
    with pytest.raises(DslError, match="already used"):
        design.meander("m", **{**good, "segment": 0})  # type: ignore[arg-type]
    with pytest.raises(DslError, match="already stands"):
        design.meander("m_again", **good)  # type: ignore[arg-type]
    with pytest.raises(DslError, match="already used"):
        design.track("m", (mm(1), mm(1)), (mm(2), mm(1)), net=Net("X"))


def test_an_arc_segment_is_refused() -> None:
    design = _pair()
    design.track("bend", (mm(1), mm(1)), arc_to((mm(2), mm(2)), (mm(3), mm(1))), (mm(9), mm(1)), net=Net("X"))
    with pytest.raises(DslError, match="arc"):
        design.meander("m", track="bend", segment=0, target=mm(30), amplitude=mm(1), pitch=mm(1))
    design.meander("m", track="bend", segment=1, target=mm(30), amplitude=mm(1), pitch=mm(1))


def test_exports_and_imports() -> None:
    assert dsl.MeanderIntent is MeanderIntent and dsl.meanders is meanders
    assert "MeanderIntent" in dsl.__all__ and "meanders" in dsl.__all__
    for name in ("intents.py", "design.py"):
        tree = ast.parse((Path(dsl.__file__).parent / name).read_text(encoding="utf-8"))
        modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert all(
            m.startswith(("fenolite.core", "fenolite.model", "fenolite.dsl"))
            for m in modules
            if "fenolite" in m
        )
