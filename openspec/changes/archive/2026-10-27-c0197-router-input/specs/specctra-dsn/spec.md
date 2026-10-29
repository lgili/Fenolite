## MODIFIED Requirements

### Requirement: Routing rules in design files
`write_dsn` SHALL lower the rules of `design.rules` that the Specctra subset can carry, by this closed table, and SHALL report every other rule (`H-G-DSN-CLEARANCE`, `H-G-DSN-EDGE-2`). A rule of severity `ignore` MUST be skipped without an issue.

| model rule | written as |
|---|---|
| `clearance`, A `all`, B absent or `all` | the default rule's clearance and every class clearance raised to at least `min` |
| `clearance`, one side a class or an `or` of classes, the other absent or `all` | one `(class_class (classes <c> <o>) (rule (clearance <min>)))` per written class `c` of that side and per other written class `o`; the class's clearance against itself is not raised; nets without a class keep the default clearance against `c`, with one `specctra.rule-not-sent` (info) naming the rule |
| `clearance`, A and B classes or `or`s of classes | one `(class_class (classes <a> <b>) (rule (clearance <min>)))` in the network per pair of written classes; a class paired with itself raises its own clearance, unless a later rule of the board gives that same pair |
| `track_width`, A classes, with `opt` | without a layer clause, those classes' width becomes `opt`; with one, each of its layers gives `(layer_rule <layer> (rule (width <opt>)))` in those classes |
| `track_width`, A `all`, with `opt` | `opt` becomes the width of each class that holds no width of its own; a class width inside `[min, max]` is kept and one outside is clamped into it, with one `specctra.rule-widened` (info) naming the rule and the classes it left unchanged |
| `track_width`, A `all` or classes, without `opt` | each of those class widths clamped into `[min, max]` |
| `edge_clearance` | nothing: reported with `specctra.rule-not-sent` (Decision 11's fallback, `H-G-DSN-EDGE-2`) |
| `no_tracks` | nothing here; "Routing layers in design files" carries it through `net_layers` |

- Values MUST be combined by maximum, except where the table names the board's rule order: the router keeps at least what any applicable rule asks. A class split by "Routing layers in design files" MUST get the values and lists of its class, and a `class_class` pair MUST be written for every pair of their groups.
- A layer clause on a `clearance` rule MUST be dropped, the rule written for every layer, with one `specctra.rule-widened` (info) naming the rule. A `track_width` rule with a layer clause and without `opt`, or whose layer is not a copper layer of the board, MUST be left out with `specctra.rule-not-sent`. A pair of classes of which one is `Default` without a class of that name MUST be reported with `specctra.rule-not-sent`.
- Any other rule (a `net`, `ref`, `item_kind` or `area` leaf, a glob, a `not`, a kind not in the table) MUST be left out with one `specctra.rule-not-sent` (info) naming the rule and the reason.
- **Edge clearance.** The file MUST hold no keep-out band along the board edges: an `edge_clearance` rule, whatever its selector, MUST be left out with `specctra.rule-not-sent`. Measured on 2026-10-08 (`dsn-edge-band`): bands of half width `E − d` removed the edge findings where the board left room and lost the route of a 2 mm passage that the file without bands routed.

#### Scenario: Class to class clearance
- **GIVEN** the bench with the rule `hv-sig` (`clearance`, A `netclass HV`, B `netclass SIG`, `min=1 mm`)
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -k class_class` calls `write_dsn`
- **THEN** the network holds `(class_class (classes HV SIG) (rule (clearance 1000)))`, and the classes `HV` and `SIG` keep their own clearances

#### Scenario: Board-wide clearance above a class value
- **GIVEN** the bench with a rule `clearance`, A `all`, `min=0.25 mm`, and class clearances of 0.2 mm (`SIG`) and 0.3 mm (`HV`)
- **WHEN** `write_dsn` runs with defaults of 0.2 mm clearance
- **THEN** the default rule holds `(clearance 250)`, `SIG` holds 250 and `HV` holds 300

#### Scenario: One-sided clearance writes pairs
- **GIVEN** classes `HV` (clearance 0.3 mm) and `SIG` (0.2 mm), and the rule `hv-any` (`clearance`, A `netclass HV`, B absent, `min=1.4 mm`)
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -k one_sided` calls `write_dsn`
- **THEN** the network holds `(class_class (classes HV SIG) (rule (clearance 1400)))`, the class `HV` keeps `(clearance 300)`, and no `class_class` pair `HV HV` is written

#### Scenario: Board-wide preferred width keeps class widths
- **GIVEN** classes `PWR` (width 1.0 mm) and `SIG` (0.25 mm), a class `HV` without a width, and a `track_width` rule, A `all`, `min=0.1 mm`, `opt=3 mm`, `max=6 mm`
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -k width_all` calls `write_dsn`
- **THEN** `PWR` holds `(width 1000)`, `SIG` holds `(width 250)`, `HV` holds `(width 3000)`, and the result holds one `specctra.rule-widened` naming the rule, `PWR` and `SIG`

#### Scenario: Per-layer width
- **GIVEN** a `track_width` rule on `netclass SIG` with `layers=("F.Cu",)` and `min = opt = max = 0.35 mm`
- **WHEN** `write_dsn` runs
- **THEN** the class `SIG` holds `(layer_rule F.Cu (rule (width 350)))` and keeps its width of 200

#### Scenario: Rules the file cannot carry
- **GIVEN** a `clearance` rule with A `net HV1` and a `hole_to_hole` rule
- **WHEN** `write_dsn` runs
- **THEN** the file holds neither, and the result holds two `specctra.rule-not-sent` infos, one naming each rule

#### Scenario: Edge clearance is not sent
- **GIVEN** the bench with a board-wide `edge_clearance` rule of 0.5 mm and one on `netclass HV`, and defaults of 0.2 mm clearance
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -k edge` calls `write_dsn`
- **THEN** the text equals the text without the two rules, it holds no `(keepout (path signal …))`, and the result holds two `specctra.rule-not-sent` infos, one naming each rule
