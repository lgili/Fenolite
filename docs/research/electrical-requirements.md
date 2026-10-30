# Electrical requirements the library can check

Status: **research, nothing here is implemented**. Date: 2026-10-29. It reviews the proposed contracts
(c0248 device ratings, c0252 parametric interfaces, c0253 electrical contracts, c0246 ranges) against
what other tools do, and lists the corrections and additions made before implementation.

The goal is to declare that:
- an input accepts a voltage range;
- a part withstands a power;
- an interface needs a logic level.

Fenolite then finds incompatibilities **before layout**, with explicit limits and intervals and no
general equation solver. Everything extends the net roles (c0222) instead of creating a parallel rule
system.

Clean-room: concepts only. No code, trait or property name, check catalogue, conflict-matrix values,
derating table or logic-threshold table of another tool or standard is copied.

## 1. What the others do

| Tool | How a requirement is declared | What is checked, when | Weak point |
|---|---|---|---|
| atopile | every value is a range (`3.3V +/- 5%`, `1.8V to 5.5V`); `assert x within range`; power interface with voltage (alias) and current/power (sum); a logic line carries its reference rail | checks at named stages (graph, design, after solving, after PCB) with "fails" and "maybe fails"; ERC for shorted rails, sources tied together, a rail with no voltage, incompatible interfaces | the current budget sums *all* ports on both sides: the code calls it a tautology, so an overloaded rail is not caught; failures come back as solver "contradictions" |
| JITX (older Stanza docs) | a toleranced voltage property on a net; rated voltage on parts; checks written once in a part ("EP must connect to VSS") | a design check reporting derating for passives and the regulator input voltage | pins do not inherit net voltages, so a part shows a missing *operating point*. That is good: it is not a silent pass. The public Python API has no check module today |
| KiCad | an electrical type per pin; a pin-conflict matrix with editable severities; power flags | ERC by pin types and connectivity, with exclusions that persist and carry a comment | no voltage at all; power flags confuse users (a supply through a ferrite is "not driven") |
| Altium | pin/port connection matrix with four levels; No-ERC directives; net parameters; the Requirements & Systems Portal | compile errors by type; the portal links requirements to design items but sets verification **by hand** | no voltage or I/O level checks |
| Siemens Xpedition Schematic Analysis (Valydate) | models built from the manufacturer part numbers of the BOM | voltage-level mismatches, pin types, capacitor derating, missing pull-ups, across boards; results grouped critical/defect/warning | commercial, model library closed |
| Calibre PERC (IC) | voltages seeded on a few nets | voltages propagated along paths, assignment checked for consistency | heuristics weaken in mixed-voltage designs |
| Zuken CR-8000 | "Circuit Adviser" rules at schematic entry | power-IC voltage margins, thermal limits; a clearance table by voltage difference handed to layout | commercial |
| SKiDL | `erc_assert("expr")` strings; pin functions; net drive | evaluated at ERC | string evaluation; waiver with no reason |
| tscircuit | pin attributes (requires power, requires a voltage, must connect) | only connection presence; "does not validate the net's voltage" | most attributes declared, not checked |
| Celus | port definition plus specifications at node and link level; dependent ports (SPI needs a supply and a chip select) | compatibility by port type (I²C across different supplies "not matched") | proprietary |
| Flux | AI design review | capacitor voltage margin, resistor power, pull-ups | not deterministic: the vendor says to review its suggestions |

Sources:
- atopile: github.com/atopile/atopile (MIT), `src/faebryk/library/ElectricPower.py`, `src/faebryk/libs/app/erc.py`, `implements_design_check.py`, `.claude/skills/ato/SKILL.md`, read at commit `619eda7`.
- JITX: docs.jitx.com, older tutorial pages (now 404, read from search snippets: UNVERIFIED), and jitx.com/product/detailed-design-checks-component-level-user-checks.
- KiCad: docs.kicad.org/9.0/en/eeschema/eeschema.html.
- Altium: altium.com/documentation (connection matrix, design validation, Requirements & Systems Portal).
- Siemens: blogs.sw.siemens.com (2020-06-22, 2023-05-16), and the Calibre PERC voltage-dependent DRC video.
- Zuken: zuken.com, the CR-8000 2025 release note.
- SKiDL: devbisme.github.io/skidl.
- tscircuit: docs.tscircuit.com/guides/tscircuit-essentials/pin-attributes.
- Celus: celus.io/knowledge/interfaces-ports-specs-and-connection-validation.
- Flux: flux.ai/p/blog/introducing-the-ai-design-review-tab.

**Standards:**
- NASA EEE-INST-002, appendix A (derating): a US government work, publicly downloadable.
- ECSS-Q-ST-30-11C Rev.2: free PDF, copyright ESA.
- MIL-HDBK-1547A: cancelled.
- JEDEC JESD8 (logic levels): free after registration, redistribution restricted.

Fenolite cites these by document and clause and never embeds their tables. Logic thresholds come from
each part's datasheet.

## 2. What our specs already have

- **Ratings (c0248):** device `voltage`, `current`, `power` and `temperature`, plus pin limits measured
  from the device's ground function. All are exact integers.
- **Interfaces (c0252):**
  - rail voltage is an intersection of the values set on it (alias), and current is a sum;
  - logic voltage, a high-level minimum and a reference rail;
  - an accepted pull-up range;
  - checks `circuit.rail-voltage`, `rail-current`, `rail-sources`, `logic-level` and `bus-pullup`.
- **Contracts (c0253):**
  - ratings judged against applied values, with power from V²/R or I²R and temperature from the
    declared ambient;
  - a derating policy (no shipped numbers);
  - `expect()` as data with pass, unsure and fail;
  - a test rig;
  - one requirement table with value, limit and source (`device`, `role`, `policy`, `user`).

  Applied values come from the rig, then the rail, then the declared or confirmed **net role**, so no
  second system is needed.
- **Timing:** all of it runs in `circuit.rules` right after `model.validate`, with no tool, before
  layout.

## 3. What is wrong or missing (the review)

### Inconsistencies between the specs

1. **Skip reasons:** `no-model`, `no-parameters` and `no-contracts` are named differently in c0252 and
   c0253.
2. **The check module:** c0252 already defines a package `checks/circuit/` that c0253 says it creates.
3. **The unit parser:** `core/quantities` (c0248) versus `core/units.py` (c0253).
4. **Range encoding:** c0246 stores mantissa and exponent with unit names (`volt`), while the sketches in
   c0252 and c0253 write `min`/`max` strings with symbols (`V`).
5. **Temperature:** c0246 has no temperature unit, but c0253 needs `between(celsius(-20), celsius(70))`.
6. **`pct()` meaning:** in c0246 it is a ± tolerance; c0253 reads `pct(50)` as "50 % of the rating".
7. **Classifiers:** two class tables, and they disagree (`FB`, `J`) with the roles' prefix table.
8. **Waivers:** the living spec waives only copper and DRC findings (to `info`). c0252 and c0253 assume
   `circuit.*` waivers (to `warning`), but no delta extends the waiver pipeline.
9. **Current sources:** roles take a current from the role, then `[[current]]`, then `--current`; c0253
   forgets `--current`, so the two tables can differ.
10. **Expectation ids:** written `buck/expect#1` in one place and `buck1/expect#1` in another.

### Model gaps

11. **Absolute limits and operating ranges share one field.** The device example puts an operating
    minimum (2.7 V) in the slot that c0252 and c0253 read as an absolute rating. Derating "toward zero"
    then *loosens* that minimum.
12. **Pin-to-pin limits:** only from the device's single ground. BST−SW and the Vgs of a high-side switch
    cannot be written.
13. **Device current on ICs:** judged only for inductors and shunts, so the `current` of a regulator is
    undefined.
14. **Logic levels are incomplete:** no low-level input maximum, no output high/low levels, no output
    current, and the driver's level is assumed to be its rail.
15. **Power in `expect()`:** c0246 has no V·V or A·A products, and one-sided ranges cannot enter
    arithmetic.
16. **Unknowns stay quiet:** an unknown rating row gives only an info count, so a design that states
    nothing passes. That is the opposite of c0252's warnings for an unset rail.
17. **Current budgets need direction:** c0252 counts `out` ports as sources, which is right. It must
    stay explicit (`in`, `out`, `pass`), and atopile's tautology is the case its test must exclude.
18. **No voltage propagation:** a net behind a ferrite, a 0 Ω link or a fuse has no voltage unless one is
    declared, and the result does not say where a value came from.
19. **No requirement can say "decided later":** track current and voltage drop are decidable only after
    routing.
20. **No companion requirements:** an I²C port needs pull-ups and a supply, SPI needs a chip select.

## 4. What changes

| # | Correction or addition | Where |
|---|---|---|
| 1–3, 10 | one skip vocabulary (`no-model`, `no-parameters`, `no-contracts`), one check package, one unit parser (`core/quantities`), one id form (`<instance path>/expect#n`) | c0252, c0253 edited |
| 4 | the requirement table and `rules.json` use c0246's encoding (unit name, mantissa and exponent) | c0252, c0253 edited |
| 5, 15 | ranges gain temperature (kelvin internally, `celsius()` at the boundary) and the products V·V→V², A·A→A², V²/Ω→W, A²·Ω→W; one-sided ranges allowed where the result stays one-sided | c0274 (extends c0246, which is being implemented) |
| 6 | derating takes `ratio(50)` ("at most 50 % of the rating"); `pct()` stays a tolerance | c0253 edited |
| 7 | one classifier, the roles' `PartClass`, with `FB` added there and tested once | c0253 edited, roles touched in c0274 |
| 8 | waivers extended to `circuit.*`, with reason, scope, the waived code and the **value digest at waiver time**: a waiver expires when the value changes | c0274 |
| 9 | applied current: role, then `[[current]]`, then `--current`, the same order as roles | c0253 edited |
| 11 | pin and device data split into `abs_max` (judged by ratings, derated) and `operating` (judged by rails, never derated) | c0248, c0252, c0253 edited |
| 12 | pin-pair limits: `[[limits]] between = ["BST", "SW"], voltage = {abs_max = "6V"}` | c0248, c0253 edited |
| 13 | device `current` defined per class: regulators judge output current against their `out` port, passives against the net | c0253 edited |
| 14 | logic thresholds per pin or port: `input_high_min`, `input_low_max`, `output_high_min`, `output_low_max`, `output_current_max`, each from the datasheet. Check driver output high ≥ receiver input high, driver output low ≤ receiver input low, and receiver absolute maximum ≥ the driver's rail | c0252 edited |
| 16 | a **strictness** setting: `design.contracts(unknown="warning")` makes unknown rows warnings; the default stays `info` until the shipped devices carry ratings, then becomes `warning` | c0253 edited |
| 17 | port direction is mandatory for sum parameters, with the scenario "1.2 A load on a 1 A source fails" | c0252 edited |
| 18 | voltage propagation through parts whose class allows it (ferrite, 0 Ω, fuse, closed jumper), with each net's value recording its **origin** (`declared`, `role`, `rig`, `propagated via FB1`) | c0274 |
| 19 | each requirement row has a `decidable` stage (`build`, `place`, `route`); `check` reports rows not yet decidable as `deferred`, never `pass` | c0274 |
| 20 | interfaces may declare companions (`requires = ["pullup", "supply"]`), judged as `circuit.requires-missing` | c0252 edited |
| — | the requirement table becomes a **verification matrix**: stable row id → status → evidence → receipt, exported by `fenolite check --matrix` | c0274 |
| — | the rig evaluates every expectation at each **corner** (each supply at its minimum and maximum) | c0253 edited |

## 5. The result, in code

```python
# a device states its limits once (c0248, corrected)
# devices/example/EXB6202/device.toml
#   [pins.VIN]   operating = { min = "2.7V", max = "6V" }   abs_max = "6.5V"
#   [pins.EN]    input_high_min = "1.2V"  input_low_max = "0.4V"  abs_max = "6.5V"
#   [[limits]]   between = ["BST", "SW"]  voltage = { abs_max = "6V" }
#   [ratings]    temperature = { min = "-40degC", max = "125degC" }

design.contracts(unknown="warning")  # an unstated value is a finding, not a pass
design.derating(capacitor_voltage=ratio(50), resistor_power=ratio(50), source="house policy HP-1")
design.operating(ambient=between(celsius(-20), celsius(70)))
design.rig(supply(v12, gnd, voltage=volt("12").pct(10), current=amp(2)))  # corners: 10.8 V and 13.2 V

v33 = power.VOUT  # a Rail: 3.234..3.366 V, out port, 1 A
connect(v33, mcu.vdd, sen.vdd)  # in ports: operating ranges judged (circuit.rail-voltage)
connect(mcu.PA3, sen.EN)  # logic: VOH(min) of PA3 >= VIH(min) of EN, VOL(max) <= VIL(max)
b.expect(b.power_of(r_top) <= b.rating_of(r_top, "power"), "divider top resistor power")
```

```
$ fenolite check build/sensor --stages circuit.rules --matrix
id                                  check              value            limit               source   status
circuit.rating-voltage:C3           capacitor voltage  0..13.2 V        <= 12.5 V (50%×25V) policy   fail
circuit.logic-level:mcu.PA3>sen.EN  output high        >= 2.9 V         >= 1.2 V            device   pass
circuit.rail-current:3V3            load current       <= 1.15 A        <= 1 A              device   fail
circuit.rating-power:sense_a/top    resistor power     <= 0.4 mW        <= 50 mW            policy   pass
roles.width-current:VBUS            track width        —                —                   role     deferred (route)
```

## 6. Order

The corrections to c0248, c0252 and c0253 are made in those specs now, because none of them is
implemented yet. The cross-cutting additions go into a new change, **c0274
`electrical-requirements`**:
- range units for c0246;
- waivers that expire;
- voltage propagation with origin;
- decidable stages;
- the verification matrix.

It is implemented after c0253.
