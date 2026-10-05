## Why

A script connects a bus one pin at a time. Nothing stops an I2C bus without pull-ups, a UART wired TX to TX, or a USB pair whose net names KiCad's differential-pair tools do not recognise. The DSL knows three interface kinds: `Power`, `DiffPair` and `Harness`. A part's value is free text, so `4k7`, `4.7k` and `4700` are three values to a BOM.

The plan gives v0.2b "interfaces `I2C/SPI/UART/USB2` + `Quantity`" (`dsl/interfaces.py`, `dsl/quantity.py`). c0047 kept voltages off nets in the model. Quantities therefore stay script values, and the model gains no field.

Probes on 9.0.9 and 10.0.6 (2026-10-05, a rules bench with `A.inDiffPair('<base>')`) show how KiCad pairs nets by name. Two names form a pair when they are equal except for the last character, `P` and `N` or `+` and `-`: `USB_P`/`USB_N`, `USB+`/`USB-`, `USB_DP`/`USB_DN` and `USBP`/`USBN` are pairs. `USB_DP`/`USB_DM`, `USB_p`/`USB_n` and `USB_P`/`USB-` are not.

## What Changes

- **`Quantity`** (`dsl/quantity.py`): exact values in ohms, farads, henries, volts, amperes, hertz, watts and seconds. It is built from integers, fractions or text with SI prefixes (`4.7k`, `100nF`, `3.3V`) or the IEC 60062 letter code (`4k7`, `2R2`). It compares exactly, refuses floats, and prints one canonical text. `Part(value=q)` stores that text, so equal values group in a BOM.
- **Typed interfaces**: `I2C(sda, scl)`, `SPI(sck, mosi, miso, cs=…)`, `UART(tx, rx)` and `USB2(dp, dn, vbus=…, gnd=…)` become model `Interface`s of kinds `i2c`, `spi`, `uart` and `usb2`, with fixed member roles.
- **Attach by role.** `bus.attach(part, sda=…, scl=…)` connects a part's pins by role. `UART.attach(part, side="b", …)` crosses TX and RX for the second device, and SPI tells a controller from a peripheral and its chip select.
- **Build checks**: `build.diff-pair-name` when the two nets of a `diff_pair` or `usb2` interface do not form a KiCad pair by name; `build.i2c-pullup-missing` when an I2C line has no two-pin part to the high net of a `Power` interface.
- **Altium**: the new kinds are reported as not lowered, as diff pairs already are.

Size: 8 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-dsl`: MODIFIED "Interfaces in the DSL"; ADDED "Quantities in the DSL", "Part values from quantities", "Typed interfaces in the DSL", "Attaching parts to interfaces", "Interface checks in a build".
- `altium-build`: ADDED "Typed interfaces in an Altium build".
- `kicad-oracle`: ADDED "Differential pair names are probed".

## Non-goals

- No values shipped: no pull-up value, bus speed, impedance or USB geometry. Fenolite checks structure, and the user gives every number (plan D6).
- No unit algebra (`V / A`) and no quantity in the model or in `.fenolite/`.
- No differential-pair rules (gap, skew, length): v0.6 in the plan's rules row.
- No lowering of typed interfaces to KiCad files, which have no place for them; they stay in `.fenolite/`.
- No part database: which pin is SDA is the script's to say.

## Evidence level required

- New row `H-K-DIFFPAIR-NAMES`, settled by the probe on both majors; `build.diff-pair-name` cites it.
- Quantities, interfaces and the pull-up check are mechanical: tested by unit scenarios, nothing to probe.

## Impact

- New: `src/fenolite/dsl/quantity.py`, `tests/unit/dsl/test_quantity.py`, `tests/unit/dsl/test_interfaces_typed.py`, `tests/kicad/rules/test_diffpair_names.py`.
- Changed: `dsl/interfaces.py`, `dsl/part.py`, `dsl/__init__.py`, `lens/build.py`, `lens/altium.py`, `docs/dsl.md`, `docs/formats/kicad/rules.md`.
- No dependency on v0.2a.
