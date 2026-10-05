## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Rule kinds and limits
The twelve model kinds SHALL lower one to one, with these constraints and limits:

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

- Values MUST be written as the shortest exact millimetre decimal of the nanometre value, with the unit `mm` (`core.units.format_length`). They MUST never be rounded.
- Limits MUST be written in the order `min`, `opt`, `max`.
- A limit outside the table, or a rule with no limit, MUST give the error `rules.unsupported-limit`.
- `severity` MUST map one to one to `(severity error|warning|ignore)`, and a lowered rule MUST always carry its severity clause.
- Each of the first six kinds MUST be enforced by `kicad-cli` 9.0.9 and 10.0.6 on the items its condition selects (`H-K-DRU-KIND`). Each of the six new kinds MUST be written only for the majors of its `KIND_SUPPORT` entry ("Kind support by major", `H-K-DRU-KIND-2`), and its DRC types MUST be listed in `docs/formats/kicad/rules.md`. A `min` of 0 MUST be accepted for the six new kinds.

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

### Requirement: Closed selector grammar
Selectors SHALL lower only through this table, where side `S` is `A` for `selector_a` and `B` for `selector_b`:

| model selector | condition text |
|---|---|
| `all`, at the top level only | no term |
| `net v` | `S.NetName == 'v'` |
| `netclass v` | `S.NetClass == 'v'` |
| `ref v` | `S.memberOfFootprint('v')`; for `courtyard_clearance`, `S.Reference == 'v'` (`H-K-DRU-COURTYARD`) |
| `item_kind v`, v in `track`, `via`, `pad`, `zone` | `S.Type == 'Track'`, `'Via'`, `'Pad'` or `'Zone'` |
| `and(x, y, …)` | `(x && y && …)` |
| `or(x, y, …)` | `(x \|\| y \|\| …)` |
| `not(x)` | `!(x)` |

- The two sides MUST combine as `<A> && <B>`, each side a leaf or a parenthesised compound. An `all` side adds no term, and a rule whose sides are both `all` has no condition clause.
- `selector_b` MUST be used only with `clearance` and `creepage`.
- `rulemap.KIND_SELECTORS` MUST narrow the grammar per kind: `hole_to_hole`, `hole_clearance` and `annular_width` take side A only and no layer clause; `courtyard_clearance` takes `all`, or `ref` leaves without a glob combined with `and`, `or` and `not`, on side A only and with no layer clause; `silk_clearance` takes `all` only; `creepage` takes `net` and `netclass` leaves combined with `and`, `or` and `not`, on both sides, with no layer clause. The first six kinds take the grammar as this requirement states it.
- `rulemap.SELECTOR_SUPPORT` MUST have the keys `net`, `netclass`, `ref`, `item_kind`, `and`, `or`, `not`, `glob` (a `*` inside a leaf value), `selector_b` (a `selector_b` other than `all`) and `layer_clause` (a non-empty `Rule.layers`). Each entry MUST hold exactly the majors on which that key's `dru-cond-*` probe passed (`H-K-DRU-COND`, `H-K-DRU-GLOB`); a key without a passing probe MUST have an empty entry. `all` at the top level writes no term and needs no entry.
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
- **GIVEN** one bench per op (`net`, `netclass`, `ref`, `item_kind`, layer clause, `and`, `or`, `not`, `selector_b`, glob), each with a probe pair and a control pair 4 mm apart, a 5 mm rule and the canary
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
