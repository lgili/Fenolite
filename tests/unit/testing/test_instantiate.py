# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A c0251 block tested alone (c0256, design-testing: "A buck block alone")."""

import os
from pathlib import Path

import pytest

from fenolite.dsl import Ground, Rail, block, connect, mm, volt
from fenolite.testing import TestingError, instantiate

VOUT = volt("3.3").pct(3)  # the block's promise; chosen for the test


@block
def buck(b, *, vout=VOUT):
    """An authored regulator block with catalog parts only. Ports: VIN (in), VOUT (out), GND."""
    vin = b.port("VIN", Rail, direction="in")
    out = b.port("VOUT", Rail, direction="out", voltage=vout)
    gnd = b.port("GND", Ground)
    reg = b.part("U1", "Fenolite:Linear_Regulator", footprint="Fenolite:SOT223_3_Diodes", value="REG")
    c_out = b.part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="10u")
    connect(vin.hv, reg["IN"])
    connect(out.hv, reg["OUT"], c_out[1])
    connect(gnd.gnd, reg["GND"], c_out[2])
    reg.place(mm(20), mm(20))
    c_out.place(mm(30), mm(20))


def _files(folder: Path) -> set[str]:
    return {os.path.join(root, name) for root, _dirs, names in os.walk(folder) for name in names}


def test_a_buck_block_alone(script: Path):
    """``script`` (the authored fixture) only forbids subprocesses here; the block needs no script file."""
    before = _files(script.parent)
    with instantiate(buck, vout=volt("3.3").pct(3)) as d:
        vout = d.net("dut/VOUT")  # the Rail port, read as its main member
        regulator, capacitor = d.ref("dut/U1"), d.ref("dut/C1")
        assert regulator.value == "REG" and regulator["OUT"].net == vout.name == "dut/VOUT.hv"
        assert vout.pins == tuple(sorted((f"{regulator.ref}-3", f"{capacitor.ref}-1")))
        assert d.connected(regulator["OUT"], vout) and d.net("dut/GND").name == "dut/GND"
        private = d.path.parent
        assert private.is_dir()
    assert not private.exists()
    assert _files(script.parent) == before


def test_instantiate_takes_a_block():
    with pytest.raises(TestingError, match="@block"):
        instantiate(lambda b: None)
