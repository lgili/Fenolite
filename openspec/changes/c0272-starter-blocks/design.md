## Context

- **Source.** `docs/research/circuit-blocks.md` (2026-10-29), section 3.6 "The first five blocks" and the row
  c0272 of section 4. Clean-room: the blocks, their parameters, their relations and their layouts are
  authored for Fenolite. No block, value table, schematic, layout or API name of another tool is used, and
  no vendor reference design or application note is read for content. Relations are written in Fenolite's
  words with their public sources (decision 8).
- **What the batch gives.**
  - c0251: `@block`, ports, local nets, `design.use`; c0252: `Rail`, `Ground`, `Logic`, `I2C` ports, port
    parameters (`reference`), the stage `circuit.rules` and `circuit.bus-pullup`.
  - c0253: `expect(test, reason)` with `within`, `at_least`, `at_most` over `value_of`, `rating_of`,
    `voltage_of`, `current_of` and c0246 ranges; `design.rig`; three-valued judgement; the requirement table.
  - c0254: queries and generators (`voltage_divider`, `rc_lowpass`, `led_resistor`, `i2c_pull_ups`) with
    exact search, `gen.achieved` and `gen.unachievable`, π and the I2C rise-time constant replaced by
    rational enclosures; the E-series table and the I2C mode constants, registered by c0254.
  - c0268: `@block(id=, version=, summary=, category=, sources=)`, `param(default, *, doc, min, max,
    choices)`, port docs, `fenolite blocks list|show|doc`.
  - c0269: `b.schematic(...)` groups local to a block. c0270: the test convention and `stimulus`. c0271: the
    block layout file, `fenolite blocks capture`.
  Task 0.1 records the final names of each.
- **Shipped catalog.** `Fenolite:Resistor`, `Fenolite:Capacitor`, `Fenolite:LED` and `Fenolite:Diode` symbols
  and the footprints `Fenolite:Chip_0603`, `Fenolite:LED0603_Kingbright_APT1608SURCK` and
  `Fenolite:SOD323_Diodes` exist on `dev`, each with its registered sources.

## Goals / Non-Goals

**Goals**

- Five blocks small enough to read in one sitting, each judged on every build by its own expectations.
- Every number either the user's (a parameter), a device's (c0248 rating), a series value (c0254), or a
  constant of a registered public source; nothing invented.
- Each block passes its usage build, tests and golden comparison (c0270) and ships a layout (c0271).

**Non-Goals**

- See the proposal. Also: no SPICE, no temperature effects, no tolerance stacking other than worst case.

## Decisions

### 1. Package and conventions

```
src/fenolite/blocks/
  __init__.py      # exports voltage_divider, rc_lowpass, led_indicator, i2c_pullups, protected_input
  divider.py  rc.py  led.py  i2c.py  protect.py
  usage/<name>.py  tests/test_<name>.py  golden/<name>.json  layouts/<name>.toml
```

- c0268 creates the package `fenolite.blocks` (allowed to import `dsl`, `model` and `core`; imported by
  `cli` and the root modules). The starter block modules keep to a narrower set: `fenolite.dsl` (with
  c0254's generators), `fenolite.core` and the standard library. The import-graph test gets the row.
- Each block gets its row in c0268's `VERSIONS.toml` for blocks, checked by its version test. The import-graph test gets the row.
- The block names equal the ids' names. c0254's generators have similar names in `fenolite.dsl`; a generator
  makes parts inside the caller's block, a block is instanced with `design.use`. Passing a generator to
  `design.use` raises c0251's `DslError`, whose hint names the block of the same purpose.
- **Expectations read nets on power ports, parameters on signal ports.** A `Rail` or `Ground` port is bounded
  by c0252 in a real design, so its expectation reads `voltage_of(port)` and is judged with the real
  wiring. A signal port is rarely bounded, so an expectation about it uses the block parameter that states
  its range; otherwise every design would carry `circuit.expect-unknown` warnings.
- **Ratings at 100 %.** c0253 applies the user's derating policy to its own ratings checks, not to
  expectations. The power expectations below compare against `rating_of(part, "power")`; a design that needs
  margin states a derating policy, which c0253's automatic check applies wherever both voltages of a part
  are known (open question 1).
- Every block is `version="1.0.0"`, `licence` Apache-2.0 (from the package), `evidence` `INFERRED`.

### 2. `Fenolite:voltage_divider`

```python
import fenolite.dsl.generators as gen
from fenolite.dsl import Ground, Net, Rail, amp, at_least, between, block, param, value_of, volt
from fenolite.dsl import rating_of, voltage_of, within


@block(
    id="Fenolite:voltage_divider",
    version="1.0.0",
    summary="Resistive divider with a worst-case output range",
    category="analog",
    sources=["S-DIV", "S-JOULE", "S-INTERVAL"],
)
def voltage_divider(
    b,
    *,
    vin=param(volt("12").pct(2), doc="input range, HI against LO, used to choose the resistors"),
    vout=param(volt("3.3").pct(5), doc="accepted output range"),
    current=param(between(amp("50u"), amp("200u")), doc="divider current window at nominal input"),
    series=param("E96", choices=("E24", "E96"), doc="resistor series"),
):
    hi = b.port("HI", Rail, direction="in", doc="input")
    out = b.port("OUT", Net, direction="out", doc="divided output, unloaded")
    lo = b.port("LO", Ground, direction="in", doc="reference")
    top, bot = gen.voltage_divider(b, hi, out, lo, target=vout, vin=vin, current=current, series=series)
    b.schematic(column=[top, bot], title="Divider")
    b.expect(within(voltage_of(hi) / (1 + value_of(top) / value_of(bot)), vout), "output in range")
    b.expect(at_least(rating_of(top, "power"), voltage_of(hi) * voltage_of(hi) / value_of(top)), "top power")
    b.expect(at_least(rating_of(bot, "power"), voltage_of(hi) * voltage_of(hi) / value_of(bot)), "bot power")
    b.layout(reuse="layouts/voltage_divider.toml", copper=True)
```

(`S-DIV` and the other `S-` names here are placeholders for the ids task 0.2 registers.)

- **Output.** `VOUT = VHI / (1 + Rtop / Rbot)` for an unloaded divider. Each resistor appears once, so
  c0253's interval arithmetic gives the exact worst case (`S-INTERVAL`: an expression in which every
  variable occurs once and that is monotone in each is bounded exactly by its corners).
- **Power.** The whole input across one resistor bounds its power from above (`P = V² / R`, `S-JOULE`); it
  is conservative and never needs `voltage_of(OUT)`, which nothing states.
- **Why `vin` and `voltage_of(HI)`.** The generator runs in the block body, before the outside connects HI,
  so it cannot read the rail; `vin` chooses the resistors. The expectation reads the real rail, so a block
  chosen for 12 V ± 2 % and wired to a 12 V ± 10 % rail is judged against the rail.
- **Worked numbers** (scenarios; c0254's search and choice rules, E96 1 %): defaults → top 137 kΩ, bottom
  52.3 kΩ, output 3.202246 V to 3.430848 V (bounds rounded outward to 1 µV), nominal 3.315372 V; top power at
  most 1.104606 mW, bottom 2.893517 mW. With `vin=volt("12").pct(10)` no E96 1 % pair stays in 3.3 V ± 5 %:
  `gen.unachievable`, best pair 107 kΩ over 40.2 kΩ, 2.906770 V to 3.657539 V.

### 3. `Fenolite:rc_lowpass`

- Ports `IN` (`Net`, in), `OUT` (`Net`, out), `GND` (`Ground`, in). Parts `r` and `c`.
- Parameters: `corner` (default `hertz("1k").pct(20)`, the accepted cut-off range), `c` (default
  `farad("100n")`, the fixed capacitor value; `None` lets c0254 choose it), `c_tolerance` (default `pct(10)`),
  `series` (`"E96"`), `voltage` (default `volt("5")`, the highest voltage across the capacitor).
- Body: `b.defaults(capacitor={"tolerance": c_tolerance, "rating": voltage})`, then
  `gen.rc_lowpass(b, inp, out, gnd, corner=corner, c=c)`.
- Expectations: `within(1 / (2 * gen.PI * value_of(r) * value_of(c)), corner)` ("cut-off in range"), where
  `gen.PI` is c0254's enclosure of π as a ratio range `[3.14159265358, 3.14159265359]`; and
  `at_least(rating_of(c, "voltage"), voltage)` ("capacitor voltage rating").
- Relation: `f = 1 / (2πRC)` for a first-order RC low-pass (`S-RC`). With π enclosed, the judged range
  contains the exact one; the enclosure widens it by less than one part in 10¹¹.
- **Worked numbers:** defaults → `r` 1.58 kΩ (E96 1 %), cut-off 906.669 Hz to 1130.538 Hz (outward to
  1 mHz). With `corner=hertz("1k").pct(10)` the capacitor's ± 10 % alone exceeds the window:
  `gen.unachievable`.

### 4. `Fenolite:led_indicator`

- Ports `HI` and `LO` (`Net`, in). Current flows from `HI` through the resistor `r` and the LED `led` to
  `LO`. A pin driving high on `HI` with `LO` on ground, or a rail on `HI` with a pin pulling low on `LO`, are
  the two wirings of one topology, so one layout serves both.
- Parameters: `drive` (default `volt("3.3").pct(5)`, the voltage between HI and LO when on), `current`
  (default `amp("2m").pct(50)`), `led` (a c0248 device id, default `None`), `vf` (forward voltage range,
  default `None`), `led_current_max` (default `None`), `source_limit` (default `None`, the most current the
  driving pin may give or take), `colour` (default `"red"`, written into the LED's value text, no electrical
  meaning), `led_footprint` (default `"Fenolite:LED0603_Kingbright_APT1608SURCK"`), `series` (`"E96"`).
- `vf` and the LED's current rating come from the device record when `led` is given, else from `vf` and
  `led_current_max`; neither given is a `DslError` at `design.use` ("state the LED's forward voltage").
  Fenolite ships no LED electrical data.
- Body: `gen.led_resistor(b, hi, led, current=current, vf=vf)` with the LED part between the resistor and
  `LO`; the generator's choice rule (c0254) picks `r`.
- Expectations, with `i = (drive − vf) / value_of(r)` where `drive − vf` is computed exactly as a literal
  range (`S-LED`):
  - `within(i, current)` ("LED current in window");
  - `at_least(rating_of(led, "current"), i)` with a device, or `at_least(led_current_max, i)` ("LED current
    rating");
  - `at_least(source_limit, i)` when `source_limit` is given ("driving pin current");
  - `at_least(rating_of(r, "power"), (drive − vf) * (drive − vf) / value_of(r))` ("resistor power",
    `S-JOULE`).
- **Worked numbers:** defaults with `vf=volt("2").pct(10)` → `r` 649 Ω (E96 1 %), current 1.426413 mA to
  2.591400 mA, resistor power at most 4.314680 mW.
- Layout property: pad 1 of the LED land (its cathode, c0144's cathode-first lands) is on `LO`, and the
  footprint's polarity mark lies on the side of `LO` in the layout.

### 5. `Fenolite:i2c_pullups`

- Ports `BUS` (`I2C`, inout, with c0252's `reference` set to `RAIL`) and `RAIL` (`Rail`, in). Parts `r_sda`
  and `r_scl`.
- Parameters: `mode` (`"standard"`, choices `"standard"`, `"fast"`, `"fast-plus"`), `vdd` (default
  `volt("3.3").pct(5)`, the rail range used to choose), `bus_capacitance` (default
  `between(farad("10p"), farad("200p"))`), `series` (`"E24"`).
- Body: `gen.i2c_pull_ups(b, bus, rail, bus_capacitance=bus_capacitance, mode=mode)` (one value for both
  lines, the largest series value inside the window).
- Expectations per line resistor, with `vol`, `iol` and `rp_max` read from c0254's recorded mode constants
  through `gen.i2c_mode_limits(mode, bus_capacitance)` (`UM10204`, cited by document id; no table is
  restated here):
  - `at_least(value_of(r), (voltage_of(rail) − vol) / iol)` ("pull-up not below the bus minimum");
  - `at_most(value_of(r), rp_max)` ("pull-up not above the rise-time maximum").
- **One pull-up set per bus.** Two blocks on one bus put resistors in parallel; c0253's expectations of
  each block cannot see the other. The stage `circuit.rules` gains `circuit.pullup-parallel` (warning): a
  line of an `i2c` bus joined to a rail through more than one resistor, naming the line, the resistors and
  their parallel range. It is computed from c0252's bus members and part classes, for any design.
- Whether the rail is the bus's reference stays c0252's `circuit.bus-pullup`.

### 6. `Fenolite:protected_input`

- Ports `EXT` (`Net`, in: the connector side), `INT` (`Net`, out: toward the protected input), `GND`
  (`Ground`, in). Parts `tvs` (the protection device between `EXT` and `GND`) and `r` (in series, `EXT` to
  `INT`).
- Parameters: `signal` (default `between(volt(0), volt(5))`, the external signal in normal operation),
  `protection` (a c0248 device id, required), `clamp` (the protection's clamping range at the surge the user
  designs for, required), `r_series` (default `ohm("1k")`), `abs_max` (the downstream input's absolute
  maximum voltage, required), `inject_max` and `hold` (default `None`: the current the downstream's internal
  clamps accept, and the voltage they hold `INT` at).
- Expectations (`S-TVS` for the terms, `S-DIV` for Ohm's law):
  - `at_least(rating_of(tvs, "voltage"), signal)` ("protection working voltage covers the signal");
  - without `inject_max`: `at_most(clamp, abs_max)` ("clamp below the downstream maximum");
  - with `inject_max` and `hold`: `at_least(inject_max, (clamp − hold) / value_of(r))` ("current into the
    downstream clamps limited").
- **Worked numbers** (scenarios): `clamp=volt("9.2").max()`, `hold=volt("3.6")`, `inject_max=amp("5m")`:
  1 kΩ ± 1 % gives at most 5.656566 mA, `circuit.expect-failed`; 1.5 kΩ gives at most 3.771044 mA, pass.
  Without `inject_max` and with `abs_max=volt("3.6")`, the 9.2 V clamp fails the second expectation.
- Layout property: the protection device is the part nearest the `EXT` edge of the frame, and its return to
  `GND` is at most 1.5 mm of copper from its pad to the ground via.
- The shipped layout is for a protection device on `Fenolite:SOD323_Diodes`; another package changes the
  `parts_digest`, and c0271 refuses the layout with `reuse.layout-stale`.

### 7. Tests, usage, goldens and layouts (c0270, c0271)

| block | tests (each a `test_*` function on `fenolite.testing`) |
|---|---|
| `voltage_divider` | math grid (vout 1.8, 2.5, 3.3, 5 V against a brute-force corner evaluation); the unreachable target is `gen.unachievable`; two instances do not collide in refs or nets; the power rows pass |
| `rc_lowpass` | math grid; the ± 10 % corner is `gen.unachievable`; the capacitor voltage row; golden |
| `led_indicator` | math; the LED rating row with a device and with `led_current_max`; `source_limit` failing at 1 mA; polarity of the layout |
| `i2c_pullups` | netlist (two blocks on one bus give `circuit.pullup-parallel`; two buses give none); math (the chosen value inside the window for each mode and capacitance corner); the reference rail |
| `protected_input` | ratings (pass at 5 V, fail at 6 V); the injected-current rows; layout property (protection at the EXT edge, short return) |

- Each usage example builds a small board with the block, a connector for its ports and a rig; each golden
  is written by `fenolite blocks test ID --golden --confirm`.
- Each layout is captured from the block's usage board by `fenolite blocks capture` and committed; the
  KiCad jobs build every usage board for targets 9 and 10 and run KiCad DRC on it (c0271's
  `H-K-BLOCK-LAYOUT-DRC`).
- The usage example of `protected_input` uses a project device record authored for it
  (`examples`-style namespace `Example:`, evidence `UNVERIFIED`, its numbers marked as illustrative), never
  a vendor part.

### 8. Sources (registered at task 0.2)

| placeholder | what is used | source |
|---|---|---|
| `S-DIV` | output of an unloaded two-resistor divider; Ohm's law | a public textbook page on the voltage divider (for example the encyclopedia article "Voltage divider") |
| `S-JOULE` | power in a resistor, `V² / R` and `I² R` | a public page on Joule heating |
| `S-RC` | cut-off of a first-order RC low-pass, `1 / (2πRC)` | a public page on the RC circuit |
| `S-LED` | series resistor of an LED, `(V − VF) / R` | a public page on LED circuits |
| `S-INTERVAL` | exact bounds of an expression where each variable occurs once | a public page on interval arithmetic |
| `S-TVS` | stand-off (working) and clamping voltage of a protection diode | a public page on transient-voltage-suppression diodes |
| `UM10204` | the bus limits by mode, through c0254's registered constants | NXP "I2C-bus specification and user manual", document UM10204, cited by id only (c0254 registers it) |

Each row records its licence and "read for facts, nothing copied"; every relation above is written in
Fenolite's words.

### 9. Generated documentation

- c0268's `tools/gen_block_docs.py` writes `docs/blocks/index.md` and `docs/blocks/<name>.md` from the
  records with the `fenolite blocks doc` renderer; this change adds the first five pages. Beside c0268's
  sections (summary, parameters, ports, sources), each starter page shows its expectations (their
  reasons), the usage example (included from the file) and the layout's footprints, which the tool reads
  from c0270's and c0271's conventions.
- `tools/gen_block_docs.py --check` fails on drift; `tests/unit/blocks/test_block_docs.py` runs it.
- `docs/dsl.md` links the index; the guide's `design-script` page gains the tested line.

### 10. Next blocks (later, not in this change)

Decoupling set (c0247's `decouple` as a block), reverse-polarity protection, crystal with load capacitors,
reset network, connector with ESD protection. Each needs a source for its relations and is its own change.

### 11. Codes and evidence

| code | severity | when |
|---|---|---|
| `circuit.pullup-parallel` | warning | a line of an `i2c` bus is joined to a rail through more than one resistor |

It joins `checks.codes.ISSUE_CODES`, explained by `fenolite explain`, listed in `docs/cli-contract.md`,
"Circuit checks". No new `FEN-` code.

| behaviour | level before merge |
|---|---|
| expectations and generator results | `INFERRED`, `H-G-STARTER-ENCLOSURE`: for each block, a property test evaluates every corner of the parameter and tolerance ranges exactly and checks that the judged range encloses them |
| `circuit.pullup-parallel` | `INFERRED`, unit tests |
| usage boards and layouts | `KICAD-VERIFIED` read-back; `H-K-BLOCK-LAYOUT-DRC` (c0271) |

## Risks / Trade-offs

- **Generator choices change with c0254's tables.** A new family or a corrected series value can change a
  pick; the golden files and the lock (c0254 picks) make it a reviewed change.
- **Conservative power bounds** can flag a resistor that is fine in practice (the whole input across one
  resistor). The reason text says "upper bound"; a larger case or a smaller input fixes it.
- **Vendor-named footprints** (`LED0603_Kingbright_APT1608SURCK`, `SOD323_Diodes`) are catalog lands with
  their sources, not reference designs; a user's other land changes the digest and refuses the layout.

## Open Questions

1. Should c0253 offer a derated rating handle (`rating_of(part, key, derated=True)`) so that block
   expectations apply the user's policy? **Recommended:** yes, as a small follow-up of c0253; until then
   blocks judge at 100 %.
2. Should `led_indicator` ship a generic LED forward-voltage default by colour? **Recommended:** no; it needs
   a source per colour, and a wrong default hides an unstated number.
3. Should `circuit.pullup-parallel` be part of c0252 instead? **Recommended:** keep it here, where the first
   block that can cause it ships; c0252's stage owns the code table either way.
4. Should the starter blocks live in a separate package from the start? **Recommended:** no (research
   question 1): in the core, versioned with Fenolite; c0273 serves further blocks from `fenolite-library` (c0279).

## Relation to the other changes of this batch

- **c0268**: records and parameter metadata of the five blocks; `blocks doc` renders their pages.
- **c0269**: `b.schematic(column=[top, bot])` and the other groups; KiCad hierarchical pins from the ports.
- **c0270**: the usage examples, tests and golden files follow its convention and run in its CI.
- **c0271**: one layout per block, captured from the usage board; the LED polarity and the protection
  layout properties are tests on it.
- **c0273**: further blocks in `fenolite-library`; the starter blocks are the model for its CI.
- **c0254**: the generators and constants; **c0253**: the expectations; **c0252**: rails, buses and the stage.
