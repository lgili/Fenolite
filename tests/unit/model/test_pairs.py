# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Differential pairs in the model (capability design-model, "Differential pairs in the model"; change
c0104): the name rule of ``model.pairs``, the pair leaf of a selector, and the class pair values in
``circuit.json``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from _schema import load, validate

from fenolite.model import canonical
from fenolite.model.circuit import Circuit, Interface, NetClass
from fenolite.model.pairs import (
    PAIR_ROLES,
    PairName,
    base_matches,
    coupled_name,
    net_bases,
    pair_base,
    pair_nets,
    split_pair_name,
)
from fenolite.model.rules import LEAF_OPS, RuleKind, RuleSubject, Selector, SelectorOp

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = load("fenolite.model.v0/circuit.json")


def test_names_that_pair() -> None:
    names = (
        ("USB_P", "USB_N"),
        ("USB+", "USB-"),
        ("USB_DP", "USB_DN"),
        ("D_P0", "D_N0"),
        ("D_P_2", "D_N_2"),
        ("DP1", "DN1"),
    )
    assert [pair_base(*pair) for pair in names] == ["USB_", "USB", "USB_D", "D_", "D_", "D"]


def test_names_that_do_not_pair() -> None:
    names = (
        ("USB_DP", "USB_DM"),
        ("USB_p", "USB_n"),
        ("USB_P", "USB-"),
        ("D_P1", "D_N2"),
        ("D_PA", "D_NA"),
        ("USB_N", "USB_P"),
    )
    assert [pair_base(*pair) for pair in names] == [None] * len(names)
    assert coupled_name("USB_DP") == "USB_DN"


def test_split_and_coupled_name() -> None:
    assert split_pair_name("D_P_2") == PairName("D_", "P", "_2")
    assert split_pair_name("CLK-") == PairName("CLK", "-", "")
    assert split_pair_name("DATA") is None and split_pair_name("12_") is None and split_pair_name("") is None
    assert coupled_name("CLK-") == "CLK+" and coupled_name("D_N0") == "D_P0" and coupled_name("GND") is None
    for name in ("USB_P", "USB_N7", "A+", "B-_1"):
        assert coupled_name(coupled_name(name) or "") == name


def test_nets_of_a_usb_interface() -> None:
    usb = Interface(
        id="itf_1", name="USB", kind="usb2", members={"dp": "n1", "dn": "n2", "vbus": "n3", "gnd": "n4"}
    )
    i2c = Interface(id="itf_2", name="BUS", kind="i2c", members={"sda": "n5", "scl": "n6"})
    assert pair_nets(usb) == ("n1", "n2") and pair_nets(i2c) is None
    assert pair_nets(Interface(id="itf_3", name="HALF", kind="diff_pair", members={"p": "n1"})) is None
    assert dict(PAIR_ROLES) == {"diff_pair": ("p", "n"), "usb2": ("dp", "dn")}


def test_bases_of_a_design() -> None:
    names = ["USB_P", "USB_N", "CLK+", "CLK-", "D_P1", "D_N2", "LONE_P", "GND"]
    assert net_bases(names) == {"USB_P": "USB_", "USB_N": "USB_", "CLK+": "CLK", "CLK-": "CLK"}
    assert net_bases([]) == {}


def test_pair_leaf_matches_by_base() -> None:
    subjects = [RuleSubject("track", net=n, diff_pair=b) for n, b in (("USB_P", "USB_"), ("usb_P", "usb_"))]
    subjects.append(RuleSubject("track", net="VIN"))
    for value in ("USB", "USB_"):
        assert [Selector("diff_pair", value).matches(s) for s in subjects] == [True, False, False]
    assert [Selector("diff_pair", "*").matches(s) for s in subjects] == [True, True, False]
    assert (
        base_matches("USB_D", "USB_D") and not base_matches("USB_D", "USB_") and not base_matches(None, "*")
    )


def test_the_leaf_and_the_kinds_are_in_the_model() -> None:
    assert "diff_pair" in LEAF_OPS and "diff_pair" in get_args(SelectorOp)
    assert get_args(RuleKind)[-5:] == (
        "diff_pair_gap",
        "diff_pair_uncoupled",
        "skew",
        "diff_pair_skew",
        "length",
    )
    with pytest.raises(ValueError, match="needs a value"):
        Selector("diff_pair")
    assert RuleSubject("track").diff_pair is None


def test_older_circuit_document_loads() -> None:
    """A ``circuit.json`` written before the pair fields existed loads with the three values ``None``, and
    a document that holds them validates and loads back."""
    current = Circuit(
        netclasses=(NetClass(id="cls_00000000-0000-4000-8000-000000000001", name="HV", clearance=2_000_000),)
    )
    data = json.loads(canonical.dumps(current))
    (entry,) = data["netclasses"]
    for key in ("diff_pair_width", "diff_pair_gap", "diff_pair_via_gap"):
        entry.pop(key, None)
    assert validate(data, SCHEMA) == []
    loaded = canonical.loads(json.dumps(data), Circuit)
    (hv,) = loaded.netclasses
    assert (hv.diff_pair_width, hv.diff_pair_gap, hv.diff_pair_via_gap) == (None, None, None)
    paired = Circuit(
        netclasses=(
            NetClass(
                id="cls_00000000-0000-4000-8000-000000000002",
                name="USB",
                diff_pair_gap=150_000,
                diff_pair_width=300_000,
            ),
        )
    )
    text = canonical.dumps(paired)
    assert validate(json.loads(text), SCHEMA) == []
    assert canonical.loads(text, Circuit) == paired
