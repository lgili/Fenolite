## ADDED Requirements

### Requirement: Rule specificity
`fenolite.checks.specificity.rank(selector) -> int` SHALL give each selector a documented rank: `ALL` 0, `area` and `item` 1, `netclass` 2, `net` with `*` 3, `pair` and `ref` 4, `net` exact 5; `&` the sum of its items, `|` the least of its items, `~` 0, and a two-sided rule the sum of both sides. `docs/dsl.md`, "Design rules", MUST hold this table.

#### Scenario: Ranks
- **WHEN** `uv run pytest tests/unit/checks/test_specificity.py -k ranks` ranks `ALL`, `netclass("HS")`, `net("CLK")`, `net("CLK*") & item("track")` and `net("A") | netclass("HS")`
- **THEN** the ranks are 0, 2, 5, 4 and 2

### Requirement: Precedence unchanged by specificity
The governing rule of an item SHALL stay the last matching rule in `rule_precedence` order (priority, then name, then id), as KiCad applies it; specificity MUST NOT change the lowered text of a design that does not call `design.rules.precedence("specificity")`.

#### Scenario: Same bytes
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lowering.py -k specificity_neutral` lowers every rule bench before and after this change
- **THEN** the lowered texts are byte-equal

### Requirement: Shadowed rules are reported
When two rules of one kind match an item and the governing rule has a strictly lower rank than a rule it overrides, the build and `fenolite check` SHALL report `rules.shadowed` (info) once per pair of rules, naming both rules and their ranks, with a hint naming `priority=` and `design.rules.precedence("specificity")`.

#### Scenario: A class rule over a net rule
- **GIVEN** a `track_width` rule on `net("CLK")` at priority 3 and one on `netclass("HS")` at priority 1, `CLK` being in `HS`
- **WHEN** `uv run pytest tests/unit/checks/test_specificity.py -k shadowed` builds it with `--dry-run`
- **THEN** one `rules.shadowed` info names both rules with ranks 5 and 2

### Requirement: Specificity precedence on request
`design.rules.precedence("specificity")` SHALL give every rule without an explicit `priority=` a priority from its rank, so that among matching rules the most specific governs, ties keeping name order; rules with an explicit priority MUST keep it.

#### Scenario: The net rule governs
- **GIVEN** the rules of "A class rule over a net rule" without explicit priorities and with `precedence("specificity")`
- **WHEN** they are lowered and `rule_precedence` is applied to `CLK`
- **THEN** the `net("CLK")` rule governs, and no `rules.shadowed` is reported

### Requirement: Topology constraints lowered as lengths
A topology `delay` or `skew` whose path lies on one net, crosses no bridge and uses layers of one propagation value SHALL lower to a `length` rule (`max` = floor of `max_fs * 10^6 / per_mm_fs` nm, `min` = ceil) or a `skew` rule named `topology:<name>:<constraint>`; any other topology constraint MUST stay in the model with `rules.topology-not-lowered` (info).

#### Scenario: One-net delay lowered
- **GIVEN** a topology on one net routed on `F.Cu` at 5 900 fs/mm with `delay(max=ps(295))`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lowering.py -k topology` lowers it for target 10
- **THEN** one `length` rule `topology:<name>:delay` is written with `(max 50mm)`, and a bridged topology gives one `rules.topology-not-lowered`
