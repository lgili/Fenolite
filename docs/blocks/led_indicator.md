# Fenolite:led_indicator 1.0.0

LED indicator with explicit forward voltage and current limit

| category | licence | evidence |
|---|---|---|
| indicator | Apache-2.0 | INFERRED |

## Parameters

| name | type | unit | default | allowed | doc |
|---|---|---|---|---|---|
| colour | str |  | red |  | Value text only; no electrical meaning |
| current | range | ampere | 2mA (1mA..3mA) |  | Accepted LED current range |
| drive | range | volt | 3.3V (3.135V..3.465V) |  | Voltage HI against LO when on |
| led | none |  |  |  | Device id; operating voltage is its forward-voltage range |
| led_current_max | none |  |  |  | LED current limit, required when the device does not state it |
| led_footprint | str |  | Fenolite:LED0603_Kingbright_APT1608SURCK |  | Cathode-first LED land |
| series | str |  | E96 | E24, E96 | Resistor series |
| source_limit | none |  |  |  | Most current the driving pin may source or sink |
| vf | none |  |  |  | Forward-voltage range, required when the device does not state it |

## Ports

Not elaborated: led_indicator: state vf (the LED forward voltage) or give led with an operating voltage range.

## Requires

- symbol `Fenolite:LED`

## Sources

- S-1121: https://en.wikipedia.org/wiki/Joule_heating (Wikipedia, read 2026-11-01)
- S-1123: https://en.wikipedia.org/wiki/LED_circuit (Wikipedia, read 2026-11-01)
- S-1124: https://en.wikipedia.org/wiki/Interval_arithmetic (Wikipedia, read 2026-11-01)

## Expectations

- LED current in window
- LED current rating
- resistor power upper bound
- driving pin current

## Usage

`usage/led_indicator.py`:

```python
# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; circuit, dimensions and illustrative inputs are original.
"""Authored bench for led_indicator; every port is connected to J1.

Bench placement and copper are authored in code, then captured. No GUI review is claimed.
Protection figures, where used, are illustrative and UNVERIFIED.
"""

from fenolite.blocks import led_indicator
from fenolite.dsl import Design, Part, amp, connect, mm, supply, volt

design = Design("led_indicator_usage")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
design.add(j1)
dut = design.use(led_indicator, "dut", vf=volt(2).pct(10), led_current_max=amp("20m"))
dut.place(mm(12), mm(12))
j1.place(mm(28), mm("11.27"), rot=180)
connect(dut.HI, j1[1])
connect(dut.LO, j1[2])
design.rig(supply(dut.HI, dut.LO, voltage=volt("3.3").pct(5), name="bench"))

dut.part("r").field("Reference", layer="fab")
dut.part("led").field("Reference", layer="fab")

# Host copper: original bench routes; the captured asset holds the local block copper.

r, led = dut.part("r"), dut.part("led")
design.via("bench_hi_via", mm("11.2"), mm(10), net=connect(dut.HI), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_hi_front", r.pad(1), (mm("11.2"), mm(10)), width=mm("0.25"))
design.track("bench_hi_back", (mm("11.2"), mm(10)), j1.pad(1), layer="B.Cu", width=mm("0.25"))
design.via("bench_lo_via", mm("16.825"), mm(15), net=connect(dut.LO), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_lo_front", led.pad(1), (mm("16.825"), mm(15)), width=mm("0.25"))
design.track("bench_lo_back", (mm("16.825"), mm(15)), j1.pad(2), layer="B.Cu", width=mm("0.25"))
```

## Layout

`layouts/led_indicator.toml`; evidence `INFERRED`.

| local part | footprint |
|---|---|
| `led` | `Fenolite:LED0603_Kingbright_APT1608SURCK` |
| `r` | `Fenolite:Chip_0603` |

Coordinates and copper are authored by `tools/blocks/starter_layouts.py` and
captured through the CLI. No GUI placement or human layout review is claimed.
The containing board routes the connectors and fills any return zone.

No LED electrical default is shipped. An LED device's `operating` voltage
states its forward-voltage range, with an `abs_max` current rating, or pass
`vf` and `led_current_max` explicitly. Colour affects value text only.
