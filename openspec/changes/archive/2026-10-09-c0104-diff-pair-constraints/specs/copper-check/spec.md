## ADDED Requirements

### Requirement: Clearance between the nets of a differential pair
`ClearanceResolver` SHALL apply KiCad's clearance inside a differential pair (`H-K-PRO-PAIR`, `H-K-COPPER-PAIR`). This requirement refines the subjects, the leaf comparison and the class value `k` of "Clearance in force"; everything else there holds.
- **Subjects.** `subject(…)` MUST set `RuleSubject.diff_pair` to the base of the subject's net when the design holds that net's coupled net (`design-model`, "Differential pairs in the model", `net_bases`), and to `None` otherwise.
- **Leaves.** A `diff_pair` leaf MUST be matched as "Differential pairs in the model" states, its value and the subject's base compared with their letter case; the other leaves keep their comparison without letter case.
- **Class value.** For two subjects whose nets are the two nets of one pair and are in one class whose `diff_pair_gap` is set and below its `clearance`, `k` MUST be that `diff_pair_gap`, with the source `pair-gap:<class name>`. A governing rule MUST replace it wherever it replaces a class value, and the board minimum `f` and the zone clearance `z` combine with it as with any `k`.
- `max_value` is unchanged: a pair gap lowers a value and adds none.
- **Explanation.** The explanation of a clearance (`copper-rule-explanation`, "Clearance rule explanation", change c0097, which is on `dev` before this change) MUST show the pair gap as a candidate row of its own, with the source `pair-gap:<class name>`, the gap as value and the severity of a class value, beside the row `class:<class name>` that it replaces. The row MUST come from the resolver's own candidates, with no second matcher, and the explained subjects MUST carry `diff_pair`. Where the pair gap does not apply (the nets are not one pair, the class holds no gap, or the gap is not below the class clearance) no such row is shown.

#### Scenario: Pair below its class clearance
- **GIVEN** nets `USB_P`, `USB_N` and `CLK` in the class `USB`, with a clearance of 0.2 mm and a `diff_pair_gap` of 0.1 mm, and no rule
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k pair` resolves a `USB_P` track against a `USB_N` track, and a `USB_P` track against a `CLK` track
- **THEN** the first gives 0.1 mm with source `pair-gap:USB`, and the second 0.2 mm with source `class:USB`

#### Scenario: Rules over the pair gap
- **GIVEN** the same nets and a board-wide `clearance` rule `board` of 0.2 mm and priority 0
- **WHEN** the pair is resolved with `rules_over_classes=True`
- **THEN** it gives 0.2 mm with source `rule:board`; with a further `clearance` rule `inside` of priority 1, whose two sides are `diff_pair USB_` and whose `min` is 0.1 mm, it gives 0.1 mm with source `rule:inside`

#### Scenario: Board minimum above the pair gap
- **GIVEN** the same nets without a rule, and `min_clearance` 0.12 mm
- **WHEN** the pair is resolved
- **THEN** it gives 0.12 mm with source `floor`

#### Scenario: Letter case of the pair leaf
- **GIVEN** the same nets and a `clearance` rule of 0.5 mm on `diff_pair usb_`
- **WHEN** the pair is resolved
- **THEN** the rule does not govern, and the value is 0.1 mm with source `pair-gap:USB`

#### Scenario: Pair gap in the explanation
- **GIVEN** the nets of "Pair below its class clearance" and a finding between a `USB_P` track and a `USB_N` track 0.08 mm apart
- **WHEN** `uv run pytest tests/unit/checks/test_copper_rule_review.py -k pair_gap` reads the finding's explanation
- **THEN** its candidate rows hold `pair-gap:USB` with 0.1 mm and `class:USB` with 0.2 mm, the governing source is `pair-gap:USB`, and resolving the explained subjects gives the finding's limit; the explanation of a `USB_P` track against a `CLK` track holds no `pair-gap` row
