# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact authored starter assets, polarity, short return and conservative capture replay."""

import importlib.util
from pathlib import Path

import pytest

from fenolite.blocks.tests._support import ROOT, bench
from fenolite.reuse.blocklayout import parts_digest, read_block_layout, write_block_layout

TOOLS = Path(__file__).resolve().parents[3] / "tools/blocks/starter_layouts.py"


def author_tool():
    spec = importlib.util.spec_from_file_location("starter_layout_author", TOOLS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "name",
    (
        "voltage_divider",
        "rc_lowpass",
        "led_indicator",
        "i2c_pullups",
        "protected_input",
    ),
)
def test_layout_matches_usage_and_capture(name, tmp_path):
    asset = ROOT / "layouts" / f"{name}.toml"
    layout = read_block_layout(asset)
    assert write_block_layout(layout) == asset.read_bytes()
    assert layout.tracks and layout.evidence == "INFERRED"
    with bench(name) as design:
        assert parts_digest(design.model, "dut") == layout.parts_digest
        assert not design.findings("reuse.copper-dropped")
    captured = author_tool().capture(name, tmp_path / asset.name)
    assert captured == asset.read_bytes()


def test_led_cathode_and_polarity_side():
    layout = read_block_layout(ROOT / "layouts/led_indicator.toml")
    assert layout.parts["led"].rotation == 180_000_000
    assert layout.tracks[0].net_id == "net:anode"
    assert layout.pads[layout.tracks[0].id] == ("led.2", "r.2")
    with bench("led_indicator") as design:
        light = design.ref("dut/led")
        assert design.connected(light[2], design.net("dut/LO"))
        component = next(c for c in design.model.circuit.components if c.id == light.id)
        assert component.pads_of("2") == ("1",)  # symbol cathode → cathode-marked land pad


def test_protection_at_external_edge_and_short_ground_return():
    layout = read_block_layout(ROOT / "layouts/protected_input.toml")
    assert layout.parts["tvs"].at.x < layout.parts["r"].at.x
    ground = next(t for t in layout.tracks if t.net_id == "port:GND")
    assert (ground.end.x - ground.start.x) ** 2 + (ground.end.y - ground.start.y) ** 2 <= 1_500_000**2
    assert len(layout.vias) == 1 and layout.vias[0].position == ground.end
    assert any(z.net_id == "port:GND" and z.layers == ("B.Cu",) for z in layout.zones)


def test_free_end_on_ordinary_reusable_net_is_still_rejected(tmp_path):
    tool = author_tool()
    tool.BENCHES["rc_lowpass"] += """
design.track("free_end", r.pad(1), r.pad(1).at(mm(-2), mm(0)), width=mm("0.25"))
"""
    output = tmp_path / "bad.toml"
    with pytest.raises(RuntimeError, match="blocks.capture-check-failed"):
        tool.capture("rc_lowpass", output)
    assert not output.exists()
