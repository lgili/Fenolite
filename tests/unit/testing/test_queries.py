# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Queries use logical identities and distinguish unrouted copper from a netlist."""

from pathlib import Path

import pytest

from fenolite.testing import TestingError, load


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
