## ADDED Requirements

### Requirement: Fenolite lowers only the design's rules
`fenolite.backends.kicad.lowering.lower_rules(ruleset, *, target=DEFAULT_TARGET, allow_lossy=False)` SHALL write the rules of `ruleset` and nothing else, and SHALL return `LoweredRules(text, issues)`, where `lowering.LoweredRules` is c0017's `backends.base.WriteResult`.
- Fenolite MUST NOT ship requirement values, rule tables or default rules, in code or in package data, for the files it writes for the user: the output of `lower_rules` and `write_rules`, and build outputs. A rule reaches such a file only when the user's `RuleSet` holds it.
- Diagnostic oracle rules, such as the canary, are exempt only when they are written to temporary copies that a check reads and that never reach the user's files.
- An empty `RuleSet` MUST lower to the text `"(version 1)\n"` with no issues.
- The text MUST start with `(version 1)`, followed by one `rule` list per rule and per layer (see "Rule layers and lowered names").
- A `RuleSet` whose `ext["kicad"]` holds slots (one read from a file) MUST raise `ValueError` naming `write_rules`.
- The KiCad backend's capability report MUST list `lower` in `operations`.

#### Scenario: Empty rule set
- **GIVEN** `RuleSet(id=..., rules=())`
- **WHEN** `lower_rules(ruleset, target=10)` is called
- **THEN** `text == "(version 1)\n"` and `issues == ()`

#### Scenario: One rule gives one rule list
- **GIVEN** a `RuleSet` with one `clearance` rule on `net HV` with `min=2_000_000`
- **WHEN** it is lowered for target 9
- **THEN** the text holds exactly one `rule` list, whose constraint is `(constraint clearance (min 2mm))`

#### Scenario: Lowering listed in capabilities
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the `operations` of the `kicad` entry of `result.backends` contain `lower`

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
The six model kinds SHALL lower one to one, with these constraints and limits:

| kind | written constraint | limits |
|---|---|---|
| `clearance` | `clearance` | `min` |
| `edge_clearance` | `edge_clearance` | `min` |
| `track_width` | `track_width` | `min`, `opt`, `max` |
| `via_diameter` | `via_diameter` | `min`, `opt`, `max` |
| `hole_size` | `hole_size` | `min`, `max` |
| `via_drill` | `hole_size`, with `A.Type == 'Via'` as the first conjunct of the condition | `min`, `max` |

- Values MUST be written as the shortest exact millimetre decimal of the nanometre value, with the unit `mm` (`core.units.format_length`). They MUST never be rounded.
- Limits MUST be written in the order `min`, `opt`, `max`.
- A limit outside the table, or a rule with no limit, MUST give the error `rules.unsupported-limit`.
- `severity` MUST map one to one to `(severity error|warning|ignore)`, and a lowered rule MUST always carry its severity clause.
- Each kind MUST be enforced by `kicad-cli` 9.0.9 and 10.0.6 on the items its condition selects (`H-K-DRU-KIND`).

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

### Requirement: Closed selector grammar
Selectors SHALL lower only through this table, where side `S` is `A` for `selector_a` and `B` for `selector_b`:

| model selector | condition text |
|---|---|
| `all`, at the top level only | no term |
| `net v` | `S.NetName == 'v'` |
| `netclass v` | `S.NetClass == 'v'` |
| `ref v` | `S.memberOfFootprint('v')` |
| `item_kind v`, v in `track`, `via`, `pad`, `zone` | `S.Type == 'Track'`, `'Via'`, `'Pad'` or `'Zone'` |
| `and(x, y, …)` | `(x && y && …)` |
| `or(x, y, …)` | `(x \|\| y \|\| …)` |
| `not(x)` | `!(x)` |

- The two sides MUST combine as `<A> && <B>`, each side a leaf or a parenthesised compound. An `all` side adds no term, and a rule whose sides are both `all` has no condition clause.
- `selector_b` MUST be used only with `clearance`.
- `rulemap.SELECTOR_SUPPORT` MUST have the keys `net`, `netclass`, `ref`, `item_kind`, `and`, `or`, `not`, `glob` (a `*` inside a leaf value), `selector_b` (a `selector_b` other than `all`) and `layer_clause` (a non-empty `Rule.layers`). Each entry MUST hold exactly the majors on which that key's `dru-cond-*` probe passed (`H-K-DRU-COND`, `H-K-DRU-GLOB`); a key without a passing probe MUST have an empty entry. `all` at the top level writes no term and needs no entry.
- A key MUST be written for a target only when that target is in its entry. The unit scenarios of this capability set every entry to `{9, 10}` unless they say otherwise.
- The error `rules.unsupported-selector` MUST be given for: the `layer` op; `all` below the top level; an `item_kind` value outside the table; a value containing `'`, `"`, `?`, `[` or `]`; a `*` for a target outside the `glob` entry; `selector_b` with a kind other than `clearance` or for a target outside its entry; and any op outside its entry. A selector MUST never be approximated.

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
- **GIVEN** one bench per op (`net`, `netclass`, `ref`, `item_kind`, layer clause, `and`, `or`, `not`, `selector_b`, glob), each with a probe pair and a control pair 4 mm apart, a 5 mm rule and the canary
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_conditions.py` runs on 9.0.9 and on 10.0.6
- **THEN** for each op the report holds the probe pair's violation, not the control pair's, and the canary violation, and each outcome is recorded under its `dru-cond-*` probe id

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
- `RulesLossError.droppable` MUST be `True` only when every error is a target refusal of a preserved item (see `kicad-file-backend`, "Custom rules files are read and written"). Only then MUST its hint name `--allow-lossy`.
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
