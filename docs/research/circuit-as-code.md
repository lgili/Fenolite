# Circuits as code: what JITX, atopile and tscircuit teach Fenolite

Status: **research, nothing here is implemented**. Every "Proposed" snippet is a design sketch to be
argued in OpenSpec changes; names may change. Date: 2026-10-29.

This page compares how the three best-known "PCB as code" tools write a circuit with how Fenolite writes
it today (0.6.0), and proposes changes to Fenolite's core. Each topic shows **Today** (real Fenolite
code), **What the others do** (described in words, with the public source), and **Proposed** (Fenolite
code as it could look).

Clean-room: only concepts are taken. No code, grammar, schema, library text, constant or table of these
projects is copied, whatever their licence (atopile and tscircuit are MIT, JITX is proprietary). The
short descriptions below paraphrase public documentation; numeric facts we adopt later come from public
standards recorded in `docs/formats/` with evidence labels.

## Sources

| Tool | Version read | Main public sources |
|---|---|---|
| JITX | Python API 4.x (4.4.3, 2026-10); the older Stanza language is legacy | docs.jitx.com/en/latest (design hierarchy, pin assignment, SI topology and constraints, kinematic tree, design constraints, footguns, parts query API, voltage divider); blog.jitx.com "What's new in JITX 2025"; pypi.org/project/jitx |
| atopile | 0.14.x (repository `main`, 2026-03) | github.com/atopile/atopile: README, `examples/` (equations, auto-picking, layout_reuse, esp32_minimal), in-repo language reference, `src/faebryk/library` (ElectricPower, bus-parameter traits, design checks), `src/atopile/layout.py`, `kicad_plugin/README.md` |
| tscircuit | current docs (2026-10) | docs.tscircuit.com (elements, layout properties, relative positioning, automatic layout, manual edits, autorouter, tsci export/snapshot/check); github.com/tscircuit/circuit-json and /props |

Items that could not be confirmed from a public page are marked UNVERIFIED.

## The one-paragraph summary

- **JITX** is the most complete:
  - parts carry full device data;
  - ports are typed bundles that connect as a whole;
  - pins are assigned at the interface level ("give me one I2C");
  - ordered topologies carry signal-integrity constraints in time and dB;
  - rules are selected by tags with a documented specificity;
  - generators take requirements and return parts plus the tolerance they achieve.

  Its weak points are layout and pin choices kept as hidden UI state, metaclass magic, floats, and a live
  parts database.
- **atopile** is the clearest about values:
  - every value is a range with tolerance;
  - interface parameters are either *equal across a connection* (rail voltage) or *summed*, where loads
    must not exceed sources (current);
  - design checks travel with the interface type;
  - packages ship a laid-out sub-board;
  - hierarchical paths are the identity that keeps layout across rebuilds.

  Its weak points are an opaque constraint solver, picks hidden inside the `.kicad_pcb`, and feature
  pragmas.
- **tscircuit** is the best at the edit loop:
  - live preview on save;
  - drag edits kept in a separate, diffable file, with a warning when code and edit disagree;
  - placement relative to other parts, pads and the board edge;
  - layout strategies per group (row, grid, pack);
  - diagnostics as typed records linked to the offending part or pin;
  - visual snapshot tests in CI.

  Its weak points are untyped string selectors, a logical connection and a copper trace being the same
  element, float units, and silent supplier auto-selection.

Fenolite already does several things better than all three: integer nanometres and microdegrees,
evidence labels, plan/confirm writes with receipts, byte-identical outputs, net roles for power
electronics, KiCad *and* Altium output, and no runtime dependency in the core. The proposals below keep
all of that.

## Where Fenolite stands today (0.6.0)

| Concept | Fenolite today | Gap |
|---|---|---|
| Part | `Part("R1", "Fenolite:Resistor", footprint=..., value="330")` | refs by hand; no MPN, ratings or tolerance; symbol and footprint chosen apart and joined by `pad_map` |
| Connection | `connect(net, *pins)` | verbose; no series chain; unused pins marked one by one |
| Hierarchy | `Module(name)` = named container; reuse by a Python function closing over global nets | no ports, no parameters, net names and refs prefixed by hand |
| Interfaces | `I2C(sda, scl)`, `Power(hv, lv)`, `bus.attach(part, sda=...)` | no parameters (voltage, speed, current); two interfaces cannot be connected |
| Values | exact `ohm("4k7")`, `volt("3.3")`; lengths in nm | no tolerance or range; quantities never reach the model |
| Requirements | rules, selectors, net roles, `requirements.toml` (raw `_nm` keys) | nothing checks part ratings against the circuit; requirements split between DSL and TOML |
| Part choice | by hand | no parametric choice, no lock, no variants |
| Placement | `place(x, y)`, intents `near()` checked not applied, `fenolite place --strategy ...` | no relative placement, no anchor by pad, no per-module layout strategy |
| Manual edits | the board wins for layout; `sync --to-source` writes `placements.toml` | value, footprint and property edits are overwritten; no per-property merge |
| Testing | `fenolite check`, `fenolite.api.run` | no assertion API on the circuit; no snapshot helper |

---

## 1. Parts that are complete devices

**Today.** A part is a symbol plus a footprint plus free text:

```python
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="10uF", properties={"MPN": "X-1"})
```

The catalog (`src/fenolite/catalog`) holds geometry and provenance only.

**What the others do.**
- *JITX:* a component class holds its ports, land pattern, symbol, pad and pin mappings, MPN,
  manufacturer, reference prefix, and BOM and assembly flags. It keeps three layers: port (logical), pin
  (schematic), pad (physical).
- *atopile:* an imported part is a component file stamped with its source, date and a checksum, so a hand
  edit is detected.
- *tscircuit:* a chip carries `manufacturerPartNumber`, supplier part numbers and pin labels.

**Proposed.** A `Device` in the catalog joins everything once, with evidence. A part is placed from a
device, and the symbol, footprint and pin map come with it.

```toml
# src/fenolite/catalog/devices/example_buck_6v_2a.toml  (illustrative device, authored for Fenolite)
schema = "fenolite.device.v0"
id = "Example:BUCK_6V_2A"
manufacturer = "Example Semi"
mpn = "EXB6202"
datasheet = "https://example.invalid/exb6202.pdf"
symbol = "Fenolite:Buck_Regulator_6pin"
footprint = "Fenolite:SOT23_6"
ref_prefix = "U"
evidence = "UNVERIFIED"          # raised to CORPUS-VERIFIED once the pin map is reviewed

[pins]                            # function -> pad, reviewed once
VIN = "5"
GND = "2"
SW = "6"
BST = "1"
EN = "4"
FB = "3"

[ratings]                         # what checks compare against
vin = { max = "6V" }
iout = { max = "2A" }
temperature = { min = "-40degC", max = "125degC" }
```

```python
u1 = design.part(device="Example:BUCK_6V_2A")  # ref assigned: U1 (see section 3)
connect(vin, u1.VIN)  # pin by function, checked against the device
```

**Core change.**
- `catalog` gains a `Device` record: manufacturer, MPN, datasheet, symbol, footprint, function-to-pad
  map, ratings, evidence.
- `Part` gains `device=`.
- `u1.VIN` becomes attribute access that is checked: a wrong name is a `DslError` that lists the closest
  pin names.

## 2. Values with tolerance (ranges)

**Today.** `ohm("10k")` is exact. There is no tolerance outside impedance targets.

**What the others do.**
- *atopile:* every literal is a range (`10kohm +/- 5%`, `3V to 3.6V`), and a zero-tolerance value is
  warned against because no real part matches it.
- *JITX:* a `Toleranced` (min/typ/max) does worst-case arithmetic.

Both use floats.

**Proposed.** A `Range` stored as exact integer bounds (or `Fraction`s, as quantities are today), built at
the DSL boundary only:

```python
v33 = volt("3.3").pct(3)  # 3.201 V .. 3.399 V
r_top = ohm("100k").pct(1)
ripple = between(mv(0), mv(30))
i_load = amp("1.5").max()  # 0 .. 1.5 A
vout = vref * (1 + r_top / r_bot)  # worst-case range arithmetic, exact
vout.within(v33)  # -> bool, used by checks (section 7)
```

**Core change.**
- `quantity.py` gains `Range`, with `pct()`, `between()`, `.min`, `.max`, `.nominal`, worst-case
  `+ - * /` and `within()`.
- There is no solver: arithmetic and comparisons only (atopile's solver is its most criticised part).

## 3. Reference designators and identity

**Today.** Every ref is typed by hand. Repeated blocks number them by hand (`n*100+k`).

**What the others do.**
- *atopile* keys layout on the hierarchical path (`power.buck.c_in`), not on the ref. It keeps refs, net
  names and picks stable across rebuilds ("frozen" mode for releases).
- *JITX* warns that renaming the design class loses the stored layout.
- *tscircuit* keys manual edits on refs, so a rename orphans them.

**Proposed.**
- Identity is the **path** (`buck1/L`). Fenolite ids are already path-based (`docs/design-model.md`).
- Refs are assigned automatically per prefix in a deterministic order, then **recorded in a lock file**
  so they never change by themselves.
- A hand ref still works, and wins.

```python
l1 = design.part(device="Example:IND_4u7_3A")  # -> L1, recorded in design.lock
r5 = design.part("R5", device=...)  # explicit ref, kept
```

```toml
# design.lock  (written by build --confirm; reviewed in git like any lockfile)
schema = "fenolite.lock.v0"
[refs]
"buck1/U" = "U1"
"buck1/L" = "L1"
"sensor/R_pull_sda" = "R3"
```

`design.moved()` (already there) carries ids across a rename. `build --frozen` refuses any change to the
lock (refs, picks, pin choices) and exits 7.

**Core change.**
- A `design.lock` file holds refs, part picks (section 8) and pin choices (section 12).
- The lock is written through the plan/confirm protocol.
- Add `--frozen`.

## 4. Blocks with ports and parameters

**Today.** `Module` is a named container. A reusable circuit is a function that closes over global nets
and names everything by hand (`examples/yardstick/design.py`).

```python
def channel(n, x, y):
    m = Module(f"ch{n}")
    en = Net(f"CH{n}_EN")
    r = Part(f"R{n * 100 + 1}", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
    connect(en, r[1])
    connect(vin, r[2])  # vin is global
    ...
```

**What the others do.**
- *JITX:* a `Circuit` class with ports; parameters in the constructor; ports that connect to exactly one
  component port "dissolve" into it; schematic groups labelled by path.
- *atopile:* `module` with `interface` children, arrays, and a check that a block's port is used from
  outside.
- *tscircuit:* a subcircuit isolates nets and refs; a group is layout-only.

**Proposed.** A block is a plain function with typed ports. Its nets are local (auto-prefixed) unless
exported as a port. Instances are made with `design.use`. No metaclass and no class-body magic (JITX's
own "footguns" page lists what that costs).

```python
from fenolite.dsl import block, Rail, Ground, volt, amp


@block
def buck(b, *, vout=volt("3.3").pct(5), current=amp(2)):
    """12 V -> vout step-down. Ports: VIN, VOUT, GND."""
    vin, out, gnd = b.port("VIN", Rail), b.port("VOUT", Rail, provides=True), b.port("GND", Ground)
    u = b.part(device="Example:BUCK_6V_2A")
    l = b.part(inductor(henry("4u7").pct(20), current=current * 1.3))
    fb = b.net("FB")  # becomes buck1/FB, never collides
    top, bot = voltage_divider(b, out, fb, gnd, target=vout, ref=volt("0.6").pct(1))
    connect(vin, u.VIN)
    connect(gnd, u.GND)
    connect(fb, u.FB)
    series(u.SW, l, out)
    decouple(vin, gnd, capacitor(farad("10u"), rating=vin.voltage * 2), near=u.VIN)
    out.supplies(voltage=vout, current=current)  # what the port promises
    return b.ports()


p1 = design.use(buck, "buck1", vout=volt("3.3").pct(5))
p2 = design.use(buck, "buck2", vout=volt("5").pct(5))
connect(v12, p1.VIN, p2.VIN)
connect(gnd, p1.GND, p2.GND)
```

**Core change.**
- `Module` grows into a block. It has ports (name, interface type, direction), parameters (keyword
  arguments, recorded in the model), local nets, a ref namespace and a check that ports are used (a
  `FEN-` finding).
- Schematic groups come from the block path, which is already partly there via `schematic_block`.

## 5. Interfaces with parameters, connected as a whole

**Today.**

```python
bus = I2C(sda, scl)
design.add(bus)
bus.attach(u1, sda=u1["PB7"], scl=u1["PB6"])
design.add(Power(vin, gnd))  # a record; carries no voltage
```

**What the others do.**
- *atopile:* a power interface has `hv`, `lv`, voltage and current. A connection *aliases* the voltage
  (one rail, one voltage) and *sums* the currents (loads ≤ sources). A logic line carries its reference
  rail. Whole buses connect in one statement. ERC flags shorted rails, two sources tied together, a rail
  with no voltage, and incompatible types.
- *JITX:* typed bundles. Connecting two bundles nets every member and type-checks them. Compatibility
  goes by lane configuration rather than exact type.

**Proposed.** Interfaces become typed ports on devices and blocks, with parameters:

```python
mcu = design.part(device="Example:MCU_QFN32")  # the device declares mcu.i2c1 (I2C), mcu.vdd (Rail)
sen = design.part(device="Example:SENSOR_I2C")
rail = design.rail("3V3", voltage=volt("3.3").pct(3))

connect(mcu.i2c1, sen.i2c)  # nets SDA-SDA, SCL-SCL; FEN- finding on a type mismatch
connect(rail, mcu.vdd, sen.vdd, p1.VOUT)
pull_up(mcu.i2c1, rail, ohm("4k7").pct(1))  # one call for both lines
```

The checks that come with it:

| Check | Meaning | Example finding |
|---|---|---|
| rail.voltage | every pin on a rail accepts the rail's range | `SEN.vdd accepts 1.7–3.6 V; 3V3 is 3.201–3.399 V`: ok |
| rail.current | sum of loads ≤ sum of sources | `3V3: loads 2.3 A > buck1 2 A` |
| rail.sources | two sources tied without a declared sharing part | `buck1.VOUT and J2.VBUS drive 5V0` |
| logic.level | a logic line driven at one reference rail and read at another | `mcu.PA3 (3V3) drives sen.INT (1V8 input)` |
| bus.pullup | the I2C pull-up is present and within range (already `build.i2c-pullup-missing`, extended) | |

**Core change.**
- Every interface gets a parameter table. Each parameter is marked *alias* or *sum*, in integer ranges.
- `connect()` accepts two interfaces of compatible types.
- A `Logic` interface carries its reference rail.
- `Rail` replaces the bare `Power` record and keeps `Power` as an alias.
- The checks are a new `circuit.*` stage of `fenolite check`. It needs no tool.

## 6. Connection helpers

**Today.** Every pin goes through `connect()`. In blink, 29 unused pins are marked one by one.

**What the others do.**
- *atopile:* a series "bridge" (`a ~> part ~> b`) for two-terminal parts.
- *tscircuit:* `connections={{pin: net}}` on the part; a resistor may say which pin it pulls up.
- *JITX:* `no_connect()` on a port.

**Proposed.**

```python
series(vin, f1, d1, vprot)  # two-terminal chain: vin-F1-D1-vprot
decouple(rail, gnd, capacitor(farad("100n")), near=mcu.vdd)  # also records a near() intent
u1.unused_no_connect()  # every pin with no net and no "must connect" flag
r1.a, r1.b  # two-pin parts get named ends (a/b, or the device's +/-)
```

**Core change.** Helpers live in `fenolite.dsl` and lower to `connect`/`no_connect` and `near`. A device
pin may carry `must_connect=true`, so `unused_no_connect()` refuses to mark it.

## 7. Requirements and electrical contracts

**Today.** Requirements are spread over three places: DSL rules, net roles and `requirements.toml` (with
raw `clearance_nm = 1200000`). Nothing checks a part against the circuit.

**What the others do.**
- *atopile:* `assert x within range`, with equations written in the design; checks attached to interface
  types, run at stages (graph, after solving, after PCB) with fail / maybe-fail results; opt-out per
  check by qualified name.
- *JITX:* checks "written once, run every build"; a **test rig**, which instantiates the external world
  (a supply, a cable) so that voltages propagate to the checks.

**Proposed.** One requirement system extends the net roles (c0222):

- ratings come from devices (section 1);
- voltages and currents come from rails and roles;
- derating is a design policy;
- block authors add `expect()` lines;
- `requirements.toml` keeps working but takes units.

```python
design.derating(capacitor_voltage=pct(50), resistor_power=pct(50), semiconductor_tj=celsius(110))
design.net_role(vbus, "power", current=amp(20), voltage=volt(400))  # unchanged from 0.6.0

# inside a block: an explicit, explained expectation
b.expect(out.voltage.within(vout), "VOUT set by the divider")
b.expect(l.rating.current >= current * 1.3, "inductor saturation margin")

# test rig: context for checks only, never in the BOM nor on the board
design.rig(supply(v12, voltage=volt("12").pct(10), current=amp(3)))
```

```toml
# requirements.toml, same schema family, now with units (raw _nm keys still accepted)
[[distance]]
a = { net = "VBUS" }
b = { net = "*" }
clearance = "1.2mm"
source = "user"
```

Every check reports a `FEN-` finding with the entity ids, the value, the limit and where the limit came
from (device, role, policy or user). This is the "Constraint Manager" table, rendered by
`fenolite roles --check` and by the c0245 workspace.

**Core change.**
- A `circuit.ratings` check stage: cap voltage, resistor power, current, temperature, against derating.
- `expect()` records an assertion in the model, judged by the stage. It is not a Python `assert`, so one
  failure does not stop the build.
- `rig()` creates stimulus parts flagged out of the BOM, board and outputs.
- Units in `requirements.toml`.

## 8. Choosing parts by parameters, offline and locked

**Today.** By hand.

**What the others do.**
- *atopile:* parameter constraints plus a package, resolved against a hosted LCSC/JLC database. Picks are
  persisted as hidden properties inside the `.kicad_pcb`.
- *JITX:* `Resistor(resistance=..., tolerance=..., case=...)` queries a live database, with design-wide
  defaults that cascade down to modules and calls.
- *tscircuit:* a parts engine silently picks an in-stock part.

All three depend on a remote, changing database.

**Proposed.** The same convenience, but resolved against a **local, versioned catalog** and **written to
`design.lock`**. A supplier lookup is an optional extra that only *proposes* rows for the catalog.

```python
design.defaults(
    resistor={"case": "0603", "tolerance": pct(1)}, capacitor={"case": "0603", "dielectric": "X7R"}
)
r = design.part(resistor(ohm("10k")))  # case and tolerance from the defaults
c = design.part(capacitor(farad("10u"), rating=volt(25), case="0805"))
```

```toml
# design.lock
[picks."buck1/C_in"]
device = "Fenolite:Cap_0805_X7R_10u_25V"
query = "capacitor(10uF, >=25V, 0805, X7R)"
catalog = "fenolite-catalog 2026.10"
sha256 = "…"
```

A pick changes only through `fenolite pick --update PATH` (plan/confirm). A changed query that no longer
matches the locked part is a finding, not a silent swap.

**Core change.**
- Generic passives become queries.
- The catalog gains parametric rows (value, tolerance, rating, case, dielectric).
- The lock holds the picks.
- No network in the core.

## 9. Generators that return what they achieved

**What the others do.** *JITX's* voltage-divider solver takes `vin`, `vout` and a current, picks real
resistors, and returns the achieved output range (even over temperature). *atopile* writes the same
equations as assertions.

**Proposed.**

```python
top, bot = voltage_divider(
    b, out, fb, gnd, target=volt("3.3").pct(5), ref=volt("0.6").pct(1), series="E96", current=ua(50)
)
# top.value = 61.9k 1 %, bot.value = 13.7k 1 %; the achieved VOUT range is recorded:
#   evidence: "divider buck1/FB: VOUT 3.2247–3.3994 V within 3.135–3.465 V"
# (worst case counts the reference tolerance too; at ±3 % no E96 1 % pair fits, which is a finding)
```

Generators are pure functions over the local catalog, deterministic, and they write their computation to
the build evidence. Start with the divider, RC filter, LED resistor, pull-ups and the shunt value for a
current range.

## 10. Placement in code: relative, anchored, per block

**Today.** `u1.place(mm(14), mm(15), rot=90)`. `near()` is checked, never applied. Layout strategies are
CLI steps.

**What the others do.**
- *tscircuit:* positions as expressions over other parts, pads and the board (`R1.maxX + 2mm`); anchor a
  part by a pin; flex, grid and pack layouts per group.
- *JITX:* placement relative to the parent block, which makes a block's placed children a rigid group;
  "bottom" means the side opposite the parent.
- *atopile:* a package ships its own laid-out sub-board, which is pulled into the main board.

**Proposed.**

```python
c5.place(right_of=u1.pad("VDD"), gap=mm("0.5"), anchor=c5.pad(1))  # anchored by a pad
j1.place(left=board.left + mm(2), center_y=board.center_y, rot=90)
p1.layout(row(gap=mm(1)))  # strategy for the block's unplaced parts
p1.place(mm(10), mm(8))  # the whole block moves as one rigid group
p1.layout(reuse="blocks/buck.kicad_pcb")  # block layout shipped with the block, nets remapped by port
```

Precedence is written down (tscircuit leaves it as "TODO"):

1. locked `place()`;
2. the board;
3. `placements.toml`;
4. relative `place()`;
5. the block strategy;
6. staging.

**Core change.**
- `place()` accepts references (`right_of`, `left`, `anchor`). They are resolved to integer nm at build
  time and recorded in the evidence.
- Blocks get a pose and a layout strategy.
- Layout reuse (c0210/c0227) attaches to a block, with deterministic net mapping by port, not by majority
  vote.

## 11. Manual edits that survive: three-way, per property

**Today.**
- The board wins for layout, and `sync --to-source` writes positions to `placements.toml`.
- A value, footprint or property changed in KiCad is reported (`sync.value-differs`) and then
  overwritten.
- The schematic is regenerated, keeping only symbol positions.

**What the others do.**
- *tscircuit:* drag edits go to a separate `manual-edits.json` keyed by selector. A conflict with code
  gives an explicit warning.
- *atopile:* footprints matched by hierarchical address keep their position and routing.
- *JITX:* layout capture back into Python (4.4).

**Proposed.** A three-way merge per property, keyed by stable id. The three sides are *base* (last build,
already in `.fenolite/`), *code* (this build) and *CAD* (the edited file).

| base | code | CAD | result |
|---|---|---|---|
| A | A | B | B (keep the CAD edit), recorded in `edits.toml` |
| A | B | A | B (code changed) |
| A | B | B | B |
| A | B | C | **conflict**: build exits 5 with `sync.conflict`; resolve with `--take code` or `--take cad` per id and property |

```toml
# edits.toml  (generalises placements.toml; written by sync --to-source, reviewed in git)
schema = "fenolite.edits.v0"
["buck1/L"]
position = { x = "12.7mm", y = "30mm", rotation = "90deg" }
value = "6u8"                 # changed in KiCad; kept, and flagged by circuit checks if out of range
footprint = "Fenolite:IND_4x4"
```

Start with position, rotation, value and footprint. Fields and properties come next.

**Core change.**
- The board merge records *base* hashes per property.
- `edits.toml` replaces and extends `placements.toml` (which stays readable).
- Add the conflict finding and `--take`.

## 12. Pin assignment at the interface level (later)

**What the others do.** *JITX:* an MCU *offers* "an I2C on PB6/PB7 or PB8/PB9", and a consumer *requires*
one I2C. A solver picks. JITX fixes the choice only when the signal is routed, which leaves it as hidden
state.

**Proposed (later, after sections 4–5).** Same idea, solved at build time, deterministic under `--seed`,
shown in `result.plan` and recorded in `design.lock`:

```python
i2c = mcu.take(I2C)  # one of the device's declared I2C options
connect(i2c, sen.i2c)
```

```toml
[pins."mcu/i2c#0"]
choice = "I2C1 on PB8/PB9"
```

## 13. Topologies and signal-integrity constraints (later)

**What the others do.** *JITX:*
- ordered connections (`a >> r.p1`, `r.p2 >> b`) form a tree of pads;
- series parts carry a bridging model, so the constraint continues through them;
- constraints are given in delay and loss (fs, dB), and as protocol objects typed by bundle
  (`USB2`, ...).

**Proposed (later).** `design.topology(src.tx >> r_term >> dst.rx)` plus constraints in integer
femtoseconds and milli-dB, on top of today's `rules.pair` and `rules.impedance`. Rule selection already
has `select.*` with `& | ~`. Add documented **specificity** and print the winning rule per item in
`check`, as JITX's tag algebra does.

## 14. Diagnostics, reviews and tests

**What the others do.**
- *tscircuit:*
  - errors and warnings are typed records next to the geometry, linked to the part or pin;
  - `tsci snapshot` compares PCB and schematic images in CI;
  - net "x-ray" renders;
  - a style lint for odd angles.
- *atopile:* every library type carries a tested usage example.
- *JITX:* a lost (created but unattached) object is reported with its file and line.

**Proposed.**

```python
# tests/test_board.py: pytest helpers over the model, no kicad-cli
from fenolite.testing import load, snapshot


def test_rails():
    d = load("design.py")
    assert d.net("3V3").voltage.within(volt("3.3").pct(5))
    assert d.connected(d.ref("U1").VDD, d.ref("C5").a)
    assert not d.findings("circuit.*")


def test_layout_snapshot():
    snapshot("design.py", layers=("F.Cu",), net="GND")  # golden canonical render; diff in CI
```

- `fenolite render --net GND` highlights one net.
- Every finding carries entity ids, so the c0245 viewer can select them. This exists for findings on the
  board, and should be extended to circuit findings.
- A part or net created in the script but never added is a warning with its file and line.

---

## The same board, today and proposed

A 12 V input, a 3.3 V buck, an MCU and an I2C sensor. Illustrative devices, authored for this page.

**Today (0.6.0):**

```python
from fenolite.dsl import Design, Net, Part, Power, I2C, connect, no_connect, mm

design = Design("sensor")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="12V")
u1 = Part("U1", "Example:Buck", footprint="Fenolite:SOT23_6", value="BUCK")
l1 = Part("L1", "Fenolite:Inductor", footprint="Fenolite:IND_4x4", value="4u7")
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="10uF", properties={"MPN": "?"})
c2 = Part("C2", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="22uF")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="45k3")
r2 = Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
u2 = Part("U2", "Example:MCU", footprint="Fenolite:QFN_32", value="MCU")
u3 = Part("U3", "Example:Sensor", footprint="Fenolite:DFN_6", value="SENSOR")
r3 = Part("R3", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="4k7")
r4 = Part("R4", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="4k7")
c3 = Part("C3", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="100nF")
design.add(j1, u1, l1, c1, c2, r1, r2, u2, u3, r3, r4, c3)

v12, gnd, sw, v33, fb, sda, scl = (Net(n) for n in ("V12", "GND", "SW", "3V3", "FB", "SDA", "SCL"))
connect(v12, j1[1], u1["VIN"], c1[1])
connect(gnd, j1[2], u1["GND"], c1[2], c2[2], r2[2], c3[2])
connect(sw, u1["SW"], l1[1])
connect(v33, l1[2], c2[1], r1[1], u2["VDD"], u3["VDD"], r3[1], r4[1], c3[1])
connect(fb, u1["FB"], r1[2], r2[1])
connect(sda, u2["PB7"], u3["SDA"], r3[2])
connect(scl, u2["PB6"], u3["SCL"], r4[2])
connect(gnd, u2["GND"], u3["GND"])
no_connect(*(u2[p] for p in range(1, 33) if p not in (4, 5, 17, 18)))  # by hand
bus = I2C(sda, scl)
design.add(bus, Power(v33, gnd))
# Nothing checks: C1's voltage vs 12 V, the divider's VOUT, the 3V3 current budget, the sensor's VDD range.
```

**Proposed:**

```python
from fenolite.dsl import Design, connect, decouple, pull_up, volt, amp, ohm, farad, mm, pct
from blocks import buck  # the block of section 4, reusable, with its own tests

design = Design("sensor")
design.board(mm(40), mm(30))
design.defaults(resistor={"case": "0603", "tolerance": pct(1)}, capacitor={"case": "0603"})
design.derating(capacitor_voltage=pct(50))

j1 = design.part(device="Fenolite:Header_1x2_P2.54")
v12 = design.rail("V12", voltage=volt("12").pct(10))
gnd = design.ground("GND")
connect(v12, j1[1])
connect(gnd, j1[2])

power = design.use(buck, "buck", vout=volt("3.3").pct(5), current=amp(1))
connect(v12, power.VIN)
connect(gnd, power.GND)
v33 = power.VOUT  # a Rail: carries 3.135–3.465 V, 1 A available

mcu = design.part(device="Example:MCU_QFN32")
sen = design.part(device="Example:SENSOR_I2C")
connect(v33, mcu.vdd, sen.vdd)
connect(gnd, mcu.gnd, sen.gnd)
connect(mcu.i2c1, sen.i2c)
pull_up(mcu.i2c1, v33, ohm("4k7"))
decouple(v33, gnd, capacitor(farad("100n")), near=mcu.vdd)
mcu.unused_no_connect()

power.place(mm(6), mm(8))
mcu.place(mm(24), mm(15))
sen.place(right_of=mcu, gap=mm(3))
# Checked at build/check: ratings vs rails with derating, VOUT range from the divider, 3V3 current budget,
# sensor VDD range, I2C pull-ups, logic levels. Refs and picks go to design.lock.
```

---

## What changes in the core

| # | Core change | Main package | Learned from | Size |
|---|---|---|---|---|
| A | `Range` quantities (exact integer bounds) and ranges in the model | `dsl/quantity`, `model` | atopile, JITX | M |
| B | `Device` catalog records (MPN, pin functions, ratings, evidence), `Part(device=)`, checked pin access | `catalog`, `dsl/part` | JITX, LibrePCB | L |
| C | `design.lock`: refs, picks, pin choices; `--frozen` | `core`, `cli` | atopile | M |
| D | Blocks: ports, parameters, local nets, ref namespace, `design.use` | `dsl/module`, `model` | JITX, atopile, tscircuit | L |
| E | Parametric interfaces (alias/sum), interface-to-interface `connect`, `Rail`, `Logic` | `dsl/interfaces` | atopile, JITX | M |
| F | `circuit.*` check stage: ratings, rails, logic levels, `expect()`, `rig()`, derating | `checks`, `analysis` | atopile, JITX | L |
| G | Three-way per-property merge, `edits.toml`, `sync.conflict`, `--take` | `lens`, `backends/kicad` | tscircuit, atopile | L |
| H | Offline parametric picking and generators (divider first) | `catalog`, `dsl` | JITX, atopile | M |
| I | Relative and anchored placement, block pose and strategy, block layout reuse | `dsl/part`, `placement` | tscircuit, JITX, atopile | M |
| J | Connection helpers (`series`, `decouple`, `pull_up`, `unused_no_connect`) | `dsl` | atopile, tscircuit | S |
| K | `fenolite.testing`, `render --net`, unattached-object warning | `api`, `lens` | tscircuit, JITX | S |
| L | Interface-level pin assignment (later) | `dsl`, `core` | JITX | L |
| M | Topologies with delay and loss constraints, rule specificity (later) | `dsl/rules`, `routing` | JITX | L |

Nothing here adds a runtime dependency. Every new file (`design.lock`, `edits.toml`, device TOML) is
canonical text, written only through plan/confirm, and byte-identical under `--seed`/`--timestamp`.

## What we deliberately do not copy

- **A general constraint solver** (atopile). Its users restate equations "for the solver", and
  contradictions are hard to explain. Fenolite uses ranges plus explained checks.
- **A live parts database in the build** (all three). It breaks reproducibility and the no-dependency
  rule. Fenolite uses a local catalog plus a lock, and an optional extra only proposes rows.
- **State hidden in the CAD file or the UI** (atopile picks in `.kicad_pcb`; JITX pin choices fixed by
  routing, and layout in `designs/`). Fenolite keeps state in reviewable text and the receipt.
- **Class-body metaclass magic** (JITX). Blocks are plain functions.
- **Untyped string selectors as the main wiring** (tscircuit), and a connection that is also a copper
  trace.
- **Floats** (all three). Fenolite stays integer.
- **Silent order-based pin mapping** (JITX's default). Fenolite requires an explicit map or a finding.
- **Feature pragmas for core syntax** (atopile). Features ship stable or not at all.
- **Telemetry** (atopile's CLI). None.

## Proposed order (each line becomes an OpenSpec change)

The order follows dependencies. Each step ships something usable on its own.

1. **A + J:** ranges and connection helpers. Small, unblocks everything else.
2. **B + C:** devices and the lock. Parts become complete; refs stop being typed by hand.
3. **G:** three-way manual edits. It needs the stable ids and lock of step 2; it is the most requested.
4. **D + E:** blocks and parametric interfaces.
5. **F:** electrical contracts. It reads ratings (B), ranges (A), rails (E) and roles (c0222).
6. **H + I:** offline picking, generators, relative placement and block layout.
7. **K:** testing helpers, then **L** and **M** after 1.0 unless a reference board needs them earlier.

The viewer (c0245) shows the results of steps 3, 5 and 6: conflicts, contract findings, block outlines.
The router phases (c0243/c0244) read the same rails and roles.
