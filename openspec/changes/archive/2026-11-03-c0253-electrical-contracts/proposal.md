## Why

`docs/research/circuit-as-code.md`, section 7 and core change F. Fenolite 0.6.0 checks copper, placement,
DRC, ERC and, since c0222, the copper of power nets against their roles. Nothing checks a part against the
circuit it sits in:

- a 16 V capacitor on a 12 V ± 10 % input passes every check, and so does a 10 V one;
- an inductor rated 1 A in series with a 1.2 A rail passes;
- the divider that sets a regulator's output can be edited in KiCad to a value that puts the output out
  of its range, and no check sees it;
- a block author has no way to write down "this inductor needs 30 % margin over the block's current"
  where the next user will see it fail.

The requirements are also split over three places: DSL rules, net roles (with their own `RoleLimit`
overrides and profile) and `requirements.toml`, which takes raw integers (`clearance_nm = 1200000`).

The batch of 2026-10-29 gives the inputs this check needs:

- ranges with tolerance (c0246);
- device records with ratings, including pin ratings measured from a ground function (c0248), split by
  c0274 (phase A, implemented right after c0248) into absolute maximum (`abs_max`) and operating limits,
  with limits between two pins;
- temperatures in kelvin and the range products V·V, A·A, V²/Ω and A²·Ω (c0274 phase A, on c0246);
- blocks (c0251);
- rails, together with the stage `circuit.rules` that judges them (c0252).

Net roles (c0222) already carry a net's current (`milliamps`) and working voltage (`working_mv`). This
change is the judge of ratings and expectations over them, the fifth step of the research's order.

## What Changes

- **Ratings in c0252's stage `circuit.rules`.** The stage compares each device part's limits (c0248, as
  c0274 splits them) with the voltages and currents its nets carry, and judges the recorded expectations.
  This change adds no stage, no package and no tool: its modules join c0252's package `checks/circuit/`,
  and the commands resolve the device records and inject them into the stage, as c0248 asks. `fenolite
  build` reports the new codes through c0252's build hook, under its rule.
- **Absolute limits and operating ranges are judged apart.** `abs_max` values are ratings: judged against
  the worst case, through the derating policy, as `circuit.rating-*`. `operating` values are what the part
  needs to work: judged exactly, never derated (a derating would loosen a minimum such as VIN ≥ 2.7 V), as
  `circuit.operating-range`.
- **Applied values come only from what the user stated:** the test rig, c0252 rails (their voltage and
  summed loads), and the `working_mv` of declared or confirmed net roles (c0222). A net's current comes, after
  the rig and the rail, in the order of roles: the role's `milliamps`, then a `[[current]]` row, then
  `--current NET=AMPS`, so the role table and the circuit table never differ. Fenolite infers no voltage and
  no current. A value it cannot bound is shown as `unknown`, never guessed.
- **Ratings checks:**
  - the voltage across two-pin parts;
  - the voltage of each rated pin from its device's ground function, and of each pin pair of the record's
    `[[limits]]` (BST−SW, a high-side gate−source);
  - device current defined per class: a regulator against the loads of its `out` port, an inductor or a
    shunt against the current bounds of its nets, a single pin against its net;
  - resistor and shunt power;
  - the rated temperature range against the design's ambient range.

  Part classes come from **one classifier**, c0222's `fenolite.roles.classify` (its `PartClass` and prefix
  table), run by the command and injected into the stage. No second table exists.
- **Derating policy:** `design.derating(capacitor_voltage=ratio(50), ...)` sets per-mille limits by part class and
  rating key, with optional part scope, stored in the model. `ratio(50)` reads "at most 50 % of the
  rating"; c0246's `pct()` stays a ± tolerance and is refused here. **Fenolite ships no derating number.**
  Without a policy, parts are judged at 100 % of their rating, with one info finding that says so. A
  named, sourced preset can be added later by its own change, but none ships here.
- **`expect()`:** `design.expect(...)` and the block method `b.expect(...)` (c0251) record an expectation in
  the model.
  - It compares handles (`value_of(part)`, `rating_of(part, key)`, `voltage_of(net)`, `current_of(net)`)
    and c0246 ranges, with a reason.
  - The stage judges it with three results: pass, unsure (warning) and fail (error).
  - It is not a Python `assert`: a failure stops nothing, and the expectation is judged again after a
    manual edit (c0250) or a new pick (c0254).
- **`design.rig(...)`:** test-rig stimulus (`supply()`, `sink()`) gives the voltages and currents of the
  outside world, such as a bench supply on the input connector. A rig element is a record of the rules
  layer, not a component, so it never reaches the BOM, the board, the schematic, the netlist or any
  export. Every row that depends on a rig supply is also evaluated at each **corner** (each supply at its
  minimum and at its maximum), and a failing row names its corner.
- **Strictness:** `design.contracts(unknown="warning")` makes each row that cannot be judged a warning. The
  default stays `info` (one count) until the shipped devices carry ratings; it then becomes `warning`.
- **One requirement table.** Each judged row has an id, the entity ids, the quantity, a **value** and a
  **limit** (each an exact range in c0246's encoding, unit name with mantissa and exponent, with a
  **source** of `device`, `role`, `policy` or `user`, and a basis text), a status and the evidence. Rule
  records in `rules.json` use the same encoding.
  - The rows of c0252's rail checks and of `roles.rules` (c0222) join the same table: profile defaults
    become `policy`, and overrides and requirements become `user`.
  - The table is `summary.requirements` of both stages and `result.requirements` of `fenolite roles
    --check`.
  - The viewer of c0245 reads it from the check reply it already draws.
- **Units in `requirements.toml`:** `clearance = "1.2mm"`, `current = "2A"`, `temp_rise = "10K"`,
  `voltage = "230V"`, and so on, beside the raw integer keys, which stay accepted. Giving both forms of one
  key is a `FormatError`. An optional `source` text names where the user's number comes from. Electrical
  and temperature values are parsed by `fenolite.core.quantities` (c0248, with c0274's kelvin), lengths and
  areas by `fenolite.core.units`.

## Capabilities

### New Capabilities

- `electrical-contracts`: applied values and their sources, part classes for contracts, the ratings
  checks, the derating policy (no shipped values), expectations and their three-valued judgement, the test
  rig, its corners and its exclusion from outputs, the strictness setting, the requirement table, the
  thirteen new `circuit.*` codes, evidence and the reference example.

### Modified Capabilities

- `design-dsl`: ADDED "Electrical contracts in the DSL" and "Contract helpers in the DSL".
- `design-model`: ADDED "Contracts in the model" and "Expectation trees in the model".
- `verification-loop`: ADDED "Contracts in the circuit stage" and "Device records injected into the
  circuit stage". They extend c0252's "Circuit stage" and do not restate it.
- `cli-contract`: ADDED "Requirement table in the roles command" and "Requirements file bounds both kinds
  of row".
- `net-roles`: ADDED "Role rows in the requirement table" and "Sources of role rows".
- `board-analyses`: MODIFIED "Requirement tables supplied by the user" (unit keys beside raw keys, the
  `source` text, the tables added since c0115).

`package-layering` is unchanged:

- the judge lives in `checks`, which may import `model`, and `DeviceDef` is a `model.library` type;
- the row type is in `core`;
- `cli` resolves the devices and joins the role rows and the circuit rows.

## Dependencies

- **Needs, before implementation:**
  - c0246 (ranges, `Component.value_range` and its encoding);
  - c0248 (`DeviceDef` ratings, `DevicePin` and `ground`, `fenolite.device` on components, the unit
    parser `core/quantities`);
  - c0274 phase A, implemented right after c0248 (the `abs_max`/`operating` split, `[[limits]]`, kelvin
    and `celsius()`, the range products);
  - c0251 (blocks, for `b.expect`);
  - c0252 (rails, the stage `circuit.rules`, the package `checks/circuit/`, `circuit_issues`, the build
    hook, the skip vocabulary).

  c0222 is on `dev`.
- **Works with:**
  - c0249: the lock is not touched, because rig and expectations are not picks;
  - c0250: a kept CAD edit of a value is judged again;
  - c0254: generators may record their achieved range as an expectation;
  - c0256: `fenolite.testing` reads `circuit.*` findings;
  - c0245: the viewer, on another branch;
  - c0274 (later phases): waivers of `circuit.*` findings with a value digest, voltage propagation,
    decidable stages and the verification matrix over this table. 0.7.0 is not released before them.

## Non-goals

- No circuit simulation, no solver, no operating-point analysis. Values are bounded by range arithmetic
  on what the user stated (c0246 has no solver either).
- No junction-temperature estimate, no thermal model, no power dissipation of active parts.
- No polarity check of polarised parts, no transient, surge, ripple or I²t rating, no fuse current check.
- No voltage propagated through parts (c0274 adds it for ferrites, fuses and links).
- No shipped derating table, no copy of any derating standard or handbook table.
- No inferred voltage or current. Inferred roles that are not confirmed carry none, so they give no
  applied value.
- No change of the role profile, of the role checks or of their severities (c0222), and no new part
  class (c0274 adds `FB` and the classes it needs to the roles' classifier).
- No new stage and no new `FEN-` code.

## Evidence level required

- The judgement is exact arithmetic on stated values, so the stage as a whole is `INFERRED`.
- Each row also carries the evidence of the device record it read (c0248). The lowest label wins, as in
  c0252, so a row on an `UNVERIFIED` device is `UNVERIFIED`.
- Rig exclusion: the outputs of a build with and without `design.rig(...)` are byte-identical except
  `.fenolite/rules.json` (test).

## Impact

- New:
  - `values.py`, `ratings.py`, `expect.py`, `corners.py` and `table.py` in c0252's package
    `src/fenolite/checks/circuit/`;
  - `src/fenolite/core/requirement_table.py`;
  - `src/fenolite/dsl/contracts.py`;
  - `examples/circuit/sensor/` (good and bad variants, `requirements.toml` with units);
  - `docs/contracts.md`.
- Changed:
  - `model/rules.py` (`RuleSet.contracts`);
  - `core/units.py` (`parse_area` beside `parse_length`);
  - `analysis/requirements.py` (unit keys);
  - `checks/codes.py`;
  - `cli/cmd_check.py`, `cli/cmd_roles.py`, `cli/cmd_build.py` (resolve and inject the devices and the
    part classes of `roles.classify`);
  - `roles/judge.py` (role rows);
  - `explain.toml`;
  - `docs/dsl.md`, `docs/roles.md`, `docs/analyses.md`, `docs/cli-contract.md`, `docs/design-model.md`;
  - the guide pages `checks`, `board-power` and `rules`;
  - `CHANGELOG.md`.
- Sources: none registered. Every limit is a device rating (c0248's sources) or the user's.
- Size: about 13 design-days.
