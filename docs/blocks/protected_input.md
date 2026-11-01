# Fenolite:protected_input 1.0.0

Protected input with explicit clamp and downstream limits

| category | licence | evidence |
|---|---|---|
| protection | Apache-2.0 | INFERRED |

## Parameters

| name | type | unit | default | allowed | doc |
|---|---|---|---|---|---|
| abs_max | quantity | volt | required | at least 0V | Downstream absolute maximum voltage |
| clamp | quantity | volt | required | at least 0V | Clamping range at the surge being designed for |
| hold | none |  |  |  | Voltage held by downstream clamps; requires inject_max |
| inject_max | none |  |  |  | Downstream clamp current limit; requires hold |
| protection | str |  | required |  | Protection device id; its operating voltage is the stand-off limit |
| r_series | quantity | ohm | 1kΩ | at least 10Ω | Series resistance, selected from the 0603 E96 1 % family |
| signal | range | volt | 0V..5V | at least 0V | External signal in normal operation |

## Ports

Not elaborated: required parameter abs_max.

## Requires

None.

## Sources

- S-1120: https://en.wikipedia.org/wiki/Voltage_divider (Wikipedia, read 2026-11-01)
- S-1124: https://en.wikipedia.org/wiki/Interval_arithmetic (Wikipedia, read 2026-11-01)
- S-1125: https://en.wikipedia.org/wiki/Transient-voltage-suppression_diode (Wikipedia, read 2026-11-01)

## Expectations

- protection working voltage covers the signal
- clamp below the downstream maximum
- current into the downstream clamps limited
- downstream held voltage below absolute maximum

## Usage

`usage/protected_input.py`:

```python
# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; circuit, dimensions and illustrative inputs are original.
"""Authored bench for protected_input; every port is connected to J1.

Bench placement and copper are authored in code, then captured. No GUI review is claimed.
Protection figures, where used, are illustrative and UNVERIFIED.
"""

from fenolite.blocks import protected_input
from fenolite.dsl import Design, Part, amp, connect, mm, ohm, supply, volt

design = Design("protected_input_usage")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54")
design.add(j1)
dut = design.use(
    protected_input,
    "dut",
    protection="Example:IllustrativeTVS",
    clamp=volt("9.2").max(),
    abs_max=volt("3.6"),
    r_series=ohm("1.5k"),
    inject_max=amp("5m"),
    hold=volt("3.6"),
)
dut.place(mm(12), mm(12))
j1.place(mm(28), mm("12.54"), rot=180)
connect(dut.EXT, j1[1])
connect(dut.INT, j1[2])
connect(dut.GND, j1[3])
design.rig(supply(dut.EXT, dut.GND, voltage=volt(5), name="bench"))

dut.part("tvs").field("Reference", layer="fab")
dut.part("r").field("Reference", layer="fab")

# Host copper: original bench routes; the captured asset holds the local block copper.

tvs, r = dut.part("tvs"), dut.part("r")
design.via("bench_ext_via", mm(14), mm(12), net=connect(dut.EXT), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_ext_back", (mm(14), mm(12)), j1.pad(1), layer="B.Cu", width=mm("0.25"))
design.via("bench_int_via", mm("16.8"), mm("15.5"), net=connect(dut.INT), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_int_front", r.pad(2), (mm("16.8"), mm("15.5")), width=mm("0.25"))
design.track("bench_int_back", (mm("16.8"), mm("15.5")), j1.pad(2), layer="B.Cu", width=mm("0.25"))
design.track(
    "bench_ground_back",
    tvs.pad("A").at(mm(0), mm(1)),
    (mm(9), mm(11)),
    (mm(9), mm(18)),
    (mm(28), mm(18)),
    j1.pad(3),
    layer="B.Cu",
    width=mm("0.25"),
)
```

## Layout

`layouts/protected_input.toml`; evidence `INFERRED`.

| local part | footprint |
|---|---|
| `r` | `Fenolite:Chip_0603` |
| `tvs` | `Fenolite:SOD323_Diodes` |

Coordinates and copper are authored by `tools/blocks/starter_layouts.py` and
captured through the CLI. No GUI placement or human layout review is claimed.
The containing board routes the connectors and fills any return zone.

The `Example:IllustrativeTVS` usage record is `UNVERIFIED`; every electrical
number is illustrative. Its operating voltage is the stand-off limit; the surge
clamp is a separate required input. Pair `inject_max` with `hold`; the held
voltage is also judged against `abs_max`. Overlapping ranges are `unsure`,
so a 1 kΩ example does not pass the 5 mA requirement.
