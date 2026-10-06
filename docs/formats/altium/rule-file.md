# Altium rule file (`.RUL`) and the mapping of rules

This page states, in Fenolite's own words, what the rule-file reader
`fenolite.backends.altium.read.rul`, the scope parser `read.scope` and the rule mapper `read.rules`
(change c0042) rely on. Two different files carry the extension `.RUL`: the export of the PCB rules
editor and a short summary written beside Gerber outputs. The sources are Altium's public documentation
(S-0294, S-0295, S-0296), public rule files saved by Altium Designer (S-0297 for the export form;
S-0298 and S-0188 for the summary form; corpus rows `altium-third-party-rules-01` to `-03`), fetched to
the corpus cache and never committed, and the facts that KiCad's importer states about a board's rule
records (S-0160, S-0161; facts only, nothing transcribed or followed). No reader of a `.RUL` file is
known to `kicad-cli`, so nothing here is `ORACLE-VERIFIED`, and the meaning of the keys stays
`INFERRED` whatever the corpus shows.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| The PCB rules editor exports a selection of rules to a `.RUL` file and imports rules from one | S-0294 | INFERRED | H-A-RD-PRJ-RUL-EXPORT |
| In the export form each line is one rule record: `KEY=VALUE` parts joined by `\|`, with no `\|` before the first part. Each line ends with a pilcrow sign and then LF; in the public file the pilcrow is the single byte `B6`, so the file is not UTF-8 | S-0297 | INFERRED | H-A-RD-PRJ-RUL-EXPORT |
| A record of the export form holds the keys of a board's rule record: first the common keys of a document's property record (`SELECTION`, `LAYER`, `LOCKED`, …), then `RULEKIND`, `NETSCOPE`, `LAYERKIND`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION`, `NAME`, `ENABLED`, `PRIORITY`, `COMMENT`, `UNIQUEID`, `DEFINEDBYLOGICALDOCUMENT`, then the keys of the rule kind | S-0297, S-0160 | INFERRED | H-A-RD-PRJ-RUL-EXPORT |
| The summary form starts with a line `DRC Rules Export File for PCB: <path of the board>`; each further line is `RuleKind=<kind>\|RuleName=<name>\|Scope=Board\|<key>=<number>`, with the value key `Minimum` or `Allowed` and a number without unit. Lines end with CR LF. The first line can hold an absolute path on its author's machine | S-0298, S-0188 | INFERRED | H-A-RD-PRJ-RUL-SUMMARY |
| Rules fall into ten categories; a rule is unary or binary (a binary rule has two scopes); its scope is All, a net, a net class, a layer, a net and a layer, or a custom query. Each rule has a name, a comment, a unique id and an enabled state | S-0294 | INFERRED | H-A-RD-PRJ-RULE-MAP |
| Priority 1 is the highest. Of the rules of one kind, the first one whose scopes match an object applies; a disabled rule is skipped | S-0294 | INFERRED | H-A-RD-PRJ-RULE-MAP |
| Clearance has net options (for example different nets only) and holds either one value or a matrix of values per object pair | S-0295 | INFERRED | H-A-RD-PRJ-RULE-MAP |
| Width has a minimum, a preferred and a maximum width; the minimum and the maximum are checked | S-0295 | INFERRED | H-A-RD-PRJ-RULE-MAP |
| Routing Via Style has a via diameter and a via hole, each with a minimum, a preferred and a maximum | S-0295 | INFERRED | H-A-RD-PRJ-RULE-MAP |
| Hole Size holds a minimum and a maximum, either as absolute values or as percentages | S-0295 | INFERRED | H-A-RD-PRJ-RULE-MAP |
| Board Outline Clearance exists as a rule kind. Its record holds the keys of Clearance; the records of Hole To Hole Clearance and Minimum Annular Ring hold `GAP` with `ALLOWSTACKEDMICROVIAS`, and `MINIMUMRING` (`pcb-copper.md`, "Rule kinds lowered", from public PCB documents; change c0084) | S-0295, S-0460, S-0174, S-0199, S-0200 | INFERRED | H-A-RULE-KINDS |
| The rule keys used by the mapping: `GAP`, `GENERICCLEARANCE`, `OBJECTCLEARANCES` and `IGNOREPADTOPADCLEARANCEINFOOTPRINT` of Clearance; `MINLIMIT`, `PREFEREDWIDTH` and `MAXLIMIT` of Width; `WIDTH`, `MINWIDTH`, `MAXWIDTH`, `HOLEWIDTH`, `MINHOLEWIDTH`, `MAXHOLEWIDTH` and `VIASTYLE` of Routing Via Style; `ABSOLUTEVALUES`, `MINLIMIT`, `MAXLIMIT`, `MINPERCENT` and `MAXPERCENT` of Hole Size | S-0160, S-0161, S-0297 | INFERRED | H-A-RD-PRJ-RULE-MAP |
| A length in a rule record is a decimal number followed by `mil` (or `mm`), such as `6mil` | S-0163, S-0297 | INFERRED | H-A-RD-PRJ-RULE-MAP |
| A scope is a query: membership functions (`InNet`, `InNetClass`, `InComponent`, …), object-type checks (`IsTrack`, `IsVia`, `IsPad`, …), layer checks (`OnLayer`, …) and the logical operators `And`, `Or`, `Not`. The documentation does not state the precedence of the operators | S-0296 | INFERRED | H-A-RD-PRJ-SCOPE |
| The layer checks of the query language test an object: `OnMid` is true for an object on an internal signal layer; `OnOutside` for an object on the top or the bottom layer, and an object on Multi-Layer is not returned by it; `OnPlane` for an object on an internal plane layer. The entry of `OnMid` does not say whether an object on Multi-Layer is returned | S-0555 | INFERRED | H-A-RULE-CLEARANCE-FORMS |
| `ExistsOnLayer('<name>')` is true for an object that exists on the named layer, and it is the function to use for an object on Multi-Layer that has a shape on the layer; the name is the layer's name as the layer list of the board shows it | S-0556, S-0555 | INFERRED | H-A-RULE-CLEARANCE-FORMS |
| The Constraint Manager holds the clearances as a matrix between net classes, with one entry from all net classes to all net classes by default; the value of a cell is given for all layers, for the outer layers, for the inner layers or for one layer, and the more specific one applies. Each pair of classes with a value is shown as a rule of its own | S-0557 | INFERRED | H-A-RULE-CLEARANCE-FORMS |
| In the Clearance rule one value is copied to every cell of the matrix of object kinds; an option leaves the clearances between the pads of one footprint unchecked | S-0558 | INFERRED | H-A-RULE-CLEARANCE-FORMS |
| A PCB document with a clearance matrix holds one Clearance record with `ISMATRIX=TRUE` for all objects, and one record per layer set of a cell: these hold `SOURCERULE` (the zero-based position of the `ISMATRIX` record among the rule records), `CELLROWNAME=All`, `CELLROWTYPE=0`, `CELLCOLNAME=All`, `CELLCOLTYPE=0`, and `INNERLAYERS=TRUE` with both scopes `OnMid`, or `OUTERLAYERS=TRUE` with both scopes an `Or` of `ExistsOnLayer` of the top and of the bottom layer's name. The cell records have the higher priorities. All three hold `OBJECTCLEARANCES` of one space | S-0172 (three records of one document) | CORPUS-VERIFIED (2026-10-06; test_altium_rule_kinds.py) | H-A-RULE-CLEARANCE-FORMS |
| An entry of `OBJECTCLEARANCES` is `ClearanceObj_<kind>-ClearanceObj_<kind>:<count>`, entries joined by `;`. In the four Clearance matrices of the public documents (27, 8, 8 and 1 entries) no entry holds the count of its record's `GAP` read as 0.0001 mil, and the eight distinct counts above zero are round lengths in that unit (0.1, 0.25, 0.4 and 0.55 mm; 3.5, 6, 10 and 15 mil) | S-0175, S-0176, S-0187 | CORPUS-VERIFIED (2026-10-06; test_altium_rule_kinds.py) | H-A-RULE-CLEARANCE-FORMS |
| A count of `OBJECTCLEARANCES` is 0.0001 mil (2.54 nm, the unit of the document's coordinates), and a cell that the text leaves out holds the generic value; so a text whose every entry holds the length of `GAP` says one clearance | S-0558, S-0175, S-0176, S-0187 | INFERRED | H-A-RULE-CLEARANCE-FORMS |

## Header keys

`rules.HEADER_KEYS`: the keys that every rule record of a PCB document holds after its common keys
(`pcb-copper.md`, "Rules"): `RULEKIND`, `NETSCOPE`, `LAYERKIND`, `SCOPE1EXPRESSION`,
`SCOPE2EXPRESSION`, `NAME`, `ENABLED`, `PRIORITY`, `COMMENT`, `UNIQUEID` and
`DEFINEDBYLOGICALDOCUMENT`. The keys before `RULEKIND` are allowed and not read.

## Rule kinds that map

`rules.RULE_KIND_MAP`: a record maps only when its kind is in this table, its `NETSCOPE` is the one
given, its `LAYERKIND` is `SameLayer`, its other keys are header keys or keys of its row, and the
further conditions hold. Routing Via Style gives two neutral rules. A dash is a limit the kind does not
give.

| RULEKIND | neutral kind | min | opt | max | net scope | further conditions |
|---|---|---|---|---|---|---|
| `Clearance` | `clearance` | `GAP` | — | — | `DifferentNets` | `OBJECTCLEARANCES` absent, blank or uniform; `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE`; `ISMATRIX`, `SOURCERULE`, `CELLROWNAME`, `CELLROWTYPE`, `CELLCOLNAME`, `CELLCOLTYPE`, `INNERLAYERS` and `OUTERLAYERS` absent or as in "Clearance forms that map" |
| `Width` | `track_width` | `MINLIMIT` | `PREFEREDWIDTH` | `MAXLIMIT` | `AnyNet` | — |
| `RoutingVias` | `via_diameter` | `MINWIDTH` | `WIDTH` | `MAXWIDTH` | `AnyNet` | `VIASTYLE` is `Through Hole` |
| `RoutingVias` | `via_drill` | `MINHOLEWIDTH` | `HOLEWIDTH` | `MAXHOLEWIDTH` | `AnyNet` | `VIASTYLE` is `Through Hole` |
| `HoleSize` | `hole_size` | `MINLIMIT` | — | `MAXLIMIT` | `AnyNet` | `ABSOLUTEVALUES` is `TRUE`; `MINPERCENT` and `MAXPERCENT` allowed and unused |
| `BoardOutlineClearance` | `edge_clearance` | `GAP` | — | — | `DifferentNets` | `OBJECTCLEARANCES` absent or empty; `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE` |
| `HoleToHoleClearance` | `hole_to_hole` | `GAP` | — | — | `AnyNet` | `ALLOWSTACKEDMICROVIAS` is `FALSE` |
| `MinimumAnnularRing` | `annular_width` | `MINIMUMRING` | — | — | `AnyNet` | — |

`rules.PENDING_KINDS`: kinds that have a neutral counterpart but no permitted source for their keys,
reported apart with the reason `no-verified-keys`. The table is empty since change c0084, which found the
keys of `BoardOutlineClearance` in public PCB documents; the reason stays for a later kind.

The last three kinds of the table are those of change c0084: the table holds every Altium kind of an
`exact` row of `rulemap.TABLE` (`pcb-copper.md`, "The lowering table"), so what Fenolite writes it reads.
A Hole To Hole Clearance with `ALLOWSTACKEDMICROVIAS=TRUE` exempts the holes of stacked microvias, which
the neutral rule does not, so it is reported with the reason `keys`.

## Rule kinds seen

Every rule kind that the rule files of the corpus hold (`docs/evidence/altium-project-read.md`), with the
number of records in the export form and the number of summary-form files that list it. A kind that
maps is in `RULE_KIND_MAP`; every other kind is reported as `no-counterpart`. The summary form maps
nothing (`summary-form`). `BoardOutlineClearance` and `MinimumAnnularRing` are in no rule file of the
corpus: their rows count the rule records of the corpus PCB documents (`pcb-copper.md`, "Rule kinds
lowered").

| RULEKIND seen | records | source | maps |
|---|---|---|---|
| `AssemblyTestpoint` | export (1) | S-0297 | no |
| `AssemblyTestPointUsage` | export (2) | S-0297 | no |
| `BoardOutlineClearance` | PCB documents (8 in 5 documents) | S-0174, S-0175, S-0187, S-0199, S-0200 | yes: `edge_clearance` |
| `Clearance` | export (1); summary (2 files) | S-0297, S-0298, S-0188 | yes: `clearance` |
| `ComponentClearance` | export (1) | S-0297 | no |
| `DiffPairsRouting` | export (1) | S-0297 | no |
| `FabricationTestpoint` | export (1) | S-0297 | no |
| `FabricationTestPointUsage` | export (1) | S-0297 | no |
| `FanoutControl` | export (5) | S-0297 | no |
| `Height` | export (1) | S-0297 | no |
| `HoleSize` | export (1) | S-0297 | yes: `hole_size` |
| `HoleToHoleClearance` | export (1) | S-0297 | yes: `hole_to_hole` |
| `LayerPairs` | export (1) | S-0297 | no |
| `MatchedLengths` | export (1) | S-0297 | no |
| `MinimumAnnularRing` | PCB documents (4 in 3 documents) | S-0174, S-0199, S-0200 | yes: `annular_width` |
| `MinimumSolderMaskSliver` | export (4) | S-0297 | no |
| `NetAntennae` | export (1) | S-0297 | no |
| `PasteMaskExpansion` | export (1) | S-0297 | no |
| `PlaneClearance` | export (1) | S-0297 | no |
| `PlaneConnect` | export (1) | S-0297 | no |
| `PolygonConnect` | export (1) | S-0297 | no |
| `RoomDefinition` | export (9) | S-0297 | no |
| `RoutingCorners` | export (1) | S-0297 | no |
| `RoutingLayers` | export (1) | S-0297 | no |
| `RoutingPriority` | export (1) | S-0297 | no |
| `RoutingTopology` | export (1) | S-0297 | no |
| `RoutingVias` | export (1) | S-0297 | yes: `via_diameter` and `via_drill` |
| `ShortCircuit` | export (1); summary (2 files) | S-0297, S-0298, S-0188 | no |
| `SilkToBoardRegionClearance` | export (1) | S-0297 | no |
| `SilkToSilkClearance` | export (1) | S-0297 | no |
| `SilkToSolderMaskClearance` | export (1) | S-0297 | no |
| `SolderMaskExpansion` | export (1); summary (2 files) | S-0297, S-0298, S-0188 | no |
| `UnRoutedNet` | export (1) | S-0297 | no |
| `Width` | export (1); summary (2 files) | S-0297, S-0298, S-0188 | yes: `track_width` |

## Reasons

`rules.UNMAPPED_REASONS`: every record that gives no rule is listed with the first reason that holds,
checked in this order.

| reason | when |
|---|---|
| `summary-form` | the records come from a summary-form file: its values carry no unit |
| `malformed` | no `RULEKIND`, no `NAME`, or `PRIORITY` is not a positive integer |
| `no-counterpart` | the kind is neither in `RULE_KIND_MAP` nor in `PENDING_KINDS` |
| `no-verified-keys` | the kind is in `PENDING_KINDS` (empty since c0084) |
| `disabled` | `ENABLED` is not `TRUE` |
| `net-scope` | `NETSCOPE` differs from the table |
| `layer-kind` | `LAYERKIND` is not `SameLayer` |
| `keys` | a key outside the header keys, the keys before `RULEKIND` and the keys of the kind, or a further condition fails |
| `value` | a limit the table needs is missing (`GAP`; at least one limit otherwise) or is not a length |
| `scope` | a scope is outside the closed grammar and the two are no layer condition that maps, or `SCOPE2EXPRESSION` is not `All` for a unary kind |
| `no-layer` | the two scopes are a layer condition for a kind of layer the board does not hold: the rule applies to no object ("Layer scopes of Clearance") |

## Closed scope grammar

`scope.parse_scope` accepts only these forms, spelled as written, and returns a neutral selector; any
other text is refused with a reason and the rule is reported with the reason `scope`.

| expression | selector |
|---|---|
| `All` | `all` |
| `InNet('v')` | `net v` |
| `InNetClass('v')` | `netclass v` |
| `InComponent('v')` | `ref v` |
| `IsTrack` | `item_kind track` |
| `IsVia` | `item_kind via` |
| `IsPad` | `item_kind pad` |
| `x And y`, `x && y` | `and(x, y, …)` |
| `x Or y`, `x \|\| y` | `or(x, y, …)` |
| `Not x` | `not(x)` |
| `(x)` | `x` |

## Clearance forms that map

Change c0125. A Clearance record maps in these forms beyond the plain one, and only where a neutral
`clearance` rule says exactly what the record says. They are read and never written: `rulemap.lower`
writes the plain form. `rules.matrix_problem` decides a matrix; the keys of a cell are conditions of the
table marked `read_only`.

| form | condition | neutral rule |
|---|---|---|
| blank matrix | `OBJECTCLEARANCES` holds white space only | as with an empty value: `min` = `GAP` |
| uniform matrix | every entry of `OBJECTCLEARANCES` holds the length of `GAP`, to the nanometre (a count is `rules.MATRIX_UNIT`, 0.0001 mil) | `min` = `GAP` |
| matrix cell | `ISMATRIX=TRUE`; `CELLROWNAME=All`, `CELLROWTYPE=0`, `CELLCOLNAME=All`, `CELLCOLTYPE=0`; `INNERLAYERS=TRUE`; `OUTERLAYERS=TRUE`; `SOURCERULE` with any value | the keys add nothing: the scopes, `GAP` and `PRIORITY` of the record decide |

A matrix with an entry of another length stays unmapped (`keys`): a neutral rule holds one value, and
the kinds of the matrix (arc, track, surface pad, through-hole pad, via, fill, polygon, region, text,
hole) are finer than the item kinds of the copper check. A record with
`IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE` stays unmapped (`keys`): no selector says "two pads of one
component". Any other value of a cell key stays unmapped (`keys`): a cell for a named class is in no
public file, so its scope text is not known.

### Layer scopes of Clearance

`scope.parse_layer_scope` reads a scope that is, as a whole, one layer condition: `OnMid`,
`ExistsOnLayer('<name>')`, or `ExistsOnLayer` terms joined by `Or` (or `||`), with at most one pair of
enclosing parentheses. `parse_scope` still refuses every layer function. `map_rules` considers a layer
condition only for Clearance, only with the copper layers of the record's board (`rules.CopperLayers`,
which the import of a PCB document gives; a rule file has none), and only when both scopes hold the
same one.

The neutral layer condition is the layer a pair of objects is judged on (`checks.clearance`: a rule
with `layers` is in force for a pair on one of them). Altium's functions test an object. The two say the
same for an object on one layer and differ for a via or a through-hole pad, which the check judges on
every layer it spans. So a condition maps in two cases only:

| both scopes | the board | result |
|---|---|---|
| `ExistsOnLayer` of every copper layer | any | a rule for all objects with `layers` = the board's copper layers: there is no other layer on which a pair could be judged |
| `ExistsOnLayer` of some copper layers | has others | unmapped (`scope`): two vias that exist on a named layer are governed by the record on the other layers too, where the neutral rule is not in force |
| `ExistsOnLayer` of a name that no copper layer, or more than one, holds | any | unmapped (`scope`) |
| `OnMid` | no internal signal layer | unmapped with `no-layer`: no object is on such a layer, so the rule applies to nothing. The record is no unread rule (`rules.NOT_APPLYING`) |
| `OnMid` | an internal signal layer | unmapped (`scope`): no permitted source says whether a via or a through-hole pad is "on" an internal signal layer |

A layer name is compared letter for letter with the name the board record gives the layer. An internal
signal layer is a copper layer whose id lies between the top layer's and the bottom layer's
(`pcb-records.md`, "Layers"); an internal plane is none.

## Fenolite's choices

- `RuleFile.to_bytes()` gives the input back. The form is told from the content: a first line that
  starts with `DRC Rules Export File for PCB:` is the summary form; a line holding `RULEKIND=` makes the
  export form; anything else is refused with `FormatError`. A non-empty line of an export file without
  `RULEKIND=` is kept, listed as a record and reported with `altium.rule.record-malformed`.
- The end mark of an export record (`C2 B6` or the single byte `B6`) stays in the raw line and is left
  out of the last value. Values are kept as written; `read_rule_file` interprets none of them.
- Mapping is exact or absent. A disabled rule is not mapped: in Altium the next rule applies, and a
  neutral rule of severity `ignore` would silence it. A key that the table does not know blocks the
  mapping, so a Clearance with a matrix of differing clearances or a Width with per-layer values is
  reported, not flattened.
- Lengths are converted as fractions and rounded half to even to the nanometre
  (`core.units.round_half_even_div`). Altium prints its 2.54 nm unit with a few decimals, so the error
  of that rounding is below 1 nm and raises no issue.
- Altium's priority goes into `Rule.priority` unchanged (1 the highest in both); priorities are per
  kind in Altium and rules of different kinds never compete. The preferred value becomes `opt`.
- Scopes: one parenthesis level holds one kind of operator, because no permitted source states the
  precedence. A value holding `'`, `*`, `?`, `[` or `]` is refused, because a neutral leaf value is a
  glob. `OnLayer` and the other layer functions are refused by the grammar: they need the board's layer
  names mapped to neutral names, which only the import (c0043) can do. Since change c0125 the import
  gives those layers and two layer conditions of a Clearance record map ("Layer scopes of Clearance").
  `IsPolygon` and every other function are refused.
- The values of a summary-form file have no unit, so its rules are never mapped (reason
  `summary-form`); no unit is assumed.

## Writing a rule file

`rulemap.write_rule_file` (change c0084) writes the export form from the records of `rulemap.lower`.

| fact | source | label | hypothesis |
|---|---|---|---|
| A record of the public export file starts with the six keys `SELECTION=FALSE`, `LAYER=TOP`, `LOCKED=FALSE`, `POLYGONOUTLINE=FALSE`, `USERROUTED=TRUE`, `UNIONINDEX=0`, then the header keys from `RULEKIND` to `DEFINEDBYLOGICALDOCUMENT`, then the keys of the kind; `UNIQUEID` is eight capital letters; priorities count from 1 within each kind | S-0297 | INFERRED | H-A-RULE-FILE |
| The PCB rules editor imports rules of chosen kinds from a `.RUL` file into the open board | S-0294 | INFERRED | H-A-RULE-FILE |

Fenolite's choices: each record is one line ended by the single byte `B6` and LF, and the text is 7-bit
ASCII apart from that byte, as in the public file. The six common keys are written as that file holds
them. `UNIQUEID` is `project.unique_id("rul:<name>:rule:<rule name>")`, so two exports of one design
are equal. `COMMENT` is empty. A design that lowers no rule gives a file without a record, which
`read_rule_file` refuses: the export writes no file then and says so.
