## MODIFIED Requirements

### Requirement: Design rule records
`pcbdoc.write_pcbdoc` SHALL write `Rules6` with the lowered rules of the design (`PcbDocSpec.design_rules`, the records of `rulemap.lower`; "Rule lowering table", "Scoped rule records") and with Clearance, Width and Routing Via Style rules from the net classes (S-0160, S-0161, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-RULES`). The rules of the net classes and the `All` defaults MUST be written only when the spec holds a track, an arc, a via, a zone or a net class, and only for the kinds of `PcbDocSpec.class_kinds`; the rules of the design are written whenever the spec holds them. With neither, and with `PcbDocSpec.rules` off, `Rules6` MUST be empty.
- A build (`lower.from_design` with `options`, change c0126), whose net classes the user wrote, MUST set `class_kinds` to Clearance, Width and RoutingVias. A write of a model (`lower.write_design`, a conversion, `AltiumBackend.write`) MUST write the records of the design's rules, the rules a source record or the user gave, and of the c0038 rules only those KiCad checks (change c0434): `class_kinds` MUST be Clearance alone, and empty when a Clearance record of the design has the scopes `All` and `All`, which overrides every class clearance as an unconditioned KiCad rule does. A class's track width and via size MUST NOT be written as rules: KiCad does not check them, a KiCad project gives every class a value, and a board converted from Altium gets KiCad's defaults there. Each written net class with a value that is left out MUST be counted `changed` under `netclass`.
- A rule of the design that gives fewer limits than its record holds MUST stay refused (`value-unsupported`, "Rule lowering table"): no limit is invented for a board or class minimum.
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

#### Scenario: A conversion writes only the rules of its source
- **GIVEN** the public document `altium-third-party-pcbdoc-08` converted to KiCad, whose project holds 14 net classes with KiCad's default values and whose rules file holds 8 rules
- **WHEN** the project is converted back to Altium with `--altium-pour outline`
- **THEN** the written document holds no rule scoped `InNetClass(...)` and no `All` default, 4 Clearance and 1 Width record as the source, the Width limits equal to the source's, no more records of a kind than the source holds; the 14 net classes are counted `changed` under `netclass`

#### Scenario: A KiCad board without a rules file keeps its class clearances
- **GIVEN** a model with a net class that holds a clearance, a track width and a via size, and no rule of its own
- **WHEN** `lower.from_design` lowers it without options
- **THEN** `class_kinds` is Clearance alone: the class's Clearance record and the `All` Clearance are written, no class Width or Routing Via Style record, and the class is counted `changed`; with a clearance rule on every object `class_kinds` is empty

## ADDED Requirements

### Requirement: Source rule records written back
`PcbDocSpec.source_rules` SHALL hold the rule records of the Altium document a conversion started from (change c0434), each its kind number and its keys from `RULEKIND` on; it is empty for every build. With records there, `rule_records` SHALL write:
- first each record as it is, in its order, after the common keys;
- then each lowered rule of `spec.design_rules` with the next priority of its kind and a name not yet written (`_2`, `_3`…);
- then the kept records (change c0424).
- No rule of a net class and no `All` default MUST be written. The Plane Connect and Plane Clearance rules of c0389 are written only for a kind that no record holds. The Polygon Connect Style records lowered from the zones MUST NOT be written when a record is of that kind.

#### Scenario: Records and one lowered rule
- **GIVEN** a spec whose `source_rules` hold a Width named `Signal Width` of priority 3 and whose design rules lower to one Width named `Signal Width`
- **WHEN** `write_pcbdoc` runs
- **THEN** `Rules6` holds the record as given, then a Width named `Signal Width_2` of priority 4, and no other Width, Clearance or Routing Via Style record
