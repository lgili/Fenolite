## ADDED Requirements

### Requirement: More rule kinds onto the neutral model
The reading of Altium rules onto the neutral model SHALL map every kind that `rulemap.TABLE` marks `exact`, from rule records of a PCB document and from rule files alike, and `PENDING_KINDS` SHALL hold no kind of the table.
- `read.rules.RULE_KIND_MAP` MUST hold every Altium kind of an `exact` row, with the limit keys and the `NETSCOPE` of the row.
- A rule of a mapped kind whose scope is outside the closed grammar MUST stay listed with the reason it is not mapped, as today.
- Kinds outside the table MUST stay opaque and counted.

#### Scenario: Board outline clearance
- **GIVEN** a corpus PCB document whose rules hold a board outline clearance for all objects
- **WHEN** `uv run pytest tests/corpus/test_altium_rule_kinds.py -k outline` imports it
- **THEN** the neutral rules hold that edge clearance, and the import lists no pending kind

### Requirement: Rule file written
`fenolite.backends.altium.rulemap.write_rule_file(rules, *, name="rules")` SHALL return the bytes of an Altium rule file in the export form that holds the rules of `rules` that `rulemap.lower` writes, one record per line in the order of the lowering. It lives beside the table, not in `read/rul.py`, because the text readers import no writer.
- Each record MUST hold the six common keys of `read.rul.RULE_FILE_COMMON`, the header keys and the constraint keys of the record, joined by `|`, with `UNIQUEID` = `project.unique_id("rul:<name>:rule:<rule name>")`.
- `read_rule_file(write_rule_file(rules))` mapped onto the neutral model MUST give the lowered subset of `rules`, with no unmapped record.
- The bytes MUST use the line end and the encoding that `docs/formats/altium/rule-file.md` records for the file that Altium saved: each record ends with the single byte `B6` and LF, and every other byte is 7-bit ASCII.
- Without a lowered rule the result MUST be empty; that is no rule file, and a caller writes none.

#### Scenario: Written file reads back
- **WHEN** `uv run pytest tests/unit/exports/test_altium_rul.py -k readback` writes and reads the rules of every example script and one rule of every `exact` kind
- **THEN** the rules read equal the lowered subset

## MODIFIED Requirements

### Requirement: Rules onto the neutral model
`fenolite.backends.altium.read.rules.map_rules(records, *, origin, summary=False)` SHALL return a `RuleMapping(ruleset, unmapped, issues)`. Each element of `records` is a field list: the `(key, value)` pairs of one rule in order, such as `PropRecord.fields`. Every input record appears exactly once: as the source of one or two rules of `ruleset`, or as one `Unmapped(index, kind, name, reason, detail)`. No record MUST be dropped: `RuleMapping.sources`, the indexes of the records that gave at least one rule, and the indexes of `unmapped` MUST be disjoint and together MUST be every index of `records`.
- Only the kinds of the closed table `rules.RULE_KIND_MAP` map:

  | `RULEKIND` | neutral kind | limits | further conditions |
  |---|---|---|---|
  | `Clearance` | `clearance` | `min` = `GAP` | `NETSCOPE=DifferentNets`; `OBJECTCLEARANCES` absent or empty; `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE` |
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
  | `scope` | `SCOPE1EXPRESSION` or `SCOPE2EXPRESSION` is outside "Closed scope grammar", or `SCOPE2EXPRESSION` is not `All` for a kind other than `Clearance` |

- The header keys are the closed tuple `rules.HEADER_KEYS`: `RULEKIND`, `NETSCOPE`, `LAYERKIND`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION`, `NAME`, `ENABLED`, `PRIORITY`, `COMMENT`, `UNIQUEID` and `DEFINEDBYLOGICALDOCUMENT`, the keys that every rule record of a PCB document holds after its common keys (`docs/formats/altium/pcb-copper.md`, c0038). So the rules that Fenolite's own writer puts in `Rules6` map without a `keys` reason.
- A mapped `Rule` MUST have: `name` = `NAME`; `priority` = `PRIORITY` (1 the highest, as in Altium); `severity = "error"`; `selector_a` from `SCOPE1EXPRESSION`; for `Clearance`, `selector_b` from `SCOPE2EXPRESSION`, `None` when it is `All`; `layers = ()`; `native_ids == {"altium": UNIQUEID}` when the record has one; `id = derived_id("rul", "altium", "<origin>:<index>:<neutral kind>")`; and `ext["altium"]` an `ExtBag` whose payload is `(("record", <the record text>),)`.
- A length MUST be a decimal number followed by `mil` or `mm` (`proptext.parse_length`). It MUST be converted exactly as a fraction and rounded half to even to the integer nanometre (`core.units.round_half_even_div`). No float MUST be used.
- For `RoutingVias`, a group (diameter or drill) without any of its three keys gives no rule; when both groups are empty the reason is `value`.
- `ruleset` MUST be a `RuleSet` with `id = derived_id("rst", "altium", origin)` and its rules in record order.
- Each `Unmapped` MUST add one info `altium.rule.unmapped` whose message names the rule, its kind and the reason, and whose `where` is `<origin>#<index>`. With `summary=True` a single info `altium.rule.summary-form` MUST be added first.
- `map_rules` MUST accept field lists from any source of the same keys, so that c0043 can pass the `fields` of the rule records of a PCB document (c0041), which hold every pair of the record. A caller MAY replace the id, the native id and the bag of a returned rule by its own (c0043 does). It MUST read the kind, name, priority, enabled state and scopes from the fields `RULEKIND`, `NAME`, `PRIORITY`, `ENABLED`, `SCOPE1EXPRESSION` and `SCOPE2EXPRESSION`.
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
- **GIVEN** five records: `ShortCircuit`, `PlaneConnect`, `BoardOutlineClearance`, a disabled `Width`, and a `Clearance` whose `OBJECTCLEARANCES` is not empty
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
