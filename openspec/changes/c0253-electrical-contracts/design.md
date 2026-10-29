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
    `Tolerance`, worst-case `+ - * /`, `Range.within() -> bool`, and `Component.value_range` in the model.
    It defines no ordering between ranges.
  - **c0248:** `DeviceDef` in `fenolite.model.library` (library definitions stay out of `.fenolite/`).
    - Device ratings have the closed keys `voltage`, `current`, `power` and `temperature`, each with a
      `min` and/or a `max`, stored as integers in µV, µA, µW and m°C.
    - `DevicePin(function, pin_pads, voltage, current, must_connect)`: a pin's `voltage` is measured from
      the device's `ground` function.
    - A device part's component carries the properties `fenolite.device` and `fenolite.device.sha256`.
    - c0248 states that c0253 reads the ratings "injected into the check stage by the command (checks
      cannot import catalog)".
    - The device record has no class field.
  - **c0251:** blocks with ports, parameters and a builder `b` (`b.part`, `b.net`, `b.port`, `b.path`).
  - **c0252:** `Rail`, `Ground`, `Logic`, port parameters, and **the stage `circuit.rules`**:
    - `checks/circuit.py` with `circuit_issues(model)`;
    - a default stage after `model.validate`, skipped with `no-model` and `no-parameters`;
    - eight `circuit.*` codes (`circuit.rail-voltage`, `circuit.rail-current`, `circuit.rail-sources`,
      `circuit.rail-unset`, `circuit.logic-level`, `circuit.logic-unknown`, `circuit.bus-pullup`,
      `circuit.port-split`) in `checks.codes.ISSUE_CODES`;
    - `cmd_build` runs `circuit_issues`, and an error stops the write unless a waiver covers it (c0252,
      Open question 1).

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
  - no check of a part without a device record beyond one info count;
  - no check of a board that Fenolite did not build: it has no device parts;
  - no evaluation of Python code at check time. Expectations are data, not callables.

## Decisions

### 1. Extend c0252's stage `circuit.rules`; device records injected

- **Stage.** This change adds no stage. It extends c0252's `circuit.rules`, which stands after
  `model.validate`, runs no tool and reads the `.fenolite/` model. The stage keeps its name, its place and
  c0252's skip `no-model`. c0252's skip `no-parameters` no longer applies when the model holds a
  component with a `fenolite.device` property, an expectation or a rig element.
- **Code.**
  - c0252's `checks/circuit.py` becomes the package `checks/circuit/`, holding c0252's code in `rails.py`
    and this change's `values.py`, `ratings.py`, `expect.py` and `table.py`.
  - `circuit_issues(model, *, devices=None)` keeps c0252's signature, with one keyword added.
  - `checks` imports only `model`; `DeviceDef` is a `model.library` type, so no edge is added.
- **Device records are injected.** `checks` may not import `catalog`. `cmd_check`, `cmd_build` and
  `cmd_roles` therefore resolve the `fenolite.device` id of each component through the catalog and the
  project's devices (c0248), and pass a mapping `devices: Mapping[str, DeviceDef]`. This is how the fill
  oracle, the plotter and the roles judge reach the stages today, and it is what c0248 asks for.
  - Without the mapping, the rating rows are `unknown`, and `circuit.rating-missing` counts them.
  - When a resolved record's digest differs from the component's `fenolite.device.sha256`, the record is
    still used. `circuit.device-changed` (warning) names both digests, so a stale build is visible.
- **Build.** `cmd_build` already runs `circuit_issues` (c0252). The contract findings go the same way,
  under c0252's build rule: an error stops the write unless a waiver covers it. One rule for every
  `circuit.*` code is clearer than two (Open question 1).
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
| 4 | a `ground` role, or a c0252 `Ground` | `[0, 0]` | — | `role` / `user` |
| — | anything else | unknown | unknown | — |

- **Inferred roles that are not confirmed give nothing.** They carry no voltage or current anyway
  (c0222, "Currents are never inferred").
- **Disagreement.** When two sources of different kinds bound one net and their ranges do not overlap,
  the first in the order is used, and `circuit.value-conflict` (warning) names both. Two rail values that
  do not intersect remain c0252's `circuit.rail-voltage`.
- **Why `[-v, +v]` for a role.** `working_mv` is unsigned: "the working voltage against the design's
  ground". A symmetric range is the sound reading, since it never underestimates a difference. A c0252
  rail has a signed range and is preferred when both exist.
- **`[[current]]` rows.** A `[[current]]` row of the requirements file gives a net's current to
  `fenolite roles --check --requirements FILE` exactly as it does for roles: after the role's own
  `milliamps`, so only for a net that no rig, rail or stated role bounds. Its source is `user`, and its
  basis is the row's `source` text or `requirements.toml`. The stage of `fenolite check` takes no
  requirements file, like `roles.rules`. This inconsistency already exists in c0222 and is kept.
- **Alternative considered:** infer a net's voltage from the regulator's output pin or a divider.
  Rejected: c0222 decided that Fenolite infers no electrical value, and a wrong voltage makes a wrong
  rating verdict look right.

### 3. Ratings checks

A part is judged when its component names a device (`fenolite.device`) and the command gave that
device's record. The ratings are c0248's:

| rating | parts | applied value | code |
|---|---|---|---|
| device `voltage` | two-pin parts (a diode's reverse voltage included; no polarity check) | `|V(a) − V(b)|` worst case: `max(a.max − b.min, b.max − a.min)` | `circuit.rating-voltage` |
| pin `voltage` (`DevicePin.voltage`) | any device | `V(net of the pin) − V(net of the device's ground function)`, worst case at both `min` and `max`; with no ground function, against the design's ground | `circuit.rating-voltage` |
| device `current` | parts of class `inductor` or `shunt` (decision 4) | the smaller of the two nets' current bounds; unknown unless both are known | `circuit.rating-current` |
| pin `current` (`DevicePin.current`) | any device | the net's current bound, only when that pin is the part's only pin on the net | `circuit.rating-current` |
| device `power` | parts of class `resistor` or `shunt` | `V_across.max² / R.min` when both nets have a voltage, else `I.max² × R.max` for a `shunt` with a current bound, else unknown | `circuit.rating-power` |
| device `temperature` | any device | the design's ambient range (`design.operating`) within the rated range, less the policy's margin | `circuit.rating-temperature` |

- **Pin-pair ratings come free.** c0248 measures a pin's `voltage` from the device's `ground` function. A
  MOSFET record with `ground = "S"` and `D = { pins = ["2"], voltage = { max = "40V" } }` is therefore a
  drain-to-source rating, judged as `V(D net) − V(S net)`. No new field is needed.
- **Why the current of a series part is the smaller bound.** Each net's bound is an upper bound on the
  current any of its copper carries. A two-pin series part's current flows through the copper of both
  nets, so the smaller bound is still an upper bound, and the tighter one. With only one bound the
  result would be loose enough to flag every pull-up on a 1 A rail, so the row is `unknown` instead.
- **R, ranges and tolerance.** `R` is the component's `value_range` (c0246). A part with only a text value
  is unknown.
- **Status of a row:**
  - `pass` when the worst case is within the limit;
  - `fail` when it exceeds the limit;
  - `unknown` when an input is missing.

  A rating check has no `unsure`: the worst case decides. Unknown rows give no issue each. One
  `circuit.value-unknown` (info) gives their count, and the rows stay in the table with the missing input
  named, so the user sees what to state.
- **Missing ratings.** A device part whose record has no rating for a check that applies (for example a
  capacitor with no `voltage` rating on a known 12 V net) is one row with status `unknown` and the basis
  `no rating`. A part without a device is not a row. One `circuit.rating-missing` (info) counts both.

### 4. Part classes: c0222's vocabulary, reused

The derating keys and the series rule need a part's class. The class names are c0222's, and so is the
order of evidence, strongest first:

1. a `PartClass` the user stated (`design.part_class(part, "inductor")`, already in `RuleSet.roles`);
2. a `class` key of the device record, if c0248 adds one (Open question 3);
3. the device's `ref_prefix` by a closed table:
   - `C` is `capacitor`;
   - `R` is `resistor`, or `shunt` when a stored `KelvinPair` names its pads as the element (the
     classification by value of `roles.classify` needs the role profile, which `checks` cannot read);
   - `L` and `FB` are `inductor`;
   - `D` is `diode`;
   - `Q` is `transistor`;
   - every other prefix is `other`.

A ferrite bead is an `inductor` here. A fuse is `other`, and its current is not judged in this change.
`checks` cannot import `roles.classify`, so the prefix table lives in `checks/circuit/values.py`. A test
keeps it equal to the prefix evidence of `roles.classify`.

### 5. Derating policy: user-supplied, never shipped

```python
from fenolite.dsl import pct, select, between, celsius, kelvin

design.derating(capacitor_voltage=pct(50), resistor_power=pct(50), inductor_current=pct(80))
design.derating(capacitor_voltage=pct(80), parts=select.ref("C1*"), source="project rule 4.2")
design.operating(ambient=between(celsius(-20), celsius(70)))
design.derating(temperature_margin=kelvin(15))
```

- **Keys.** The keys form a closed table, `fenolite.model.rules.DERATING_KEYS`:

  | key | rating | class |
  |---|---|---|
  | `voltage`, `current`, `power` | the device rating of that name | any |
  | `pin_voltage`, `pin_current` | `DevicePin.voltage`, `DevicePin.current` | any |
  | `capacitor_voltage` | `voltage` | `capacitor` |
  | `resistor_power`, `resistor_voltage` | `power`, `voltage` | `resistor` |
  | `shunt_power` | `power` | `shunt` |
  | `inductor_current` | `current` | `inductor` |
  | `diode_voltage`, `diode_current` | `voltage`, pin `current` | `diode` |
  | `transistor_voltage`, `transistor_current` | pin `voltage`, pin `current` | `transistor` |
  | `temperature_margin` | `temperature` | any (a temperature difference, not a ratio) |

- **Values.**
  - A ratio is c0246's `pct()` `Tolerance`, stored as an integer per-mille (`pct(50)` is 500). It must be
    above 0 and at most 1000, because a derating never raises a rating. A value that is not whole
    per-mille raises `DslError`.
  - The derated limit of a `max` is `max × permille / 1000`, exactly. A rating's `min` (for example a pin
    that must stay above −0.3 V) is scaled the same way toward zero.
  - `temperature_margin` is stored in integer millikelvin. It lowers the rated maximum and raises the
    rated minimum.
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

### 6. Expectations: recorded comparisons, judged by the stage

**Today** (0.6.0) a block author can only write a Python `assert`. It stops the build at the first failure,
explains nothing, sees only script-time values, and is never judged again:

```python
assert Fraction(45300, 10000) > 4  # a bool at script time; lost after a KiCad edit
```

**Proposed:**

```python
from fenolite.dsl import within, at_least, value_of, rating_of, voltage_of, current_of, pct, volt


@block
def buck(b, *, vout=volt("3.3").pct(3), current=amp(2)):
    ...
    top = b.part("R_top", device="Fenolite:R_0603", value=ohm("45k3").pct(1))
    bot = b.part("R_bot", device="Fenolite:R_0603", value=ohm("10k").pct(1))
    vref = volt("0.6").pct(1)
    b.expect(within(vref * (1 + value_of(top) / value_of(bot)), vout), "VOUT set by the divider")
    b.expect(at_least(rating_of(l, "current"), current * 13 / 10), "inductor saturation margin")


design.expect(within(voltage_of(v33), rating_of(sen, "voltage", pin="VDD")), "sensor VDD range")
```

- **Handles.** Functions return handles, not values, so that nothing collides with `Part.value` (text,
  c0246) or `part.device` (`DeviceDef`, c0248):
  - `value_of(part)`: the component's `value_range`;
  - `rating_of(part, key, pin=None)`: a device or pin rating;
  - `voltage_of(x)` and `current_of(x)`: the bounds of decision 2, for a net, a rail or a c0252 power
    port.

  A handle is resolved by the stage on the model, so a value changed after the build (c0250) or a new
  pick (c0254) is what is judged.
- **Expressions.** Arithmetic on handles and c0246 ranges or quantities (`+ - * /`, and integers or
  `Fraction`s as factors) builds an expression. A float factor raises `DslError`, as everywhere in the DSL.
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
- **Model.** An expectation is stored as data (decision 8): its id, its block path, its reason, its
  origin (module and line), and the expression tree. Refs name entity ids, never Python objects.
- **Ids.** The id of an expectation is `<block path>/expect#<n>`, numbered in call order within the block.
  The top level uses the path `design`. The reason text must be unique within a block. A repeated reason
  raises `DslError`, so a renumbering is visible in review.
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
  "operating": {"ambient": {"unit": "degC", "min": "-20", "max": "70"}},
  "expects": [
    {"id": "buck1/expect#1", "block": "buck1", "reason": "VOUT set by the divider",
     "origin": "blocks.buck:17",
     "test": {"op": "within",
              "a": {"op": "mul",
                    "a": {"lit": {"unit": "V", "min": "0.594", "max": "0.606"}},
                    "b": {"op": "add", "a": {"lit": {"unit": "", "min": "1", "max": "1"}},
                          "b": {"op": "div", "a": {"ref": "value", "component": "<id of buck1/R_top>"},
                                             "b": {"ref": "value", "component": "<id of buck1/R_bot>"}}}},
              "b": {"lit": {"unit": "V", "min": "3.201", "max": "3.399"}}}}
  ],
  "rig": [
    {"kind": "supply", "name": "bench", "pos": "V12", "neg": "GND",
     "voltage": {"unit": "V", "min": "10.8", "max": "13.2"}, "current": {"unit": "A", "min": "0", "max": "3"}}
  ]
}
```

- **Ranges.** A literal range is written as c0246 writes `Component.value_range` (exact decimal text and a
  unit, `Decimal10` in c0246's design). The sketch follows that, and no float is written.
- **Temperatures.** An ambient range is written in degrees Celsius with exact decimal text, compared with
  c0248's m°C ratings.
- **Closed sets.**
  - `op` is one of `within`, `at_least` and `at_most` at the top, and `add`, `sub`, `mul`, `div` and
    `neg` inside.
  - `ref` is one of `value` (with `component`), `rating` (with `component`, `key` and an optional
    `pin`), and `voltage` and `current` (with `net`).
  - A ref names an entity id of `docs/design-model.md`. A c0252 rail or port is stored as its net.
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
| `id` | stable: `<code>:<subject>[:<key>]`, such as `circuit.rating-voltage:C1:voltage` or `roles.loop-area:buck:loop_ratio_max` |
| `check` | the code the row would report |
| `entities` | the entity ids (components, nets, pads, groups) for the viewer's selection |
| `subject` | a label: `C1 (buck1/C_in)`, `net SW`, `loop buck` |
| `quantity`, `unit` | `voltage` `V`, `current` `A`, `power` `W`, `area` `mm2`, `width` `mm`, `temperature` `degC`, … |
| `value` | `{min, max, source, basis}`, or `null` when unknown |
| `limit` | `{min, max, source, basis, evidence}` |
| `status` | `pass`, `fail`, `unsure` or `unknown` |
| `severity` | the severity of the issue the row gives, or `null` |

- **Sources.** `source` is one of `device`, `role`, `policy` and `user`. The `basis` says which one:
  - a device id, rating key and digest;
  - a role and its net;
  - a policy key and ratio (or a role profile key and its `S-` or `H-G-ROLE-` id);
  - a rail, rig, expectation, requirements row or override.
- **Numbers.** Numbers are exact strings in the row's unit: decimal when the value terminates, else
  `n/d`. Rows are sorted by `id`. The table is canonical JSON in every reply.
- **c0252's checks.** They give rows too: the rail voltage against a port's accepted range, and the rail's
  load sum against its sources (limit source `device` or `user`, as c0252 names "where each limit came
  from").
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
- **Alternative considered:** a separate `fenolite contracts` command. Rejected: one table was the
  research's goal ("Constraint Manager"), and `roles --check` is already the requirements view of a
  board.

### 10. Severities

| case | severity |
|---|---|
| `fail` against a device rating, the user's derating policy or an expectation, with a value from a rig, rail, declared or confirmed role, or requirements row | `error` |
| `unsure` expectation; `circuit.expect-unknown`; `circuit.value-conflict`; `circuit.device-changed` | `warning` |
| `circuit.value-unknown`, `circuit.rating-missing`, `circuit.policy-missing` | `info` |

This is c0222's rule carried over: the user's limit on a stated value is an `error`, and nothing shipped
can make one. A device rating is a fact of the part's record, not a Fenolite default. Its evidence label
is shown in the row, and an `UNVERIFIED` device does not lower the severity (Open question 4). A waiver
(c0114) accepts a finding, as for every other check code.

### 11. Codes

`checks.codes.ISSUE_CODES` gains twelve codes, beside c0252's eight. `fenolite explain` explains each code,
and an issue outside the table raises `ValueError`. No `FEN-` code is added:

- a bad `requirements.toml` unit is `FEN-3004` (an existing `FormatError`);
- a bad DSL call is `DslError` at build time.

| code | severities | meaning |
|---|---|---|
| `circuit.rating-voltage` | warning, error | a voltage across a part or at a pin (from its ground function) exceeds its rating or derated limit |
| `circuit.rating-current` | warning, error | the current bound of a series part or a single pin exceeds its rating or derated limit |
| `circuit.rating-power` | warning, error | a resistor's or shunt's worst-case power exceeds its rating or derated limit |
| `circuit.rating-temperature` | warning, error | the design's ambient range is not within a part's rated range less the margin |
| `circuit.expect-failed` | warning, error | an expectation that never holds over the ranges |
| `circuit.expect-unsure` | warning | an expectation that holds for part of the ranges |
| `circuit.expect-unknown` | warning | an expectation with a handle that cannot be resolved or bounded |
| `circuit.value-conflict` | warning | stated sources of different kinds bound one net with ranges that do not overlap |
| `circuit.device-changed` | warning | the device record resolved now differs from the digest recorded at build |
| `circuit.value-unknown` | info | the count of rows not judged for a missing voltage or current |
| `circuit.rating-missing` | info | the count of parts with no device, no record given, or no rating for a check that applies |
| `circuit.policy-missing` | info | ratings judged at 100 % because no derating rule covers them |

The `warning` severity of the five codes that also allow `error` is the one a waived finding takes.

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

  A unit value is a TOML string, parsed exactly by the unit parsers in `core/units.py`. c0248 moves the
  electrical unit parser there ("Moving the unit parser"); this change adds `parse_temperature_difference`
  and `parse_area` beside `parse_length`, so the DSL, the device records and the file share one grammar.
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
| `Design.expect(test, reason)` and the builder's `b.expect(test, reason)` (c0251) | methods | `Expectation` |
| `Design.rig(*elements)` | method | `RigSupply`, `RigSink` |
| `within`, `at_least`, `at_most` | functions | test nodes |
| `value_of`, `rating_of`, `voltage_of`, `current_of` | functions | handles (refs) |
| `supply`, `sink` | functions | rig elements |
| `celsius`, `kelvin` | quantity constructors (temperature, temperature difference) | exact values |

- The module is `src/fenolite/dsl/contracts.py`. `pct`, `between` and `Range` are c0246's.
- `rating_of(part, key)` with a key that the part's device lacks, or `pin=` naming no function, raises
  `DslError` listing what the device has.
- `sink` was chosen over `load` to keep apart from c0256's `fenolite.testing.load`.

## Reference example

`examples/circuit/sensor/` is the research's "same board" (12 V input, buck block, MCU, I2C sensor), authored
for Fenolite with the illustrative devices of c0248 and the buck block of c0251, in two variants:

| variant | stated | expected findings |
|---|---|---|
| `good.py` | rig `bench` 12 V ± 10 %, 3 A; `capacitor_voltage=pct(50)`; input capacitor rated 50 V; inductor rated 3 A between `SW` (declared 1.5 A) and `3V3` (loads 1.2 A); divider expectation with `vref` ± 0.5 % | none above `info` |
| `bad.py` | the same rig and rail; input capacitor rated 16 V (limit 8 V by the policy, 13.2 V applied); inductor rated 1 A; divider with `vref` ± 1 %; a 1 kΩ ± 1 % bleeder rated 0.1 W across V12 | `circuit.rating-voltage` (C_in, policy), `circuit.rating-current` (L: 1.2 A over 1 A), `circuit.expect-unsure` (divider), `circuit.rating-power` (bleeder: 0.176 W) |

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
| c0246 quantity ranges | `Range`, `between`, `pct()` (`Tolerance`, read as per-mille here), worst-case arithmetic, `Component.value_range` and its model encoding |
| c0247 connection helpers | none; `decouple()` capacitors are judged like any other |
| c0248 device catalog | `DeviceDef` ratings and `DevicePin.voltage`/`current` (with the `ground` function), resolved by the command and injected; `fenolite.device` and its digest on the component; asks for an optional `class` key (Open question 3) |
| c0249 design lock | none: rig, policy and expectations are not locked; a pick change is judged again |
| c0250 manual-edit merge | a kept CAD edit of a value is the model's `value_range`, so expectations and power rows are judged again on it |
| c0251 circuit blocks | `b.expect` on the builder; expectation ids take the block path |
| c0252 parametric interfaces | **owns the stage** `circuit.rules`, `circuit_issues`, rails and the build hook; this change adds ratings, policy, expectations, rig and the table to them; rig elements are rail sources and loads |
| c0254 parametric part selection | a generator may call `b.expect(...)` to record its achieved range |
| c0255 relative placement | none |
| c0256 design testing | `d.findings("circuit.*")` reads this stage's issues |
| c0222 net roles | role voltages and currents as values; `PartClass` and the prefix vocabulary; role rows in the table; the severity rule |
| c0245 viewer | reads `summary.requirements` from the check reply |

## Risks / Trade-offs

- **Too many unknown rows** on a design that states little. They are info only and counted once. Each
  row names the missing input, so the table doubles as a to-do list.
- **Worst-case bounds are pessimistic.** Combining every tolerance at its extreme overstates real spread.
  This is deliberate: an unsure result asks the author to look, and does not fail.
- **The current bound of a series part depends on both nets being stated.** A user may state only the
  rail. The row is then `unknown`, not judged against a loose bound.
- **Ratings recorded with an `UNVERIFIED` device.** The finding is an `error` against a number that may
  be wrong. The evidence label in the row and the reply says so (Open question 4).
- **The build stops on a rating error** under c0252's build rule. While a design is being drafted this can
  be noisy. The user waives the finding, or states the policy that matches the part (Open question 1).
- **Class from the reference prefix** is weak evidence, as c0222 says. A wrong class picks the wrong
  derating key; the basis names the key used, and `design.part_class` corrects it.
- **Overlap with c0252's checks.** c0252 judges the *operating* range a port accepts (`circuit.rail-voltage`).
  This change judges *ratings*: absolute maxima, optionally derated. They are different limits of one
  device, and the table shows both with their sources.
- **A table in two replies.** `fenolite check` and `fenolite roles --check` may disagree when `roles`
  is given `--requirements`. The difference is the stated `[[current]]` rows, named as `user` rows.

## Open Questions

1. **Should contract errors stop `build --confirm`, as c0252 recommends for its circuit errors?**
   **Recommended:** yes, under the same rule for every `circuit.*` code (waivers accept a finding). If the
   maintainer answers c0252's question 1 with "warnings at build", the contract codes follow.
2. **Should a sourced derating preset ship?** A public-domain handbook, such as a U.S. Government
   parts-derating instruction (`UNVERIFIED`: its licence and figures are not checked), could give
   `design.derating(preset=...)`. **Recommended:** not in this change. A later change may register the
   source (`S-` row, label) and add the preset with every value cited. Until then, every derating number
   is the user's.
3. **Should c0248's device record gain an optional `class` key** with c0222's class names? **Recommended:**
   yes, as the second evidence of decision 4. If it does not, the user's `PartClass` and the reference
   prefix remain.
4. **Should an `UNVERIFIED` device's rating fail as an `error`?** **Recommended:** yes. The rating is the
   best fact available, and the row and the evidence show its label. Lowering the severity would hide
   real overloads on most catalog devices, which start `UNVERIFIED`.
5. **Should `fenolite check` take `--requirements`, so the stage sees `[[current]]` rows?**
   **Recommended:** not here. Keep c0222's behaviour (the stages judge with no option) and revisit both
   stages together.
6. **Should a role's `working_mv` read as `[-v, +v]`?** **Recommended:** yes, since it is unsigned. A
   c0252 rail, which is signed, is preferred when both exist.
