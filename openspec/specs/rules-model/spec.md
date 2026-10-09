# rules-model Specification

## Purpose
Specify the neutral design-rule model (rule sets, selectors and constraints) and how it is lowered to a backend's rules files, with a closed selector grammar, target gating and a self-check.

## Requirements

### Requirement: Fenolite lowers only the design's rules
`fenolite.backends.kicad.lowering.lower_rules(ruleset, *, target=DEFAULT_TARGET, allow_lossy=False)` SHALL write the rules of `ruleset` and nothing else, and SHALL return `LoweredRules(text, issues)`, where `lowering.LoweredRules` is c0017's `backends.base.WriteResult`.
- Fenolite MUST NOT ship requirement values, rule tables or default rules, in code or in package data, for the files it writes for the user: the output of `lower_rules` and `write_rules`, and build outputs. A rule reaches such a file only when the user's `RuleSet` holds it.
- Diagnostic oracle rules, such as the canary, are exempt only when they are written to temporary copies that a check reads and that never reach the user's files.
- An empty `RuleSet` MUST lower to the text `"(version 1)\n"` with no issues.
- The text MUST start with `(version 1)`, followed by one `rule` list per rule and per layer (see "Rule layers and lowered names").
- A `RuleSet` whose `ext["kicad"]` holds slots (one read from a file) MUST raise `ValueError` naming `write_rules`.
- `lower_rules` is a module function, not a backend operation. The backend's `lower` operation is defined by `backend-protocol` "Write capability fields".

#### Scenario: Empty rule set
- **GIVEN** `RuleSet(id=..., rules=())`
- **WHEN** `lower_rules(ruleset, target=10)` is called
- **THEN** `text == "(version 1)\n"` and `issues == ()`

#### Scenario: One rule gives one rule list
- **GIVEN** a `RuleSet` with one `clearance` rule on `net HV` with `min=2_000_000`
- **WHEN** it is lowered for target 9
- **THEN** the text holds exactly one `rule` list, whose constraint is `(constraint clearance (min 2mm))`

#### Scenario: Written kinds in capabilities
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the `write_kinds` of the `kicad` entry of `result.backends` contain `kicad_mod` and `kicad_dru`

#### Scenario: Rule set read from a file is refused
- **GIVEN** the result of `read_rules` on `tests/data/kicad/rules/comments.kicad_dru`
- **WHEN** `lower_rules` is called on it
- **THEN** a `ValueError` naming `write_rules` is raised

### Requirement: Lowered rules follow priority
`lower_rules` SHALL emit rules with priority 0 first, then in descending priority, so that priority 1 comes last. Ties MUST be broken by `Rule.name`, then by `Rule.id`. The order MUST follow the rule KiCad applies to overlapping rules, which `H-K-DRU-ORDER` settles on 9.0.9 and 10.0.6: when the later rule governs, priority 1 governs.

#### Scenario: Priority 1 is written last
- **GIVEN** rules named `a` (priority 1), `b` (priority 3) and `c` (priority 2)
- **WHEN** they are lowered
- **THEN** the rule lists appear in the order `b`, `c`, `a`

#### Scenario: Ties are broken by name
- **GIVEN** rules named `zeta` and `alpha`, both with priority 2
- **WHEN** they are lowered
- **THEN** the rule from `alpha` is written before the rule from `zeta`

#### Scenario: Later rule governs on both majors
- **GIVEN** a bench with two tracks whose gap is 2 mm, the canary, and two rules matching both tracks: 1 mm, then 3 mm
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_order.py` runs on 9.0.9 and on 10.0.6
- **THEN** the DRC report has the clearance violation between the two tracks and the canary violation, and with the two rules swapped it has the canary violation only

### Requirement: Rule kinds and limits
The thirteen model kinds SHALL lower one to one, with these constraints and limits:

| kind | written constraint | limits |
|---|---|---|
| `clearance` | `clearance` | `min` |
| `edge_clearance` | `edge_clearance` | `min` |
| `track_width` | `track_width` | `min`, `opt`, `max` |
| `via_diameter` | `via_diameter` | `min`, `opt`, `max` |
| `hole_size` | `hole_size` | `min`, `max` |
| `via_drill` | `hole_size`, with `A.Type == 'Via'` as the first conjunct of the condition | `min`, `max` |
| `hole_to_hole` | `hole_to_hole` | `min` |
| `hole_clearance` | `hole_clearance` | `min` |
| `annular_width` | `annular_width` | `min` |
| `courtyard_clearance` | `courtyard_clearance` | `min` |
| `silk_clearance` | `silk_clearance` | `min` |
| `creepage` | `creepage` | `min` |
| `no_tracks` | `disallow track`, one rule per layer ("Track layer rules") | none |

- Values MUST be written as the shortest exact millimetre decimal of the nanometre value, with the unit `mm` (`core.units.format_length`). They MUST never be rounded.
- Limits MUST be written in the order `min`, `opt`, `max`.
- A limit outside the table MUST give the error `rules.unsupported-limit`, and so MUST a rule with no limit of any kind but `no_tracks`, whose normal form holds none.
- `severity` MUST map one to one to `(severity error|warning|ignore)`, and a lowered rule MUST always carry its severity clause.
- Each of the first six kinds MUST be enforced by `kicad-cli` 9.0.9 and 10.0.6 on the items its condition selects (`H-K-DRU-KIND`). Each of the six kinds from `hole_to_hole` to `creepage` MUST be written only for the majors of its `KIND_SUPPORT` entry ("Kind support by major", `H-K-DRU-KIND-2`), and its DRC types MUST be listed in `docs/formats/kicad/rules.md`; `no_tracks` follows the same two rules with its own probe (`H-K-DRU-NOTRACKS`). A `min` of 0 MUST be accepted for those six kinds.
- `model.rules.RuleKind` MUST list the kinds in the order of the first twelve as before this change, with `no_tracks` last.

#### Scenario: Exact millimetres
- **GIVEN** a `track_width` rule with `min=250_000`, `opt=300_000` and `max=1_000_000`
- **WHEN** it is lowered
- **THEN** its constraint is `(constraint track_width (min 0.25mm) (opt 0.3mm) (max 1mm))`

#### Scenario: Via drill becomes a hole size for vias
- **GIVEN** a `via_drill` rule on `net PWR` with `min=300_000`
- **WHEN** it is lowered
- **THEN** its constraint is `(constraint hole_size (min 0.3mm))` and its condition is `"A.Type == 'Via' && A.NetName == 'PWR'"`

#### Scenario: Clearance with a maximum
- **GIVEN** a `clearance` rule with `min=200_000` and `max=500_000`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised and its issues hold one `rules.unsupported-limit` naming the rule

#### Scenario: Each kind is enforced
- **GIVEN** a bench with one probed item and one control item per kind, each 4 mm from other copper, and the canary
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_kinds.py` runs on 9.0.9 and on 10.0.6
- **THEN** for each kind the report holds one violation naming the probed item's uuid, none naming the control item, and the canary violation

#### Scenario: Hole-to-hole rule
- **GIVEN** a `hole_to_hole` rule on `net PWR` with `min=300_000`
- **WHEN** it is lowered for target 10
- **THEN** its constraint is `(constraint hole_to_hole (min 0.3mm))` and its condition is `"A.NetName == 'PWR'"`

#### Scenario: Limit outside a new kind
- **GIVEN** an `annular_width` rule with `min=100_000` and `max=300_000`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised with one `rules.unsupported-limit` naming the rule

#### Scenario: Thirteen kinds, one without a limit
- **WHEN** `uv run pytest tests/unit/dsl/test_minimums.py tests/unit/backends/kicad/test_lowering.py -k "kinds or no_tracks"` counts the kinds of `RuleKind` and lowers a `no_tracks` rule without a limit and a `clearance` rule without a limit
- **THEN** `RuleKind` holds thirteen kinds with `no_tracks` last, the first rule is written, and the second raises `RulesLossError` with one `rules.unsupported-limit`

### Requirement: Closed selector grammar
Selectors SHALL lower only through this table, where side `S` is `A` for `selector_a` and `B` for `selector_b`:

| model selector | condition text |
|---|---|
| `all`, at the top level only | no term |
| `net v` | `S.NetName == 'v'` |
| `netclass v` | `S.NetClass == 'v'` |
| `ref v` | `S.memberOfFootprint('v')`; for `courtyard_clearance`, `S.Reference == 'v'` (`H-K-DRU-COURTYARD`) |
| `item_kind v`, v in `track`, `via`, `pad`, `zone` | `S.Type == 'Track'`, `'Via'`, `'Pad'` or `'Zone'` |
| `area v` | `S.intersectsArea('v')` (`H-K-AREA-COND`) |
| `and(x, y, …)` | `(x && y && …)` |
| `or(x, y, …)` | `(x \|\| y \|\| …)` |
| `not(x)` | `!(x)` |

- The two sides MUST combine as `<A> && <B>`, each side a leaf or a parenthesised compound. An `all` side adds no term, and a rule whose sides are both `all` has no condition clause.
- `selector_b` MUST be used only with `clearance` and `creepage`.
- `rulemap.KIND_SELECTORS` MUST narrow the grammar per kind: `hole_to_hole`, `hole_clearance` and `annular_width` take side A only and no layer clause; `courtyard_clearance` takes `all`, or `ref` leaves without a glob combined with `and`, `or` and `not`, on side A only and with no layer clause; `silk_clearance` takes `all` only; `creepage` takes `net` and `netclass` leaves combined with `and`, `or` and `not`, on both sides, with no layer clause. The first six kinds take the grammar as this requirement states it.
- `area v` names the rule areas of the board whose `Keepout.name` matches `v`, with letter case and with `*` as a glob; it selects the items whose copper overlaps such an area on one of the area's layers (`H-K-AREA-COND`). `area` MUST be a leaf of the grammar of the first six kinds (`clearance`, `edge_clearance`, `track_width`, `via_diameter`, `hole_size` and `via_drill`), on side A and, for `clearance`, on side B, and `rulemap.KIND_SELECTORS` MUST add it to the side-A leaves of `hole_to_hole`, `hole_clearance` and `annular_width`. `courtyard_clearance`, `silk_clearance` and `creepage` MUST NOT take it, and neither does `no_tracks`, whose selector "Track layer rules" limits to nets and classes: an `area` leaf in one of their rules is a selector outside the kind's entry. Whether the board holds such an area is checked by the build (`design-dsl`, "Board items in a build"), not by the lowering.
- `read_rules` MUST lift `S.intersectsArea('v')` to `area v`, on either side. A condition that uses `S.enclosedByArea` or `S.insideArea` MUST keep its rule opaque (`rules.kept-opaque`).
- `rulemap.SELECTOR_SUPPORT` MUST have the keys `net`, `netclass`, `ref`, `item_kind`, `area`, `and`, `or`, `not`, `glob` (a `*` inside a leaf value), `selector_b` (a `selector_b` other than `all`) and `layer_clause` (a non-empty `Rule.layers`). Each entry MUST hold exactly the majors on which that key's `dru-cond-*` probe passed (`H-K-DRU-COND`, `H-K-DRU-GLOB`, and `H-K-AREA-COND` for `area`); a key without a passing probe MUST have an empty entry. `all` at the top level writes no term and needs no entry.
- A key MUST be written for a target only when that target is in its entry. The unit scenarios of this capability set every entry to `{9, 10}` unless they say otherwise.
- The error `rules.unsupported-selector` MUST be given for: the `layer` op; `all` below the top level; an `item_kind` value outside the table; a value containing `'`, `"`, `?`, `[` or `]`; a `*` for a target outside the `glob` entry; `selector_b` with a kind other than `clearance` and `creepage`, or for a target outside its entry; a selector or a layer clause outside the kind's `KIND_SELECTORS` entry; and any op outside its entry. A selector MUST never be approximated.

#### Scenario: Net and class on both sides
- **GIVEN** a `clearance` rule with `selector_a = net HV` and `selector_b = netclass LV`
- **WHEN** it is lowered for target 10
- **THEN** its condition is `"A.NetName == 'HV' && B.NetClass == 'LV'"`

#### Scenario: Compound selector
- **GIVEN** `selector_a = and(net A, not(item_kind via))`
- **WHEN** it is lowered
- **THEN** the condition is `"(A.NetName == 'A' && !(A.Type == 'Via'))"`

#### Scenario: Layer op refused
- **GIVEN** a rule whose `selector_a` is `layer F.Cu`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised, its issues hold one `rules.unsupported-selector`, and its hint does not offer `--allow-lossy`

#### Scenario: Quote inside a net name
- **GIVEN** a rule on `net it's`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised with one `rules.unsupported-selector` naming the value

#### Scenario: Glob refused where it is not proved
- **GIVEN** `rulemap.SELECTOR_SUPPORT["glob"] == frozenset({10})`, the `net` entry `{9, 10}`, and a rule on `net PWR_*`
- **WHEN** it is lowered for target 9
- **THEN** `RulesLossError` is raised with one `rules.unsupported-selector`, and for target 10 the condition is `"A.NetName == 'PWR_*'"`

#### Scenario: Unproved op refused
- **GIVEN** `rulemap.SELECTOR_SUPPORT["ref"] == frozenset()` and a rule on `ref R1`
- **WHEN** it is lowered for target 10
- **THEN** `RulesLossError` is raised with one `rules.unsupported-selector` naming `ref`, and its hint does not offer `--allow-lossy`

#### Scenario: Shipped table holds only proved majors
- **GIVEN** the committed `rulemap.SELECTOR_SUPPORT` and the probe files `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_rulemap.py -k support` runs
- **THEN** each entry holds exactly the majors whose file records `present` for that key's `dru-cond-<key>` probe

#### Scenario: Each op selects its items in KiCad
- **GIVEN** one bench per op (`net`, `netclass`, `ref`, `item_kind`, `area`, layer clause, `and`, `or`, `not`, `selector_b`, glob), each with a probe pair and a control pair 4 mm apart, a 5 mm rule and the canary
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_conditions.py` runs on 9.0.9 and on 10.0.6
- **THEN** for each op the report holds the probe pair's violation, not the control pair's, and the canary violation, and each outcome is recorded under its `dru-cond-*` probe id

#### Scenario: Courtyard by reference
- **GIVEN** a `courtyard_clearance` rule with `selector_a = or(ref U1, ref U2)` and `min=0`
- **WHEN** it is lowered for target 10
- **THEN** its condition is `"(A.Reference == 'U1' || A.Reference == 'U2')"` and its constraint is `(constraint courtyard_clearance (min 0mm))`

#### Scenario: Narrowed silk rule refused
- **GIVEN** a `silk_clearance` rule on `ref U1`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised with one `rules.unsupported-selector` naming `silk_clearance`, and its hint does not offer `--allow-lossy`

#### Scenario: Area on one side
- **GIVEN** a `track_width` rule `neck` with `selector_a = area BGA` and `min = 0.1 mm`
- **WHEN** it is lowered for target 9
- **THEN** its condition is `"A.intersectsArea('BGA')"`

#### Scenario: Areas on both sides
- **GIVEN** a `clearance` rule with `selector_a = area P` and `selector_b = area Q`
- **WHEN** it is lowered for target 10 and the text is read back with `read_rules`
- **THEN** the condition is `"A.intersectsArea('P') && B.intersectsArea('Q')"`, and the lifted rule has the same two selectors

#### Scenario: Enclosed area stays opaque
- **GIVEN** a hand-written rule with the condition `"A.enclosedByArea('HV')"`
- **WHEN** it is read with `read_rules` and an `issues` list
- **THEN** the rule is an opaque slot and `issues` hold one `rules.kept-opaque` naming the condition

#### Scenario: Area refused for a creepage rule
- **GIVEN** a `creepage` rule with `selector_a = area HV`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised with one `rules.unsupported-selector` naming `creepage`, and its hint does not offer `--allow-lossy`

### Requirement: Rule layers and lowered names
`lower_rules` SHALL name each lowered rule `fenolite_<priority>_<slug>` and SHALL write one rule per layer of `Rule.layers`.
- The slug MUST be the rule name in lower case, with each run of characters outside `[a-z0-9]` replaced by `_`, trimmed of `_`, or `rule` when empty. A name already used in the same output MUST get the suffix `_2`, `_3`, … in emission order.
- An empty `Rule.layers` MUST write no layer clause. One layer MUST write `(layer "<name>")`. Several layers MUST write one rule per layer, in tuple order, each name suffixed with `_` and the layer's slug.
- A layer name for which c0009's `layers.is_canonical(name)` is false MUST give the error `rules.unsupported-layer`. The row-type fallback of `layers.layer_kind` MUST NOT make a name acceptable.
- A rule with layers for a target outside the `layer_clause` entry of `SELECTOR_SUPPORT` MUST give the error `rules.unsupported-layer`.
- Names MUST be written as double-quoted strings.

#### Scenario: Generated name
- **GIVEN** a rule named `HV Clearance!` with priority 2
- **WHEN** it is lowered
- **THEN** its name is `"fenolite_2_hv_clearance"`

#### Scenario: Two layers give two rules
- **GIVEN** a `clearance` rule named `hv`, priority 1, with `layers == ("F.Cu", "B.Cu")`
- **WHEN** it is lowered
- **THEN** two rules are written in this order: `"fenolite_1_hv_f_cu"` with `(layer "F.Cu")` and `"fenolite_1_hv_b_cu"` with `(layer "B.Cu")`

#### Scenario: Unknown layer
- **GIVEN** a rule with `layers == ("Copper.Top",)`
- **WHEN** it is lowered
- **THEN** `RulesLossError` is raised with one `rules.unsupported-layer`

### Requirement: Lowering refuses what it cannot represent
When lowering produces an issue of severity `error`, `lower_rules` MUST raise `RulesLossError`, a `LossyWriteError` with `cli_code` `FEN-7001`, carrying every issue, and MUST return no text.
- `RulesLossError.droppable` MUST be `True` only when every error is a target refusal: of a preserved item (see `kicad-file-backend`, "Custom rules files are read and written"), or `rules.kind-unchecked` ("Kind support by major"). Only then MUST its hint name `--allow-lossy`, and with `allow_lossy=True` each refused rule MUST be dropped with `rules.dropped-for-target`.
- `rules.unsupported-selector`, `rules.unsupported-limit` and `rules.unsupported-layer` MUST never be dropped, also with `allow_lossy=True`.
- On success, `LoweredRules.issues` MUST hold every warning and info, in emission order.

#### Scenario: Several errors reported together
- **GIVEN** a rule set with one rule on a `layer` op and one `clearance` rule with a `max`
- **WHEN** it is lowered with `allow_lossy=True`
- **THEN** `RulesLossError` is raised with `droppable is False`, and its issues hold one `rules.unsupported-selector` and one `rules.unsupported-limit`

#### Scenario: Error code in the CLI registry
- **GIVEN** the `RulesLossError` raised for a rule on a `layer` op
- **WHEN** its `cli_code` is looked up in the registry of `fenolite.cli.errors`
- **THEN** the code is `FEN-7001` and its exit code is 7

### Requirement: Lowered text is self-checked
`lower_rules` SHALL return text only after the self-check of `write_rules` has passed: the text parses with `parse_rules`, `check_emittable(document.node, FileKind.RULES, target)` returns no error, and `read_rules` lifts every lowered rule back to the normal form of the rule it came from. Any failure MUST raise `RulesSelfCheckError` (`cli_code` `FEN-1001`) naming the failing step.

#### Scenario: Writer and reader disagree
- **GIVEN** a test that patches the condition writer of `rulemap` to emit `A.NetName = 'X'`
- **WHEN** `lower_rules` runs on a rule on `net X`
- **THEN** `RulesSelfCheckError` is raised naming the lift step, and no text is returned

#### Scenario: Normal form of a via drill rule
- **GIVEN** a `via_drill` rule on `net PWR`
- **WHEN** it is lowered and the text is read back with `read_rules`
- **THEN** the lifted rule is a `hole_size` rule whose `selector_a` is `and(item_kind via, net PWR)`, equal to `rulemap.normal_form` of the original

#### Scenario: Via drill normal forms
- **GIVEN** three `via_drill` rules whose `selector_a` is `all`, `net PWR` and `and(net PWR, not(netclass HV))`
- **WHEN** `rulemap.normal_form` is applied to each, and the first is lowered and read back
- **THEN** the results are `hole_size` rules whose `selector_a` is `item_kind via`, `and(item_kind via, net PWR)` and `and(item_kind via, net PWR, not(netclass HV))`; the first is written with the condition `"A.Type == 'Via'"` and lifts to its normal form

### Requirement: Rule issue codes
`fenolite.backends.kicad.rulemap.RULE_ISSUE_CODES` SHALL be this closed mapping, and every rules issue raised or returned by `rulemap`, `dru` and `lowering` MUST use one of its codes or a code of `kicad-version-gating`:

| code | severity | when |
|---|---|---|
| `rules.unsupported-selector` | error | a selector outside the closed grammar for the target |
| `rules.unsupported-limit` | error | a limit the kind does not take, or no limit |
| `rules.unsupported-layer` | error | a layer name for which `layers.is_canonical` is false, or a layer clause for a target outside the `layer_clause` entry |
| `rules.kind-unchecked` | error | a modelled rule of a kind whose `KIND_SUPPORT` entry lacks the target |
| `rules.dropped-for-target` | warning | `allow_lossy` dropped an item the target cannot load |
| `rules.kept-opaque` | info | `read_rules` kept a rule opaque, naming the reason |

#### Scenario: Closed set
- **GIVEN** the issues produced by a set of `lower_rules`, `read_rules` and `write_rules` cases, and the `rules.` code literals in `src/fenolite/backends/kicad/*.py`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lowering.py -k codes` runs
- **THEN** every produced code is a key of `RULE_ISSUE_CODES` or starts with `kicad.token.` or `kicad.version.`, its severity matches the table, and the set of literals equals the keys of `RULE_ISSUE_CODES`

### Requirement: Rules facts are documented with sources and labels
`docs/formats/kicad/rules.md` SHALL describe, in Fenolite's own words, the rules dialect, the closed grammar tables, the kind and limit table, the priority order, the target gating, the board-setup floors and the issue codes. Every fact row MUST cite a source id and carry an evidence label, and every row below the verified levels MUST name a hypothesis. The page MUST state the per-major outcome of each `H-K-DRU-*` row once the oracle has run.

#### Scenario: Fact table checked
- **GIVEN** `docs/formats/kicad/rules.md` and the source register `docs/evidence/sources.md`
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** every row of the fact table in `rules.md` has an S-id, a valid label, and a hypothesis when its label is below `CORPUS-VERIFIED`

### Requirement: Net classes lower to the project file
`fenolite.backends.kicad.lowering.lower_netclass(cls, *, base, floors, issues=None)` SHALL return a new `net_settings.classes` entry for the model `NetClass` `cls`: a copy of `base`, the `Default` entry of the project being written, with `name` set to `cls.name` and the four modelled values written.
- `clearance`, `track_width`, `via_diameter` and `via_drill` MUST map to the class keys of the same names. Each MUST be written as a `JsonNumber` holding the exact millimetre text of the nanometre value (`format_length(nm, "mm")` without the unit), and MUST keep the base value when the model field is `None`. No float MUST be produced.
- Every other key of `base` (microvia, differential pair, colours, `priority`, line style, and `tuning_profile` when present) MUST be copied unchanged.
- A non-empty `description` MUST add the info `kicad.project.unlowered-field`, because no project key holds it.
- `floors` maps model fields to the nanometre values of `board.design_settings.rules` (`min_clearance`, `min_track_width`, `min_via_diameter`, `min_through_hole_diameter`). A written value below its floor MUST add the warning `kicad.project.below-floor` naming the class, the field, the value and the floor, and the value MUST still be written, because the floor governs and the class value is not enforced (`H-K-PRO-FLOOR`).
- Every issue `lower_netclass` appends MUST use a code of the project table `proerrors.ISSUE_CODES` (re-exported as `pro.ISSUE_CODES`), with the severity the table gives. `lowering` imports that leaf module and never imports `pro`. The requirement "Rule issue codes" governs the rule issues of `lower_rules`, `read_rules` and `write_rules`, not these.
- Fenolite MUST lower net classes only to the project file and only from the user's `Circuit.netclasses`; it ships no class values of its own.

#### Scenario: HV class lowered
- **GIVEN** `NetClass(name="HV", clearance=2_000_000, track_width=500_000)` and a `Default` base whose `via_diameter` is `JsonNumber("0.6")`
- **WHEN** `lower_netclass(cls, base=base, floors={})` is called
- **THEN** the entry has `name == "HV"`, `clearance == JsonNumber("2")`, `track_width == JsonNumber("0.5")`, `via_diameter == JsonNumber("0.6")`, and every other key equal to the base

#### Scenario: Value below the floor
- **GIVEN** `NetClass(name="HV", clearance=500_000)` and `floors == {"clearance": 1_500_000}`
- **WHEN** it is lowered with an `issues` list
- **THEN** the entry has `clearance == JsonNumber("0.5")` and `issues` holds one warning `kicad.project.below-floor` naming `HV`, `clearance`, `0.5` and `min_clearance`

#### Scenario: Description has no project key
- **GIVEN** `NetClass(name="HV", description="mains side")`
- **WHEN** it is lowered with an `issues` list
- **THEN** the entry has no description key and `issues` holds one info `kicad.project.unlowered-field`

### Requirement: Board-wide rules lower to board-setup minimums
`fenolite.backends.kicad.lowering.lower_minimums(ruleset, *, target, current, issues=None)` SHALL return the board-setup minimums that the project file for KiCad `target` must hold, as a mapping from a key of `board.design_settings.rules` to nanometres. `lowering.MINIMUM_KEYS[target]` maps each rule kind, taken in normal form (`rulemap.normal_form`, so a `via_drill` rule counts as `hole_size`), to its key:

| kind in normal form | key for targets 9 and 10 |
|---|---|
| `clearance` | `min_clearance` |
| `track_width` | `min_track_width` |
| `via_diameter` | `min_via_diameter` |
| `hole_size` | `min_through_hole_diameter` |
| `edge_clearance` | `min_copper_edge_clearance` |

- A `target` that is not a key of `MINIMUM_KEYS` MUST raise `ValueError`.
- `lowering.is_board_wide(rule)` MUST be true exactly when the normal form of `rule` has `selector_a` `all`, no `selector_b` and no `layers`. A `via_drill` rule on `all` is not board-wide, because its normal form selects vias only.
- For each kind of `MINIMUM_KEYS[target]`, the governing board-wide rule MUST be the last board-wide rule of that kind in `rulemap.rule_order`, which is the one KiCad applies when several rules match (`H-K-DRU-ORDER`).
- When that governing rule has severity `error` and a `min`, its key MUST be returned with the least `min` among the governing rule and every rule of the same kind that comes after it in `rulemap.rule_order`, whatever their selectors, layers and severities. Rules before the governing rule MUST NOT count, because it governs every item they select. Otherwise, and when no board-wide rule of the kind exists, the key MUST NOT be returned.
- The function MUST return only keys of `MINIMUM_KEYS[target]`, and every returned value MUST be the `min` of a rule of `ruleset`: Fenolite ships no minimum values of its own.
- Only the modelled rules of `ruleset.rules` MUST be read; opaque rule slots are not seen. A `ruleset` of `None`, or one without a rule of the table's kinds, MUST give an empty mapping and no issue.
- `current` holds the minimums in force in the project being written (key to nanometres). It does not change the returned values; "Conflicts with board-setup minimums are reported" compares rules with it.

#### Scenario: Fab rule set
- **GIVEN** five board-wide rules of severity `error` and priority 0: `clearance` with `min=100_000`, `track_width` with `min=127_000`, `via_diameter` with `min=450_000`, `hole_size` with `min=200_000` and `edge_clearance` with `min=300_000`
- **WHEN** `lower_minimums(ruleset, target=10, current={})` is called with an `issues` list
- **THEN** it returns `{"min_clearance": 100_000, "min_track_width": 127_000, "min_via_diameter": 450_000, "min_through_hole_diameter": 200_000, "min_copper_edge_clearance": 300_000}` and `issues` stays empty

#### Scenario: A later rule lowers the minimum
- **GIVEN** a board-wide `hole_size` rule with `min=300_000` and priority 0, and a `via_drill` rule on `all` with `min=200_000` and priority 1
- **WHEN** they are lowered for target 9
- **THEN** the result is `{"min_through_hole_diameter": 200_000}`

#### Scenario: An earlier rule does not count
- **GIVEN** a board-wide `track_width` rule with `min=200_000` and priority 1, and a `track_width` rule on `net SIG` with `min=100_000` and priority 2
- **WHEN** they are lowered for target 10
- **THEN** the result is `{"min_track_width": 200_000}`, because the rule on `SIG` is written before the board-wide rule and never governs

#### Scenario: Via drill alone is not board-wide
- **GIVEN** only a `via_drill` rule on `all` with `min=200_000`
- **WHEN** it is lowered for target 10 with `current={}`
- **THEN** `is_board_wide` is false for it and the result is empty

#### Scenario: Layer or second selector
- **GIVEN** a `clearance` rule on `all` with `layers == ("F.Cu",)`, and a `clearance` rule with `selector_a = all` and `selector_b = netclass HV`
- **WHEN** `is_board_wide` is applied to each
- **THEN** it returns false for both, and true for a `clearance` rule whose `selector_a` and `selector_b` are both `all`

#### Scenario: No rules
- **GIVEN** `ruleset` is `None`
- **WHEN** `lower_minimums(None, target=10, current={"min_track_width": 200_000})` is called with an `issues` list
- **THEN** it returns `{}` and `issues` stays empty

### Requirement: Conflicts with board-setup minimums are reported
`lower_minimums` SHALL append an issue to `issues` for every rule whose value a board-setup minimum that Fenolite does not write keeps KiCad from applying. The codes extend the closed table of "Project issue codes" (see `kicad-file-backend`, "Project files carry the board-setup minimums").
- The info `kicad.project.minimum-kept` MUST be added for each kind whose governing board-wide rule has a severity other than `error` or no `min`, naming the rule and the reason. Its key is not returned, because a board-setup minimum has no severity of its own.
- The warning `kicad.project.rule-below-minimum` MUST be added for each rule of a kind of `MINIMUM_KEYS[target]` whose key is not returned, when `current` holds that key, the rule's `min` is below `current[key]`, and the key's entry in `lowering.FLOOR_OVER_RULES` holds `target`. Rules before a governing board-wide rule MUST be skipped. The message MUST name the rule, its `min`, the key and `current[key]`, and the hint MUST say that a board-wide rule of that kind with severity `error` lets Fenolite lower the minimum.
- The tables MUST follow the probes of "Board-setup minimums are proved by kicad-cli", read from `docs/evidence/kicad/probes/9.0.9.json` for major 9 and `10.0.6.json` for major 10:
  - `FLOOR_OVER_RULES[key]` holds exactly the majors M for which `pro-min-rules-template-<kind>-tM` records `present`;
  - `MINIMUM_KEYS[M]` holds a kind exactly when `pro-min-keys-template-<kind>-tM` records `present` and `pro-min-keys-lowered-<kind>-tM` records `absent`.

  The probes ran on 9.0.9 and 10.0.6 (`H-K-PRO-MIN-RULE` refuted, `H-K-PRO-MIN-RULE-2`): every `FLOOR_OVER_RULES` entry is empty, and `MINIMUM_KEYS` holds the table above for both targets, with the keys that the floor probes of the new kinds add (`H-K-PRO-MIN-RULE-3`). The unit scenarios of this capability set every `FLOOR_OVER_RULES` entry to `{9, 10}` unless they say otherwise, so that the warning they describe can occur.
- Every issue of this requirement MUST be a warning or an info: KiCad accepts these projects, and the user may change a rule later.

#### Scenario: Narrower rule below the template minimum
- **GIVEN** a `track_width` rule on `netclass SIG` with `min=100_000`, no board-wide `track_width` rule, and `current == {"min_track_width": 200_000}`
- **WHEN** it is lowered for target 10 with an `issues` list
- **THEN** no key is returned and `issues` holds one warning `kicad.project.rule-below-minimum` naming the rule, `0.1`, `min_track_width` and `0.2`; with `FLOOR_OVER_RULES["min_track_width"] == frozenset({9})`, `issues` stays empty

#### Scenario: Governing rule of severity warning
- **GIVEN** a board-wide `track_width` rule with `min=100_000` and severity `warning`, and `current == {"min_track_width": 200_000}`
- **WHEN** it is lowered for target 9 with an `issues` list
- **THEN** no key is returned, and `issues` holds the info `kicad.project.minimum-kept` naming the severity `warning` and the warning `kicad.project.rule-below-minimum` naming the same rule

#### Scenario: Shipped tables follow the probes
- **GIVEN** the committed `lowering.FLOOR_OVER_RULES`, `lowering.RULES_OVER_CLASSES` and `lowering.MINIMUM_KEYS`, and the probe files `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lowering_minimums.py -k tables` runs
- **THEN** it passes only if each table holds exactly the majors and kinds that the probe outcomes support

### Requirement: Class clearances against board-wide clearance rules are reported
`fenolite.backends.kicad.lowering.class_conflicts(ruleset, *, target, clearances, model_names, issues=None)` SHALL report the classes whose clearance KiCad does not combine with the governing board-wide `clearance` rule as the design states them. `clearances` maps the name of every class entry of the project being written to its clearance in nanometres, and `model_names` holds the names of the model's classes. `class_conflicts` MUST NOT add an issue when no board-wide `clearance` rule exists. The codes extend the closed table of "Project issue codes".
- When `target` is in `lowering.RULES_OVER_CLASSES`, KiCad applies the governing rule to the items of every class. The warning `kicad.project.class-shadowed` MUST then be added for each class whose clearance is greater than the rule's `min`, naming the class, its clearance and the rule, except for:
  - a `Default` entry that `model_names` does not hold, whose nets the rule is meant to govern;
  - a class for which a `clearance` rule after the governing rule in `rulemap.rule_order`, whose normal form has `selector_a` `netclass <class name>`, no `selector_b` and no `layers`, has a `min` at least equal to the class clearance.
- When `target` is not in `RULES_OVER_CLASSES`, a class clearance above the rule governs the items of that class. The warning `kicad.project.default-over-rule` MUST then be added when `model_names` holds no `Default` and the `Default` clearance is greater than the rule's `min`, naming both values. The hint MUST say that a model class `Default` with the rule's clearance lowers it.
- `RULES_OVER_CLASSES` MUST hold exactly the majors M for which `pro-min-class-tM` records `absent` and `pro-min-class-control-tM` records `present`, in the probe files named by "Conflicts with board-setup minimums are reported". Until the probes have run it holds `{9, 10}`, the claim of `H-K-PRO-MIN-CLASS`, and the unit scenarios use that value unless they say otherwise.
- `class_conflicts` MUST compare clearances only: class track and via values are not checked against rules.

#### Scenario: Class clearance overridden by a board-wide rule
- **GIVEN** a board-wide `clearance` rule with `min=100_000` and priority 0, `clearances == {"Default": 200_000, "HV": 2_000_000}` and `model_names == {"HV"}`
- **WHEN** `class_conflicts(ruleset, target=10, clearances=clearances, model_names=model_names)` is called with an `issues` list
- **THEN** `issues` holds one warning `kicad.project.class-shadowed` naming HV, `2` and the rule; a further `clearance` rule on `netclass HV` with `min=2_000_000` and priority 1 removes it

#### Scenario: Default class above the rule
- **GIVEN** the same inputs and `RULES_OVER_CLASSES == frozenset()`
- **WHEN** `class_conflicts` is called for target 10 with an `issues` list
- **THEN** `issues` holds one warning `kicad.project.default-over-rule` naming `0.2` and `0.1`, and no `kicad.project.class-shadowed`; with `"Default"` in `model_names`, `issues` stays empty

### Requirement: Kind support by major
`fenolite.backends.kicad.rulemap.KIND_SUPPORT` SHALL map every rule kind to the KiCad majors on which `kicad-cli` enforces it as written, and `lower_rules` and `write_rules` SHALL write a modelled rule only for a target in its kind's entry.
- The six kinds of v0.1 MUST hold `{9, 10}` (`H-K-DRU-KIND`). Each new kind MUST hold exactly the majors M whose probe `dru-kind-<kind>` records `present` in `docs/evidence/kicad/probes/9.0.9.json` (M = 9) or `10.0.6.json` (M = 10) (`H-K-DRU-KIND-2`).
- A modelled rule of a kind whose entry lacks the target MUST give `rules.kind-unchecked` (error) naming the rule, the kind and the target. It is a target refusal ("Lowering refuses what it cannot represent"): with `allow_lossy=True` the rule MUST be dropped with `rules.dropped-for-target`, and the other rules are written.
- `rulemap.KIND_SELECTORS` MUST hold, per kind, the sides, ops and layer clause it takes ("Closed selector grammar"); the two tables MUST have the same keys as `RuleKind`.
- A rule read from a file and kept opaque is not a modelled rule: its gating stays that of `kicad-file-backend`.

#### Scenario: Creepage for target 9
- **GIVEN** `KIND_SUPPORT["creepage"] == frozenset({10})` and a `creepage` rule with `selector_a = netclass HV`, `selector_b = netclass LV` and `min=4_000_000`
- **WHEN** it is lowered for target 9, then with `allow_lossy=True`, then for target 10
- **THEN** the first raises `RulesLossError` with `droppable is True` and one `rules.kind-unchecked`; the second returns `"(version 1)\n"` and one `rules.dropped-for-target`; the third writes `(constraint creepage (min 4mm))` with the condition `"A.NetClass == 'HV' && B.NetClass == 'LV'"`

#### Scenario: Tables follow the probes
- **GIVEN** the committed `KIND_SUPPORT` and the probe files of both majors
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_rulemap.py -k kind_support` runs
- **THEN** each new kind's entry holds exactly the majors whose file records `present` for `dru-kind-<kind>`, and `KIND_SUPPORT` and `KIND_SELECTORS` have the keys of `RuleKind`

### Requirement: Track layer rules
A rule of the kind `no_tracks` ("Rule kinds and limits") SHALL mean: tracks and arcs of the items that `selector_a` selects are not allowed on the copper layers of `layers`. This requirement states, for this one kind, what "Closed selector grammar", "Rule layers and lowered names" and "Kind support by major" state for the others (`H-K-DRU-NOTRACKS`). It is the rule kind, and not the `no_tracks` flag of a keep-out (`model.board.Keepout.no_tracks`), which forbids tracks inside an outline whatever their net.
- **Limits.** A `no_tracks` rule takes no limit: a `min`, `opt` or `max` MUST give `rules.unsupported-limit`.
- **Selectors.** `selector_a` MUST be `all`, or `net` and `netclass` leaves combined with `and`, `or` and `not`; `selector_b` MUST be absent. Anything else MUST give `rules.unsupported-selector`. `rulemap.KIND_SELECTORS["no_tracks"]` MUST hold that grammar.
- **Layers.** `layers` MUST hold at least one layer; an empty tuple MUST give `rules.unsupported-layer`. Each layer follows "Rule layers and lowered names".
- **Lowering.** `lower_rules` MUST write one rule per layer, named as "Rule layers and lowered names" states, with `(layer "<name>")`, the condition of `selector_a` (none for `all`), `(constraint disallow track)` and the severity clause.
- **Targets.** `rulemap.KIND_SUPPORT["no_tracks"]` MUST hold the majors whose probe `dru-kind-no_tracks` recorded `present`; a target outside it gives `rules.kind-unchecked` ("Kind support by major").
- The model schema `schemas/fenolite.model.v0/rules.json` MUST be regenerated with the new kind. A document that holds a `no_tracks` rule cannot be read by Fenolite 0.2.x or 0.3.x, whose `RuleKind` lacks the value; a document without one is unchanged, byte for byte.

#### Scenario: A class kept off the inner layers
- **GIVEN** a rule `sig-outer` of kind `no_tracks`, priority 0, `selector_a` `netclass SIG`, `layers == ("In1.Cu", "In2.Cu")`, severity `error`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lowering.py -k no_tracks` lowers it for target 10
- **THEN** two rules are written, `"fenolite_0_sig_outer_in1_cu"` with `(layer "In1.Cu")` and `"fenolite_0_sig_outer_in2_cu"` with `(layer "In2.Cu")`, each with `(condition "A.NetClass == 'SIG'")`, `(constraint disallow track)` and `(severity error)`

#### Scenario: Refusals
- **GIVEN** three `no_tracks` rules: one with `min=100_000`, one with `selector_b` set, one with no layer
- **WHEN** they are lowered
- **THEN** `RulesLossError` is raised with one `rules.unsupported-limit`, one `rules.unsupported-selector` and one `rules.unsupported-layer`

#### Scenario: Support follows the probes
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_rulemap.py -k kind_support` compares `KIND_SUPPORT["no_tracks"]` with the probe files of both majors
- **THEN** it equals the set of majors where `dru-kind-no_tracks` is `present`
