## Context

- **Source.** `docs/research/electrical-requirements.md` (2026-10-29), sections 3 and 4. Its table lists
  twenty corrections and two additions. The rows marked "c0252, c0253 edited" were applied in those two
  changes; this change holds the rest: the deltas of c0246 and c0248 (which other agents are implementing,
  so their folders are not edited), and the behaviour that no single change owns.
- **Clean-room.** The research compares atopile, JITX, KiCad, Altium, Siemens, Zuken, SKiDL, tscircuit,
  Celus and Flux in words only. No code, trait or property name, check catalogue, conflict-matrix value,
  derating table or logic-threshold table of another tool or standard is copied. Thresholds and ratings
  come from each part's datasheet through its device record, with the record's evidence label.
- **What exists on `dev` (0.6.0).**
  - Waivers: `Design.waive` (design-dsl, "Waivers in the DSL"), `findings.Waiver` (design-model) and
    `checks.waivers` (verification-loop, "Waivers in the check"), for `copper.*` and `kicad.drc.*` codes
    only. A waived finding takes `info`; an unmatched judged waiver gives `check.waiver-unmatched`.
  - Roles (c0222): `fenolite.roles.classify` with the closed vocabulary `PART_CLASSES` and the prefix table
    `PREFIXES` (`Q`, `D`, `L`, `C`, `R`, `J`, `U`). `FB1` matches no prefix.
  - Open connections of a net (`board-analyses`, "Open connections of a net").
- **What the batch adds before this change** (folders read on 2026-10-29; task 0.1 checks what landed):
  - c0246: `Range`, `Tolerance`, the closed unit table (`ohm`, `farad`, `henry`, `volt`, `ampere`,
    `hertz`, `watt`, `second`), worst-case arithmetic refused on unbounded ranges, `Decimal10` and
    `ValueRange` in the model.
  - c0248: device records (`fenolite.device.v0`), `DeviceDef`, `DevicePin(voltage, current)` measured from
    `ground`, `Rating(key, unit, min, max)` in µV, µA, µW and m°C, `core/quantities`.
  - c0252 (edited with this review): port parameters as operating values, logic thresholds on ports,
    mandatory direction for `current`, `requires`, the stage `circuit.rules` and the package
    `checks/circuit/`, the skip vocabulary `no-model`/`no-parameters`.
  - c0253 (edited with this review): `abs_max` judged as ratings with `ratio()` derating, `operating`
    judged exactly (`circuit.operating-range`), pin-pair limits, device current per class, one classifier
    injected from `roles.classify`, current in the order role → `[[current]]` → `--current`, strictness
    `design.contracts(unknown=...)`, rig corners, the requirement table in c0246's encoding, ids
    `<instance path>/expect#n`.

## Goals / Non-Goals

**Goals**

- A device record says once, without ambiguity, what damages a part and what it needs to work, including
  between two of its pins and at its logic inputs and outputs.
- Every quantity the contracts compare (temperatures, powers, one-sided limits) has an exact type.
- An accepted risk is written down with its reason and stops being accepted when what was judged changes.
- A rail behind a ferrite or a 0 Ω link is judged without being declared twice, and every value says where
  it came from.
- A row that cannot be decided yet says so; nothing passes by default.
- One export lists every requirement with a stable id, a status, the evidence and the inputs it was judged
  on.

**Non-Goals**

- See the proposal. Also: no new stage, no new `FEN-` code, no change of the role checks' findings.

## Decisions

### 1. Phase A: device limits split into `abs_max` and `operating` (c0248 delta)

**Today (c0248 as written):**

```toml
[pins]
VIN = { pins = ["5"], voltage = { min = "2.7V", max = "6V" } }   # operating or absolute?
```

**Proposed** (illustrative record, authored for Fenolite, not a real product):

```toml
schema = "fenolite.device.v0"
id = "Example:BUCK_6V_2A"
class = "controller"
ground = "GND"

[pins]
BST = "1"
GND = "2"
FB  = { pins = ["3"], voltage = { abs_max = "6.5V" } }
EN  = { pins = ["4"], voltage = { abs_max = { min = "-0.3V", max = "6.5V" } }, input_high_min = "1.2V", input_low_max = "0.4V" }
VIN = { pins = ["5"], voltage = { operating = { min = "2.7V", max = "6V" }, abs_max = "6.5V" } }
SW  = "6"

[[limits]]
between = ["BST", "SW"]
voltage = { abs_max = "6V" }

[ratings]
current = { abs_max = "2.5A", operating = "2A" }
temperature = { abs_max = { min = "-55degC", max = "150degC" }, operating = { min = "-40degC", max = "125degC" } }
```

- **One shape for every limit.** A pin's `voltage` and `current`, each `[ratings]` key, and each
  `[[limits]]` `voltage` take a table with `abs_max` and/or `operating`. Each of those is a `{ min, max }`
  table or a string, which is the maximum (`"6.5V"` is `{ max = "6.5V" }`).
- **What each kind means, and who judges it.**

  | kind | meaning | judged by | derated |
  |---|---|---|---|
  | `abs_max` | beyond it the part may be damaged | c0253 `circuit.rating-*`, worst case | yes, by the user's policy |
  | `operating` | the range in which the part works as specified | c0253 `circuit.operating-range`, exactly; c0252 for device ports | never |

- **The single form is refused.** `voltage = { min = "2.7V", max = "6V" }` (c0248's first form) gives
  `FEN-3004` naming the file and the pin, with the hint "say `abs_max` or `operating`". It was never
  released, and reading it as either kind would be a guess (Open question 1).
- **`[[limits]]`.** `between` names two distinct functions of the device; the voltage is the first minus
  the second. Rows are sorted by `between`. Two rows with the same pair are refused.
- **Logic thresholds** on a pin: `input_high_min`, `input_low_max`, `output_high_min`, `output_low_max`
  (voltages from `ground`) and `output_current_max` (a current), each one quantity text. A c0252 `logic`
  or bus port of the device takes a threshold its own table omits from its member pins, the strictest of
  them: the highest `input_high_min`, the lowest `input_low_max`, the lowest `output_high_min`, the
  highest `output_low_max`, the lowest `output_current_max`. A port that states a threshold keeps its own.
- **`class`.** One name of the roles' vocabulary (decision 4). It is evidence for `roles.classify`, not a
  second classifier.
- **Temperatures** are stored in millikelvin (unit `mK`): `"-40degC"` reads as 233 150 mK and `"233.15K"`
  as the same. A Celsius text with more than three decimals is refused, as any non-whole value is.
- **Model.** `fenolite.model.library`:
  - `Rating(key, unit, min=None, max=None, limit="abs_max")`, `limit` in `abs_max`, `operating`;
  - `DevicePin(function, pin_pads, ratings=(), thresholds=(), must_connect=False)`: `ratings` sorted by
    `(key, limit)` replaces c0248's `voltage` and `current`; `Threshold(key, unit, value)`;
  - `PinPairLimit(between, ratings)` and `DeviceDef.limits`, `DeviceDef.cls` (TOML key `class`).

  Units stay integers (`uV`, `uA`, `uW`, `mK`). The library schema is regenerated; the canonical device
  text and the digest follow, so every record's digest changes once (no record has shipped yet).
- **Alternatives considered.**
  - *Read the single form as `abs_max`.* Rejected: the research found it holding an operating minimum in
    c0248's own example.
  - *Separate keys `voltage_abs` and `voltage_op`.* Rejected: two flat keys per quantity double the key
    table and cannot express a pin-pair limit the same way.

### 2. Phase A: temperature, products and one-sided ranges (c0246 extension)

```python
from fenolite.dsl import between, celsius, kelvin, volt, ohm

ambient = between(celsius(-20), celsius(70))  # 253.15 K .. 343.15 K, prints -20°C..70°C
margin = kelvin(15)  # a difference: 15 K
p = volt("13.2") * volt("13.2") / ohm("990")  # V·V / Ω -> watt, exactly
floor = volt("4.5").min() + volt("0.2")  # one-sided: 4.7 V and up
```

- **Kelvin.** `kelvin` joins c0246's unit table in `dsl.quantity` and `RangeUnit` in the model.
  `celsius(x)` returns `kelvin(x + 273.15)` exactly; `kelvin(x)` takes kelvin. An absolute temperature and
  a difference share the unit, as in SI; the *text* tells them apart: a row or message whose quantity is a
  temperature prints degrees Celsius (`-20°C..70°C`), a difference prints kelvin (`15K`). `core.quantities`
  parses `degC` and `K` texts for device records and `requirements.toml`.
- **Products.** `UNIT_PRODUCTS` gains volt·volt → `volt_squared` and ampere·ampere → `ampere_squared`, and
  `ampere_squared`·ohm → watt; `UNIT_QUOTIENTS` gains `volt_squared`/ohm → watt and watt/ohm →
  `ampere_squared`. The two squared units exist in the DSL and in the judge only: `RangeUnit` refuses them,
  so they never reach a file. These are definitions of SI derived units (P = V²/R = I²R), not data.
- **One-sided ranges in arithmetic.** c0246 refuses arithmetic on an unbounded range. Now:
  - `a + b` and `a - b` (as `a + (-b)`) add bounds side by side; a side is unbounded when either operand
    is unbounded there;
  - `a * b` and `a / b` are allowed when both operands are non-negative (`low >= 0`): the low bound is the
    product (or quotient) of the low bounds, the high bound that of the high bounds, an unbounded high
    staying unbounded, and a division by a range whose low bound is 0 refused as today;
  - the result must keep at least one bound, else `DslError` names the operation. Signed one-sided
    products stay refused.

  `within`, `at_least` and `at_most` already accept unbounded sides; c0253's judgement reads an unbounded
  high as never below a limit.
- **Alternatives considered.** A separate `celsius` unit with offsets in arithmetic: rejected, adding two
  Celsius temperatures is meaningless and offsets make products wrong. Floats for temperature: forbidden.

### 3. Phase C: waivers of `circuit.*` findings, keyed on the judged value

```python
design.waive(
    "circuit.rating-voltage",
    "C3:voltage",
    reason="16 V part accepted at 13.2 V: bench supply is current-limited, see test plan 4",
    digest="9f2c4a1b0d3e5f67",
)
```

- **What a waiver states.** The code, the scope (the row of c0253's table, its id without the code: one
  exact item, no glob), the reason, and the digest of what was judged.
- **The digest.** Every requirement row gains `digest`: the first 16 hexadecimal digits of the SHA-256 of
  the canonical JSON of `{id, value.range, limit.range, limit.kind, value.source, limit.source}`. Each
  `circuit.*` issue's hint ends with `digest <16 hex>`, and the matrix lists it, so the author copies it
  from the finding being accepted. The basis texts are left out, so a reworded message is not a change.
- **Matching.** A `circuit.*` waiver matches a finding when the code is equal, its one item equals the
  finding's row id without the code, and its digest equals the row's. The effect is the living one: the
  issue takes `info` and ends with ` (waived by <name>: <reason>)`.
- **Expiry.** When code and item match but the digest differs, the finding is not waived and one
  `check.waiver-expired` warning names the waiver, both digests and the row, "the value or the limit
  judged changed since the waiver". A rating that moved from 13.2 V to 14 V, a part re-picked (c0254) or a
  value kept from a CAD edit (c0250) all change the digest.
- **Where waivers apply.** In the stage `circuit.rules` and in `cmd_build`'s circuit hook (c0252), with
  the same matching, so an accepted risk does not stop `build --confirm`. A `circuit.*` waiver is judged
  when the stage ran with a verdict; otherwise it is `unjudged` with `stage-not-run`.
- **Severities.** Every `circuit.*` code of `ISSUE_CODES` gains `info`, the severity of a waived finding.
- **Alternatives considered.**
  - *Waive by code and glob only, as copper waivers do.* Rejected: a circuit verdict depends on numbers
    that change silently with a pick or an edit; a waiver must not outlive them.
  - *Store the full value and limit in the waiver.* Rejected: long, unit-laden script lines; the digest
    is short, exact and shown where it is needed.
  - *Expire silently (treat as unmatched).* Rejected: the author must know why an accepted finding is back.

### 4. Phase B: the one classifier gains `FB`, `F` and `JP`

- `PART_CLASSES` (in `fenolite.model.rules`) gains `ferrite`, `fuse` and `jumper`; `roles.classify`'s
  `PREFIXES` gains `FB` → `ferrite`, `F` → `fuse` and `JP` → `jumper`.
- **Order of evidence.** The user's class; the device record's `class` (decision 1, confidence `high`,
  source `device`); pin names; pin types; then, for a part whose prefix is `FB`, `F` or `JP`, that prefix
  before the value (a ferrite's impedance and a fuse's rating read like a resistance), confidence
  `medium`; then the value or pad count; then the prefix, `low`.
- **Tested once.** `tests/unit/roles/test_classify.py` holds the prefix cases; c0253's test asserts that
  no other prefix table exists. The role inference rules read none of the three classes, so every inferred
  role of `examples/roles` stays as `H-G-ROLE-INFER` records it.
- **In c0253.** `ferrite` joins the series classes of "Device current by class" with the derating key
  `ferrite_current`. A `fuse`'s current stays unjudged (c0253 non-goal); a `jumper` has no rating row.
- **Alternative considered:** `FB` → `inductor`, as c0253's first draft did. Rejected: propagation must
  cross a ferrite and never a power inductor.

### 5. Phase D: voltage propagation through links, with origins

- **Links.** A part with exactly two nets is a link when its class (decision 4) is `ferrite`, `fuse` or
  `net_tie`; when it is a `jumper` whose class the user stated with `design.part_class(jp, "jumper")` (a
  stated jumper is a closed one; an open jumper is simply not declared); or when it is a `resistor` or
  `shunt` whose `value_range` is exactly 0 Ω. Nothing else is crossed: no inductor, no regulator, no
  diode, no resistor above 0 Ω.
- **Rule.** After c0253's stated sources (rig, rail, role, ground), each net without a stated voltage
  takes the hull of the stated voltages of the nets it reaches through links, breadth first, in net-name
  order. A stated net keeps its own value. Two stated nets joined by links whose ranges do not overlap give
  c0253's `circuit.value-conflict`, naming the links.
- **Rails.** A c0252 rail with no voltage set whose net receives a propagated voltage is judged with it
  (rail voltage, logic withstand, companions' `supply`) instead of `circuit.rail-unset`.
- **Origins.** Every voltage and current bound records an origin:

  | origin | when |
  |---|---|
  | `declared` | a c0252 design rail or an `out` port's promise |
  | `rig` | a rig element (c0253) |
  | `role` | a declared or confirmed net role |
  | `requirements` | a `[[current]]` row |
  | `option` | `--current NET=AMPS` |
  | `propagated` | through links, with `via` (the link refs in order) and `from` (the stated net) |

  The table's `value` gains `origin` (`{"kind": "propagated", "via": ["FB1"], "from": "3V3"}`), and the
  text form is `propagated via FB1 from 3V3`.
- **Opt-out.** `design.contracts(propagate=False)` (c0253's call gains the keyword) turns it off for a
  design.
- **No drop.** The propagated range is the source's: the small DC drop of a ferrite or a fuse is not
  subtracted, so the lower bound is optimistic by that drop (Open question 3).
- **Example** (`examples/circuit/ferrite/`, authored for Fenolite): an analog sensor's `vdda` port on
  `3V3A`, fed from `3V3` through `FB1`. With no voltage on `3V3A`, c0252 gave `circuit.rail-unset`; now
  `3V3A` is 3.201 V to 3.399 V, origin `propagated via FB1 from 3V3`, and the sensor's `vdda` (1.71 V to
  3.6 V) passes. The bad variant puts `3V3A` behind a 10 Ω resistor: nothing propagates and the warning
  stays.
- **Alternative considered:** power flags as in KiCad. Rejected: a flag states "driven", not a voltage,
  and it is the very symptom the research names.

### 6. Phase E: decidable stages and `deferred`

- Each `RequirementRow` gains `decidable`: `build`, `place` or `route`, from a closed table:

  | rows | decidable |
  |---|---|
  | every `circuit.*` row | `build` |
  | `roles.loop-area`, `roles.gate-loop` (pad positions) | `place` |
  | every other judged `roles.*` row (copper widths, sections, vias, Kelvin and gate returns, distances, returns) | `route` |

- **Reached, per subject.** A `place` row is reached when every component of its subject has its
  footprint inside the board outline; a `route` row when, in addition, no net of its subject has an open
  connection (`board-analyses`, "Open connections of a net"). A `build` row is reached on a built project.
- **Status.** A row whose stage is not reached and whose verdict is not `fail` gets the status
  `deferred`, with `decidable` naming the stage, and gives no issue. A `fail` stays `fail`: copper that is
  already too thin will not get wider by routing the rest. Nothing not reached is ever `pass`.
- `summary.deferred` of each stage counts the deferred rows by stage.
- **Alternative considered:** one board-wide stage (the board is "routed" or not). Rejected: a board in
  progress has routed power nets and unrouted signals, and the routed ones can be decided.

### 7. Phase F: stable row ids and `fenolite check --matrix`

- **Stable ids.** c0253's form `<code>:<subject>[:<key>]`, with a closed subject form per row family:

  | rows | id |
  |---|---|
  | part limits | `circuit.rating-voltage:C3:voltage`, `circuit.rating-voltage:U1:VIN`, `circuit.rating-voltage:U1:BST-SW`, `circuit.operating-range:U1:VIN` |
  | rails | `circuit.rail-voltage:3V3:U3/vdd`, `circuit.rail-current:3V3` |
  | logic | `circuit.logic-level:U3/int_>U2/pa3:high` (`high`, `low`, `withstand`) |
  | bus pull-ups | `circuit.bus-pullup:I2C1:SDA` |
  | expectations | `circuit.expect:buck1/expect#1` |
  | roles | `roles.loop-area:buck:loop_ratio_max` (c0253) |

  Ids use references (kept by c0249's lock), port paths, net names and expectation ids, never entity ids,
  positions or seeds. Two builds with different seeds, or with statements reordered, give the same ids.
- **The matrix.** `fenolite check PATH --matrix` adds `result.matrix`:

  ```json
  {"receipt": {"fenolite": "0.7.0", "model_sha256": "…", "devices_sha256": "…",
               "stages": ["circuit.rules", "roles.rules"]},
   "rows": [{"id": "circuit.rating-voltage:C3:voltage", "check": "capacitor voltage",
             "value": "0..13.2V", "limit": "<= 12.5V (50% x 25V)", "source": "policy",
             "origin": "rig bench", "status": "fail", "evidence": "UNVERIFIED",
             "decidable": "build", "digest": "9f2c4a1b0d3e5f67", "waiver": null}]}
  ```

  - `rows` are the requirement rows of the stages that ran, sorted by id, with the status `waived` for a
    row whose finding a waiver matched (and `waiver` its name) and `deferred` from decision 6.
  - `receipt` holds the SHA-256 of the canonical `.fenolite/` texts and of the sorted device digests, so a
    matrix pasted into a review names exactly what it judged.
  - In a terminal (`--text`) the matrix prints as a table: id, check, value, limit, source, status.
  - `--matrix` writes nothing; the shell redirects the JSON reply. It runs the default stages unless
    `--stages` says otherwise, and adds nothing when no stage gives rows.
- **Alternatives considered.** A separate `fenolite matrix` command: rejected, the rows are the check's.
  A CSV writer: rejected for now, a writing command needs a plan and a receipt (Open question 4).

### 8. Codes and errors

- New check code: `check.waiver-expired` (warning), beside `check.waiver-unmatched`.
- Every `circuit.*` code gains the severity `info` (a waived finding).
- No new skip reason, no new `FEN-` code: a bad record is `FEN-3004`, a bad DSL call `DslError`.

## Hypotheses and evidence

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-G-CIRCUIT-PROPAGATION` | Propagating stated voltages through ferrites, fuses, net ties, stated jumpers and 0 Ω parts gives each linked net the range of its source and crosses no other part | `tests/unit/checks/circuit/test_propagate.py` | on `examples/circuit/ferrite`, `3V3A` gets 3.201 V to 3.399 V via `FB1` in the good variant and nothing through the 10 Ω resistor of the bad one |
| `H-G-CIRCUIT-ROW-IDS` | Row ids depend only on references, paths, names and expectation ids | `tests/unit/checks/circuit/test_matrix.py -k stable` | the sensor example built with seeds 1 and 2, and with its statements reordered, gives identical `id` lists |

Both are registered in `docs/hypotheses.md` by the tasks, as `INFERRED`. This change also cites
`H-G-ROLE-INFER` (unchanged roles after decision 4) and c0253's `H-G-CIRCUIT-EXAMPLE` and c0248's
`H-G-DEVICE-RECORD`, which those changes register.

## Risks / Trade-offs

- **Every record written before phase A is refused.** Mitigation: phase A lands right after c0248, before
  any record ships; `fenolite catalog import` (c0248) writes the split form.
- **A digest the author must copy.** Mitigation: the hint of each finding and the matrix print it; a
  mistyped digest gives `check.waiver-expired`, never a silent waiver.
- **Propagation can carry a wrong stated value further.** Mitigation: the origin names the source and
  the links, and a conflict between two stated nets is a warning.
- **Optimistic lower bound behind a link** (no drop). Mitigation: documented; Open question 3.
- **Deferred rows hide nothing that fails,** but a long list of deferred rows can read as work left
  undone; that is what it is.

## Open Questions

1. **Refuse c0248's single `{ min, max }` form, or read it as `abs_max`?** Recommended: refuse with a
   hint; no record has shipped, and either reading is a guess.
   Decided 2026-10-29: refuse with `FEN-3004` and the hint "say abs_max ... or operating ..."
   (`DeviceLimitFormError`); implemented in phase A.
2. **Should the digest cover the device record's digest too,** so that a record edit expires a waiver even
   when the judged numbers are equal? Recommended: no; the waiver accepts numbers, and an unchanged
   number is the same risk.
   Decided 2026-10-29: no; the digest covers the judged numbers only (phase C).
3. **Should propagation subtract a stated drop** (a ferrite's DC resistance times the current bound)?
   Recommended: not now; a later change can add it once records state DC resistance, with c0246 ranges.
   Decided 2026-10-29: not now (phase D copies the source range unchanged).
4. **Should the matrix also be written as a file** (CSV or JSON) for a requirements portal?
   Recommended: later, as `fenolite export matrix` under the plan and confirm protocol, if users ask.
   Decided 2026-10-29: later; `--matrix` stays a read-only reply of `check` (phase F).
5. **Should an open jumper be stated** (`design.part_class(jp, "jumper", closed=False)`)? Recommended: no;
   an undeclared jumper is not crossed, which is the safe reading.
   Decided 2026-10-29: no; an undeclared jumper is not crossed (phase D).

### Decisions taken while implementing phase A (2026-10-29)

- **Products of two quantities.** c0246's scenario "Two quantities of different units still refused"
  (`volt("1") * amp("1")` raises `TypeError`) is kept: the one product of two quantities is a square,
  `volt(a) * volt(b)` or `amp(a) * amp(b)`, which gives a degenerate range of `volt_squared` or
  `ampere_squared` (scenario "The power of a bleeder"). Every other product needs a range operand, as in
  c0246.
- **One-sided quotients.** Decision 2's "the high bound that of the high bounds" is read as worst-case
  interval division, which is what c0246 does for bounded ranges: `a / b` is `[a0/b1, a1/b0]`, `a0/b1`
  taken as 0 when `b1` is unbounded and `a1/b0` unbounded when `a1` is. A one-sided result carries no
  nominal.
- **A repeated pair** of `[[limits]]` is the same two functions in either order: `["BST", "SW"]` and
  `["SW", "BST"]` in one record are refused, since one is the negated other.
- **Temperatures.** A device text in `degC` takes no SI prefix and cannot lie below absolute zero; a value
  in kelvin is signed in the DSL (a difference) and unsigned in a device record (an absolute
  temperature). The canonical device text prints temperatures in `degC`.
- **Where records are documented.** Device records are documented in `docs/devices.md` (c0248), not in
  `docs/catalog/README.md`, which covers the symbol and footprint catalog; phase A's record changes are
  written there.
- **The ferrite scenario in phase A.** `class = "ferrite"` needs phase B's vocabulary; phase A tests the
  `class` key with `controller` and refuses `bead`.

## Relation to the other changes of this batch

- **c0246 (A):** extended with `kelvin`, the products and one-sided arithmetic (phase A).
- **c0248 (B):** extended with `abs_max`/`operating`, `[[limits]]`, thresholds, `class` and mK (phase A).
- **c0249 (C):** the lock keeps references stable, which keeps row ids stable.
- **c0250 (G):** a kept CAD edit changes a value range, so its rows' digests change and waivers expire.
- **c0252 (E):** reads phase A's thresholds for device ports; its rails take propagated voltages; its
  rows get ids, digests and `decidable = build`; its findings can be waived.
- **c0253 (F):** reads phase A's limits, kelvin and products; its table gains `origin`, `decidable`,
  `digest` and the matrix; `design.contracts` gains `propagate`; `ferrite` joins its series classes.
- **c0254 (H):** a new pick changes digests, so a waiver of the old part expires.
- **c0256 (K):** test helpers can assert on matrix rows by id.
- **c0222 (roles, on `dev`):** the vocabulary and prefix table gain three classes; role rows gain
  `decidable` and appear in the matrix.

### Decisions taken while implementing phases B to F (2026-10-30)

- **Device class evidence.** `roles.classify(..., device_classes=)` takes the records' `class` by reference;
  `cli._contracts.classes_of(model, devices)` fills it, so build, check and roles inject it alike. With a
  device class, the terminal map comes from the pin names when they give the same class.
- **Thresholds from pins** are added where the model port is made (`dsl.devices.port_params`, called by
  `dsl.convert`), only for a threshold the port's kind and direction take; the record's canonical text is
  unchanged.
- **Findings without a row.** c0252's logic, bus, companion and split-port rules and the value conflicts give
  findings, not rows. They are waived the same way, named by their `where` and the digest of their code,
  `where` and message (which name every number judged), so every circuit error can be accepted. Logic and
  bus rows (`circuit.logic-level:...`, `circuit.bus-pullup:...` of decision 7) are not added by this
  change: those rules still give findings only.
- **Waiver outcome keys.** `result.waivers` always holds `expired`; the copper and DRC stage summaries keep
  their bytes (no `expired` key there), and `circuit.rules` lists its circuit waivers in `summary.waivers`
  only when the design has some. The build applies circuit waivers and adds `check.waiver-expired` to its
  issues; it does not report unmatched waivers (`fenolite check` does).
- **Origins.** The closed set is `declared`, `rig`, `role`, `requirements`, `option`, `propagated`; a ground
  is `declared` (c0252 ground) or `role`. A two-net value takes the origin of its non-ground net, a
  propagated one first. The precedence of currents is not changed: both the role checks
  (`roles.infer.with_currents`) and the circuit rows read a role's own current, then `[[current]]`, then
  `--current`; the circuit rows read a rig and a rail's loads before them, as c0253 states. The origin
  (`requirements` or `option`) now says which one was used, so no reconciliation was needed.
- **Propagation** stops at a stated net (it never crosses one to reach another) and takes the hull of the
  stated nets reached; `from` and `via` name the first one reached (breadth first, net-name order).
- **Role rows.** A width or section row is one row per code and net (`roles.width-current:VBUS`, its
  narrowest element), so its id is stable; a role net with a current whose power path gives no measured
  copper (open or unrouted) lists `roles.width-current:<net>` with no value, `unknown` and so `deferred`
  while the net has an open connection. The reach reads the board boundary (`analysis.boundary`) and the
  open connections (`analysis.connectivity`) in `roles.judge.board_reach`; `core.decidable` holds the
  closed table and the rule (in `core`, since `roles` imports no module of `checks`;
  `checks.circuit.decidable` re-exports it).
- **`--matrix` stages.** Without `--stages`, `--matrix` runs only `circuit.rules` and `roles.rules` (the
  stages that give rows) instead of the default stages, so it needs no `kicad-cli`. Its text table is
  printed in text mode also when the check fails (`Result.text_on_failure`).
- **Row id forms.** `circuit.rail-voltage:<rail>:<port path>` (port path `U3/vdd` or `buck/VOUT`).
- **Agent guide.** `design-script`, `checks` and `board-power` are at their 12 000-byte budget; the matrix,
  `deferred`, `waived`, `check.waiver-expired`, a circuit waiver with its digest, `abs_max`, `operating` and
  `[[limits]]` are taught in a section of `board-review` (reviewing is where the matrix is read).
