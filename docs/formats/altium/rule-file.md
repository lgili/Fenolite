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
| The matrix of the Clearance rule has a row and a column per object kind (track, arc, surface pad, through-hole pad, via, fill, polygon, region, hole); a simple view shows arc with track as one entry, and fill, polygon and region as one | S-0558 | INFERRED | H-A-RULE-CLEARANCE-CELLS |
| The object kinds named by the entries of the public Clearance matrices are `Arc`, `Track`, `SMDPad`, `THPad`, `Via`, `Fill`, `Poly`, `Region`, `Text` and `Hole`, and no other. Two of the four matrices give different values to object kinds of one item kind of the copper check (a through-hole pad and a surface pad; an arc and a track); the two others do not | S-0175, S-0176, S-0187 | CORPUS-VERIFIED (2026-10-07; test_altium_rule_kinds.py) | H-A-RULE-CLEARANCE-CELLS |
| Hole To Hole Clearance, Silk To Silk Clearance, Silk To Solder Mask Clearance, Minimum Solder Mask Sliver and Layer Pairs are checked by the DRC; an option of Hole To Hole Clearance allows stacked micro vias | S-1830 | INFERRED | H-A-RD-RULE-C0424 |
| Short Circuit reports touching primitives of different nets unless it allows the short; Net Antennae reports open-ended stubs up to its tolerance; Un-Routed Net checks routing completion | S-1831 | INFERRED | H-A-RD-RULE-C0424 |
| Routing Layers allows routing per signal layer; Differential Pairs Routing holds the least, preferred and greatest gap, per-layer widths, an impedance profile and the greatest uncoupled length; Routing Topology, Routing Priority, Routing Corners and Fanout Control guide the router | S-1832 | INFERRED | H-A-RD-RULE-C0424 |
| Component Clearance holds a horizontal and a vertical clearance between components, measured on their 3D bodies by default or on their boundaries; Height holds a component height range | S-1833 | INFERRED | H-A-RD-RULE-C0424 |
| Plane Clearance, Plane Connect Style, Solder Mask Expansion and Paste Mask Expansion apply when outputs are generated, not in the DRC | S-1834, S-1835 | INFERRED | H-A-RD-RULE-C0424 |
| The fabrication and assembly test point rules are checked by the DRC | S-1836 | INFERRED | H-A-RD-RULE-C0424 |
| A disabled rule is not considered; within one rule type the lower priority number wins and the first rule whose scope matches applies | S-1837 | INFERRED | H-A-RD-RULE-C0424 |
| The keys of the records of the public documents: `SILKTOSILKCLEARANCE` (Silk To Silk Clearance); `GAP`, `VERTICALGAP`, `COLLISIONCHECKMODE`, `SHOWDISTANCES` (Component Clearance); `MINLIMIT`, `MOSTFREQGAP`, `MAXLIMIT`, `MAXUNCOUPLEDLENGTH`, `<LAYER>_MINWIDTH`, `<LAYER>_MAXWIDTH`, `<LAYER>_PREFWIDTH` and the `IMPEDANCE…` keys (Differential Pairs Routing); `MINSOLDERMASKWIDTH`; `MINSILKSCREENTOMASKGAP`, `CLEARANCETOEXPOSEDCOPPER`; `EXPANSION` (mask and paste); `CLEARANCE` (Plane Clearance); `ALLOWED` (Short Circuit); `NETANTENNAETOLERANCE`; `MINHEIGHT`, `PREFHEIGHT`, `MAXHEIGHT`. Silk To Board Region Clearance and Unpoured Polygon records hold header keys only | S-1838, S-0297 | INFERRED | H-A-RD-RULE-C0424 |
| A Routing Layers record holds one key per signal layer: `TOP LAYER_V5` (layer id 1), `MID LAYER <n>_V5` (id n + 1) and `BOTTOM LAYER_V5` (id 32), each `TRUE` or `FALSE`; an internal plane has no key | S-1838, S-1832 | INFERRED | H-A-RD-RULE-ROUTINGLAYERS |
| `Arc` and `Track` are the tracks and arcs of the import, `SMDPad` and `THPad` its pads, `Via` its vias, and `Poly` the poured copper of a polygon, which the import reads as the fills of a zone; `Fill`, `Region`, `Text` and `Hole` are objects the copper check holds no item of | S-0558 | INFERRED | H-A-RULE-CLEARANCE-CELLS |

## Header keys

`rules.HEADER_KEYS`: the keys that every rule record of a PCB document holds after its common keys
(`pcb-copper.md`, "Rules"): `RULEKIND`, `NETSCOPE`, `LAYERKIND`, `SCOPE1EXPRESSION`,
`SCOPE2EXPRESSION`, `NAME`, `ENABLED`, `PRIORITY`, `COMMENT`, `UNIQUEID` and
`DEFINEDBYLOGICALDOCUMENT`. The keys before `RULEKIND` are allowed and not read.

## Rule kinds that map

`rules.RULE_KIND_MAP`: a record maps only when its kind is in this table, its `NETSCOPE` is the one
given, its `LAYERKIND` is `SameLayer`, its other keys are header keys or keys of its row, and the
further conditions hold. Routing Via Style gives two neutral rules. A dash is a limit the kind does not
give. A kind that limits one object (Width, Routing Via Style, Hole Size, Minimum Annular Ring) maps with
`NETSCOPE` `AnyNet` or `DifferentNets` (change c0377, `rules.ONE_OBJECT_KINDS`): the net scope relates
the nets of two objects, so it selects nothing more for a rule on one object (`H-A-RD-PRJ-NETSCOPE-ONE`,
INFERRED: no public source states what the key does on such a kind; the public documents hold both values
on it, S-0580).

| RULEKIND | neutral kind | min | opt | max | net scope | further conditions |
|---|---|---|---|---|---|---|
| `Clearance` | `clearance` | `GAP` | — | — | `DifferentNets` | `OBJECTCLEARANCES` absent, blank, uniform or a matrix of exact cells (each one more rule); `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE`; `ISMATRIX`, `SOURCERULE`, `CELLROWNAME`, `CELLROWTYPE`, `CELLCOLNAME`, `CELLCOLTYPE`, `INNERLAYERS` and `OUTERLAYERS` absent or as in "Clearance forms that map" |
| `Width` | `track_width` | `MINLIMIT` | `PREFEREDWIDTH` | `MAXLIMIT` | `AnyNet` | — |
| `RoutingVias` | `via_diameter` | `MINWIDTH` | `WIDTH` | `MAXWIDTH` | `AnyNet` | `VIASTYLE` is `Through Hole` |
| `RoutingVias` | `via_drill` | `MINHOLEWIDTH` | `HOLEWIDTH` | `MAXHOLEWIDTH` | `AnyNet` | `VIASTYLE` is `Through Hole` |
| `HoleSize` | `hole_size` | `MINLIMIT` | — | `MAXLIMIT` | `AnyNet` | `ABSOLUTEVALUES` is `TRUE`; `MINPERCENT` and `MAXPERCENT` allowed and unused |
| `BoardOutlineClearance` | `edge_clearance` | `GAP` | — | — | `DifferentNets` | `OBJECTCLEARANCES` absent or empty; `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE` |
| `HoleToHoleClearance` | `hole_to_hole` | `GAP` | — | — | `AnyNet` | `ALLOWSTACKEDMICROVIAS` is `FALSE` or `TRUE` (with `TRUE` the record is also kept: "Kept rule records") |
| `MinimumAnnularRing` | `annular_width` | `MINIMUMRING` | — | — | `AnyNet` | — |
| `SilkToSilkClearance` | `silk_clearance` | `SILKTOSILKCLEARANCE` | — | — | `AnyNet` | — |
| `ComponentClearance` | `courtyard_clearance` | `GAP` | — | — | `AnyNet` | `VERTICALGAP`, `COLLISIONCHECKMODE` and `SHOWDISTANCES` allowed and unused |
| `DiffPairsRouting` | `diff_pair_gap` | `MINLIMIT` | `MOSTFREQGAP` | `MAXLIMIT` | `AnyNet` | `IMPEDANCEPROFILEDRIVEN`, `IMPEDANCEPROFILEID` and `IMPEDANCEPROFILEVALUE` allowed and unused |
| `DiffPairsRouting` | `diff_pair_uncoupled` | — | — | `MAXUNCOUPLEDLENGTH` | `AnyNet` | as the row above: `IMPEDANCEPROFILEDRIVEN`, `IMPEDANCEPROFILEID`, `IMPEDANCEPROFILEVALUE` |

`rules.PENDING_KINDS`: kinds that have a neutral counterpart but no permitted source for their keys,
reported apart with the reason `no-verified-keys`. The table is empty since change c0084, which found the
keys of `BoardOutlineClearance` in public PCB documents; the reason stays for a later kind.

The last three kinds of the table are those of change c0084: the table holds every Altium kind of an
`exact` row of `rulemap.TABLE` (`pcb-copper.md`, "The lowering table"), so what Fenolite writes it reads.
A Hole To Hole Clearance with `ALLOWSTACKEDMICROVIAS=TRUE` exempts the holes of stacked microvias, which
the neutral rule does not: since change c0424 it maps, and its record is kept for an Altium write. The last
four rows are those of change c0424; a key of a Routing Layers record for a layer the board does not hold
applies to no object.

Of the kinds of change c0424, Silk To Silk Clearance and Component Clearance are binary (two scopes) and
map with `NETSCOPE` `AnyNet` or `DifferentNets` (`rules.NET_SCOPE_FREE`: the net scope selects nothing
more for these objects). The rules of Differential Pairs Routing select differential pairs (`diff_pair *`,
joined to another scope with `and`), and its per-layer keys `<LAYER>_MINWIDTH`, `_MAXWIDTH` and
`_PREFWIDTH` are allowed and unused. A Routing Layers record (`RoutingLayers`, no limit) gives one
`no_tracks` rule on the board's signal layers whose key is `FALSE`, none when no key is `FALSE`; its layer
keys are allowed, and without the Altium ids of the board's layers it is refused with `no-layer`.

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
| `ComponentClearance` | export (1) | S-0297 | yes: `courtyard_clearance` |
| `DiffPairsRouting` | export (1) | S-0297 | yes: `diff_pair_gap` and `diff_pair_uncoupled` |
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
| `RoutingLayers` | export (1) | S-0297 | yes: `no_tracks` |
| `RoutingPriority` | export (1) | S-0297 | no |
| `RoutingTopology` | export (1) | S-0297 | no |
| `RoutingVias` | export (1) | S-0297 | yes: `via_diameter` and `via_drill` |
| `ShortCircuit` | export (1); summary (2 files) | S-0297, S-0298, S-0188 | no |
| `SilkToBoardRegionClearance` | export (1) | S-0297 | no |
| `SilkToSilkClearance` | export (1) | S-0297 | yes: `silk_clearance` |
| `SilkToSolderMaskClearance` | export (1) | S-0297 | no |
| `SolderMaskExpansion` | export (1); summary (2 files) | S-0297, S-0298, S-0188 | no |
| `UnRoutedNet` | export (1) | S-0297 | no |
| `Width` | export (1); summary (2 files) | S-0297, S-0298, S-0188 | yes: `track_width` |

## Kept rule records

Change c0424: a record of a PCB document that the Altium writer cannot rebuild from the neutral rules is
kept on the board as one `kept_rule` pair (`import.md`, "Extension-bag keys"): its kind number, then its
keys from `RULEKIND` on (`adapter.rules.kept_text`). These are the records that give no rule (every reason
of "Reasons" but `malformed`), the records of a kind the writer has no row for (`rulemap.KIND_ORDER`), and
a Hole To Hole Clearance that allows stacked micro vias. The rules a kept record gives carry
`kept_record=1`, and the writer leaves them out: `pcbdoc.rule_records` writes the kept record back as it
is, after the records of its kind, with the next priority of that kind (`_kept` added to its name when the
writer made one of the same name). A Polygon Connect Style record stays in its own `polygon_connect` pair
(change c0215).

## Fates in a conversion

`convert.altium_rules` (change c0424) gives each record of an Altium board one outcome in the report of a
conversion to KiCad. Kept means a declared format limit: KiCad cannot hold the record, and the model keeps
it for an Altium write.

| record | outcome |
|---|---|
| a rule KiCad's lowering writes | written |
| Component Clearance; Differential Pairs Routing; Hole To Hole Clearance that allows stacked micro vias | changed (vertical gap and body check; per-layer widths; the allowance) |
| a rule with a limit its KiCad constraint does not take (`opt` of a via drill) | changed: the other limits are written |
| the first enabled Solder Mask or Paste Mask Expansion of scope All | changed: the pads' margins |
| Short Circuit of scope All that allows no short | changed: KiCad's own check of shorting items |
| Routing Layers that disallows no layer of the board | written: KiCad needs no rule |
| a disabled record | kept: KiCad has no disabled rule that leaves the next one in force |
| Plane Clearance, Plane Connect Style | kept: the conversion gives an internal plane no zone |
| Height, Minimum Solder Mask Sliver, Silk To Solder Mask Clearance, Silk To Board Region Clearance, Net Antennae | kept: no KiCad constraint of that meaning |
| Routing Topology, Routing Priority, Routing Corners, Fanout Control, the test point rules, Supply Nets, Un-Routed Net, Unpoured Polygon, Layer Pairs, Matched Lengths and every other kind | kept: KiCad has no rule of the kind |
| Polygon Connect Style that reads | changed: the connection, thermal gap and spoke width of each zone and pad it governs (change c0409) |
| Polygon Connect Style that does not read | kept |
| a record without kind or name | lost |

Altium's priority 1 governs and so does the last rule of KiCad's file; the rules keep Altium's order
through the names `fenolite_<priority>_<name>` (change c0409). A `rules.shadowed` notice after an import
names the rule Altium applies as the governing one, so it changes no meaning.

### Records through KiCad

A conversion to KiCad also writes the board property `Fenolite.Altium.Rules6` (change c0434,
`convert.rulecarrier`; `docs/formats/kicad/board.md`, "Fenolite board properties"). It holds every record
of the document, its kind number and its keys from `RULEKIND` on, with the SHA-256 of each rule list of
`<name>.kicad_dru` that the record's rules gave, as written. KiCad keeps the property and does not use it.
A conversion of the board back to Altium reads it. Two cases:

- A record whose rule lists are all still in the rules file as written, or that gave none (every `kept`
  record above), is written as it was read: its name, priority, scopes, enabled state and limits.
- A record whose rule lists were edited or removed in KiCad is not written from the property. Its rules are
  lowered as KiCad holds them, with the next priority of their kind. A rule of such a record that no
  Altium record can hold is a loss that needs `--allow-lossy` (`SOURCE_RULE_LOST`). A loss of a rule that
  KiCad alone holds is reported only.

Change c0457 compares rule lists by content, not by text. Each list is keyed by its children after the
name, in sorted order, with a condition's runs of spaces made one (`rulecarrier.rule_keys`, property
schema `fenolite.altium-rules.v1`). So a rules file that a build of the imported design writes again,
with other names (an unscoped rule the import made a board minimum is `fenolite_0_min_clearance`) or in
another order, still holds the records' rules. A rule of the same content as a kept record's is a copy and
is not written again. An edit in KiCad is a change, not a loss:

- A record whose rules keep their names and their shapes (everything but the values of `min`, `opt` and
  `max`) is written with KiCad's limits and its own name, priority, scopes and enabled state
  (`rulemap.edited_fields`); a Routing Via Style takes the `hole_size` of vias in `MINHOLEWIDTH` and
  `MAXHOLEWIDTH`.
- Any other edit is lowered as a rule of its kind. `SOURCE_RULE_LOST` stays for an edit that no Altium
  record can hold.

On that way back no other record is added: no rule of a net class, no `All` default, no Polygon Connect
Style lowered from the zones when the source holds one, and no plane rule of a kind that the source holds.
Without the file, the way back writes the rules of the KiCad project, as before.

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
| `InNet('No Net')` | `not(net *)` (`NO_NET`) |
| `InAnyNet` | `net *` (so `Not InAnyNet` is `NO_NET`) |
| `InNetClass('v')` | `netclass v` |
| `InComponent('v')` | `ref v` |
| `IsTrack` | `item_kind track` |
| `IsVia` | `item_kind via` |
| `IsPad` | `item_kind pad` |
| `InPolygon` | `item_kind zone` |
| `InPoly` | `item_kind zone` |
| `x And y`, `x && y` | `and(x, y, …)` |
| `x Or y`, `x \|\| y` | `or(x, y, …)` |
| `Not x` | `not(x)` |
| `(x)` | `x` |

The operators are read in any letter case: `and` and `AND` are `And`, `or` and `OR` are `Or`, `not`
and `NOT` are `Not` (change c0377; `H-A-RD-PRJ-SCOPE-CASE`, INFERRED). No public source states Altium's letter-case
rule (S-1531 states none); the public documents, which Altium saved, hold scopes written with `not` and
`AND` (S-0580), and Altium's pages spell `And`, `AND` and `Not` in their examples. Altium states the
precedence, highest first: brackets, `Not`, `And`, `Or`, then `&&` and `||`, ties from left to right
(S-1531); the grammar still holds one kind of operator per parenthesis level, which needs no precedence.

`InNet('No Net')` selects the objects without a net (change c0409, B7; `H-A-RD-PRJ-SCOPE-NONET`, INFERRED): an
object without a net has the Net property `No Net` (S-1680), and no public source states that `InNet` reads the
name that way. It is read as `model.rules.NO_NET`, `not(net *)` (a net glob never matches an object
without a net), which `select.no_net()` names and the KiCad target writes as `A.NetName == ''`
(`docs/formats/kicad/rules.md`, `H-K-DRU-NONET`). The Altium writer does not write it back as `InNet('No Net')`:
since change c0420 it writes `Not InAnyNet`, below.

`InAnyNet` selects the objects that are on a net, so `Not InAnyNet` selects those without one (change c0420, B7;
`H-A-RD-PRJ-SCOPE-NONET`, INFERRED): Altium's Attribute Checks page states that `Not InAnyNet` returns the objects
that are not nets or their primitives (S-1680). It is read as `net *`, so `Not InAnyNet` is `NO_NET` and a scope
such as `IsPad And (Not InAnyNet)` maps without a `scope` refusal. The Altium writer lowers `net *` to `InAnyNet`, so
`NO_NET` is written `Not InAnyNet` and `IsPad And (Not InAnyNet)` reads back as the same rule
(`backends/altium/rulemap.py`).

`InPolygon` (alias `InPoly`; change c0412) without an argument is the clearance query for the copper of a polygon pour: Altium's Object
Type Checks page says a clearance rule for a pour names `InPolygon` rather than `IsPolygon`, because the
clearance applies to the primitives of the pour (S-1702; change c0412, `H-A-RULE-SCOPE`, INFERRED).
KiCad's `A.Type == 'Zone'` (`item_kind zone`) names the same copper in a clearance. `InNamedPolygon('n')`,
which names one pour, stays outside the grammar.

**Unmapped forms on the public boards** (change c0377, task 1.1; S-0580 documents, read 2026-11-04 with
Fenolite's own reader, counts only). Kinds with no neutral counterpart, per rule record: FanoutControl 40,
PolygonConnect 18, MatchedLengths 15, SolderMaskExpansion 11, ComponentClearance 10, PlaneConnect 9,
DiffPairsRouting 9, PasteMaskExpansion 8 (and 8 each of the other kinds of the default rule set). Refused
records of mapped kinds, among them: HoleToHoleClearance with `ALLOWSTACKEDMICROVIAS=TRUE` 6, RoutingVias
with via template keys 4, BoardOutlineClearance object matrices 3, Clearance scopes 5 (`HasFootprint`,
`InPolygon` (read since change c0412), `InDifferentialPairClass`, a left-over token), Width keys and scopes 4, HoleSize scopes with
`HoleDiameter` 2, and one record each refused for `NETSCOPE` on HoleSize, RoutingVias and Width. What stays open, and why:

| form | reason it does not map (a declared loss: the rule is reported unmapped with this reason) |
|---|---|
| `HasFootprint`, `InNamedPolygon`, `InComponentClass`, `WithinRoom`, `IsDifferentialPair`, `InDifferentialPairClass`, `HoleDiameter` | the neutral selector has no footprint name, pour, component class, room, pair object or hole size leaf |
| `OnLayer`, `OnTopLayer`, `OnBottomLayer` joined with other terms | a layer condition maps only as the whole scope (change c0125) |
| Clearance with `NETSCOPE=AnyNet` | a neutral clearance holds between different nets; a clearance between objects of one net has no counterpart, so mapping the record would drop half of it |
| HoleToHoleClearance with `ALLOWSTACKEDMICROVIAS=TRUE` | the neutral rule has no exception for stacked micro-vias |
| Clearance with `IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE`, an object matrix of differing cells | the neutral rule cannot leave out the pads of one footprint or tell the objects apart (change c0125) |
| Width with per-layer widths or impedance keys (`FAVIMP`, `MAXIMP`, `<LAYER>_MINWIDTH`) | the neutral rule holds one width per rule, by selector, and no impedance profile |
| RoutingVias with via template keys | no neutral form of a via template |
| PlaneConnect, PolygonConnect | no neutral rule; the board keeps Polygon Connect Style records (change c0215) |
| SolderMaskExpansion, PasteMaskExpansion | no neutral rule; the pad's expansion modes are `INFERRED` (`pcb-read.md`, `PadRecord`), so a pad following the rule cannot be told apart |
| FanoutControl, ShortCircuit, UnRoutedNet, RoutingTopology, RoutingPriority, RoutingLayers, RoutingCorners, DiffPairsRouting, MatchedLengths, test point kinds, silk and mask sliver kinds, Height, LayerPairs, NetAntennae, UnpouredPolygon, ComponentClearance, PlaneClearance | no neutral rule kind holds them (`no-counterpart`) |

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

A matrix with an entry of another length is read cell by cell ("Cells of an object matrix", change
c0130); it stays unmapped (`keys`) when it tells apart object kinds that are one item kind of the
copper check. A record with
`IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE` stays unmapped (`keys`): no selector says "two pads of one
component". Any other value of a cell key stays unmapped (`keys`): a cell for a named class is in no
public file, so its scope text is not known.

### Cells of an object matrix

Change c0130. `rules.read_matrix` reads a matrix of differing clearances in the item kinds of the copper
check (`rules.MATRIX_KINDS`). The value of a pair of object kinds is its entry, or `GAP` without one.

| object kind | item kind of the check |
|---|---|
| `Arc`, `Track` | `track` |
| `SMDPad`, `THPad` | `pad` |
| `Via` | `via` |
| `Poly` | `zone` |
| `Fill`, `Region`, `Text`, `Hole` | none |

- A pair of item kinds is exact when every pair of object kinds in it holds one value. A value that
  differs from `GAP` is a cell and gives one more `clearance` rule: name `<NAME>/<kind>-<kind>`, the
  record's priority, `item_kind` on both sides (joined with `and` to the record's scope on its side). It
  governs above the rule of `GAP` of its record: among rules of one priority the later name governs. A
  record with two different scopes gets a second rule with the kinds exchanged for a cell of two kinds.
- When the object kinds of one item kind disagree, no neutral rule says the pair and the whole record
  stays unmapped (`keys`); the detail names the pairs, for example `track to pad`. Part of a record is
  never mapped: the rest of it would be judged with a value it does not hold.
- An entry with an object kind that has no item changes no rule; the rule of `GAP` keeps such entries
  as written in its bag (`cells_not_lifted`).
- `RuleMapping.matrix_cells` counts, per enabled Clearance record with entries, those a rule holds and
  those none holds; the copper stage of a document check reports the sums as `summary.clearance_cells`.
- A cell of 0 is a rule of 0: no clearance is asked of the pair, and a short is still a short.

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

Scoped native support for the two Clearance hypotheses (2026-10-14):

| measured fact | source | label | hypothesis |
|---|---|---|---|
| On the authored two-layer matrix, native AD 26.5.0 reports all three planted 4-mil pairs with the outer 5-mil constraint and none with the inner 7-mil constraint. Report headings group under the 10-mil parent; native save names the child rules `Fallback_1` and `Fallback_2`, preserving their scopes | S-0744 | INFERRED | H-A-RULE-CLEARANCE-FORMS |
| On the authored generic 4-mil rule with a via-via cell of 3.5 mil, a 3.7-mil via-via gap passes and a 3.7-mil via-track gap fails in native AD 26.5.0. The native saved cell text and Fenolite's finding count agree | S-0744 | INFERRED | H-A-RULE-CLEARANCE-CELLS |

These are scoped automated observations; neither row graduates the broader hypothesis.

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
