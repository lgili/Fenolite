## MODIFIED Requirements

### Requirement: Rule kinds and limits
The eighteen model kinds SHALL lower one to one, with these constraints and limits:

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
| `diff_pair_gap` | `diff_pair_gap` | `min`, `opt`, `max` |
| `diff_pair_uncoupled` | `diff_pair_uncoupled` | `max` |
| `skew` | `skew` | `opt`, `max` |
| `diff_pair_skew` | `skew`, with the list `(within_diff_pairs)` after its limits | `opt`, `max` |
| `length` | `length` | `min`, `opt`, `max` |

- Values MUST be written as the shortest exact millimetre decimal of the nanometre value, with the unit `mm` (`core.units.format_length`). They MUST never be rounded.
- Limits MUST be written in the order `min`, `opt`, `max`.
- A limit outside the table MUST give the error `rules.unsupported-limit`, and so MUST a rule with no limit of any kind but `no_tracks`, whose normal form holds none.
- `severity` MUST map one to one to `(severity error|warning|ignore)`, and a lowered rule MUST always carry its severity clause.
- Each of the first six kinds MUST be enforced by `kicad-cli` 9.0.9 and 10.0.6 on the items its condition selects (`H-K-DRU-KIND`). Each of the six kinds from `hole_to_hole` to `creepage` MUST be written only for the majors of its `KIND_SUPPORT` entry ("Kind support by major", `H-K-DRU-KIND-2`), and its DRC types MUST be listed in `docs/formats/kicad/rules.md`; `no_tracks` follows the same two rules with its own probe (`H-K-DRU-NOTRACKS`). A `min` of 0 MUST be accepted for those six kinds.
- `model.rules.RuleKind` MUST list the kinds in the order of the table: the first twelve as before change c0107, `no_tracks` thirteenth, and the five pair and length kinds after it.
- The last five kinds, the pair and length kinds, MUST be written only for the majors of their `KIND_SUPPORT` entries, which their probes `dru-kind-<kind>` set ("Kind support by major", `H-K-DRU-PAIR`). Their DRC types, `diff_pair_gap_out_of_range`, `diff_pair_uncoupled_length_too_long`, `skew_out_of_range` and `length_out_of_range`, MUST be listed in `docs/formats/kicad/rules.md`. KiCad's DRC checks their `min` and `max` and not their `opt`, which is written for KiCad's interactive tools and for later changes, as the `opt` of `track_width` is, and which `rules.md` MUST say is not checked. `skew` compares every net that the rule selects with the longest of them; `diff_pair_skew` compares the two nets of each pair that it selects.
- `read_rules` MUST lift a `skew` constraint whose children are its limits and the list `(within_diff_pairs)` as `diff_pair_skew`, and one whose children are its limits alone as `skew`; any other child MUST keep the rule opaque.

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
- **THEN** `RuleKind` holds the thirteen kinds that change c0107 left, with `no_tracks` thirteenth, and the five pair and length kinds after them, eighteen in all; the first rule is written, and the second raises `RulesLossError` with one `rules.unsupported-limit`

#### Scenario: Pair gap rule
- **GIVEN** a `diff_pair_gap` rule on `diff_pair USB_` with `min=130_000` and `max=200_000`
- **WHEN** it is lowered for target 9
- **THEN** its constraint is `(constraint diff_pair_gap (min 0.13mm) (max 0.2mm))` and its condition is `"A.inDiffPair('USB_')"`

#### Scenario: Skew within each pair
- **GIVEN** a `diff_pair_skew` rule on `diff_pair *` with `max=150_000`
- **WHEN** it is lowered for target 10 and the text is read back with `read_rules`
- **THEN** its constraint is `(constraint skew (max 0.15mm) (within_diff_pairs))` and the lifted rule is a `diff_pair_skew` rule equal to the original; the same rule of kind `skew` is written without the list and lifts as `skew`

#### Scenario: Gap with a target on one layer
- **GIVEN** a `diff_pair_gap` rule named `usb gap` with priority 1, on `diff_pair USB_`, with `min=130_000`, `opt=150_000`, `max=170_000` and `layers == ("F.Cu",)`
- **WHEN** it is lowered for target 9
- **THEN** one rule `"fenolite_1_usb_gap"` is written with `(layer "F.Cu")` and `(constraint diff_pair_gap (min 0.13mm) (opt 0.15mm) (max 0.17mm))`

#### Scenario: Limit outside a pair kind
- **GIVEN** a `diff_pair_uncoupled` rule with `min=1_000_000` and `max=5_000_000`, and a `skew` rule with `min=100_000`
- **WHEN** each is lowered
- **THEN** each raises `RulesLossError` with one `rules.unsupported-limit` naming the rule

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
| `diff_pair v` | `S.inDiffPair('v')` (`H-K-DRU-PAIRSEL`) |
| `and(x, y, …)` | `(x && y && …)` |
| `or(x, y, …)` | `(x \|\| y \|\| …)` |
| `not(x)` | `!(x)` |

- The two sides MUST combine as `<A> && <B>`, each side a leaf or a parenthesised compound. An `all` side adds no term, and a rule whose sides are both `all` has no condition clause.
- `selector_b` MUST be used only with `clearance` and `creepage`.
- `rulemap.KIND_SELECTORS` MUST narrow the grammar per kind: `hole_to_hole`, `hole_clearance` and `annular_width` take side A only and no layer clause; `courtyard_clearance` takes `all`, or `ref` leaves without a glob combined with `and`, `or` and `not`, on side A only and with no layer clause; `silk_clearance` takes `all` only; `creepage` takes `net` and `netclass` leaves combined with `and`, `or` and `not`, on both sides, with no layer clause; `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length` take `all`, or `diff_pair`, `net` and `netclass` leaves combined with `and`, `or` and `not`, on side A only, and of them only `diff_pair_gap` takes a layer clause. The first six kinds take the grammar as this requirement states it, `diff_pair` included.
- A `diff_pair v` leaf MUST select the items on the two nets of every pair (`design-model`, "Differential pairs in the model") whose base is `v`, or `v` followed by `_`; `v` MAY be `*`, which selects every pair. KiCad compares its value with letter case, unlike the other leaves (`H-K-DRU-PAIRSEL`).
- `area v` names the rule areas of the board whose `Keepout.name` matches `v`, with letter case and with `*` as a glob; it selects the items whose copper overlaps such an area on one of the area's layers (`H-K-AREA-COND`). `area` MUST be a leaf of the grammar of the first six kinds (`clearance`, `edge_clearance`, `track_width`, `via_diameter`, `hole_size` and `via_drill`), on side A and, for `clearance`, on side B, and `rulemap.KIND_SELECTORS` MUST add it to the side-A leaves of `hole_to_hole`, `hole_clearance` and `annular_width`. `courtyard_clearance`, `silk_clearance` and `creepage` MUST NOT take it, and neither does `no_tracks`, whose selector "Track layer rules" limits to nets and classes, nor do `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length`, whose leaves are `diff_pair`, `net` and `netclass`: an `area` leaf in one of their rules is a selector outside the kind's entry. Whether the board holds such an area is checked by the build (`design-dsl`, "Board items in a build"), not by the lowering.
- `read_rules` MUST lift `S.intersectsArea('v')` to `area v`, on either side. A condition that uses `S.enclosedByArea` or `S.insideArea` MUST keep its rule opaque (`rules.kept-opaque`).
- `rulemap.SELECTOR_SUPPORT` MUST have the keys `net`, `netclass`, `ref`, `item_kind`, `area`, `diff_pair`, `and`, `or`, `not`, `glob` (a `*` inside a leaf value), `selector_b` (a `selector_b` other than `all`) and `layer_clause` (a non-empty `Rule.layers`). Each entry MUST hold exactly the majors on which that key's `dru-cond-*` probe passed (`H-K-DRU-COND`, `H-K-DRU-GLOB`, `H-K-AREA-COND` for `area` and `H-K-DRU-PAIRSEL` for `diff_pair`); a key without a passing probe MUST have an empty entry. `all` at the top level writes no term and needs no entry.
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
- **GIVEN** one bench per op (`net`, `netclass`, `ref`, `item_kind`, `area`, `diff_pair`, layer clause, `and`, `or`, `not`, `selector_b`, glob), each with a probe pair and a control pair 4 mm apart, a 5 mm rule and the canary
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

#### Scenario: Clearance inside a pair
- **GIVEN** a `clearance` rule whose `selector_a` and `selector_b` are both `diff_pair USB_`, with `min=100_000`
- **WHEN** it is lowered for target 10 and the text is read back with `read_rules`
- **THEN** its condition is `"A.inDiffPair('USB_') && B.inDiffPair('USB_')"`, and the lifted rule has the same two selectors

#### Scenario: Pair leaf outside a kind's grammar
- **GIVEN** a `creepage` rule whose `selector_a` is `diff_pair USB_`, and a `length` rule whose `selector_a` is `ref U1`
- **WHEN** each is lowered
- **THEN** each raises `RulesLossError` with one `rules.unsupported-selector` naming its kind, and its hint does not offer `--allow-lossy`

### Requirement: Net classes lower to the project file
`fenolite.backends.kicad.lowering.lower_netclass(cls, *, base, floors, issues=None)` SHALL return a new `net_settings.classes` entry for the model `NetClass` `cls`: a copy of `base`, the `Default` entry of the project being written, with `name` set to `cls.name` and the seven modelled values written.
- `clearance`, `track_width`, `via_diameter`, `via_drill`, `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap` MUST map to the class keys of the same names (`lowering.NETCLASS_KEYS`). Each MUST be written as a `JsonNumber` holding the exact millimetre text of the nanometre value (`format_length(nm, "mm")` without the unit), and MUST keep the base value when the model field is `None`. No float MUST be produced.
- Every other key of `base` (microvia, colours, `priority`, line style, and `tuning_profile` when present) MUST be copied unchanged.
- A non-empty `description` MUST add the info `kicad.project.unlowered-field`, because no project key holds it.
- `floors` maps model fields to the nanometre values of `board.design_settings.rules` (`min_clearance`, `min_track_width`, `min_via_diameter`, `min_through_hole_diameter`). A written value below its floor MUST add the warning `kicad.project.below-floor` naming the class, the field, the value and the floor, and the value MUST still be written, because the floor governs and the class value is not enforced (`H-K-PRO-FLOOR`). The three pair values have no floor entry.
- The pair values are the defaults of KiCad's interactive router and no DRC limits. A `diff_pair_gap` below the class clearance lowers the clearance between the two nets of each pair of the class where no custom clearance rule governs them (`H-K-PRO-PAIR`); `copper-check`, "Clearance between the nets of a differential pair", follows it.
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

#### Scenario: Pair values lowered
- **GIVEN** `NetClass(name="USB", clearance=200_000, diff_pair_width=300_000, diff_pair_gap=150_000)` and a `Default` base whose `diff_pair_via_gap` is `JsonNumber("0.25")`
- **WHEN** `lower_netclass(cls, base=base, floors={"track_width": 200_000})` is called with an `issues` list
- **THEN** the entry has `diff_pair_width == JsonNumber("0.3")`, `diff_pair_gap == JsonNumber("0.15")` and `diff_pair_via_gap == JsonNumber("0.25")`, and `issues` stays empty
