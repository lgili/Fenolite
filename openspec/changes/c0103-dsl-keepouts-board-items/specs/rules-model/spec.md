## MODIFIED Requirements

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
- `area v` names the rule areas of the board whose `Keepout.name` matches `v`, with letter case and with `*` as a glob; it selects the items whose copper overlaps such an area on one of the area's layers (`H-K-AREA-COND`). `area` MUST be a leaf of the grammar of the first six kinds (`clearance`, `edge_clearance`, `track_width`, `via_diameter`, `hole_size` and `via_drill`), on side A and, for `clearance`, on side B, and `rulemap.KIND_SELECTORS` MUST add it to the side-A leaves of `hole_to_hole`, `hole_clearance` and `annular_width`. `courtyard_clearance`, `silk_clearance` and `creepage` MUST NOT take it: an `area` leaf in one of their rules is a selector outside the kind's entry. Whether the board holds such an area is checked by the build (`design-dsl`, "Board items in a build"), not by the lowering.
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
