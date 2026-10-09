## MODIFIED Requirements

### Requirement: Rule lowering table
`fenolite.backends.altium.rulemap.TABLE` SHALL be the closed table that maps each neutral rule kind to the Altium rule kind that carries it. Each row MUST hold the neutral kind, the Altium kind and its kind number, the limits a rule must give, the constraint fields in written order, the `NETSCOPE`, the scope forms it supports, and either `exact` or one reason of `NOT_LOWERED_REASONS` (`no-counterpart`, `scope-unsupported`, `value-unsupported`, `unit-loss`) with a note.
- Every neutral rule kind of `model/rules.py` MUST have a row. A row MUST be `exact` only when `docs/formats/altium/pcb-copper.md` ("Rule kinds lowered") records, with a public source and a label, the Altium constraint and the keys of its record. The `exact` rows are: `clearance` → `Clearance` (0), `track_width` → `Width` (2), `via_diameter` and `via_drill` → `RoutingVias` (11), `hole_size` → `HoleSize` (42), `edge_clearance` → `BoardOutlineClearance` (63), `hole_to_hole` → `HoleToHoleClearance` (52), `annular_width` → `MinimumAnnularRing` (19). `hole_clearance`, `courtyard_clearance`, `silk_clearance` and `creepage` are `no-counterpart`.
- The five pair and length kinds, `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length`, MUST each have a row with the reason `no-counterpart`, in the model's order after `no_tracks`. Each note MUST say that the record of the Altium rule that would carry the kind is in no public source that `pcb-copper.md` records, so its keys are not known; no note MAY name a kind number or a key. A row of these five becomes `exact` only through a later change that first records the fact rows.
- `lower(rules)` MUST return the rule records of the rules it writes and, for every rule that is not written, its kind, selector and reason. A rule is written only when its row is `exact`, its severity is `error`, it gives exactly the limits of its row (`min` for a clearance kind, `hole_to_hole` and `annular_width`; `min` and `max` for `hole_size`; `min`, `opt` and `max` for `track_width`, `via_diameter` and `via_drill`), and each value is 0 or at least one PCB unit and inside the 32-bit range; otherwise the reason is `value-unsupported`. `lower` MUST never write a rule whose value or scope differs from the neutral rule's beyond the 2 nm of the PCB unit.
- A `via_diameter` and a `via_drill` rule of the same selector MUST share one `RoutingVias` record; either one without the other MUST be `value-unsupported`.
- Fixed constraint values: `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE` and an empty `OBJECTCLEARANCES` (Clearance, BoardOutlineClearance), `VIASTYLE=Through Hole`, `ABSOLUTEVALUES=TRUE` with `MAXPERCENT=80.000` and `MINPERCENT=20.000`, and `ALLOWSTACKEDMICROVIAS=FALSE`.
- `lift(records)` MUST return the neutral rules of the records that `read.rules.map_rules` maps, in record order, and the count of the others by Altium kind. `lift` MUST never return a rule of the five pair and length kinds or a selector with a `diff_pair` leaf: `read.scope.parse_scope` keeps its closed grammar, and a scope outside it stays unmapped as before.
- `lift(lower(rules).records)` MUST equal the lowered subset of `rules` (`Lowered.written`) in kind, selectors and limits within 2 nm (`rulemap.same_rules`); the priority of a lifted rule is the record's, which counts within its Altium kind.

#### Scenario: Every kind has a row
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k complete` compares the kinds of `model/rules.py` with `TABLE` and with the table "The lowering table" of `docs/formats/altium/pcb-copper.md`
- **THEN** every kind has exactly one row, the five pair and length kinds included, the page's table equals `TABLE`, and every `exact` row is cited on the page with a source and is a kind of `read.rules.RULE_KIND_MAP`

#### Scenario: Round trip of the table
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k roundtrip` lowers and lifts one rule of every `exact` kind and generated rule sets
- **THEN** the lifted rules equal the lowered subset, within 2 nm, and every rule is either written or named with one reason

#### Scenario: A rule with no counterpart
- **GIVEN** a rule of a kind whose row has the reason `no-counterpart`
- **WHEN** `lower` runs
- **THEN** no record is written for it, and the result names its kind, its selector and that reason

#### Scenario: A minimum alone is not a Width rule
- **GIVEN** a `track_width` rule with `min` only
- **WHEN** `lower` runs
- **THEN** no record is written and the reason is `value-unsupported`, because a Width record holds a minimum, a preferred and a maximum width

#### Scenario: Pair and length rules are named, not written
- **GIVEN** one rule of each of `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length`, each on `diff_pair USB_`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k pair` calls `lower` on them
- **THEN** no exception is raised, no record is written, and the result names each rule once with its kind, the selector `diff_pair USB_` and the reason `no-counterpart`

### Requirement: Track layer rules in the Altium rule table
`fenolite.backends.altium.rulemap.TABLE` SHALL hold one row for the neutral kind `no_tracks` (`rules-model`, "Track layer rules"), thirteenth, after `creepage` and before the five pair and length kinds, as the kind stands in `RuleKind`, with the status `no-counterpart` and a note. This requirement extends "Rule lowering table": with it every kind of `model/rules.py`, eighteen of them with the five pair and length kinds, has exactly one row.
- The note MUST say that Altium's rule of the routing layers of a scope is the nearest counterpart and that its record (kind number, constraint keys) is in no public file read under the sources register, so the row cannot be `exact`.
- `lower` MUST write no record for a `no_tracks` rule and MUST name its kind, its selector and the reason `no-counterpart`; `fenolite build --target altium` then gives one `altium.not-lowered` (warning) with `where` `design-rules/no_tracks` and lists the rule in `result.rules.not_lowered` ("Rules in an Altium build"). The rule is never dropped without that issue.
- The table "The lowering table" of `docs/formats/altium/pcb-copper.md` MUST gain the row, with the source of the statement about Altium's rule (`S-0660`) and the label `INFERRED`.
- `lift` is unchanged: a record of that Altium kind in a document is counted among the records it does not map.
- The row MAY become `exact` only through a later change that registers a public file holding the record.

#### Scenario: Eighteen rows
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k complete` compares the kinds of `model/rules.py` with `TABLE` and with the page's table
- **THEN** every kind has exactly one row, the thirteenth is `no_tracks` with the status `no-counterpart` and a note, and the page's table equals `TABLE`

#### Scenario: A track layer rule in an Altium build
- **GIVEN** the four-layer blink variant with `design.rules.rule("sig-outer", "no_tracks", where=select.netclass("SIG"), layers=("In1.Cu", "In2.Cu"))`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rules.py -k no_tracks` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` hold one `altium.not-lowered` warning with `where` `design-rules/no_tracks` naming `sig-outer`, `result.rules.not_lowered` holds it with the reason `no-counterpart`, and the PCB document holds the rule records of the same script without the rule
