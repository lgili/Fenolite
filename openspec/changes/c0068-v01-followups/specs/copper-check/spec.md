## MODIFIED Requirements

### Requirement: Clearance in force
`fenolite.checks.clearance.ClearanceResolver(design, *, min_clearance=None, rules_over_classes=True, floor_over_rules=False)` SHALL return, through `resolve(a, b, *, zone_clearance=None)` for two `RuleSubject`s on the same layer, a `Clearance(value, severity, source)`:
- **Subjects.** `item_kind` is `track` for tracks and arcs, `via`, `pad` or `zone` (fills); `net` is the net name; `netclass` is the name of the net's class, or `Default` when its `netclass_id` is `None`; `ref` is the component reference for a pad and `None` otherwise; `layer` is the shared layer.
- **Rules.** The candidates MUST be the rules of `design.rules.rules` (none when `design.rules` is `None`) with `kind == "clearance"`, a `min` limit, and empty `layers` or `layers` holding the shared layer. A rule MUST match the pair when `selector_a` matches one subject and `selector_b` (or every subject, when it is `None`) matches the other, in either order. Leaf values and subject names MUST be compared without regard to letter case (`H-K-DRU-COND`).
- **Precedence.** The governing rule MUST be the last matching rule in the order of `rule_precedence(rules)`, which MUST equal c0018's `rulemap.rule_order`: priority 0 first, then descending priority, ties by name, then id.
- **Value.** Let `k` be the larger `clearance` of the two nets' classes that set one, the class of a net whose `netclass_id` is `None` being the class named `Default` when `design.circuit.netclasses` holds one, let `f` be `min_clearance` when it is positive, and let `z` be `zone_clearance` when it is positive.
  - A governing rule with severity `ignore` MUST give `value=None` and `severity=None`, so the pair is not judged for clearance.
  - Without a governing rule, the value MUST be the largest of `k`, `z` and `f` that exist, with severity `error` and source `class:<name>`, `zone` or `floor` (`H-K-PRO-FLOOR`, `H-K-PRO-MIN-KEYS`, `H-K-COPPER-ZONECLR`). Among equal values the source MUST be the class, then the zone, then the floor.
  - With a governing rule of `min` `r`, the value MUST start at `r` with the rule's severity and source `rule:<name>`; when `rules_over_classes` is false, the largest of it, `k` and `z` MUST be taken (`H-K-PRO-MIN-CLASS`), so `z` is kept wherever a class value is kept and replaced wherever a class value is replaced; when `floor_over_rules` is true, the larger of the result and `f` MUST be taken (the claim of `H-K-PRO-MIN-RULE`, which c0026 refuted on 9.0.9 and 10.0.6: `H-K-PRO-MIN-RULE-2`). The source names whichever value governs, and the severity is the rule's when its `min` governs and `error` otherwise.
  - `rules_over_classes` and `floor_over_rules` carry c0026's measured tables `lowering.RULES_OVER_CLASSES` and `lowering.FLOOR_OVER_RULES["min_clearance"]` for the major being judged. The defaults are the values those tables ship with for 9 and 10: `rules_over_classes` true (`H-K-PRO-MIN-CLASS`) and `floor_over_rules` false, because a custom rule governs below the board minimum (`H-K-PRO-MIN-RULE-2`).
- **Unset.** When nothing gives a value, `value` MUST be `None` and the pair is judged for shorts only; `check_copper` MUST count such pairs in `summary.unset_pairs` and report one `copper.clearance-unset` info with the count.
- **Zone clearance.** `zone_clearance` is the `settings.clearance` of the zone of a fill. `check_copper` MUST pass it for a pair of one fill and one item that is not a fill, and MUST pass `None` for every other pair, two fills included. KiCad's DRC judges a stored fill against a track, a via or a pad with the zone's clearance as it does a class value, lets a governing custom rule replace it, and judges no pair of two fills (`H-K-COPPER-ZONECLR`, measured on 9.0.9 and 10.0.6). The zone's clearance is not written into a rule and changes no file.
- `max_value` MUST be the largest value `resolve` can return for the design, the `settings.clearance` of every zone of the board that has fills included, or 0.

#### Scenario: Rule overrides the classes
- **GIVEN** nets `HV` and `LV` in classes with clearances 0.5 mm and 0.2 mm, and a `clearance` rule `hv_lv` with `selector_a = net HV`, `selector_b = net LV` and `min = 1 mm`
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k rule` resolves an `LV` track against an `HV` pad
- **THEN** it returns 1 mm, severity `error` and source `rule:hv_lv`; without the rule it returns 0.5 mm with source `class:<HV class name>`

#### Scenario: Classes above a rule where KiCad keeps them
- **GIVEN** the same nets and a rule of 0.1 mm on the pair
- **WHEN** the pair is resolved with `rules_over_classes=True` and with `rules_over_classes=False`
- **THEN** the first gives 0.1 mm with source `rule:<name>`, and the second 0.5 mm with source `class:<HV class name>`

#### Scenario: Later rule governs
- **GIVEN** two matching clearance rules `a` (priority 1, 0.1 mm) and `b` (priority 2, 0.3 mm)
- **WHEN** the pair is resolved
- **THEN** the value is 0.1 mm, because `rule_order` puts `a` last

#### Scenario: Floor and ignore
- **GIVEN** a governing rule of 0.1 mm and `min_clearance = 0.15 mm`, and then the same rule with severity `ignore`
- **WHEN** the pair is resolved
- **THEN** the first gives 0.1 mm with source `rule:<name>`, the second gives `value is None`, and with `floor_over_rules=True` the first gives 0.15 mm with source `floor`

#### Scenario: Letter case ignored
- **GIVEN** a rule on `net gnd` and a track on net `GND`
- **WHEN** the pair is resolved
- **THEN** the rule governs

#### Scenario: Zone clearance above the class
- **GIVEN** nets `A` and `B` in a class with a clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k zone` resolves a fill of `A` against a track of `B` with `zone_clearance=300_000`, and again with `zone_clearance=100_000`
- **THEN** the first gives 0.3 mm, severity `error` and source `zone`, and the second 0.2 mm with source `class:<class name>`

#### Scenario: Rule replaces the zone clearance
- **GIVEN** the same nets, a `clearance` rule of 0.2 mm on the pair and `zone_clearance=500_000`
- **WHEN** the pair is resolved with `rules_over_classes=True` and with `rules_over_classes=False`
- **THEN** the first gives 0.2 mm with source `rule:<name>`, and the second 0.5 mm with source `zone`

#### Scenario: Board minimum above the zone
- **GIVEN** the same nets without a rule, `min_clearance = 0.4 mm` and `zone_clearance=300_000`
- **WHEN** the pair is resolved
- **THEN** the value is 0.4 mm with source `floor`; with `min_clearance = 0.25 mm` it is 0.3 mm with source `zone`

#### Scenario: Fill against a track and against another fill
- **GIVEN** a board whose zone of net `A` has a clearance of 0.5 mm and a stored fill, a track of net `B` 0.3 mm from that fill, and a second zone of net `B`, also with a clearance of 0.5 mm, whose stored fill is 0.3 mm from the first fill, both nets in a class with a clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_clearance` runs `check_copper`
- **THEN** it reports exactly one `copper.clearance`, between the first fill and the track, with clearance 500 000 nm and source `zone`

### Requirement: Clearance findings
`check_copper` SHALL report one `copper.clearance` finding for each judged item pair that does not short and whose shapes are closer than the clearance in force on a shared copper layer (`thick_closer_than(a, b, value)`, a strict comparison). For a pair that involves an arc, the arc's shape MUST first be widened by twice its band, so that no violation is missed. When the value in force of such a pair comes from a zone (`source == "zone"`), the pair MUST be judged twice: the widened shape with the value that `resolve` gives without `zone_clearance`, and the arc's shape narrowed by twice its band, never below a width of 0, with the zone's value. The pair is a finding when either is too close; it carries the zone's value and source when the narrowed shape is, and the other value and its source otherwise. KiCad's filler cuts a fill to the zone's clearance around the true arc, so the widened shape judged with the zone's value would report fills that KiCad just made; with this rule no finding of the earlier rule is lost.
- The severity MUST be the governing rule's severity, and `error` for a class, zone or floor value.
- The finding MUST hold the gap rounded down to a whole nanometre (`thick_gap_floor`, a lower bound for arcs), the clearance value and its source.
- The message MUST name both nets, the layer, the point, the gap and the clearance in millimetres, and the source.

#### Scenario: Strict comparison
- **GIVEN** two 0.25 mm tracks of nets `A` and `B` on `F.Cu` whose edges are 0.2 mm apart, and a class clearance of 0.2 mm on both nets
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k strict` runs `check_copper`
- **THEN** it reports no finding, and with the edges 1 nm closer it reports one `copper.clearance` error with gap 199 999 nm, clearance 200 000 nm and source `class:<class name>`

#### Scenario: Warning rule
- **GIVEN** the same pair at 0.15 mm and a governing rule of 0.2 mm with severity `warning`
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` warning naming the rule

#### Scenario: Arc band never hides a violation
- **GIVEN** a 0.25 mm arc track and a track of another net whose true edge gap is 5 µm below a 0.2 mm clearance
- **WHEN** `check_copper` runs with the default `arc_tol`
- **THEN** it reports one `copper.clearance` finding

#### Scenario: A fill cut around an arc is not reported
- **GIVEN** a 0.25 mm arc track of net `B` and a fill of net `A` whose zone has a clearance of 0.5 mm, the fill's edge following the arc at a true distance of exactly 0.5 mm, both nets in a class of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_arc` runs `check_copper` with the default `arc_tol`
- **THEN** it reports no finding; with the fill's edge 5 µm closer it reports one `copper.clearance` with source `zone`; and with the fill's edge 0.19 mm from the arc it reports one with the class value and source `class:<class name>`, as before this change

### Requirement: Supported cases are documented against KiCad's DRC
`docs/formats/kicad/copper.md` SHALL hold a table of the cases this check supports and how they compare with KiCad's DRC, with a hypothesis id or the word "documented difference" per row. It MUST state at least: tracks, vias and pads exact; arcs within their band; vias and through-hole pads on every spanned layer, with unused-layer removal not modelled (Fenolite may report more); net-tie pad groups reported as shorts; zone fills checked as stored, outlines only for overlaps; the zone's own clearance applied between a fill and a track, a via or a pad as KiCad's DRC applies it, a governing custom rule replacing it (`H-K-COPPER-ZONECLR`); pairs of two fills judged with the rule, class and board-minimum values only, although KiCad's DRC judges no pair of fills (Fenolite may report more); graphics, texts, holes, edges, mask and silkscreen not checked; KiCad project severity overrides and exclusions not applied; opaque custom rules not applied (`copper.rules-incomplete`); a project without net classes gives no clearance in force. The parity proven on canaries (`kicad-oracle`, "Copper verdict parity canaries") MUST be stated per row and per major.

#### Scenario: Table checked
- **GIVEN** `docs/formats/kicad/copper.md`
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** every fact row has an S-id, a valid label and a hypothesis below `CORPUS-VERIFIED`, and the supported-cases table has a hypothesis id or "documented difference" in every row

#### Scenario: Zone rows of the table
- **GIVEN** `docs/formats/kicad/copper.md` after this change
- **WHEN** `uv run pytest tests/unit/test_format_facts.py -k copper` reads the supported-cases table
- **THEN** the row of the zone's own clearance names `H-K-COPPER-ZONECLR` and its parity on 9.0.9 and 10.0.6, a row for pairs of two fills says "documented difference", and no row says that the zone's clearance is not applied
