## ADDED Requirements

### Requirement: Rule lowering table
`fenolite.backends.altium.rulemap.TABLE` SHALL be the closed table that maps each neutral rule kind to the Altium rule kind that carries it. Each row MUST hold the neutral kind, the Altium kind and its kind number, the limits a rule must give, the constraint fields in written order, the `NETSCOPE`, the scope forms it supports, and either `exact` or one reason of `NOT_LOWERED_REASONS` (`no-counterpart`, `scope-unsupported`, `value-unsupported`, `unit-loss`) with a note.
- Every neutral rule kind of `model/rules.py` MUST have a row. A row MUST be `exact` only when `docs/formats/altium/pcb-copper.md` ("Rule kinds lowered") records, with a public source and a label, the Altium constraint and the keys of its record. The `exact` rows are: `clearance` → `Clearance` (0), `track_width` → `Width` (2), `via_diameter` and `via_drill` → `RoutingVias` (11), `hole_size` → `HoleSize` (42), `edge_clearance` → `BoardOutlineClearance` (63), `hole_to_hole` → `HoleToHoleClearance` (52), `annular_width` → `MinimumAnnularRing` (19). `hole_clearance`, `courtyard_clearance`, `silk_clearance` and `creepage` are `no-counterpart`.
- `lower(rules)` MUST return the rule records of the rules it writes and, for every rule that is not written, its kind, selector and reason. A rule is written only when its row is `exact`, its severity is `error`, it gives exactly the limits of its row (`min` for a clearance kind, `hole_to_hole` and `annular_width`; `min` and `max` for `hole_size`; `min`, `opt` and `max` for `track_width`, `via_diameter` and `via_drill`), and each value is 0 or at least one PCB unit and inside the 32-bit range; otherwise the reason is `value-unsupported`. `lower` MUST never write a rule whose value or scope differs from the neutral rule's beyond the 2 nm of the PCB unit.
- A `via_diameter` and a `via_drill` rule of the same selector MUST share one `RoutingVias` record; either one without the other MUST be `value-unsupported`.
- Fixed constraint values: `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE` and an empty `OBJECTCLEARANCES` (Clearance, BoardOutlineClearance), `VIASTYLE=Through Hole`, `ABSOLUTEVALUES=TRUE` with `MAXPERCENT=80.000` and `MINPERCENT=20.000`, and `ALLOWSTACKEDMICROVIAS=FALSE`.
- `lift(records)` MUST return the neutral rules of the records that `read.rules.map_rules` maps, in record order, and the count of the others by Altium kind.
- `lift(lower(rules).records)` MUST equal the lowered subset of `rules` (`Lowered.written`) in kind, selectors and limits within 2 nm (`rulemap.same_rules`); the priority of a lifted rule is the record's, which counts within its Altium kind.

#### Scenario: Every kind has a row
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k complete` compares the kinds of `model/rules.py` with `TABLE` and with the table "The lowering table" of `docs/formats/altium/pcb-copper.md`
- **THEN** every kind has exactly one row, the page's table equals `TABLE`, and every `exact` row is cited on the page with a source and is a kind of `read.rules.RULE_KIND_MAP`

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

### Requirement: Scoped rule records
Rule records SHALL carry the scope of their rule as an expression of the closed scope grammar of `altium-project-reader` ("Closed scope grammar"): all objects (`All`), a net (`InNet('<net>')`), a net class (`InNetClass('<class>')`), and the conjunction of those with `And`; a `clearance` rule with a second selector uses both scope fields, and every other kind writes `All` as its second scope. Every written scope MUST be one that `read.scope.parse_scope` turns back into the rule's selector.
- A layer is not a written scope: the closed grammar refuses layer functions, so a rule with `layers` or a `layer` selector MUST give `scope-unsupported`.
- Rules of one Altium kind MUST be written from the most governing neutral rule to the least (priority 1, 2, … and then priority 0; ties by falling name, then id), with `PRIORITY` from 1 in that order within the kind. This is the reverse of the order of a KiCad rules file, where the last rule governs.
- A selector outside the written forms (a glob, a value that holds `'` or cannot be written, `ref`, `item_kind`, `or`, `not`, a second selector for a kind other than `clearance`) MUST give the reason `scope-unsupported` for that rule only; the other rules of the kind are written.
- Rule names MUST be unique in the document and derived from the kind and the scopes (`<Kind>`, `<Kind>_<class>`, `<Kind>_net_<net>`, `_and_` between the parts of a conjunction, `_to_` before the second scope; a repeated name gets `_2`, `_3`…), so that two builds give equal names.

#### Scenario: Class rule above the general rule
- **GIVEN** a design with a track width (minimum, preferred and maximum) for all nets and another, of priority 1, for the class `PWR`
- **WHEN** the PCB document is written and read back
- **THEN** two Width rules exist, `Width_PWR` with the scope `InNetClass('PWR')` and `PRIORITY=1`, and `Width` with the scope `All` and `PRIORITY=2`

#### Scenario: A scope outside the grammar
- **GIVEN** a `track_width` rule on the net glob `PWR_*`, a second on the layer `F.Cu` and a third on the class `PWR`
- **WHEN** `lower` runs
- **THEN** one record `Width_PWR` is written, and the two others are named with the reason `scope-unsupported`

## MODIFIED Requirements

### Requirement: Design rule records
`pcbdoc.write_pcbdoc` SHALL write `Rules6` with the lowered rules of the design (`PcbDocSpec.design_rules`, the records of `rulemap.lower`; "Rule lowering table", "Scoped rule records") and with Clearance, Width and Routing Via Style rules from the net classes (S-0160, S-0161, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-RULES`). The rules of the net classes and the `All` defaults MUST be written only when the spec holds a track, an arc, a via, a zone or a net class; the rules of the design are written whenever the spec holds them. With neither, and with `PcbDocSpec.rules` off, `Rules6` MUST be empty.
- Each rule MUST be a 16-bit rule-kind number (0 Clearance, 2 Width, 11 RoutingVias, 42 HoleSize, 63 BoardOutlineClearance, 52 HoleToHoleClearance, 19 MinimumAnnularRing), then one property block with, in this order: the seven common keys with `LAYER=TOP`, `RULEKIND`, `NETSCOPE` (`DifferentNets` for Clearance and BoardOutlineClearance, `AnyNet` otherwise), `LAYERKIND=SameLayer`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION` (`All`, or the second scope of a Clearance rule of the design), `NAME`, `ENABLED=TRUE`, `PRIORITY`, `COMMENT` (empty), `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:rule:<name>")`, `DEFINEDBYLOGICALDOCUMENT=FALSE`, then the kind's keys.
- Kind keys: Clearance `GAP`, `GENERICCLEARANCE`, `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE`, `OBJECTCLEARANCES` (empty); Width `MAXLIMIT`, `MINLIMIT`, `PREFEREDWIDTH`; RoutingVias `HOLEWIDTH`, `WIDTH`, `VIASTYLE=Through Hole`, `MINHOLEWIDTH`, `MINWIDTH`, `MAXHOLEWIDTH`, `MAXWIDTH`; HoleSize `ABSOLUTEVALUES=TRUE`, `MAXLIMIT`, `MINLIMIT`, `MAXPERCENT=80.000`, `MINPERCENT=20.000`; BoardOutlineClearance the keys of Clearance; HoleToHoleClearance `GAP`, `ALLOWSTACKEDMICROVIAS=FALSE`; MinimumAnnularRing `MINIMUMRING`; lengths as mil text.
- Per kind, one rule `<Kind>_<class>` with `SCOPE1EXPRESSION=InNetClass('<class>')` MUST be written for each class that holds the kind's value (clearance; track width; via diameter and drill), in class-name order with `PRIORITY` from 1, then one rule named `Clearance`, `Width` or `RoutingVias` with `SCOPE1EXPRESSION=All` and the next priority. The rules of one kind are written together, in the order of `rulemap.KIND_ORDER`: Clearance, Width, RoutingVias, HoleSize, BoardOutlineClearance, HoleToHoleClearance, MinimumAnnularRing.
- Within a kind the rules of the design MUST come first, in the order of `rulemap.lower`, then the class rules and the `All` rule; `PRIORITY` counts from 1 over them all. A class rule or `All` rule whose two scopes are those of a rule of the design MUST be left out: the design's rule replaces it. A class rule whose name a rule of the design holds gets the suffix `_class`.
- The `All` rules MUST use `pcbdoc.DEFAULT_CLEARANCE` (0.2 mm), `DEFAULT_TRACK_WIDTH` (0.25 mm), `DEFAULT_VIA_DIAMETER` (0.6 mm) and `DEFAULT_VIA_DRILL` (0.3 mm), Fenolite's choices.
- A class or `All` width rule's `MINLIMIT` and `MAXLIMIT` MUST be the smallest and the largest of the preferred width and the widths of the written tracks and arcs in its scope; a via rule's minimum and maximum likewise over the written vias. So the written copper never breaks the width or via rule of a net class or the default; a rule of the design holds the limits of the script exactly, and the copper may break it.

#### Scenario: Rules of the blink sample
- **WHEN** `Rules6` of the blink sample is read
- **THEN** it holds five rules in this order: `Clearance_PWR` (kind 0, `GAP=7.874mil`, priority 1), `Clearance` (priority 2, `GAP=7.874mil`), `Width_PWR` (kind 2, `PREFEREDWIDTH=19.685mil`, priority 1), `Width` (priority 2, `PREFEREDWIDTH=9.8425mil`) and `RoutingVias` (kind 11, priority 1, `WIDTH=23.622mil`, `HOLEWIDTH=11.811mil`)

#### Scenario: Limits follow the copper
- **GIVEN** a class `PWR` with track width 0.5 mm and tracks of 0.4 mm and 1.0 mm on its nets
- **WHEN** `Width_PWR` is read
- **THEN** `MINLIMIT` is `15.748mil`, `PREFEREDWIDTH` is `19.685mil` and `MAXLIMIT` is `39.3701mil`

#### Scenario: A rule of the design replaces the default of its scope
- **GIVEN** the blink sample with a `clearance` rule of 0.15 mm for all objects and an `edge_clearance` rule of 0.5 mm
- **WHEN** `Rules6` is read
- **THEN** it holds, in this order, `Clearance` (`GAP=5.9055mil`, priority 1), `Clearance_PWR` (priority 2), `Width_PWR`, `Width`, `RoutingVias` and `BoardOutlineClearance` (kind 63, `GAP=19.685mil`, priority 1), and no second rule with the scope `All` of the kind Clearance
