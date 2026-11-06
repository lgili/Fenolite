## MODIFIED Requirements

### Requirement: Rule lowering table
`fenolite.backends.altium.rulemap.TABLE` SHALL be the closed table that maps each neutral rule kind to the Altium rule kind that carries it. Each row MUST hold the neutral kind, the Altium kind and its kind number, the limits a rule must give, the constraint fields in written order, the `NETSCOPE`, the scope forms it supports, and either `exact` or one reason of `NOT_LOWERED_REASONS` (`no-counterpart`, `scope-unsupported`, `value-unsupported`, `unit-loss`) with a note.
- Every neutral rule kind of `model/rules.py` MUST have a row. A row MUST be `exact` only when `docs/formats/altium/pcb-copper.md` ("Rule kinds lowered") records, with a public source and a label, the Altium constraint and the keys of its record. The `exact` rows are: `clearance` → `Clearance` (0), `track_width` → `Width` (2), `via_diameter` and `via_drill` → `RoutingVias` (11), `hole_size` → `HoleSize` (42), `edge_clearance` → `BoardOutlineClearance` (63), `hole_to_hole` → `HoleToHoleClearance` (52), `annular_width` → `MinimumAnnularRing` (19), and since change c0434 `courtyard_clearance` → `ComponentClearance` (24), `silk_clearance` → `SilkToSilkClearance` (55), `diff_pair_gap` and `diff_pair_uncoupled` → `DiffPairsRouting` (51). `hole_clearance` and `creepage` are `no-counterpart`.
- The five pair and length kinds MUST each have a row, in the model's order after `no_tracks`. `diff_pair_gap` and `diff_pair_uncoupled` are `exact` since change c0434. `skew`, `diff_pair_skew` and `length` have the reason `no-counterpart`. Each of their notes MUST say that the record of the Altium rule that would carry the kind is in no public source that `pcb-copper.md` records, so its keys are not known; no such note MAY name a kind number or a key.
- `lower(rules)` MUST return:
  - the rule records of the rules it writes;
  - for every rule that is not written, its kind, selector and reason;
  - for every rule written in another form (`Lowered.changed`, change c0434), its selector and why.
- A rule is written only when all of these hold; otherwise the reason is `value-unsupported`:
  - its row is `exact` and its severity is `error`;
  - it gives at least one limit of its row and no other limit;
  - each value it gives is 0 or at least one PCB unit, and inside the 32-bit range.
- A limit of the row that the rule does not give MUST be written open, and the rule counted changed:
  - a missing minimum is written as 0;
  - a missing preferred value is written as the rule's minimum, or its maximum without one;
  - a missing maximum is written as `rulemap.OPEN_MAX`, 100 mm, or the largest given limit when that is larger.
- `lower` MUST never write a value or scope that the rule gives differently from the neutral rule's, beyond the 2 nm of the PCB unit.
- Partner rules of one selector share one record:
  - A `via_diameter` and a `via_drill` rule MUST share one `RoutingVias` record.
  - A `diff_pair_gap` and a `diff_pair_uncoupled` rule MUST share one `DiffPairsRouting` record.
- A rule without its partner:
  - A `via_diameter` rule MUST take the minimum and maximum of the most governing `hole_size` rule, looked for on the vias of its selector, then of its selector, then on every via, then on every hole; the hole's minimum is also the preferred hole. The rule is counted changed.
  - A `diff_pair_gap` rule MUST take an open uncoupled length, and is counted changed.
  - A `via_drill` rule, a `diff_pair_uncoupled` rule, and a `via_diameter` rule with no hole rule MUST be `value-unsupported`.
- Differential Pairs Routing records:
  - The scope is `All` for `diff_pair *`. For `diff_pair *` joined with `and` to another selector, it is that selector's scope.
  - Any other pair selector MUST be `scope-unsupported`.
  - Its per-layer width keys (`TOPLAYER`, `MIDLAYER1` to `MIDLAYER30`, `BOTTOMLAYER`) MUST take the limits of the most governing `track_width` rule on every object, or 0, 0.25 mm and 100 mm without one.
- `courtyard_clearance` and `silk_clearance` rules MUST always be counted changed, because Altium measures them otherwise.
- Fixed constraint values: `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE` and an empty `OBJECTCLEARANCES` (Clearance, BoardOutlineClearance), `VIASTYLE=Through Hole`, `ABSOLUTEVALUES=TRUE` with `MAXPERCENT=80.000` and `MINPERCENT=20.000`, `ALLOWSTACKEDMICROVIAS=FALSE`, and `COLLISIONCHECKMODE=3` with `SHOWDISTANCES=FALSE` and `VERTICALGAP` equal to `GAP` (ComponentClearance).
- `lift(records)` MUST return the neutral rules of the records that `read.rules.map_rules` maps, in record order, and the count of the others by Altium kind. `lift` MUST never return a rule of `skew`, `diff_pair_skew` or `length`. A `diff_pair` leaf comes only from the pair narrowing of a Differential Pairs Routing record (`diff_pair *`): `read.scope.parse_scope` keeps its closed grammar, and a scope outside it stays unmapped as before.
- `lift(lower(rules).records)` MUST equal, within 2 nm (`rulemap.same_rule`), the written rules that are not changed, in kind, selectors and limits. A changed rule reads back with the limits its record holds. The priority of a lifted rule is the record's, which counts within its Altium kind.

#### Scenario: Every kind has a row
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k complete` compares the kinds of `model/rules.py` with `TABLE` and with the table "The lowering table" of `docs/formats/altium/pcb-copper.md`
- **THEN** every kind has exactly one row, the five pair and length kinds included, the page's table equals `TABLE`, and every `exact` row is cited on the page with a source and is a kind of `read.rules.RULE_KIND_MAP`

#### Scenario: Round trip of the table
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k roundtrip` lowers and lifts one rule of every `exact` kind and generated rule sets
- **THEN** each record lifts to a rule of every kind it holds, the unchanged rules equal the lowered ones within 2 nm, and every rule is either written or named with one reason

#### Scenario: A rule with no counterpart
- **GIVEN** a rule of a kind whose row has the reason `no-counterpart`
- **WHEN** `lower` runs
- **THEN** no record is written for it, and the result names its kind, its selector and that reason

#### Scenario: A minimum alone is written open
- **GIVEN** a `track_width` rule with `min` only (a KiCad board minimum)
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap_c0434.py -k open` calls `lower`
- **THEN** one Width record is written with the minimum, a preferred width equal to it and the maximum 100 mm, and the rule is in `Lowered.changed`, not in `not_lowered`

#### Scenario: A via whose drill is a hole rule on vias
- **GIVEN** a `via_diameter` rule on the class `PWR` and a `hole_size` rule on `and(item_kind via, netclass PWR)`
- **WHEN** `lower` runs
- **THEN** one `RoutingVias` record scoped `InNetClass('PWR')` holds the diameter and the hole limits of the hole rule, the hole rule keeps its own Hole Size record, and the via rule is counted changed

#### Scenario: Courtyard, silkscreen and pair rules
- **GIVEN** a `courtyard_clearance`, a `silk_clearance`, and a `diff_pair_gap` with a `diff_pair_uncoupled` rule on `diff_pair *`
- **WHEN** `lower` runs and the records are lifted
- **THEN** a ComponentClearance (24), a SilkToSilkClearance (55) and one DiffPairsRouting (51) record scoped `All` are written, and they lift to rules of the same kinds and selectors

#### Scenario: Pair and length rules are named, not written
- **GIVEN** one rule of each of `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length`, each on `diff_pair USB_`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k pair` calls `lower` on them
- **THEN** no exception is raised and no record is written. The result names each rule once with its kind and the selector `diff_pair USB_`: the reason is `scope-unsupported` for the two kinds of Differential Pairs Routing, which select every pair of a scope, and `no-counterpart` for the other three

### Requirement: Scoped rule records
Rule records SHALL carry the scope of their rule as an expression of the closed scope grammar of `altium-project-reader` ("Closed scope grammar"): all objects (`All`), a net (`InNet('<net>')`), a net class (`InNetClass('<class>')`), a component (`InComponent('<ref>')`), an item kind (`IsTrack`, `IsVia`, `IsPad`, and `InPolygon` for `zone`), and their combinations with `And`, `Or` and `Not` (change c0412); a `clearance`, `courtyard_clearance` or `silk_clearance` rule with a second selector uses both scope fields, and every other kind writes `All` as its second scope. A pair rule's `diff_pair *` is written as the scope of the rest of its selector (change c0434). Every written scope MUST be one that `read.scope.parse_scope` turns back into the rule's selector.
- An operand that is itself a conjunction, a disjunction or a negation MUST be written in parentheses, because the grammar holds one kind of operator per parenthesis level.
- A layer is not a written scope: the closed grammar refuses layer functions, so a rule with `layers` or a `layer` selector MUST give `scope-unsupported`.
- Rules of one Altium kind MUST be written from the most governing neutral rule to the least (priority 1, 2, … and then priority 0; ties by falling name, then id), with `PRIORITY` from 1 in that order within the kind. This is the reverse of the order of a KiCad rules file, where the last rule governs.
- A selector outside the written forms (a glob, a value that holds `'` or cannot be written, an `area` leaf, a `diff_pair` leaf other than the `diff_pair *` of a pair rule, an item kind other than `track`, `via`, `pad` and `zone`, a second selector for a kind other than `clearance`, `courtyard_clearance` and `silk_clearance`) MUST give the reason `scope-unsupported` for that rule only; the other rules of the kind are written.
- Rule names MUST be unique in the document and derived from the kind and the scopes (`<Kind>`, `<Kind>_<class>`, `<Kind>_net_<net>`, `<Kind>_ref_<ref>`, `<Kind>_<item>` for an item kind, `_and_`, `_or_` and `not_` for the operators, `_to_` before the second scope; a repeated name gets `_2`, `_3`…), so that two builds give equal names.

#### Scenario: Class rule above the general rule
- **GIVEN** a design with a track width (minimum, preferred and maximum) for all nets and another, of priority 1, for the class `PWR`
- **WHEN** the PCB document is written and read back
- **THEN** two Width rules exist, `Width_PWR` with the scope `InNetClass('PWR')` and `PRIORITY=1`, and `Width` with the scope `All` and `PRIORITY=2`

#### Scenario: A scope outside the grammar
- **GIVEN** a `track_width` rule on the net glob `PWR_*`, a second on the layer `F.Cu` and a third on the class `PWR`
- **WHEN** `lower` runs
- **THEN** one record `Width_PWR` is written, and the two others are named with the reason `scope-unsupported`

#### Scenario: Composite clearance scopes
- **GIVEN** clearance rules on `and(ref J1, item_kind pad)`; on `net A` against `or(net B, net C)`; on `netclass HV` against `and(item_kind zone, not(netclass HV))`; and on `and(item_kind pad, net SENSE)` against `not(netclass HV)`
- **WHEN** `lower` runs and the records are lifted again
- **THEN** four Clearance records are written with the scopes `InComponent('J1') And IsPad`; `InNet('A')` and `InNet('B') Or InNet('C')`; `InNetClass('HV')` and `InPolygon And (Not InNetClass('HV'))`; `IsPad And InNet('SENSE')` and `Not InNetClass('HV')`, and the lifted rules equal the lowered ones

#### Scenario: Pads without a net
- **GIVEN** a single-sided clearance rule on `or(and(or(ref R1, ref R2), item_kind pad), and(ref U1, item_kind pad, not(or(net A, net B))))`
- **WHEN** `lower` runs and the record is lifted again
- **THEN** one Clearance record is written with the first scope `((InComponent('R1') Or InComponent('R2')) And IsPad) Or (InComponent('U1') And IsPad And (Not (InNet('A') Or InNet('B'))))` and the second `All`, and the lifted rule equals the written one

#### Scenario: Limit combinations
- **GIVEN** `track_width` rules with min, opt and max (scoped `all` and by a class), with min only and with min and max; `via_diameter` rules with min, opt and max beside a `via_drill` rule of the same selector, alone (scoped `all` and by a class) and with min only; and `hole_size` rules with min and max and with min only
- **WHEN** `lower` runs on each
- **THEN** every Width rule and Hole Size rule is written, those without every limit counted changed with the missing limits open (change c0434). The via pair is written. A `via_diameter` rule without a `via_drill` partner or any `hole_size` rule is one `value-unsupported` loss whose detail names the missing partner rule
