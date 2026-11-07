---
topic: starter-blocks
title: Five starter circuits with checked ranges
summary: Five reusable circuits with exact expectations and explicit electrical inputs.
---

# Five starter circuits with checked ranges

Import `voltage_divider`, `rc_lowpass`, `led_indicator`, `i2c_pullups` and
`protected_input` from `fenolite.blocks`. A generator chooses parts inside a block;
`design.use` instantiates a circuit and gives its parts stable local paths.

```fenolite-design
from fenolite.blocks import voltage_divider, rc_lowpass, led_indicator, i2c_pullups, protected_input
from fenolite.dsl import Design, Part, connect, mm, supply, volt

design = Design("starter_divider")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54")
design.add(j1)
dut = design.use(voltage_divider, "sense")
dut.place(mm(12), mm(12))
j1.place(mm(28), mm(10))
connect(dut.HI, j1[1])
connect(dut.OUT, j1[2])
connect(dut.LO, j1[3])
design.rig(supply(dut.HI, dut.LO, voltage=volt(12).pct(2), name="example_input"))
```

The divider judges its output against the actual rail; `vin` is the range used when
choosing resistors. The filter encloses π and all part tolerances. Expectations compare
ratings at 100 percent; state your own derating policy when margin is required.

For `led_indicator`, give `vf` and `led_current_max`, or an LED device record with its
forward-voltage operating range and current rating. Colour supplies no electrical data.
For `protected_input`, `protection`, `clamp` and `abs_max` are REQUIRED. Its working
voltage uses the device's operating limit; a surge clamp is a separate input. Pair
`inject_max` with `hold`. The Example protection device is UNVERIFIED and illustrative.

The I2C block uses the existing UM10204 facts. `fenolite.dsl.generators.i2c_mode_limits`
and `PI` share exact constants with the selectors. The supported sink-current facts
require a supply above 2 V. `circuit.pullup-parallel` warns when multiple resistor sets
pull one bus line to a rail; check their combined resistance.

```fenolite-cmd
fenolite blocks list --json
fenolite blocks show Fenolite:protected_input --json
fenolite blocks test Fenolite:voltage_divider --json
fenolite explain circuit.pullup-parallel --json
```

Every block ships plain tool-free tests, an authored usage, a deterministic golden and
an exact captured layout. The layout method is authored DSL coordinates and native
copper, then CLI capture. GUI review is pending. The host board connects and routes
its external connectors and fills the protection return area; those operations need
board-level checking. Read `docs/blocks/index.md` for each usage and its assumptions.

Read next: `block-layouts`, `block-testing`, `rules`.
