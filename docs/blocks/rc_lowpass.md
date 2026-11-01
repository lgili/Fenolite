# Fenolite:rc_lowpass 1.0.0

RC low-pass with a worst-case cut-off range

| category | licence | evidence |
|---|---|---|
| analog | Apache-2.0 | INFERRED |

## Parameters

| name | type | unit | default | allowed | doc |
|---|---|---|---|---|---|
| c | quantity | farad | 100nF |  | Fixed capacitance; None lets the generator choose |
| c_tolerance | int |  | 10 | 0 to 100 | Required symmetric capacitor tolerance in percent |
| corner | range | hertz | 1kHz (800Hz..1.2kHz) |  | Accepted cut-off range |
| series | str |  | E96 | E24, E96 | Resistor series |
| voltage | quantity | volt | 5V | at least 0V | Highest normal voltage across the capacitor |

## Ports

The ports are those of the default parameters.

| name | kind | direction | optional | doc |
|---|---|---|---|---|
| GND | ground | in | no | Capacitor return |
| IN | net | in | no | Filter input |
| OUT | net | out | no | Unloaded filter output |

## Requires

- query `rc_lowpass(corner=1kHz (800Hz..1.2kHz), c=capacitor(100nF), role=c)`
- query `rc_lowpass(corner=1kHz (800Hz..1.2kHz), c=capacitor(100nF), role=r)`

## Sources

- S-1122: https://en.wikipedia.org/wiki/RC_circuit (Wikipedia, read 2026-11-01)
- S-1124: https://en.wikipedia.org/wiki/Interval_arithmetic (Wikipedia, read 2026-11-01)

## Expectations

- cut-off in range
- capacitor voltage rating

## Usage

`usage/rc_lowpass.py`:

```python
# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; circuit, dimensions and illustrative inputs are original.
"""Authored bench for rc_lowpass; every port is connected to J1.

Bench placement and copper are authored in code, then captured. No GUI review is claimed.
Protection figures, where used, are illustrative and UNVERIFIED.
"""

from fenolite.blocks import rc_lowpass
from fenolite.dsl import Design, Part, connect, mm, supply, volt

design = Design("rc_lowpass_usage")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54")
design.add(j1)
dut = design.use(rc_lowpass, "dut")
dut.place(mm(12), mm(12))
j1.place(mm(28), mm("12.54"), rot=180)
connect(dut.IN, j1[1])
connect(dut.OUT, j1[2])
connect(dut.GND, j1[3])
design.rig(supply(dut.IN, dut.GND, voltage=volt(5), name="bench"))

dut.part("filter_R").field("Reference", layer="fab")
dut.part("filter_C").field("Reference", layer="fab")

# Host copper: original bench routes; the captured asset holds the local block copper.

r, c = dut.part("filter_R"), dut.part("filter_C")
design.via("bench_in_via", mm("11.2"), mm(10), net=connect(dut.IN), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_in_front", r.pad(1), (mm("11.2"), mm(10)), width=mm("0.25"))
design.track("bench_in_back", (mm("11.2"), mm(10)), j1.pad(1), layer="B.Cu", width=mm("0.25"))
design.via("bench_out_via", mm(14), mm(12), net=connect(dut.OUT), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_out_back", (mm(14), mm(12)), j1.pad(2), layer="B.Cu", width=mm("0.25"))
design.via("bench_gnd_via", mm("16.8"), mm("15.5"), net=connect(dut.GND), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_gnd_front", c.pad(2), (mm("16.8"), mm("15.5")), width=mm("0.25"))
design.track("bench_gnd_back", (mm("16.8"), mm("15.5")), j1.pad(3), layer="B.Cu", width=mm("0.25"))
```

## Layout

`layouts/rc_lowpass.toml`; evidence `INFERRED`.

| local part | footprint |
|---|---|
| `filter_C` | `Fenolite:Chip_0603` |
| `filter_R` | `Fenolite:Chip_0603` |

Coordinates and copper are authored by `tools/blocks/starter_layouts.py` and
captured through the CLI. No GUI placement or human layout review is claimed.
The containing board routes the connectors and fills any return zone.
