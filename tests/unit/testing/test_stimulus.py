# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stimulus reference validation and rig-only effects (change c0270)."""

from pathlib import Path

import pytest

from fenolite import api
from fenolite.cli.blocksrc import import_file
from fenolite.dsl import I2C, Ground, Net, amp, block, connect, mm, volt
from fenolite.testing import TestingError, instantiate
from fenolite.testing.stimulus import draw, source, stimulus

DIVIDER = Path(__file__).resolve().parents[2] / "data/blocks/lib/divider.py"
divider = import_file(DIVIDER).divider


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        (lambda: stimulus(HI=volt(0), LO=volt(0)), "HI.*LO"),
        (lambda: stimulus(HX=volt(1)), "HX.*HI.*LO.*OUT"),
        (lambda: stimulus({"HI.net": volt(1)}), "HI.net"),
        (lambda: stimulus(HI=amp(1)), "HI.*volt"),
        (lambda: stimulus(HI=volt(1), ref="HX"), "HX"),
        (lambda: stimulus(HI=volt(1), ref="HI"), "HI.*0 V"),
    ],
)
def test_reference_refused_before_folder(inputs, message, monkeypatch):
    def refuse(**kwargs):
        raise AssertionError("a temporary folder was allocated")

    monkeypatch.setattr("fenolite.testing.design.tempfile.mkdtemp", refuse)
    with pytest.raises(TestingError, match=message):
        instantiate(divider, stimulus=inputs())


def test_reference_ground_fallback_and_explicit():
    for inputs in (stimulus(HI=volt(12)), stimulus(HI=volt(12), ref="LO")):
        with instantiate(divider, stimulus=inputs) as design:
            rig = design.model.rules.contracts.rig
            assert len(rig) == 1 and rig[0].name == "stim_HI"


def test_reference_missing_and_multiple_ground():
    @block
    def bare(b):
        b.port("A", Net)
        b.port("G1", Ground)
        b.port("G2", Ground)

    with pytest.raises(TestingError, match="G1.*G2"):
        instantiate(bare, stimulus=stimulus(A=volt(1)))


def test_helpers_check_dimensions():
    with pytest.raises(TestingError, match="ampere"):
        draw(volt(1))
    with pytest.raises(TestingError, match="volt"):
        source(amp(1))
    with pytest.raises(TestingError, match="ampere"):
        source(volt(1), current=volt(1))


def test_judged_rig_never_changes_board_netlist_or_bom():
    with (
        instantiate(divider) as plain,
        instantiate(
            divider,
            stimulus=stimulus(HI=source(volt(12).pct(2), current=amp("1m")), LO=volt(0), OUT=draw(amp("1u"))),
        ) as driven,
    ):
        assert plain.model.circuit == driven.model.circuit
        assert plain.model.board == driven.model.board
        for suffix in (".kicad_sch", ".kicad_pcb"):
            a = next(plain.path.glob(f"*{suffix}"))
            b = next(driven.path.glob(f"*{suffix}"))
            assert a.read_bytes() == b.read_bytes()
        for command, args in (("netlist", ("--source", "fenolite")), ("bom", ("--source", "model"))):
            a = api.run(command, str(plain.path), *args)
            b = api.run(command, str(driven.path), *args)
            assert a.exit_code == b.exit_code == 0
            assert a.result == b.result
        assert not driven.findings("circuit.expect-*")
        assert len(plain.findings("circuit.expect-unknown")) == 1


def test_reference_interface_member():
    @block
    def bus(b):
        port = b.port("BUS", I2C)
        ground = b.port("G", Ground)
        for name, x in (("sda", 10), ("scl", 20)):
            r = b.part(name, "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1000", prefix="R")
            connect(port[name], r[1])
            connect(ground, r[2])
            r.place(mm(x), mm(10))

    with instantiate(bus, stimulus=stimulus({"BUS.sda": volt(3)})) as design:
        assert design.model.rules.contracts.rig[0].name == "stim_BUS_sda"
