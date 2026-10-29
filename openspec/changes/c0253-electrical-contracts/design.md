## Context

- **Source.** `docs/research/circuit-as-code.md`, section 7 ("Requirements and electrical contracts") and
  core change F of "What changes in the core". The research describes the concepts of atopile (assertions
  on ranges, checks attached to interface types, fail and maybe-fail results) and JITX (checks written once
  and run on every build, a test rig that brings in the outside world) in words only. No code, grammar,
  schema, library text, constant or table of these projects is used here.
- **What exists on `dev` (0.6.0).**
  - **Net roles (c0222).** `fenolite.model.rules`:
    - `NetRole(net, kind, source, rule, confidence, milliamps, working_mv, sensitive)`;
    - `RoleLimit(key, value, net, kind)`;
    - `RoleSet` in `RuleSet.roles`;
    - `PartClass(ref, cls, terminals)` for the classes the user states with `design.part_class`. The class
      names are c0222's closed vocabulary (`transistor`, `diode`, `inductor`, `capacitor`, `resistor`,
      `shunt`, …).

    `fenolite.roles.profile` holds the default role limits, each with an `S-` source or an `H-G-ROLE-`
    hypothesis. Each finding names its limit as `key=value (origin)`, where `origin` is `profile`,
    `override` or `requirements`. Severity: a default limit gives at most a `warning`; the user's limit on a
    confirmed or declared role gives an `error`. The stage `roles.rules` takes its judge from `cmd_check`
    (`checks.roles.RolesJudge`), because `checks` may not import `roles` or `analysis`. Fenolite infers
    no current and no voltage.
  - **The requirements file.** `analysis/requirements.py`, schema `fenolite.requirements.v0`: integer
    keys whose names carry the unit (`clearance_nm`, `milliamps`, `temp_rise_mk`, `millivolts`,
    `up_to_mv`, `drop_mv`, `max_distance_nm`, `min_width_nm`, `max_area_nm2`). A float is refused.
    "No shipped requirement values" (board-analyses) forbids default values in `analysis`.
  - **Quantities.** `dsl.quantity` parses `ohm`, `farad`, `henry`, `volt`, `amp`, `hertz`, `watt` and
    `second` into an exact `Fraction` value. Comparing two quantities returns a `bool`. There is no
    temperature unit.
  - **Check pipeline.** `checks/stages.py` (`STAGE_ORDER`, `DEFAULT_STAGES`, `StageSkip`) and
    `checks/documents.py` (`DOCUMENT_STAGES`). The fill oracle, the plotter and the roles judge are
    injected by `cmd_check`, because `checks` may import only `model`, `geometry` and `backends.base`.
  - **Agent guide coverage.** `tests/unit/agent/test_pages.py` requires a tested guide line for every new
    public DSL name and command.
- **What the batch adds before this change.** These are implementation steps 1 to 4. Their folders were
  written in parallel and read on 2026-10-29; task 0.1 checks them against what landed.
  - **c0246:** `Range` with exact bounds and a nominal, `between()`, `Quantity.pct()`, `pct()` returning a
    `Tolerance` (a ± tolerance), worst-case `+ - * /`, `Range.within() -> bool`, and `Component.value_range`
    in the model, encoded as a unit name (`volt`, `ampere`, `ohm`, ...) and `Decimal10` bounds (integer
    mantissa and exponent). It defines no ordering between ranges.
  - **c0274 phase A** (implemented right after c0248, before c0252): the unit `kelvin` with `celsius()` and
    `kelvin()` at the boundary; the products V·V → V², A·A → A², V²/Ω → W and A²·Ω → W; one-sided ranges in
    arithmetic where the result keeps a bound; and the c0248 delta below.
  - **c0248:** `DeviceDef` in `fenolite.model.library` (library definitions stay out of `.fenolite/`), and
    the exact unit parser `fenolite.core.quantities`.
    - Device ratings have the closed keys `voltage`, `current`, `power` and `temperature`, each with a
      `min` and/or a `max`, stored as integers (µV, µA, µW; temperatures in mK after c0274).
    - `DevicePin(function, pin_pads, voltage, current, must_connect)`: a pin's `voltage` is measured from
      the device's `ground` function.
    - **As c0274 phase A splits them:** every rating and pin limit is either `abs_max` (an absolute maximum
      rating) or `operating` (the range the part needs to work), `[[limits]]` states a voltage between two
      functions (`between = ["BST", "SW"]`), and pins carry logic thresholds.
    - A device part's component carries the properties `fenolite.device` and `fenolite.device.sha256`.
    - c0248 states that c0253 reads the ratings "injected into the check stage by the command (checks
      cannot import catalog)".
    - The device record has no class field.
  - **c0251:** blocks with ports, parameters and a builder `b` (`b.part`, `b.net`, `b.port`, `b.path`).
  - **c0252:** `Rail`, `Ground`, `Logic`, port parameters (operating values and logic thresholds), and
    **the stage `circuit.rules`**:
    - the package `checks/circuit/` with `rails.py` and `circuit_issues(model)`;
    - a default stage after `model.validate`, skipped with `no-model` and `no-parameters`, and
      `summary.halves`;
    - nine `circuit.*` codes (`circuit.rail-voltage`, `circuit.rail-current`, `circuit.rail-sources`,
      `circuit.rail-unset`, `circuit.logic-level`, `circuit.logic-unknown`, `circuit.bus-pullup`,
      `circuit.requires-missing`, `circuit.port-split`) in `checks.codes.ISSUE_CODES`;
    - `cmd_build` runs `circuit_issues`, and an error stops the write (c0252, Open question 1). Waivers of
      `circuit.*` codes are c0274's.

    A rail's voltage is the intersection of the values set on it. Its loads' upper draws add up and are
    judged against its sources' capacities. c0252 names c0253 as the change that "adds ratings with
    derating, `expect()` and `rig()` to the stage `circuit.rules`".

## Goals / Non-Goals

**Goals**

- A part whose rating the circuit exceeds, with or without the user's derating, is an `error` of
  `fenolite check`, naming the part, the net, the value, the limit and where each comes from.
- A block author writes an explained expectation once; every user of the block sees it judged on every
  check, including after a manual edit or a new pick.
- The outside world (bench supply, load) is stated in the script and reaches no output.
- One table of requirements, from roles and from circuit checks, with value, limit and source, for the
  terminal (`fenolite roles --check`), for `fenolite check` and for the viewer.
- `requirements.toml` takes values with units.

**Non-Goals**

- See the proposal. In addition:
  - no new stage: c0252 creates `circuit.rules`, and this change extends it;
  - no new role kind or part class, and no change of the role checks;
  - no check of a part without a device record beyond one count (info, or a warning each under
    `design.contracts(unknown="warning")`);
  - no check of a board that Fenolite did not build: it has no device parts;
  - no evaluation of Python code at check time. Expectations are data, not callables.

## Decisions

### 1. Extend c0252's stage `circuit.rules`; device records and classes injected

- **Stage.** This change adds no stage. It extends c0252's `circuit.rules`, which stands after
  `model.validate`, runs no tool and reads the `.fenolite/` model. The stage keeps its name, its place and
  the batch's one skip vocabulary (c0252, decision 6):
  - `no-model`: no readable `.fenolite/` model;
  - `no-parameters`: nothing for c0252's rail half;
  - `no-contracts`: nothing for this change's half: no component with a `fenolite.device` property, no
    expectation and no rig element.

  The stage is skipped with `no-model`, or with `no-parameters` when `no-contracts` holds too. When it
  runs, `summary.halves.contracts` is `ran` or `no-contracts`.
- **Code.**
  - c0252 creates the package `checks/circuit/` with `rails.py`. This change adds `values.py`,
    `ratings.py`, `expect.py`, `corners.py` and `table.py` to it, and no other package.
  - `circuit_issues(model, *, devices=None, classes=None)` keeps c0252's signature, with two keywords added.
  - `checks` imports only `model` and `core`; `DeviceDef` is a `model.library` type, so no edge is added.
- **Device records are injected.** `checks` may not import `catalog`. `cmd_check`, `cmd_build` and
  `cmd_roles` therefore resolve the `fenolite.device` id of each component through the catalog and the
  project's devices (c0248), and pass a mapping `devices: Mapping[str, DeviceDef]`. This is how the fill
  oracle, the plotter and the roles judge reach the stages today, and it is what c0248 asks for.
  - Without the mapping, the rating rows are `unknown`, and `circuit.rating-missing` counts them.
  - When a resolved record's digest differs from the component's `fenolite.device.sha256`, the record is
    still used. `circuit.device-changed` (warning) names both digests, so a stale build is visible.
- **Part classes are injected too** (decision 4): `classes: Mapping[str, PartClassName]`, from component id
  to the class of `fenolite.roles.classify`.
- **Build.** `cmd_build` already runs `circuit_issues` (c0252). The contract findings go the same way,
  under c0252's build rule: an error stops the write. One rule for every `circuit.*` code is clearer than
  two (Open question 1). c0274 adds the waivers that accept one finding.
- **Alternatives considered.**
  - *A separate stage `contracts.rules`.* Rejected: c0252 and the research call for one `circuit.*`
    stage, and splitting it would split the requirement table.
  - *Snapshot the ratings into the `.fenolite/` model at build.* Rejected for this change: c0248 keeps
    library definitions out of `.fenolite/` ("Library definitions"). The digest check above catches a
    record that changed since the build.
  - *Put the judge in `fenolite.roles`* and inject it as `RolesJudge` is injected. Rejected: the judge
    needs no `analysis` and no board.

### 2. Applied values come only from stated sources

Each net may have a **voltage bound** (a range, against the design's ground) and a **current bound** (an
upper bound on the current any copper of the net carries). They come from these sources, in this order:

| order | source | voltage | current | table source |
|---|---|---|---|---|
| 1 | a rig element on the net (decision 7) | the supply's range | the supply's `current`, or a sink's `current` | `user` (basis `rig <name>`) |
| 2 | a c0252 rail on the net | the rail's voltage (the intersection c0252 computes) | the upper sum of the rail's loads (c0252) | `user` (basis `rail <name>`) |
| 3 | a declared or confirmed `NetRole` | `working_mv` as the range `[-v, +v]` | `milliamps` | `role` |
| 4 | a `[[current]]` row of the requirements file (`fenolite roles --check --requirements`) | — | its `current` | `user` (basis its `source` text or `requirements.toml`) |
| 5 | `--current NET=AMPS` of `fenolite roles --check` | — | the option's value | `user` (basis `--current`) |
| 6 | a `ground` role, or a c0252 `Ground` | `[0, 0]` | — | `role` / `user` |
| — | anything else | unknown | unknown | — |

- **Current: the order of roles.** Orders 3 to 5 are c0222's order for a role's current ("Currents are
  never inferred": the role, then `[[current]]`, then `--current`). The circuit rows use the same order, so
  `fenolite roles --check` never shows a role row and a circuit row with two currents for one net.
  `fenolite check` takes neither a requirements file nor `--current`, like `roles.rules` (Open question 5),
  so only orders 1 to 3 and 6 reach its stage.
- **Inferred roles that are not confirmed give nothing.** They carry no voltage or current anyway
  (c0222, "Currents are never inferred").
- **Disagreement.** When two sources of different kinds bound one net and their ranges do not overlap,
  the first in the order is used, and `circuit.value-conflict` (warning) names both. Two rail values that
  do not intersect remain c0252's `circuit.rail-voltage`.
- **Why `[-v, +v]` for a role.** `working_mv` is unsigned: "the working voltage against the design's
  ground". A symmetric range is the sound reading, since it never underestimates a difference. A c0252
  rail has a signed range and is preferred when both exist.
- **Propagation is not here.** A net behind a ferrite or a 0 Ω link has no bound unless one is stated;
  c0274 propagates voltages through the parts whose class allows it and records each value's origin.
- **Alternative considered:** infer a net's voltage from the regulator's output pin or a divider.
  Rejected: c0222 decided that Fenolite infers no electrical value, and a wrong voltage makes a wrong
  rating verdict look right.

### 3. Ratings and operating checks

A part is judged when its component names a device (`fenolite.device`) and the command gave that
device's record. Each limit of the record is either **`abs_max`** or **`operating`** (c0274 phase A):

| limit | meaning | judged as | derated | code |
|---|---|---|---|---|
| `abs_max` | an absolute maximum rating: beyond it the part may be damaged | worst case of the applied value within the limit | yes, by the policy (decision 5) | `circuit.rating-*` |
| `operating` | the range the part needs to work as specified (VIN 2.7 V to 6 V) | the applied range within the limit, exactly | never | `circuit.operating-range` |

A derating tightens an absolute rating toward zero; applied to an operating minimum it would *loosen* it,
which is why the two are separate keys and never share a check.

| rating | parts | applied value | code |
|---|---|---|---|
| device `voltage` | two-pin parts (a diode's reverse voltage included; no polarity check) | `|V(a) − V(b)|` worst case: `max(a.max − b.min, b.max − a.min)` | `circuit.rating-voltage` |
| pin `voltage` | any device | `V(net of the pin) − V(net of the device's ground function)`, worst case at both `min` and `max`; with no ground function, against the design's ground | `circuit.rating-voltage` |
| `[[limits]]` `voltage` between two functions | any device | `V(net of the first) − V(net of the second)`, worst case at both `min` and `max` | `circuit.rating-voltage` |
| device `current` | by class, the table below | by class | `circuit.rating-current` |
| pin `current` | any device | the net's current bound, only when that pin is the part's only pin on the net | `circuit.rating-current` |
| device `power` | parts of class `resistor` or `shunt` | `V_across.max² / R.min` when both nets have a voltage, else `I.max² × R.max` for a `shunt` with a current bound, else unknown | `circuit.rating-power` |
| device `temperature` | any device | the design's ambient range (`design.operating`) within the rated range, less the policy's margin | `circuit.rating-temperature` |

The same rows exist for every `operating` limit (pin, pin pair, device `current`, device `temperature`),
compared without derating and without margin, as `circuit.operating-range`. An `operating` voltage of a pin
that is a member of a c0252 device port stating `voltage` is not judged again here: c0252's
`circuit.rail-voltage` is the one row for it.

- **Pin pairs.** A pin's voltage is measured from the device's `ground` function (c0248), which covers a
  MOSFET's drain-to-source rating when `ground = "S"`. Every other pair is a `[[limits]]` row of the
  record: `between = ["BST", "SW"]` with `voltage = { abs_max = "6V" }` is judged as `V(BST) − V(SW)`, and a
  high-side switch's gate-to-source as `between = ["G", "S"]`. A pair whose second net has no bound (a
  switching node) is `unknown`, never judged against the design's ground.
- **Device current, per class.** c0248's device `current` has no meaning until its path is said:

  | class or port | judged against | why |
  |---|---|---|
  | a part that owns an `out` power port (c0252 device port: a regulator, an LDO) | the upper load sum of that port's rail, with c0252's hiding | the output current is what the loads draw |
  | `inductor`, `shunt` | the smaller of the two nets' current bounds; unknown unless both are known | the series current flows through both nets |
  | any other class | not judged, and no row | no current path is defined for it |

- **Why the current of a series part is the smaller bound.** Each net's bound is an upper bound on the
  current any of its copper carries. A two-pin series part's current flows through the copper of both
  nets, so the smaller bound is still an upper bound, and the tighter one. With only one bound the
  result would be loose enough to flag every pull-up on a 1 A rail, so the row is `unknown` instead.
- **Power uses c0274's products.** `V_across.max²` is a V·V product and `V²/R` gives watts, both exact.
- **R, ranges and tolerance.** `R` is the component's `value_range` (c0246). A part with only a text value
  is unknown.
- **Status of a row:**
  - `pass` when the worst case is within the limit;
  - `fail` when it exceeds the limit;
  - `unknown` when an input is missing.

  A rating or operating check has no `unsure`: the worst case decides. Unknown rows give no issue each by
  default. One `circuit.value-unknown` (info) gives their count, and the rows stay in the table with the
  missing input named, so the user sees what to state. The strictness setting (decision 10) makes each
  one a warning.
- **Missing ratings.** A device part whose record has no limit for a check that applies (for example a
  capacitor with no `voltage` rating on a known 12 V net) is one row with status `unknown` and the basis
  `no rating`. A part without a device is not a row. One `circuit.rating-missing` (info) counts both.

### 4. Part classes: one classifier, the roles' `PartClass`

The derating keys, the series rule and the power rule need a part's class. There is **one** classifier:
c0222's `fenolite.roles.classify`, with its vocabulary (`PartClassName`), its evidence order (the user's
`PartClass`, pin names, pin types, the value or pad count, the reference prefix) and its prefix table.

- `checks` cannot import `roles`. `cmd_check`, `cmd_build` and `cmd_roles` therefore run
  `roles.classify` on the model's circuit, with the user's `PartClass` entries of `RuleSet.roles`, and
  pass `classes` (component id to class) to `circuit_issues`, as they pass the devices.
- Without the mapping (a test, `fenolite.api` without a command), a part takes the user's `PartClass`
  from the model, and a part without one has no class: its class-specific rows are `unknown` with the
  basis `no class`. No prefix table exists under `checks/`, and a test asserts it.
- Today's prefix table maps `C`, `R`, `L`, `D`, `Q`, `J` and `U`; `FB` matches nothing. This change does
  not touch it. c0274 adds `FB` (and the classes that voltage propagation needs) to that one table, with
  its test, so the change lands in one place.
- A ferrite bead is therefore not an `inductor` here: until c0274, an `FB` part is classified by its
  value or stays without a class, and its current is not judged.
- **Alternative considered:** a second prefix table in `checks/circuit/values.py`, kept equal to the roles'
  by a test. Rejected: the first draft did that, and the two tables already disagreed on `FB` and `J`.

### 5. Derating policy: user-supplied, never shipped

```python
from fenolite.dsl import ratio, select, between, celsius, kelvin

design.derating(capacitor_voltage=ratio(50), resistor_power=ratio(50), inductor_current=ratio(80))
design.derating(capacitor_voltage=ratio(80), parts=select.ref("C1*"), source="project rule 4.2")
design.operating(ambient=between(celsius(-20), celsius(70)))
design.derating(temperature_margin=kelvin(15))
```

`celsius()` and `kelvin()` are c0274's (phase A): a temperature is a kelvin quantity inside, and
`celsius(-20)` is 253.15 K exactly. `kelvin(15)` here is a temperature difference.

- **Keys.** The keys form a closed table, `fenolite.model.rules.DERATING_KEYS`:

  | key | rating | class |
  |---|---|---|
  | `voltage`, `current`, `power` | the device `abs_max` rating of that name | any |
  | `pin_voltage`, `pin_current` | a pin's `abs_max` `voltage` or `current`, and a `[[limits]]` `abs_max` voltage | any |
  | `capacitor_voltage` | `voltage` | `capacitor` |
  | `resistor_power`, `resistor_voltage` | `power`, `voltage` | `resistor` |
  | `shunt_power` | `power` | `shunt` |
  | `inductor_current` | `current` | `inductor` |
  | `diode_voltage`, `diode_current` | `voltage`, pin `current` | `diode` |
  | `transistor_voltage`, `transistor_current` | pin `voltage`, pin `current` | `transistor` |
  | `temperature_margin` | `temperature` | any (a temperature difference, not a ratio) |

  Every key applies to `abs_max` limits only. An `operating` limit is never derated (decision 3).

- **Values.**
  - A derating is `ratio(p)`: "at most `p` % of the rating", a `Derating` value of `dsl/contracts.py`,
    stored as an integer per-mille (`ratio(50)` is 500). It must be above 0 and at most 100 %, because a
    derating never raises a rating. A value that is not whole per-mille raises `DslError`.
  - c0246's `pct()` keeps its one meaning, a ± tolerance. Passing a `Tolerance` to `derating` raises
    `DslError` with the hint `ratio(50)`, so `pct(50)` can never be read as "half the rating".
  - The derated limit of a `max` is `max × permille / 1000`, exactly. A rating's `min` (for example a pin
    that must stay above −0.3 V) is scaled the same way toward zero.
  - `temperature_margin` is a kelvin difference stored in integer millikelvin. It lowers the rated
    maximum and raises the rated minimum of an `abs_max` temperature only.
- **Scope and precedence.** The most specific rule wins:
  1. a rule with `parts=` (a `select.ref` glob or a part);
  2. a class key;
  3. a generic key;
  4. none.

  Two rules of the same specificity that both match a part give `DslError` at build time, naming both.
- **No policy.** With no rule for a rating, the limit is the rating itself (100 %), with source `device`.
  One `circuit.policy-missing` (info) per stage run names the ratings that were judged without derating.
- **Source.**
  - A policy limit has the table source `policy` and a basis such as `capacitor_voltage 500‰ of 16 V
    (device Fenolite:C_0805)`, adding the user's `source=` text when given.
  - Fenolite ships no rule, no preset and no default number. This applies, for derating, the rule of
    board-analyses ("No shipped requirement values") and the maintainer's rule for this batch: "default
    derating numbers must cite public sources or be explicitly user-supplied". No public source has been
    checked and registered for derating values, so none ships.
- **Alternatives considered.**
  - *Reuse `RoleLimit`* with new keys. Rejected: a role limit is scoped by net or role kind, while a
    derating rule is scoped by part, part class and rating. Sharing the type would make `kind` mean two
    things. The *pattern* is shared instead: a closed key table with units, most specific wins, the origin
    named in each finding, and the same severity rule (decision 10).
  - *Ship a preset from a public handbook.* Deferred to Open question 2.
  - *`pct(50)` as the derating* (the first draft). Rejected: `pct()` is c0246's ± tolerance, and one name
    with two meanings in one script invites `pct(50)` as "± 50 %".

### 6. Expectations: recorded comparisons, judged by the stage

**Today** (0.6.0) a block author can only write a Python `assert`. It stops the build at the first failure,
explains nothing, sees only script-time values, and is never judged again:

```python
assert Fraction(45300, 10000) > 4  # a bool at script time; lost after a KiCad edit
```

**Proposed:**

```python
from fenolite.dsl import within, at_least, value_of, rating_of, voltage_of, current_of, volt


@block
def buck(b, *, vout=volt("3.3").pct(3), current=amp(2)):
    ...
    top = b.part("R_top", device="Fenolite:R_0603", value=ohm("45k3").pct(1))
    bot = b.part("R_bot", device="Fenolite:R_0603", value=ohm("10k").pct(1))
    vref = volt("0.6").pct(1)
    b.expect(within(vref * (1 + value_of(top) / value_of(bot)), vout), "VOUT set by the divider")
    b.expect(at_least(rating_of(l, "current"), current * 13 / 10), "inductor saturation margin")


design.expect(
    within(voltage_of(v33), rating_of(sen, "voltage", pin="VDD", limit="operating")), "sensor VDD range"
)
```

- **Handles.** Functions return handles, not values, so that nothing collides with `Part.value` (text,
  c0246) or `part.device` (`DeviceDef`, c0248):
  - `value_of(part)`: the component's `value_range`;
  - `rating_of(part, key, pin=None, limit="abs_max")`: a device or pin limit, `abs_max` or `operating`;
  - `voltage_of(x)` and `current_of(x)`: the bounds of decision 2, for a net, a rail or a c0252 power
    port.

  A handle is resolved by the stage on the model, so a value changed after the build (c0250) or a new
  pick (c0254) is what is judged.
- **Expressions.** Arithmetic on handles and c0246 ranges or quantities (`+ - * /`, and integers or
  `Fraction`s as factors) builds an expression, with c0246's unit table and c0274's products (V·V, A·A,
  V²/Ω and A²·Ω), so a power such as `voltage_of(a) * voltage_of(a) / value_of(r)` can be written. A float
  factor raises `DslError`, as everywhere in the DSL.
- **Comparisons.** These are `within(a, b)`, `at_least(a, b)` and `at_most(a, b)`. Each builds an
  `Expectation` test.
  - Handles and expressions define no ordering operators. c0246 ranges define none either, so `>=`
    between ranges stays an error.
  - The `__bool__` of a handle, an expression or a test raises `DslError` ("use design.expect(...)"), so
    `if rating_of(l, "current"):` cannot silently take a branch.
- **Literal-only comparisons.** c0246's `Range.within()` returns a `bool`. `expect(True, ...)` and
  `expect(False, ...)` raise `DslError` with the hint to use `within(a, b)`, which records both operands.
- **Three-valued judgement** on worst-case ranges:

  | comparison | pass | fail | otherwise |
  |---|---|---|---|
  | `within(a, b)` | `b.min ≤ a.min` and `a.max ≤ b.max` | `a.max < b.min` or `a.min > b.max` | unsure |
  | `at_least(a, b)` | `a.min ≥ b.max` | `a.max < b.min` | unsure |
  | `at_most(a, b)` | `a.max ≤ b.min` | `a.min > b.max` | unsure |

  A `fail` is `circuit.expect-failed` (error), and an `unsure` is `circuit.expect-unsure` (warning). An
  expectation whose handle cannot be resolved or bounded is `circuit.expect-unknown` (warning): for
  example, a value turned into text, or a rail without a voltage.
- **Worked example.** The divider above, with `vref` 0.6 V ± 1 % and both resistors ± 1 %, gives
  3.2315–3.4066 V against 3.201–3.399 V. That overlaps without being inside, so the result is unsure.
  With `vref` ± 0.5 % it gives 3.2478–3.3898 V: pass. After a KiCad edit of `R_top` to 49.9 k ± 1 % kept
  by c0250, it gives 3.4994–3.6910 V: fail.
- **Model.** An expectation is stored as data (decision 8): its id, its instance path, its reason, its
  origin (module and line), and the expression tree. Refs name entity ids, never Python objects.
- **Ids.** The id of an expectation is `<instance path>/expect#<n>`: the path of the block *instance*
  (c0251's path, `buck1` for `design.use(buck, "buck1")`, `power/buck1` when nested), numbered in call order
  within that instance. The top level uses the path `design`. The reason text must be unique within an
  instance. A repeated reason raises `DslError`, so a renumbering is visible in review. Every example and
  scenario of this change writes ids in this one form (`buck1/expect#1`).
- **Alternatives considered.**
  - *Python callables run by the check.* Rejected: code in the model cannot be canonical JSON, and check
    would execute user code.
  - *A constraint solver* (atopile). Rejected by the research ("What we deliberately do not copy").
  - *Attribute handles* (`part.value`, `part.rating.current`). Rejected: `Part.value` is already text, and
    `part.device` is c0248's record.
  - *Two results only* (pass and fail). Rejected: an overlap of ranges is the common case of a nearly
    good design, and calling it a failure would teach users to widen their ranges.

### 7. The test rig: records, not components

```python
from fenolite.dsl import supply, sink

design.rig(
    supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench"),
    sink(v33, gnd, current=amp("0.2"), name="probe"),
)
```

- **Elements.**
  - `supply(pos, neg=None, *, voltage, current=None, name=None)` states the voltage range of `pos`
    against `neg`, and the most current the outside world delivers.
  - `sink(net, ret=None, *, current, name=None)` states a current the outside world draws.
  - `pos`, `neg`, `net` and `ret` are nets or c0252 rails and grounds.
  - When `neg` or `ret` is omitted it is the design's one ground (a c0252 `Ground` or a `ground` role).
    If there is not exactly one, build raises `DslError`.
- **What a rig gives.**
  - Decision 2's voltage and current bounds, with source `user` and basis `rig <name>`.
  - In c0252's rail checks, a supply counts as a source of its rail (its `current` as the capacity) and a
    sink as a load. A rig supply on a rail that a board regulator also drives is therefore c0252's
    `circuit.rail-sources`, which is the right verdict.
- **Corners.** A rig supply's voltage is a range, and the worst case over it stays the verdict of every
  row. In addition, the stage evaluates each row and each expectation whose value reads a rig supply at
  every **corner**: each of the design's `n` supplies at its minimum and at its maximum, the `2^n`
  combinations named like `bench=max,aux=min`. Each corner pins the supplies to exact values and keeps the
  other inputs as ranges.
  - The row's `corners` list one entry per corner with its status and value, and the issue of a failing
    row names the corners that fail (`fails at bench=max: 13.2 V over 8 V`), so the author sees which
    extreme of the bench breaks the part.
  - The corners never loosen the verdict: a row that is `unsure` over the full range stays `unsure` even
    when every corner passes, because an expression that is not monotone can fail between corners.
  - With more than six supplies (64 corners), corners are not evaluated and `summary.corners` says
    `too-many-supplies`; the verdicts are unchanged.
- **Stored as records** in `RuleSet.contracts.rig`, not as components with a flag:
  - No consumer of the circuit reads the rules layer's rig: not the netlist, schematic, board, BOM, PnP,
    exports, ERC, DRC or parity. Exclusion is therefore by construction, not by a filter that every
    consumer must remember.
  - A test builds the sensor example with and without its rig and compares every output file byte for
    byte, except `.fenolite/rules.json`.
- **Limits.** A rig names nets of the design that have at least one pin of a board part; another net is a
  `DslError`. A rig name is a key (`KEY` of `dsl/intents.py`), unique per design.
- **Alternative considered:** components with an `exclude_from_board` flag, as JITX's rig instantiates
  parts (research, section 7). Rejected for the reason above. Fenolite's outputs have many readers, and
  one missed filter would put a bench supply on a BOM.

### 8. Model: `RuleSet.contracts`

`fenolite.model.rules` gains frozen value objects. `RuleSet` gains `contracts: ContractSet | None`, written
under the key `contracts` only when it is not empty, so every existing `rules.json` loads and is written
back to the same bytes. `SCHEMA_VERSION` stays `"0"` (as in c0222) and the schema is regenerated.

```json
"contracts": {
  "derating": [
    {"key": "capacitor_voltage", "permille": 500, "parts": "", "source": ""},
    {"key": "capacitor_voltage", "permille": 800, "parts": "C1*", "source": "project rule 4.2"}
  ],
  "operating": {"ambient": {"high": {"e": -2, "m": 34315}, "low": {"e": -2, "m": 25315}, "unit": "kelvin"}},
  "unknown": "warning",
  "expects": [
    {"id": "buck1/expect#1", "instance": "buck1", "reason": "VOUT set by the divider",
     "origin": "blocks.buck:17",
     "test": {"op": "within",
              "a": {"op": "mul",
                    "a": {"lit": {"high": {"e": -3, "m": 606}, "low": {"e": -3, "m": 594},
                                  "nominal": {"e": -1, "m": 6}, "unit": "volt"}},
                    "b": {"op": "add", "a": {"num": [1, 1]},
                          "b": {"op": "div", "a": {"ref": "value", "component": "<id of buck1/R_top>"},
                                             "b": {"ref": "value", "component": "<id of buck1/R_bot>"}}}},
              "b": {"lit": {"high": {"e": -3, "m": 3399}, "low": {"e": -3, "m": 3201},
                            "nominal": {"e": -1, "m": 33}, "unit": "volt"}}}}
  ],
  "rig": [
    {"kind": "supply", "name": "bench", "pos": "<id of V12>", "neg": "<id of GND>",
     "voltage": {"high": {"e": -1, "m": 132}, "low": {"e": -1, "m": 108}, "nominal": {"e": 0, "m": 12},
                 "unit": "volt"},
     "current": {"high": {"e": 0, "m": 3}, "low": {"e": 0, "m": 3}, "nominal": {"e": 0, "m": 3},
                 "unit": "ampere"}}
  ]
}
```

- **Ranges: c0246's encoding, one form.** A literal range, an ambient range and a rig value are written
  exactly as c0246 writes `Component.value_range`: the unit *name* (`volt`, `ampere`, `ohm`, `watt`, and
  c0274's `kelvin`), and `low`, `nominal` and `high` as `Decimal10` objects (integer mantissa `m`,
  exponent `e`), each omitted when absent. No `min`/`max` string and no unit symbol (`V`) is written.
- **Dimensionless factors.** An `int` or `Fraction` factor of an expression is `{"num": [numerator,
  denominator]}` in lowest terms, since c0246's model units have no ratio.
- **Temperatures.** An ambient range is a kelvin range (c0274): `celsius(-20)` is written as 253.15 K.
  Device temperatures are millikelvin integers after c0274, so the comparison is exact.
- **Closed sets.**
  - `op` is one of `within`, `at_least` and `at_most` at the top, and `add`, `sub`, `mul`, `div` and
    `neg` inside.
  - `ref` is one of `value` (with `component`), `rating` (with `component`, `key`, an optional `pin` and
    `limit`, `abs_max` or `operating`), and `voltage` and `current` (with `net`).
  - A ref names an entity id of `docs/design-model.md`. A c0252 rail or port is stored as its net.
  - `unknown` is `info` (omitted, the default) or `warning` (decision 10).
- **Origin.** `origin` is the module name and line of the call, never a file path, because the
  repository rule forbids absolute user paths.
- **Why the rules layer.** Roles already live there (c0222). A rig and an expectation are requirements
  and context for checks, not circuit. Putting them in `Circuit` would make every circuit reader see
  them.

### 9. The requirement table

`fenolite.core.requirement_table` (standard library only, so `checks`, `roles` and `cli` all import it)
defines the row:

| field | meaning |
|---|---|
| `id` | stable: `<code>:<subject>[:<key>]`, such as `circuit.rating-voltage:C1:voltage`, `circuit.rating-voltage:U1:BST-SW`, `circuit.expect:buck1/expect#1` or `roles.loop-area:buck:loop_ratio_max` |
| `check` | the code the row would report (for an expectation, the code of its status) |
| `entities` | the entity ids (components, nets, pads, groups) for the viewer's selection |
| `subject` | a label: `C1 (buck1/C_in)`, `net SW`, `loop buck` |
| `quantity`, `unit` | `voltage` `volt`, `current` `ampere`, `power` `watt`, `temperature` `kelvin`, `width` `metre`, `area` `square_metre`, … |
| `value` | `{range, text, source, basis}`, or `null` when unknown |
| `limit` | `{range, text, source, basis, evidence, kind}`; `kind` is `abs_max`, `operating` or `requirement` |
| `corners` | for a row that depends on a rig supply: one `{corner, status, text}` per corner (decision 7) |
| `status` | `pass`, `fail`, `unsure` or `unknown` |
| `severity` | the severity of the issue the row gives, or `null` |

- **Ranges in c0246's encoding.** `range` holds `unit`, `low` and `high` exactly as c0246 encodes a
  `ValueRange` (unit name, `Decimal10` mantissa and exponent, rounded outward to 15 digits when the exact
  value does not terminate). `core` cannot import `model`, so `requirement_table.Bound` re-states that
  encoding, and a test keeps the two byte-identical. The unit names are c0246's, c0274's `kelvin`, and,
  for role rows, `metre`, `square_metre` and `ratio`. `text` is c0246's canonical text for people
  (temperatures in degrees Celsius); it is never parsed.
- **Sources.** `source` is one of `device`, `role`, `policy` and `user`. The `basis` says which one:
  - a device id, rating key, limit kind and digest;
  - a role and its net;
  - a policy key and ratio (or a role profile key and its `S-` or `H-G-ROLE-` id);
  - a rail, rig, expectation, requirements row, `--current` or override.
- **Order.** Rows are sorted by `id`. The table is canonical JSON in every reply, and no number in it is
  a JSON float.
- **c0252's checks.** They give rows too: the rail voltage against a port's operating range, the rail's
  load sum against its sources, and each logic comparison (limit source `device` or `user`, as c0252
  names "where each limit came from").
- **Mapping the role rows** (c0222):
  - each role measure judged against a limit becomes a row;
  - a profile default becomes `policy` with its source id;
  - an `override` becomes `user` with basis `role_limits`;
  - a `requirements` limit becomes `user` with basis `requirements.toml`;
  - the role's `milliamps` or `working_mv`, as a value, becomes `role`.

  The role findings' own messages (`key=value (origin)`) do not change.
- **Where it is shown.**
  - `summary.requirements` of `roles.rules` and of `circuit.rules`.
  - `result.requirements` of `fenolite roles --check`, which joins the role rows and, for a built
    project, the circuit rows. `cli/cmd_roles.py` may import `checks.circuit`.
  - The viewer of c0245 reads the rows from the check reply it already draws ("View command draws check
    findings", on its branch). Each row's `entities` let it select the part and the net. This change
    adds no requirement to the viewer.
  - c0274 turns the table into a verification matrix (`fenolite check --matrix`) and adds each row's
    decidable stage, value origin and digest.
- **Alternative considered:** a separate `fenolite contracts` command. Rejected: one table was the
  research's goal ("Constraint Manager"), and `roles --check` is already the requirements view of a
  board.

### 10. Severities and strictness

| case | severity |
|---|---|
| `fail` against a device rating, an operating range, the user's derating policy or an expectation, with a value from a rig, rail, declared or confirmed role, requirements row or `--current` | `error` |
| `unsure` expectation; `circuit.expect-unknown`; `circuit.value-conflict`; `circuit.device-changed` | `warning` |
| `circuit.value-unknown`, `circuit.rating-missing` | `info` (one count each), or `warning` (one per row or part) under `design.contracts(unknown="warning")` |
| `circuit.policy-missing` | `info` |

This is c0222's rule carried over: the user's limit on a stated value is an `error`, and nothing shipped
can make one. A device rating is a fact of the part's record, not a Fenolite default. Its evidence label
is shown in the row, and an `UNVERIFIED` device does not lower the severity (Open question 4).

- **Strictness.** A design that states nothing must not look like a design that passes.
  `design.contracts(unknown="warning")` stores `ContractSet.unknown`; the stage then gives one
  `circuit.value-unknown` warning per unknown row (naming the row and its missing input) and one
  `circuit.rating-missing` warning per part without a needed rating. `unknown` takes `info` or
  `warning`; another value raises `DslError`.
- **The default.** The default stays `info` while most shipped devices carry no ratings, because a warning
  on every part would bury the real findings. It becomes `warning` in a later change, once every shipped
  `Fenolite:` device states the ratings its class needs; that change names the test that proves it.
- **Waivers.** Nothing in this change waives a finding. c0274 extends the waivers to `circuit.*` codes,
  keyed on the digest of the judged value, so a waiver expires when the value changes.

### 11. Codes

`checks.codes.ISSUE_CODES` gains thirteen codes, beside c0252's nine. `fenolite explain` explains each code,
and an issue outside the table raises `ValueError`. No `FEN-` code is added:

- a bad `requirements.toml` unit is `FEN-3004` (an existing `FormatError`);
- a bad DSL call is `DslError` at build time.

| code | severities | meaning |
|---|---|---|
| `circuit.rating-voltage` | error | a voltage across a part, at a pin (from its ground function) or between two pins (`[[limits]]`) exceeds its `abs_max` rating or derated limit |
| `circuit.rating-current` | error | the current of a part (by class) or a single pin exceeds its `abs_max` rating or derated limit |
| `circuit.rating-power` | error | a resistor's or shunt's worst-case power exceeds its rating or derated limit |
| `circuit.rating-temperature` | error | the design's ambient range is not within a part's `abs_max` temperature range less the margin |
| `circuit.operating-range` | error | an applied voltage, current or ambient range is not within an `operating` range, compared exactly |
| `circuit.expect-failed` | error | an expectation that never holds over the ranges |
| `circuit.expect-unsure` | warning | an expectation that holds for part of the ranges |
| `circuit.expect-unknown` | warning | an expectation with a handle that cannot be resolved or bounded |
| `circuit.value-conflict` | warning | stated sources of different kinds bound one net with ranges that do not overlap |
| `circuit.device-changed` | warning | the device record resolved now differs from the digest recorded at build |
| `circuit.value-unknown` | info, warning | rows not judged for a missing voltage or current: a count, or one per row under strictness |
| `circuit.rating-missing` | info, warning | parts with no device, no record given, or no rating for a check that applies: a count, or one per part under strictness |
| `circuit.policy-missing` | info | ratings judged at 100 % because no derating rule covers them |

c0274 adds the severity `info` that a waived finding takes to every `circuit.*` code.

### 12. Units in `requirements.toml`

```toml
# requirements.toml: authored for Fenolite; illustrative values, not requirements
schema = "fenolite.requirements.v0"

[[current]]
select = { net = "V12" }
current = "3A"            # or milliamps = 3000
temp_rise = "10K"         # or temp_rise_mk = 10000
source = "bench supply limit"

[[distance]]
a = { net = "VBUS" }
b = { net = "*" }
clearance = "1.2mm"       # or clearance_nm = 1200000
source = "project insulation decision 2026-10"
```

- **Unit keys.** Every raw key gains a unit form:

  | raw key | unit key |
  |---|---|
  | `clearance_nm` | `clearance` |
  | `creepage_nm` | `creepage` |
  | `embedded_nm` | `embedded` |
  | `insulation_nm` | `insulation` |
  | `groove_nm` | `groove` |
  | `max_distance_nm` | `max_distance` |
  | `min_width_nm` | `min_width` |
  | `max_area_nm2` | `max_area` |
  | `milliamps` | `current` |
  | `temp_rise_mk` | `temp_rise` |
  | `millivolts` | `voltage` |
  | `up_to_mv` | `up_to` |
  | `drop_mv` | `drop` |

- **One parser per kind of unit.** Electrical values (`current`, `voltage`, `up_to`, `drop`) and the
  temperature difference `temp_rise` are parsed by `fenolite.core.quantities`, the one exact parser of
  quantities that c0248 creates and c0274 extends with `kelvin`; the DSL and the device records use the
  same module. Lengths and areas are geometry: `fenolite.core.units.parse_length` exists, and this change
  adds `parse_area` beside it. No other unit parser is written.
- **Errors.** Each of these is a `FormatError` naming the file and key: a value that is not a whole number
  of the raw unit (for example `"0.0001nm"`), a string with no or the wrong unit, a float, or both forms
  of one key in a row.
- **`source`.** An optional text on every row. It becomes the `basis` of a `user` limit in the table.
  The default basis is `requirements.toml`.
- **Schema.** The schema name stays `fenolite.requirements.v0`. A file that uses unit keys is refused by
  a loader that predates them, as c0115 did when it added keys under the same name.
- **No values ship.** "No shipped requirement values" is unchanged.

### 13. DSL surface

| name | kind | stored as |
|---|---|---|
| `Design.derating(*, parts=None, source="", **keys)` | method | `DeratingRule` |
| `Design.operating(*, ambient)` | method | `OperatingRange` |
| `Design.contracts(*, unknown="info")` | method | `ContractSet.unknown` |
| `Design.expect(test, reason)` and the builder's `b.expect(test, reason)` (c0251) | methods | `Expectation` |
| `Design.rig(*elements)` | method | `RigSupply`, `RigSink` |
| `within`, `at_least`, `at_most` | functions | test nodes |
| `value_of`, `rating_of`, `voltage_of`, `current_of` | functions | handles (refs) |
| `supply`, `sink` | functions | rig elements |
| `ratio` | function | a `Derating` (whole per-mille) |

- The module is `src/fenolite/dsl/contracts.py`. `pct`, `between` and `Range` are c0246's; `celsius` and
  `kelvin` are c0274's.
- `rating_of(part, key)` with a key that the part's device lacks, `pin=` naming no function, or a `limit`
  that the record does not state for that key, raises `DslError` listing what the device has.
- `sink` was chosen over `load` to keep apart from c0256's `fenolite.testing.load`.

## Reference example

`examples/circuit/sensor/` is the research's "same board" (12 V input, buck block, MCU, I2C sensor), authored
for Fenolite with the illustrative devices of c0248 and the buck block of c0251, in two variants:

| variant | stated | expected findings |
|---|---|---|
| `good.py` | rig `bench` 12 V ± 10 %, 3 A; `capacitor_voltage=ratio(50)`; input capacitor rated `abs_max` 50 V; regulator `VIN` operating 4.5 V to 18 V; inductor rated 3 A between `SW` (declared 1.5 A) and `3V3` (loads 1.2 A); divider expectation with `vref` ± 0.5 % | none above `info` |
| `bad.py` | the same rig, rail and regulator; input capacitor rated `abs_max` 16 V (limit 8 V by the policy, 13.2 V applied, failing at both corners); inductor rated 1 A; divider with `vref` ± 1 %; a 1 kΩ ± 1 % bleeder rated 0.1 W across V12 | `circuit.rating-voltage` (C_in, policy), `circuit.rating-current` (L: 1.2 A over 1 A), `circuit.expect-unsure` (divider), `circuit.rating-power` (bleeder: 0.176 W) |

`requirements.toml` of the example uses unit keys only, with its authored mark.

## Hypotheses and evidence

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-G-CIRCUIT-EXAMPLE` | The ratings checks and the expectation judgement give exactly the designed findings of the sensor example and nothing above `info` on its good variant | `tests/unit/checks/circuit/test_example.py` | the bad variant's four findings with their values; none on the good one |

| behaviour | level | proof |
|---|---|---|
| range arithmetic and three-valued judgement | `INFERRED` (exact arithmetic; the bounds are only as true as the stated values) | `tests/unit/checks/circuit/test_expect.py` |
| rating rows | the lowest of `INFERRED` and the device record's label (c0248), as c0252 does for its rows | `tests/unit/checks/circuit/test_ratings.py` |
| rig exclusion | byte-identical outputs | `tests/unit/dsl/test_contracts.py -k rig_outputs` |
| units in requirements | `INFERRED`; the parser is exact | `tests/unit/analysis/test_requirements.py -k units` |

## Relation to the other changes of the batch

| change | what this change reads or gives |
|---|---|
| c0246 quantity ranges | `Range`, `between`, worst-case arithmetic, `Component.value_range` and its encoding (unit name, `Decimal10`), used for every range of `rules.json` and of the table; `pct()` stays a tolerance, and the derating is this change's `ratio()` |
| c0247 connection helpers | none; `decouple()` capacitors are judged like any other |
| c0248 device catalog | `DeviceDef` ratings and `DevicePin` limits (with the `ground` function), resolved by the command and injected; `fenolite.device` and its digest on the component; the parser `core/quantities` |
| c0274 electrical requirements | phase A (before c0252): `abs_max`/`operating`, `[[limits]]`, kelvin, the products, a device `class` key read by `roles.classify`; later phases: `circuit.*` waivers with a value digest, voltage propagation with origins, decidable stages, `fenolite check --matrix`, `FB` in the roles' classifier |
| c0249 design lock | none: rig, policy and expectations are not locked; a pick change is judged again |
| c0250 manual-edit merge | a kept CAD edit of a value is the model's `value_range`, so expectations and power rows are judged again on it |
| c0251 circuit blocks | `b.expect` on the builder; expectation ids take the instance path (`buck1/expect#1`) |
| c0252 parametric interfaces | **owns the stage** `circuit.rules`, the package `checks/circuit/`, `circuit_issues`, rails, the skip vocabulary and the build hook; this change adds ratings, operating ranges, policy, expectations, rig and the table to them; rig elements are rail sources and loads; device ports' operating `voltage` is c0252's row, not this change's |
| c0254 parametric part selection | a generator may call `b.expect(...)` to record its achieved range |
| c0255 relative placement | none |
| c0256 design testing | `d.findings("circuit.*")` reads this stage's issues |
| c0222 net roles | role voltages and currents as values, in the order role, `[[current]]`, `--current`; the one classifier `roles.classify` (`PartClass`), injected by the commands; role rows in the table; the severity rule |
| c0245 viewer | reads `summary.requirements` from the check reply |

## Risks / Trade-offs

- **Too many unknown rows** on a design that states little. By default they are info only and counted
  once, which can read as a pass; `design.contracts(unknown="warning")` turns each into a warning, and the
  default flips once the shipped devices carry ratings. Each row names the missing input, so the table
  doubles as a to-do list.
- **Worst-case bounds are pessimistic.** Combining every tolerance at its extreme overstates real spread.
  This is deliberate: an unsure result asks the author to look, and does not fail.
- **The current bound of a series part depends on both nets being stated.** A user may state only the
  rail. The row is then `unknown`, not judged against a loose bound.
- **Ratings recorded with an `UNVERIFIED` device.** The finding is an `error` against a number that may
  be wrong. The evidence label in the row and the reply says so (Open question 4).
- **The build stops on a rating error** under c0252's build rule. While a design is being drafted this can
  be noisy. The user waives the finding (c0274), or states the policy that matches the part (Open
  question 1).
- **Class from the reference prefix** is weak evidence, as c0222 says. A wrong class picks the wrong
  derating key; the basis names the key used, and `design.part_class` corrects it.
- **Overlap with c0252's checks.** c0252 judges the *operating* range a device port accepts
  (`circuit.rail-voltage`); this change judges the `operating` limits of pins that are in no such port
  (`circuit.operating-range`) and every `abs_max` rating (`circuit.rating-*`, derated). One limit is
  judged by one check, and the table shows each with its source and kind.
- **Records written before the split.** c0248's first records hold one `voltage` per pin. c0274 phase A
  lands before this change and refuses that form, so no record reaches this judge with an ambiguous
  limit.
- **A table in two replies.** `fenolite check` and `fenolite roles --check` may disagree when `roles`
  is given `--requirements`. The difference is the stated `[[current]]` rows, named as `user` rows.

## Open Questions

1. **Should contract errors stop `build --confirm`, as c0252 recommends for its circuit errors?**
   **Recommended:** yes, under the same rule for every `circuit.*` code (c0274's waivers accept a finding). If the
   maintainer answers c0252's question 1 with "warnings at build", the contract codes follow.
2. **Should a sourced derating preset ship?** A public-domain handbook, such as a U.S. Government
   parts-derating instruction (`UNVERIFIED`: its licence and figures are not checked), could give
   `design.derating(preset=...)`. **Recommended:** not in this change. A later change may register the
   source (`S-` row, label) and add the preset with every value cited. Until then, every derating number
   is the user's.
3. **Should c0248's device record gain an optional `class` key** with c0222's class names? **Recommended:**
   yes; c0274 phase A adds it, and `roles.classify` reads it right after the user's `PartClass`, so the
   one classifier stays one.
4. **Should an `UNVERIFIED` device's rating fail as an `error`?** **Recommended:** yes. The rating is the
   best fact available, and the row and the evidence show its label. Lowering the severity would hide
   real overloads on most catalog devices, which start `UNVERIFIED`.
5. **Should `fenolite check` take `--requirements`, so the stage sees `[[current]]` rows?**
   **Recommended:** not here. Keep c0222's behaviour (the stages judge with no option) and revisit both
   stages together.
6. **Should a role's `working_mv` read as `[-v, +v]`?** **Recommended:** yes, since it is unsigned. A
   c0252 rail, which is signed, is preferred when both exist.
7. **Should `design.contracts(unknown=...)` also take `error`?** **Recommended:** not now. A CI that wants
   to gate on unknowns can read the counts of the reply; `error` can be added once the default is
   `warning`.
8. **Should the corners loosen an `unsure` expectation when every corner passes and every rig handle
   occurs once in the expression** (where interval arithmetic is exact anyway)? **Recommended:** no; the
   rule "corners never loosen" is simpler to trust, and the corners list already shows the case.
