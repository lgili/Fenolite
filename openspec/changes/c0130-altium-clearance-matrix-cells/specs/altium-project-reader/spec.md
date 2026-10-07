## ADDED Requirements

### Requirement: Cells of an object matrix
A `Clearance` record whose `OBJECTCLEARANCES` holds clearances that differ from `GAP` SHALL map to the rule of `GAP` and one more `clearance` rule per cell, where the neutral rule says the cell exactly, and SHALL stay unmapped otherwise. `rules.read_matrix(text, gap)` MUST return a `Matrix(cells, judged, unjudged)` or a string that says why the matrix is refused. The forms are read and MUST NOT be written by `rulemap.lower`.
- **Kinds.** `rules.MATRIX_KINDS` MUST map the object kinds of the matrix to the item kinds of the copper check (`rules.ITEM_KINDS` = `track`, `pad`, `via`, `zone`): `Arc` and `Track` to `track`, `SMDPad` and `THPad` to `pad`, `Via` to `via`, `Poly` to `zone`, and `Fill`, `Region`, `Text` and `Hole` to none (the check holds no item of the kind). A name outside the table, two entries for one pair of kinds, and entries without a `GAP` that is a length MUST give the reason `keys`.
- **Value of a pair.** A pair of object kinds holds the length of its entry (a count is `rules.MATRIX_UNIT`), or `GAP` when the text holds no entry for it.
- **Exact cells only.** A pair of item kinds is said exactly when every pair of object kinds in it holds one value. That value is a cell when it differs from `GAP`, to the nanometre. When the object kinds of one item kind disagree (an arc and a track, a through-hole pad and a surface pad), no neutral rule says the pair: the record MUST stay unmapped with the reason `keys` and a detail that names each such pair of item kinds (`track to pad`) and says that a neutral rule tells no arc from a track and no through-hole pad from a surface pad. Nothing of such a record is mapped: no cell is judged with a value the record does not hold for all its objects.
- **Cell rules.** For a cell of the item kinds `a` and `b` the mapper MUST add a rule with `kind` `clearance`, `min` the cell's value (0 for a cell of 0), `name` `<NAME>/<a>-<b>`, the record's `priority`, `severity`, `layers` and `native_ids`, `id = derived_id("rul", "altium", "<origin>:<index>:clearance:<a>-<b>")`, `selector_a` = the record's first selector narrowed to `item_kind a` and `selector_b` = its second selector (`all` when the scope is `All`) narrowed to `item_kind b`; narrowing `all` gives the `item_kind` leaf, narrowing another selector gives `and(selector, item_kind)`. When `a` and `b` differ and the two selectors of the record differ, a second rule `<NAME>/<b>-<a>` with the kinds exchanged MUST be added, because either object may be of either kind. The bag of a cell rule MUST hold `("record", <the record text>)` and `("cell", "<a>-<b>")`.
- **Order.** The cell rules follow the rule of `GAP` in `ruleset`, in the order of `ITEM_KINDS`. A cell rule governs its pairs above the rule of `GAP` of its record and below every record of a higher priority: it has the record's priority and a longer name, and among rules of one priority the later name governs (`checks.clearance.rule_precedence`).
- **Entries that no rule holds.** An entry with an object kind that maps to none changes no rule. The rule of `GAP` MUST carry them in its bag as `("cells_not_lifted", <the entries as written, joined by ;>)`.
- **Counts.** `RuleMapping.matrix_cells` MUST hold, for each enabled `Clearance` record whose `OBJECTCLEARANCES` is not blank, `(index, judged, unjudged)`: for a mapped record the entries whose two object kinds map to an item kind, and the others; for an unmapped record 0 and the number of its entries.

#### Scenario: One cell
- **GIVEN** a `Clearance` record for all objects with `GAP=4mil`, priority 4 and the entry `ClearanceObj_Via-ClearanceObj_Via:35000`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k one_cell` maps it
- **THEN** the rules are `Clearance` (101 600 nm, all objects) and `Clearance/via-via` (88 900 nm, `item_kind via` on both sides) with one priority, and `matrix_cells == ((0, 1, 0),)`

#### Scenario: Cells of the poured polygons
- **GIVEN** a record with `GAP=4mil` and eight entries: arc, track, surface pad, through-hole pad, via, fill and polygon against polygon at 15 mil, and via against via at 3.5 mil
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k by_item_kind` maps it
- **THEN** the cell rules are `track-zone`, `pad-zone`, `via-via`, `via-zone` and `zone-zone`, the rule of `GAP` names the entry of the fill in `cells_not_lifted`, and `matrix_cells == ((0, 7, 1),)`

#### Scenario: A cell without a counterpart
- **GIVEN** records whose matrix holds an entry for a track against a through-hole pad only, or 0 for an arc against a polygon and 0.25 mm for a track against a polygon
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k disagree` maps them
- **THEN** each is unmapped with `keys`, the detail names `track to pad` or `track to zone`, and every entry is counted as unjudged

#### Scenario: Cells of a scoped record
- **GIVEN** a record whose first scope is `InNet('A')` and second `All`, with cells for via against polygon and via against via
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k scoped_record` maps it
- **THEN** the cell rules are `via-via`, `via-zone` and `zone-via`, each with `and(net A, item_kind …)` on its first side

#### Scenario: Cell rules in the import
- **GIVEN** a PCB document with the record of "One cell" and an entry for a track against text
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_rules.py -k cell_rules` imports it
- **THEN** the cell rule has a native id and a bag of its own, the clearance in force between two vias is 88 900 nm from `Clearance/via-via`, and between a via and a track 101 600 nm from `Clearance`

## MODIFIED Requirements

### Requirement: More forms of a Clearance record
The rule mapper SHALL map a `Clearance` record in each of the forms below, and only where the neutral rule says exactly what the record says; every other form MUST stay unmapped with a reason that names it. The forms are read and MUST NOT be written by `rulemap.lower`.
- **Blank matrix.** An `OBJECTCLEARANCES` that is empty or holds white space only holds no entry: the record is one clearance, `GAP`.
- **Uniform matrix.** An `OBJECTCLEARANCES` whose entries (`ClearanceObj_<kind>-ClearanceObj_<kind>:<count>` joined by `;`, a count being 0.0001 mil, `rules.MATRIX_UNIT`) all hold the length of `GAP`, to the nanometre, is one clearance, `GAP`. A matrix with an entry of another length is read by "Cells of an object matrix". Text that is no entry MUST give the reason `keys`. `rules.matrix_problem(text, gap)` says why a matrix is refused, or `""`.
- **Matrix cell.** The keys of a cell of the clearance matrix between net classes are allowed with these values only: `ISMATRIX=TRUE`, `CELLROWNAME=All`, `CELLROWTYPE=0`, `CELLCOLNAME=All`, `CELLCOLTYPE=0`, `INNERLAYERS=TRUE`, `OUTERLAYERS=TRUE`, and `SOURCERULE` with any value. They are not read further: the record's scopes, `GAP` and `PRIORITY` say what it governs. Any other value MUST give `keys`.
- **Layer condition.** `scope.parse_layer_scope(text)` MUST return a `LayerScope` for a scope that is, as a whole and with at most one pair of enclosing parentheses, `OnMid`, `ExistsOnLayer('<name>')`, or such `ExistsOnLayer` terms joined by `Or` (or `||`), and `None` for any other text; `parse_scope` keeps refusing every layer function. A layer condition is considered only for `Clearance`, only when `layers` is given, and only when the two scopes give equal `LayerScope` values (the same condition on both objects of a pair); otherwise the reason is `scope`.
  - `ExistsOnLayer`: each name MUST be the document's name of exactly one copper layer of the board, letter for letter, else `scope`. When the names are every copper layer of the board the record MUST map to a rule with `selector_a` `all`, no `selector_b` and `layers` = the neutral names of the board's copper layers from top to bottom. When they are some of the copper layers the reason MUST be `scope`, with a detail that names the other layers: a via or a through-hole pad that exists on a named layer is also judged on the others, where the neutral layer condition does not hold.
  - `OnMid`: on a board without an internal signal layer the reason MUST be `no-layer`; on a board with one the reason MUST be `scope`, because no permitted source says whether a via or a through-hole pad is on an internal signal layer.
- The neutral layer condition this relies on is that of `copper-check`, "Clearance in force": a clearance rule with `layers` is in force for a pair judged on one of those layers and for no other pair.
- `rulemap.lift(records, *, origin="rules", layers=None)` MUST pass `layers` to `map_rules`.

#### Scenario: The entry of the clearance matrix
- **GIVEN** a `Clearance` record for all objects with `GAP=10mil`, `OBJECTCLEARANCES` of one space and `ISMATRIX=TRUE`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k blank_matrix` maps it
- **THEN** it gives one `clearance` rule of 254 000 nm for all objects without layers, and the same record with `ISMATRIX=FALSE` is unmapped with `keys`

#### Scenario: A uniform matrix
- **GIVEN** a `Clearance` record with `GAP=10mil` whose three matrix entries all hold the count 100000
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k uniform_matrix` maps it
- **THEN** it gives one `clearance` rule of 254 000 nm

#### Scenario: Text that is no matrix
- **GIVEN** `Clearance` records whose `OBJECTCLEARANCES` is `x:1`, names the object kind `OutlineEdge`, or holds two entries for one pair of kinds
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k no_matrix` maps them
- **THEN** each is unmapped with `keys` and a detail that says which

#### Scenario: Every copper layer of the board
- **GIVEN** a board whose copper layers are `Top Layer` and `Bottom Layer`, and a `Clearance` record of 5 mil whose two scopes are `(ExistsOnLayer('Top Layer') Or ExistsOnLayer('Bottom Layer'))`, with the cell keys and `OUTERLAYERS=TRUE`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k outer_layers` maps it with those layers
- **THEN** it gives one `clearance` rule of 127 000 nm for all objects with `layers == ("F.Cu", "B.Cu")`

#### Scenario: Some of the copper layers
- **GIVEN** the same record and a board of four copper layers
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k stay_unmapped` maps it
- **THEN** it is unmapped with `scope` and the detail names `In1.Cu, In2.Cu`; without `layers`, with one scope `All`, or with a layer name the board does not hold it is unmapped with `scope` too

#### Scenario: No internal signal layer
- **GIVEN** a `Clearance` record whose two scopes are `OnMid`
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k inner_layers` maps it
- **THEN** on a board of two copper layers, and on one whose inner layers are planes, the reason is `no-layer`; on a board with an internal signal layer it is `scope`

#### Scenario: A clearance matrix on a two-layer board
- **GIVEN** three `Clearance` records: 5 mil for `OnMid` (priority 1), 5 mil for the two outer layers (priority 2) and 10 mil for all objects with `ISMATRIX=TRUE` (priority 3)
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_rule_map.py tests/unit/backends/altium/adapter/test_rules.py -k "matrix_on_two_layers or take_the_layers"` maps them for a board of two copper layers
- **THEN** the rules are the 5 mil rule on `F.Cu` and `B.Cu` and the 10 mil rule, and the first record is unmapped with `no-layer`

#### Scenario: A rule of some layers in the copper check
- **GIVEN** two pairs of parallel tracks 0.2 mm apart, one pair on `F.Cu` and one on `B.Cu`, a clearance rule of 0.1 mm and a clearance rule of 0.3 mm with `layers == ("B.Cu",)` and priority 1
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k rule_of_some_layers` runs the copper check
- **THEN** the one finding is the pair on `B.Cu`, against 0.3 mm

### Requirement: Rules onto the neutral model
`fenolite.backends.altium.read.rules.map_rules(records, *, origin, summary=False, layers=None)` SHALL return a `RuleMapping(ruleset, unmapped, issues, rule_records, matrix_cells)`. Each element of `records` is a field list: the `(key, value)` pairs of one rule in order, such as `PropRecord.fields`. Every input record appears exactly once: as the source of one or more rules of `ruleset` (two for a Routing Via Style; for a Clearance one and one more per cell of "Cells of an object matrix"), or as one `Unmapped(index, kind, name, reason, detail)`. No record MUST be dropped: `RuleMapping.sources`, the indexes of the records that gave at least one rule, and the indexes of `unmapped` MUST be disjoint and together MUST be every index of `records`.
- Only the kinds of the closed table `rules.RULE_KIND_MAP` map:

  | `RULEKIND` | neutral kind | limits | further conditions |
  |---|---|---|---|
  | `Clearance` | `clearance` | `min` = `GAP` | `NETSCOPE=DifferentNets`; `OBJECTCLEARANCES` absent, blank, uniform or a matrix that "Cells of an object matrix" reads; `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE`; the keys `ISMATRIX`, `SOURCERULE`, `CELLROWNAME`, `CELLROWTYPE`, `CELLCOLNAME`, `CELLCOLTYPE`, `INNERLAYERS` and `OUTERLAYERS` absent or with the values of "More forms of a Clearance record" |
  | `Width` | `track_width` | `min` = `MINLIMIT`, `opt` = `PREFEREDWIDTH`, `max` = `MAXLIMIT` | `NETSCOPE=AnyNet` |
  | `RoutingVias` | `via_diameter` and `via_drill` (two rules) | diameter: `MINWIDTH`, `WIDTH`, `MAXWIDTH`; drill: `MINHOLEWIDTH`, `HOLEWIDTH`, `MAXHOLEWIDTH` as `min`, `opt`, `max` | `NETSCOPE=AnyNet`; `VIASTYLE=Through Hole` |
  | `HoleSize` | `hole_size` | `min` = `MINLIMIT`, `max` = `MAXLIMIT` | `NETSCOPE=AnyNet`; `ABSOLUTEVALUES=TRUE`; `MINPERCENT` and `MAXPERCENT` are allowed and unused |
  | `BoardOutlineClearance` | `edge_clearance` | `min` = `GAP` | `NETSCOPE=DifferentNets`; `OBJECTCLEARANCES` absent or empty; `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE` |
  | `HoleToHoleClearance` | `hole_to_hole` | `min` = `GAP` | `NETSCOPE=AnyNet`; `ALLOWSTACKEDMICROVIAS=FALSE` |
  | `MinimumAnnularRing` | `annular_width` | `min` = `MINIMUMRING` | `NETSCOPE=AnyNet` |

- A record maps only when all of these hold, checked in this order; the first failure gives the reason:

  | reason | when |
  |---|---|
  | `summary-form` | `summary` is true (the values of a summary record carry no unit) |
  | `malformed` | no `RULEKIND`, no `NAME`, or `PRIORITY` is not a positive integer |
  | `no-counterpart` | the kind is not in `RULE_KIND_MAP` and not in `rules.PENDING_KINDS` |
  | `no-verified-keys` | the kind is in `rules.PENDING_KINDS`: the model has a counterpart, and no permitted source gives the record's keys. The table is empty since change c0084 |
  | `disabled` | `ENABLED` is not `TRUE` |
  | `net-scope` | `NETSCOPE` differs from the table |
  | `layer-kind` | `LAYERKIND` is not `SameLayer` |
  | `keys` | a key other than the header keys, the keys before `RULEKIND` and the kind's keys of the table is present, or a condition of the table fails |
  | `value` | a limit is missing where the table needs one (`GAP` of Clearance and BoardOutlineClearance; at least one limit otherwise), or is not a length |
  | `scope` | `SCOPE1EXPRESSION` or `SCOPE2EXPRESSION` is outside "Closed scope grammar" and the two are no layer condition that maps ("More forms of a Clearance record"), or `SCOPE2EXPRESSION` is not `All` for a kind other than `Clearance` |
  | `no-layer` | the two scopes are a layer condition for a kind of layer that the board does not hold, so the rule applies to no object ("More forms of a Clearance record") |

- The header keys are the closed tuple `rules.HEADER_KEYS`: `RULEKIND`, `NETSCOPE`, `LAYERKIND`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION`, `NAME`, `ENABLED`, `PRIORITY`, `COMMENT`, `UNIQUEID` and `DEFINEDBYLOGICALDOCUMENT`, the keys that every rule record of a PCB document holds after its common keys (`docs/formats/altium/pcb-copper.md`, c0038). So the rules that Fenolite's own writer puts in `Rules6` map without a `keys` reason.
- A mapped `Rule` MUST have: `name` = `NAME`; `priority` = `PRIORITY` (1 the highest, as in Altium); `severity = "error"`; `selector_a` from `SCOPE1EXPRESSION`; for `Clearance`, `selector_b` from `SCOPE2EXPRESSION`, `None` when it is `All`; `layers = ()`, or the neutral names of the board's copper layers for a layer condition that maps ("More forms of a Clearance record"); `native_ids == {"altium": UNIQUEID}` when the record has one; `id = derived_id("rul", "altium", "<origin>:<index>:<neutral kind>")`; and `ext["altium"]` an `ExtBag` whose payload starts with `("record", <the record text>)`; "Cells of an object matrix" adds one pair to it and says what a cell rule holds instead.
- A length MUST be a decimal number followed by `mil` or `mm` (`proptext.parse_length`). It MUST be converted exactly as a fraction and rounded half to even to the integer nanometre (`core.units.round_half_even_div`). No float MUST be used.
- For `RoutingVias`, a group (diameter or drill) without any of its three keys gives no rule; when both groups are empty the reason is `value`.
- `ruleset` MUST be a `RuleSet` with `id = derived_id("rst", "altium", origin)` and its rules in record order.
- Each `Unmapped` MUST add one info `altium.rule.unmapped` whose message names the rule, its kind and the reason, and whose `where` is `<origin>#<index>`. With `summary=True` a single info `altium.rule.summary-form` MUST be added first.
- `map_rules` MUST accept field lists from any source of the same keys, so that c0043 can pass the `fields` of the rule records of a PCB document (c0041), which hold every pair of the record. A caller MAY replace the id, the native id and the bag of a returned rule by its own (c0043 does). It MUST read the kind, name, priority, enabled state and scopes from the fields `RULEKIND`, `NAME`, `PRIORITY`, `ENABLED`, `SCOPE1EXPRESSION` and `SCOPE2EXPRESSION`.
- `layers` MUST be `None` or a `rules.CopperLayers`: the copper layers of the board the records belong to, from top to bottom, each a `CopperLayer(document_name, name, inner_signal)`. A rule file has no board, so its records are mapped without them.
- `rules.NOT_APPLYING` MUST be the reasons `disabled` and `no-layer`: an unmapped record with one of them takes no part in a check, and every other reason leaves a rule of the document unread.
- Fenolite MUST ship no rule values: every limit of `ruleset` comes from a record.

#### Scenario: Clearance and width
- **GIVEN** two export records: `Clearance` (`NETSCOPE=DifferentNets`, scopes `All` and `All`, `PRIORITY=1`, `GAP=6mil`) and `Width` (`NETSCOPE=AnyNet`, `SCOPE1EXPRESSION=InNetClass('PWR')`, `PRIORITY=1`, `MINLIMIT=10mil`, `PREFEREDWIDTH=20mil`, `MAXLIMIT=100mil`)
- **WHEN** `map_rules(records, origin="board.RUL")` is called
- **THEN** the rule set holds a `clearance` rule with `min == 152_400`, `selector_a` `all` and `selector_b is None`, and a `track_width` rule with `min == 254_000`, `opt == 508_000`, `max == 2_540_000` and `selector_a == Selector("netclass", "PWR")`; `unmapped == ()`

#### Scenario: Via style gives two rules
- **GIVEN** a `RoutingVias` record with `VIASTYLE=Through Hole`, `MINWIDTH=25mil`, `WIDTH=25mil`, `MAXWIDTH=50mil`, `MINHOLEWIDTH=12mil`, `HOLEWIDTH=12mil`, `MAXHOLEWIDTH=28mil`
- **WHEN** it is mapped
- **THEN** the rule set holds a `via_diameter` rule (`635_000`, `635_000`, `1_270_000`) and a `via_drill` rule (`304_800`, `304_800`, `711_200`), with the same name, priority and `native_ids`, and different ids

#### Scenario: Fenolite's own rules map
- **GIVEN** the field lists of the five rules that c0038's writer puts in `Rules6` of the blink sample (`Clearance_PWR`, `Clearance`, `Width_PWR`, `Width`, `RoutingVias`), each with the common keys before `RULEKIND` and every header key
- **WHEN** `map_rules(records, origin="blink.PcbDoc")` is called
- **THEN** `unmapped == ()` and the rule set holds two `clearance` rules, two `track_width` rules, one `via_diameter` rule and one `via_drill` rule

#### Scenario: Every other kind is reported
- **GIVEN** five records: `ShortCircuit`, `PlaneConnect`, `BoardOutlineClearance`, a disabled `Width`, and a `Clearance` whose `OBJECTCLEARANCES` is no object matrix
- **WHEN** they are mapped
- **THEN** the rule set is empty, `unmapped` has five entries with the reasons `no-counterpart`, `no-counterpart`, `net-scope` (the `BoardOutlineClearance` record has `NETSCOPE=AnyNet`), `disabled` and `keys` in record order, and the issues hold five infos `altium.rule.unmapped`

#### Scenario: Rounding to the nanometre
- **GIVEN** a `Clearance` record with `GAP=3.937mil`
- **WHEN** it is mapped
- **THEN** `min == 100_000` (99 999.8 nm rounded half to even) and no float appears in the rule

#### Scenario: Summary records are never mapped
- **GIVEN** the records of a summary-form file with three rules
- **WHEN** `map_rules(records, origin="out.RUL", summary=True)` is called
- **THEN** the rule set is empty, `unmapped` has three entries with the reason `summary-form`, and the first issue is `altium.rule.summary-form`

#### Scenario: The count holds on the corpus
- **GIVEN** the fetched rule files of the corpus
- **WHEN** `uv run pytest tests/corpus/test_altium_text.py -k rules` runs
- **THEN** for each file `sources` and the indexes of `unmapped` are disjoint and together are every record index
