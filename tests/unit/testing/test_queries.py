# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Queries use logical identities and distinguish unrouted copper from a netlist."""

from pathlib import Path

import pytest

from fenolite.testing import TestingError, instantiate, load, stimulus


def test_views_and_connected(script: Path):
    with load(script) as d:
        net = d.net("GND")
        assert net.pins == ("R1-1", "R2-1")
        part = d.ref("R1")
        assert part.id == next(p.id for p in d.model.circuit.components if p.ref == "R1")
        assert part[1].net == "GND"
        assert d.connected(part[1], "R2-1")
        assert not d.connected(part[1], "R2-1", copper=True)
        assert d.connected(net, part[1])
        assert not d.connected("R1-2", "R2-2")
        assert part.device is None and net.voltage is None


def test_unknown_names(script: Path):
    with load(script) as d:
        for lookup, name, expected in (
            (d.net, "GDN", "GND"),
            (d.ref, "R9", "R1"),
            (d.ref("R1").__getitem__, "BAD", "1"),
        ):
            with pytest.raises(TestingError, match=expected):
                lookup(name)


def test_copper_uses_explicit_pin_to_pad_map(script: Path):
    text = script.read_text().replace('connect(Net("GND"),', 'gnd = Net("GND")\nconnect(gnd,')
    text = text.replace('value="1000")', 'value="1000", pad_map={"1": "2", "2": "1"})')
    text = text.replace("r1.place(mm(5), mm(5))", "r1.place(mm(5), mm(5), rot=90)")
    text = text.replace("r2.place(mm(15), mm(5))", "r2.place(mm(15), mm(5), rot=90)")
    text += '\ndesign.track("mapped", r1.pad(2), r2.pad(1), width=mm("0.2"))\n'
    script.write_text(text)
    with load(script) as d:
        assert d.connected("R1-1", "R2-1", copper=True)
        assert not d.connected("R1-2", "R2-1", copper=True)


def test_requirements_share_findings_cache(monkeypatch):
    from fenolite import api
    from fenolite.cli.blocksrc import import_file
    from fenolite.dsl import Range, volt

    divider = import_file(Path(__file__).resolve().parents[2] / "data/blocks/lib/divider.py").divider
    with instantiate(divider, stimulus=stimulus(HI=volt(12).pct(2), LO=volt(0))) as d:
        calls = []
        original = api.run

        def record(*args, **kwargs):
            calls.append(args[0])
            return original(*args, **kwargs)

        monkeypatch.setattr(api, "run", record)
        (row,) = d.requirements("dut/*")
        assert row.id == "dut/expect#1" and row.status == "pass"
        assert isinstance(row.value, Range) and isinstance(row.limit, Range)
        assert row.evidence == "INFERRED"
        assert not d.findings("circuit.expect-*")
        assert d.requirements() == (row,)
        assert calls == ["check"]
    with instantiate(divider) as d:
        assert d.requirements("dut/*")[0].status == "unknown"


def test_requirements_missing_circuit_stage(monkeypatch, script):
    from fenolite.checks import stages

    with load(script) as d:
        monkeypatch.setattr(stages, "STAGE_ORDER", ("model.validate",))
        with pytest.raises(TestingError, match="needs the circuit stage"):
            d.requirements()


def test_achieved_generated_range():
    from fenolite.dsl import Ground, Net, amp, between, block, connect, mm, pct, volt, voltage_divider

    @block
    def generated(b):
        hi, out, lo = b.port("HI", Net), b.port("OUT", Net), b.port("LO", Ground)
        b.defaults(resistor={"case": "0603", "tolerance": pct(1), "series": "E96"})
        top, bot = voltage_divider(
            b,
            hi,
            out,
            lo,
            target=volt(4).pct(5),
            vin=volt(12).pct(2),
            current=between(amp("40u"), amp("100u")),
            name="ratio",
        )
        top.place(mm(10), mm(10))
        bot.place(mm(20), mm(10))
        extra = b.part("J1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1000", prefix="R")
        connect(hi, extra[1])
        connect(lo, extra[2])
        extra.place(mm(30), mm(10))

    with instantiate(generated) as d:
        achieved = d.achieved("dut/ratio_top")
        assert achieved.unit == "volt" and achieved.within(volt(4).pct(5))
        assert achieved == d.achieved("dut/ratio_bot")
        with pytest.raises(TestingError, match="no generator.*dut/J1"):
            d.achieved("dut/J1")


def test_placement_from_the_built_board(script: Path):
    script.write_text(
        script.read_text().replace("r1.place(mm(5), mm(5))", 'r1.place(mm(10), mm(5), rot=90, side="bottom")')
    )
    with load(script) as d:
        part = d.ref("R1")
        assert part.at == (10_000_000, 5_000_000)
        assert part.rotation == 90_000_000 and part.side == "bottom"


def test_achieved_pull_up_resistance(script: Path):
    from fractions import Fraction

    script.write_text("""from fenolite.dsl import Design, I2C, Net, between, farad, i2c_pull_ups
from fenolite.dsl import mm, pct, volt
design = Design("pull_up_test")
design.board(mm(30), mm(20))
design.defaults(resistor={"case": "0603", "tolerance": pct(5), "series": "E24"})
bus = I2C(Net("SDA"), Net("SCL"))
a, b = i2c_pull_ups(design, bus, Net("V3V3"),
    bus_capacitance=between(farad("50p"), farad("100p")), vdd=volt("3.3").pct(3))
a.place(mm(10), mm(10))
b.place(mm(20), mm(10))
""")
    with load(script) as design:
        achieved = design.achieved("PU_sda")
        assert achieved.unit == "ohm"
        assert achieved.low == Fraction(3135) and achieved.high == Fraction(3465)
        assert achieved == design.achieved("PU_scl")
