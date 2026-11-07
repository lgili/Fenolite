# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Protocol limits are authored inputs, typed by their interface or topology."""

from dataclasses import FrozenInstanceError

import pytest

from fenolite.dsl import I2C, USB2, Design, DslError, Net, Part, connect, fs, protocol, ps, to_model


def usb() -> tuple[Design, USB2]:
    design = Design("usb")
    host = Part("J1", device="Fenolite:Conn_1x2_P2.54")
    load = Part("J2", device="Fenolite:Conn_1x2_P2.54")
    design.add(host, load)
    pair = USB2(Net("USB_P"), Net("USB_N"), name="usb")
    pair.attach(host, dp=1, dn=2)
    pair.attach(load, dp=1, dn=2)
    design.propagation("F.Cu", per_mm=fs(5_900))
    return design, pair


def test_kind_checked_and_member_topologies() -> None:
    design, pair = usb()
    with pytest.raises(DslError, match="USB2 or DiffPair"):
        design.constrain(I2C(Net("SDA"), Net("SCL")), protocol.Usb2(skew_max=ps(10)))
    design.constrain(pair, protocol.Usb2(skew_max=ps(10), delay_max=ps(1_500)))
    model = to_model(design)
    assert model.rules is not None
    assert len(model.rules.topologies) == 2
    assert all(topology.constraints[0].max_fs == 1_500_000 for topology in model.rules.topologies)
    (skew,) = model.rules.protocol_skews
    assert skew.max_fs == 10_000 and skew.interface == "usb"


def test_clock_limits_expand() -> None:
    design = Design("clock")
    a, b, c = (Part(f"J{i}", device="Fenolite:Conn_1x2_P2.54") for i in range(1, 4))
    design.add(a, b, c)
    connect(Net("CLK"), a[1], b[1], c[1])
    topology = design.topology("clk", a[1] >> (b[1], c[1]))
    design.constrain(topology, protocol.Clock(delay_max=ps(400), skew_max=ps(20)))
    assert [constraint.kind for constraint in topology.to_model().constraints] == ["delay", "delay", "skew"]
    with pytest.raises(DslError, match="topology"):
        design.constrain(I2C(Net("SDA"), Net("SCL")), protocol.Clock(delay_max=ps(400)))


def test_no_default_numbers_and_frozen() -> None:
    with pytest.raises(DslError, match="user-supplied"):
        protocol.Usb2()
    with pytest.raises(DslError, match="user-supplied"):
        protocol.Clock()
    limits = protocol.Usb2(skew_max=ps(10))
    assert limits.delay_max is None and limits.loss_max is None
    with pytest.raises(FrozenInstanceError):
        limits.skew_max = ps(20)  # type: ignore[misc]
