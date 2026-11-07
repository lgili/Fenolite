# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""LED series resistor without guessed electrical defaults; S-1121, S-1123, S-1124."""

from fractions import Fraction
from typing import Any

from fenolite.dsl import (
    DslError,
    Net,
    Range,
    amp,
    at_least,
    block,
    connect,
    param,
    rating_of,
    schematic_group,
    value_of,
    volt,
    within,
)
from fenolite.dsl import generators as gen
from fenolite.dsl.block import Block


@block(
    id="Fenolite:led_indicator",
    version="1.0.0",
    summary="LED indicator with explicit forward voltage and current limit",
    category="indicator",
    sources=("S-1121", "S-1123", "S-1124"),
)
def led_indicator(
    b: Block,
    *,
    drive: Any = param(volt("3.3").pct(5), doc="Voltage HI against LO when on", unit="volt"),
    current: Any = param(amp("2m").pct(50), doc="Accepted LED current range", unit="ampere"),
    led: Any = param(None, doc="Device id; operating voltage is its forward-voltage range"),
    vf: Any = param(None, doc="Forward-voltage range, required when the device does not state it"),
    led_current_max: Any = param(None, doc="LED current limit, required when the device does not state it"),
    source_limit: Any = param(None, doc="Most current the driving pin may source or sink"),
    colour: Any = param("red", doc="Value text only; no electrical meaning"),
    led_footprint: Any = param("Fenolite:LED0603_Kingbright_APT1608SURCK", doc="Cathode-first LED land"),
    series: Any = param("E96", choices=("E24", "E96"), doc="Resistor series"),
) -> None:
    hi = b.port("HI", Net, direction="in", doc="High side of the on-state drive")
    lo = b.port("LO", Net, direction="in", doc="Low side of the on-state drive; LED cathode")
    b.layout(reuse="layouts/led_indicator.toml", copper=True)
    anode = b.net("anode")
    if led is None:
        light = b.part(
            "led",
            "Fenolite:LED",
            footprint=led_footprint,
            prefix="D",
            value=colour,
            pad_map={"1": "2", "2": "1"},
        )
    else:
        light = b.part("led", device=led, value=colour)
        if vf is None and light.device is not None:
            forward = next(
                (r for r in light.device.ratings if r.key == "voltage" and r.limit == "operating"), None
            )
            if forward is not None:
                vf = Range(
                    "volt",
                    None if forward.min is None else Fraction(forward.min, 10**6),
                    None if forward.max is None else Fraction(forward.max, 10**6),
                )
    if vf is None:
        raise DslError(
            "led_indicator: state vf (the LED forward voltage) or give led with an operating voltage range"
        )
    if led_current_max is None:
        if light.device is None or not any(
            r.key == "current" and r.limit == "abs_max" for r in light.device.ratings
        ):
            raise DslError("led_indicator: state led_current_max or give led with an absolute current rating")
        limit = rating_of(light, "current")
    else:
        limit = led_current_max
    # Bind the record's symbol pin numbers explicitly: the layout digest is
    # computed before backend function-name lowering.
    a_pins = light.device.pin("A").pins if light.device is not None else ("1",)
    k_pins = light.device.pin("K").pins if light.device is not None else ("2",)
    connect(anode, *(light[number] for number in a_pins))
    connect(lo, *(light[number] for number in k_pins))
    b.defaults(resistor={"case": "0603", "series": series})
    resistor = gen.led_resistor(b, hi, anode, current=current, vf=vf, vs=drive, name="r")
    drop = drive - vf
    amps = drop / value_of(resistor)
    b.expect(within(amps, current), "LED current in window")
    b.expect(at_least(limit, amps), "LED current rating")
    if source_limit is not None:
        b.expect(at_least(source_limit, amps), "driving pin current")
    b.expect(at_least(rating_of(resistor, "power"), amps * drop), "resistor power upper bound")
    b.schematic(schematic_group("indicator", resistor, light, title="LED indicator"))


__all__ = ["led_indicator"]
