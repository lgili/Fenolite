# Fenolite:voltage_divider 1.0.0

Resistive divider with a worst-case output range

| category | licence | evidence |
|---|---|---|
| analog | Apache-2.0 | INFERRED |

## Parameters

| name | type | unit | default | allowed | doc |
|---|---|---|---|---|---|
| current | range | ampere | 50uA..200uA |  | Divider current window at nominal input |
| series | str |  | E96 | E24, E96 | Resistor series |
| vin | range | volt | 12V (11.76V..12.24V) |  | Input HI against LO used to choose resistors |
| vout | range | volt | 3.3V (3.135V..3.465V) |  | Accepted unloaded output range |

## Ports

The ports are those of the default parameters.

| name | kind | direction | optional | doc |
|---|---|---|---|---|
| HI | power | in | no | Input rail; its actual voltage is judged |
| LO | ground | in | no | Input and output reference |
| OUT | net | out | no | Unloaded divided output |

## Requires

- query `voltage_divider(target=3.3V (3.135V..3.465V), vin=12V (11.76V..12.24V), current=50uA..200uA, case=0603, series=E96, role=bot)`
- query `voltage_divider(target=3.3V (3.135V..3.465V), vin=12V (11.76V..12.24V), current=50uA..200uA, case=0603, series=E96, role=top)`

## Sources

- S-1120: https://en.wikipedia.org/wiki/Voltage_divider (Wikipedia, read 2026-11-01)
- S-1121: https://en.wikipedia.org/wiki/Joule_heating (Wikipedia, read 2026-11-01)
- S-1124: https://en.wikipedia.org/wiki/Interval_arithmetic (Wikipedia, read 2026-11-01)

## Expectations

- output in range
- top power upper bound
- bottom power upper bound

## Usage

`usage/voltage_divider.py`:

```python
# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; circuit, dimensions and illustrative inputs are original.
"""Authored bench for voltage_divider; every port is connected to J1.

Bench placement and copper are authored in code, then captured. No GUI review is claimed.
Protection figures, where used, are illustrative and UNVERIFIED.
"""

from fenolite.blocks import voltage_divider
from fenolite.dsl import Design, Part, connect, mm, supply, volt

design = Design("voltage_divider_usage")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54")
design.add(j1)
dut = design.use(voltage_divider, "dut")
dut.place(mm(12), mm(12))
j1.place(mm(28), mm("12.54"), rot=180)
connect(dut.HI, j1[1])
connect(dut.OUT, j1[2])
connect(dut.LO, j1[3])
design.rig(supply(dut.HI, dut.LO, voltage=volt(12).pct(2), name="bench"))

dut.part("divider_top").field("Reference", layer="fab")
dut.part("divider_bot").field("Reference", layer="fab")

# Host copper: original bench routes; the captured asset holds the local block copper.

top, bot = dut.part("divider_top"), dut.part("divider_bot")
design.via("bench_hi_via", mm(12), mm(10), net=connect(dut.HI), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_hi_front", top.pad(1), (mm(12), mm(10)), width=mm("0.25"))
design.track("bench_hi_back", (mm(12), mm(10)), j1.pad(1), layer="B.Cu", width=mm("0.25"))
design.via("bench_out_via", mm(14), mm(14), net=connect(dut.OUT), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_out_front", (mm(12), mm(14)), (mm(14), mm(14)), net=connect(dut.OUT), width=mm("0.25"))
design.track("bench_out_back", (mm(14), mm(14)), j1.pad(2), layer="B.Cu", width=mm("0.25"))
design.via("bench_lo_via", mm(12), mm(18), net=connect(dut.LO), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_lo_front", bot.pad(2), (mm(12), mm(18)), width=mm("0.25"))
design.track("bench_lo_back", (mm(12), mm(18)), j1.pad(3), layer="B.Cu", width=mm("0.25"))
```

## Layout

`layouts/voltage_divider.toml`; evidence `INFERRED`.

| local part | footprint |
|---|---|
| `divider_bot` | `Fenolite:Chip_0603` |
| `divider_top` | `Fenolite:Chip_0603` |

Coordinates and copper are authored by `tools/blocks/starter_layouts.py` and
captured through the CLI. No GUI placement or human layout review is claimed.
The containing board routes the connectors and fills any return zone.
