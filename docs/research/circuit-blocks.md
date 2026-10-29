# A library of circuit blocks: from components to reusable solutions

Status: **research, nothing here is implemented**. The code below is a design sketch for OpenSpec
changes; names may change. Date: 2026-10-29.

A component library gives parts. A block library gives **solutions**: a voltage divider, an RC filter, an
LED indicator, a communication interface, a protected input. Each is a sub-circuit that is:

- parametrised;
- checked against its requirements;
- tested;
- drawn as an organised schematic;
- optionally laid out once and reused.

This page compares how other tools do it and proposes the missing layer on top of the blocks of c0251
(ports, parameters, local nets), c0252 (interfaces), c0253 (`expect()`), c0254 (generators), c0255
(block layout) and c0256 (`fenolite.testing`).

Clean-room: concepts only. No block content, layout, value table, reference schematic or API name of
another tool is copied. Vendor reference designs and standards are cited by document id, never
transcribed.

## 1. What the others do

| Tool | Block = | Instances | Requirements and tests | Reusable layout | Distribution |
|---|---|---|---|---|---|
| atopile | a declarative `module` with typed interfaces and `assert`s | `new X`, arrays; designator rule not documented | `assert x within …`; every package ships a **usage build** that must pass in CI | each package carries its own `.kicad_pcb`; a KiCad plugin "pulls" it into the board (manual step) | packages with manifest, version, licence (MIT), registry; about 100 packages, mostly IC drivers, a few generic (indicator LEDs, buttons, headers) |
| tscircuit | a TSX function wrapping `<subcircuit>` | selectors scoped to the subcircuit; designators prefixed on silkscreen | per-package tests; no requirement layer | none as such | npm-style registry, `@tsci/author.pkg`; prebuilt vendor subcircuits |
| JITX | a `Circuit` class; parametric **solver** blocks (divider: constraints → solve → circuit with achieved tolerance) | pools of N copies; provide/require pin choice | the solver checks the target range; no shipped test convention found | layout lives in the tool's state | Python packages (`jitxlib`) |
| KiCad 9/10 design blocks | a folder with a `.kicad_sch` (and in 10 a layout) plus JSON metadata | "place as group" or "place as sheet"; reannotation for unique refs; sheet fields act as parameters | none (run ERC before saving) | 10: apply a block's layout to the matching footprints; **Repeat Layout** for multichannel (same part count, prefixes, footprints, connectivity) | block library tables; no versioning, no official library |
| Altium | Reuse Blocks (schematic + PCB), managed sheets, snippets, multichannel rooms | flat or as sheet symbol; ports become sheet entries | none; lifecycle states and approval | placed automatically in the ECO; **Copy Room Formats** between channel rooms | Workspace with revisions, lifecycle, **Where Used**, push-or-stay updates |
| SKiDL | a decorated function returning named I/O | refs auto-assigned, stable **tags** independent of call order | `erc_assert` queued per block | none | Python |
| Celus | "CUBO": ports with signal types and constraints, BOM, support schematic, app-note links | matched from abstract function blocks | "validated", process not public | none | proprietary |
| Flux, EasyEDA Pro, Cadence | modules / reuse blocks / replicate modules | auto-grouped in the PCB | none | placement module applied to matching parts | in-tool libraries |

Sources:
- atopile: https://github.com/atopile/packages and a package manifest (`packages/bosch-bme280/ato.yaml`)
- tscircuit: https://docs.tscircuit.com/elements/subcircuit and the registry API docs
- JITX: https://docs.jitx.com/en/4.0/jitxlib/jitxlib.voltage_divider.circuit.html and the `jitxlib.circuits.pool` docs
- KiCad design blocks:
  - https://docs.kicad.org/master/en/eeschema/eeschema.html
  - https://docs.kicad.org/master/en/pcbnew/pcbnew.html
  - https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/
- Altium: https://www.altium.com/documentation/altium-designer/schematic/design-reuse/reuse-blocks
- SKiDL: https://devbisme.github.io/skidl/
- Celus: https://www.celus.io/knowledge/what-is-a-cubo

**What nobody does well, and Fenolite can:**
- requirements that travel with the block and are judged on every build;
- tests shipped with the block;
- a layout tied to the block's *version*, with a stale layout detected rather than applied silently;
- all of it as reviewable text, deterministic, for KiCad and Altium.

## 2. What Fenolite has, and what is missing

**Has today:**
- `Module`: a named container whose path prefixes part paths.
- Interfaces (`Power`, `I2C`, `SPI`, `UART`, `USB2`, `DiffPair`).
- Schematic grouping for Altium (`schematic_block`).
- Physical reuse (c0210, c0227): `fenolite place --strategy reuse` fits a reference board's block onto
  target parts and copies its copper. Nets are *inferred* from pads; it is a CLI step after the build.
- De-facto blocks written by hand: `channel(n)` in the yardstick (refs `n*100+k`, nets `CH{n}_*`),
  `bank(i)` in `board_40parts`, and the roles boards (good/bad variants with `requirements.toml`, the
  closest thing to "a block with requirements and negative tests").

**Proposed (specified, not implemented):**

| Change | Gives a block |
|---|---|
| c0251 | `@block` functions, typed ports, recorded parameters, local nets `<inst>/FB`, `design.use` |
| c0249 | automatic references from the lock: no collisions, stable across rebuilds |
| c0252 | ports with parameters (rail voltage, current, logic reference), `connect` of whole interfaces, `circuit.rules` |
| c0253 | `b.expect(...)`: requirements judged by `check`; `design.rig` for stimulus |
| c0254 | generators (`voltage_divider`, `rc_lowpass`, `led_resistor`, `i2c_pull_ups`, `shunt`) with achieved ranges |
| c0255 | block pose, per-block strategies, `b.layout(reuse=...)` mapping parts by local path and nets by port |
| c0256 | `fenolite.testing.instantiate(block, **params)`, golden renders |

**Still missing for a *library*:**
1. A **block record**: identity `namespace:name`, version, summary, category, licence, sources, evidence,
   required devices. Today a block is only a Python function name.
2. **Parameter metadata**: unit, allowed range, choices, documentation per parameter and per port. Also
   generated documentation pages.
3. An **organised schematic inside a block**: groups, order and anchors that every instance reuses. Today
   grouping is design-level and Altium-only, and KiCad sheets have no pins (global labels).
4. **Shipped tests**: a convention for where a block's tests live, a stimulus argument for `instantiate`,
   and a usage example that must build.
5. A **versioned layout artefact**: the reference layout bundled with the block, tied to its version and
   digest, refused when parameters change the part set, with mirrored (bottom) poses.
6. **Distribution**: blocks are Python, so the data-only packs of c0266 cannot carry them. This needs a
   catalog (`fenolite blocks list/show`), the block version recorded in the model and pinned in the lock,
   and Where-Used.
7. **Generators vs blocks**: c0254's generators are builder functions. The library wraps each in a block
   with ports, so it can be instantiated, tested and laid out.

## 3. The proposal

### 3.1 A block, complete

```python
# src/fenolite/blocks/divider.py  (the shipped starter library; authored for Fenolite)
from fenolite.dsl import Rail, block, ma, param, ua, volt
from fenolite.dsl.generators import voltage_divider


@block(
    id="Fenolite:voltage_divider",
    version="1.0.0",
    summary="Resistive divider with a worst-case output range",
    category="analog",
    sources=["S-0xxx Ohm's law and worst-case tolerance analysis (textbook)"],
)
def voltage_divider_block(
    b,
    *,
    vout=param(volt("3.3").pct(5), doc="target output range"),
    vin=param(volt("12").pct(10), doc="input range"),
    current=param(ua(100), doc="bias current at nominal input", min=ua(1), max=ma(10)),
    series=param("E96", choices=("E24", "E96"), doc="resistor series"),
):
    hi = b.port("HI", Rail, direction="in", doc="input")
    out = b.port("OUT", Rail, direction="out", doc="divided output")
    lo = b.port("LO", Rail, direction="in", doc="reference, usually ground")
    top, bot = voltage_divider(b, hi, out, lo, target=vout, vin=vin, current=current, series=series)
    b.schematic(column=[top, bot], title="Divider")  # organised schematic, same in every instance
    b.expect(b.voltage_of(out).within(vout), "output stays in range over tolerances")
    b.expect(b.rating_of(top, "power") >= b.power_of(top), "top resistor power")
    b.layout(reuse="layouts/voltage_divider.toml")  # optional; tied to this block version
    return b.ports()
```

```python
# a design using two instances: internal nets and references never collide
from fenolite.blocks import voltage_divider_block as divider

a = design.use(divider, "sense_a", vout=volt("3.3").pct(5))
c = design.use(divider, "sense_b", vout=volt("1.8").pct(5), series="E24")
connect(v12, a.HI, c.HI)
connect(gnd, a.LO, c.LO)
connect(a.OUT, mcu.ADC0)
connect(c.OUT, mcu.ADC1)
# parts: sense_a/top -> R1, sense_a/bot -> R2, sense_b/top -> R3, ... recorded in design.lock
```

### 3.2 The block record and the catalog

The decorator *is* the record. `fenolite blocks list|show|doc` reads it without building:

```
$ fenolite blocks show Fenolite:voltage_divider --json
{ "id": "Fenolite:voltage_divider", "version": "1.0.0", "category": "analog",
  "ports": [{"name": "HI", "kind": "rail", "direction": "in", "doc": "input"}, ...],
  "params": [{"name": "vout", "type": "range", "unit": "V", "default": "3.135..3.465 V", ...}],
  "requires": {"devices": ["Fenolite:R_0603"]}, "layout": "layouts/voltage_divider.toml",
  "tests": "tests/test_voltage_divider.py", "evidence": "INFERRED", "licence": "Apache-2.0" }
```

- The model records `block`, `version` and the bound parameters on each instance (c0251 records the name
  and parameters; this adds the version).
- The design lock gets `[blocks."sense_a"] = "Fenolite:voltage_divider@1.0.0"`, so an upgrade is a
  reviewed lock change. `build --frozen` refuses it.
- `fenolite inspect --blocks` lists where each block version is used.

### 3.3 Organised schematic inside a block

- `b.schematic(...)` declares groups, order and anchors local to the block, reused by every instance.
- **KiCad:** each instance gets its sheet with **hierarchical pins from the declared ports** (instead of
  global labels).
- **Altium:** sheet entries come from the ports, not from inferred crossings.
- Without `b.schematic`, the block gets one tidy default group.

### 3.4 Tests that ship with the block

```python
# src/fenolite/blocks/tests/test_voltage_divider.py
from fenolite.blocks import voltage_divider_block as divider
from fenolite.testing import instantiate, stimulus


def test_output_in_range():
    t = instantiate(divider, vout=volt("3.3").pct(5), stimulus=stimulus(HI=volt("12").pct(10), LO=volt(0)))
    assert not t.findings("circuit.*")
    assert t.net("dut/OUT").voltage.within(volt("3.3").pct(5))


def test_unreachable_target_is_a_finding():
    t = instantiate(divider, vout=volt("3.3").pct(1), series="E24")
    assert t.findings("gen.unachievable")
```

The convention:
- every block has a `usage` example that must build;
- every block has tests covering math, ratings, netlist, and the layout properties once laid out;
- every block has a golden canonical JSON under `--seed`/`--timestamp`.

`fenolite blocks test [ID]` runs them, and CI runs them for the shipped library.

### 3.5 The reusable layout, versioned

```toml
# src/fenolite/blocks/layouts/voltage_divider.toml   (relative placement, not a board file)
schema = "fenolite.block-layout.v0"
block = "Fenolite:voltage_divider"
block_version = "1.0.0"
parts_digest = "sha256:…"          # digest of the instance's part set; a different set refuses the layout
[part.top]
at = ["0mm", "0mm"]
rotation = "90deg"
[part.bot]
at = ["0mm", "2.5mm"]
rotation = "90deg"
[copper]
tracks = [{ from = "top.2", to = "bot.1", width = "0.25mm" }]   # by local pad, remapped by port and local net
```

- The layout is relative to the block's frame, so `inst.place(x, y, rot, side=...)` moves it as a rigid
  group (c0255). `side="bottom"` mirrors it.
- If a parameter changes the part set (for example a series that adds a part), the digest differs and the
  layout is refused with a finding, never applied wrongly.
- A layout can be captured from a laid-out instance with `fenolite blocks capture BOARD --instance
  sense_a`, which reuses the fit of c0210/c0227. This turns today's CLI reuse into a block asset.

### 3.6 The first five blocks (authored, small, well tested)

| Block | Ports | Parameters | Requirements (`expect`) | Tests |
|---|---|---|---|---|
| `voltage_divider` | HI, OUT, LO | vout range, vin range, bias current, series | output within range over tolerances; resistor power ≤ rating (with the design's derating) | math grid; unreachable target is a finding; two instances, no collision |
| `rc_lowpass` | IN, OUT, GND | cut-off range, R or C fixed, series, voltage | cut-off within range (exact bounds instead of π); capacitor voltage rating | math grid; ratings; golden |
| `led_indicator` | DRIVE, GND (or high-side variant) | supply range, LED current, LED device, colour | current within the LED rating; driver pin current ≤ the source's limit (c0252 logic port) | math; ratings; polarity mark on the layout |
| `i2c_pullups` (communication interface) | BUS (I2C), RAIL | rail, bus mode, bus capacitance estimate | resistor between the minimum from the sink current and the maximum from the rise time, cited to the bus specification by id; exactly one pull-up set per bus | netlist rule; math; two buses |
| `protected_input` | EXT, INT, GND | working voltage, clamp target, series resistance, protection device | protection working voltage ≥ the maximum signal; clamp ≤ the downstream absolute maximum; series current into internal clamps limited | ratings; layout property: protection close to the connector, short return |

Rules for these blocks:
- each relation is written in Fenolite's words, with its source registered in `docs/evidence/sources.md`
  and an evidence label;
- nothing is taken from vendor reference designs or app notes beyond citing their document id.

Next blocks (later): decoupling set, reverse-polarity protection, crystal, reset, connector with ESD.

### 3.7 Distribution

- **Starter library:** `fenolite.blocks` in the core package. It is code, stdlib only, Apache-2.0, and
  versioned with Fenolite.
- **Further blocks:** a separate Python package (`fenolite-blocks`) with its own versions, declared as a
  dependency of the *project*, never of the core. The lock pins the block versions (3.2), so a project
  builds byte-identically.
- **Project blocks:** a project's own blocks are plain Python modules beside the script, as today.

## 4. Proposed changes

| Id | Change | Depends on | Size |
|---|---|---|---|
| c0268 | `block-records`: `@block(id=, version=, summary=, category=, sources=)`, `param()` metadata (unit, range, choices, doc), port docs, block version in the model and lock, `fenolite blocks list/show/doc`, Where-Used in `inspect` | c0251, c0249 | M |
| c0269 | `block-schematic`: `b.schematic(...)` groups local to a block, KiCad hierarchical pins and Altium sheet entries from declared ports, default tidy group | c0251 | M |
| c0270 | `block-tests`: shipped test convention, `instantiate(..., stimulus=)`, usage example per block, golden JSON, `fenolite blocks test` | c0256, c0253 | S |
| c0271 | `block-layouts`: `fenolite.block-layout.v0` relative layout tied to version and parts digest, mirrored pose, refusal on mismatch, `fenolite blocks capture` from a laid-out instance (reusing c0210/c0227's fit) | c0255, c0268 | M |
| c0272 | `starter-blocks`: the five blocks of 3.6 with requirements, tests and layouts, plus docs pages generated from the records | c0268–c0271, c0254 | M |
| c0273 | `block-packages`: blocks outside the core (`fenolite-blocks` package), discovery without import side effects, versions pinned in the lock, upgrade review | c0268 | S |

## 5. Questions for the maintainer

1. **Starter blocks in the core package** (recommended) or only in a separate package from the start?
2. **Licence of shipped blocks:** Apache-2.0 like the code (recommended), or CC0 like the data
   repository?
3. **Block identity:** `Fenolite:voltage_divider` with semantic versions (recommended). Should a project's
   own blocks need an id, or only shipped ones?
4. **Upgrades:** a newer block version is never taken silently. Recommended: the lock keeps the old
   version until `fenolite blocks upgrade` plans the change.
