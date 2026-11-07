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
| The Clearance rule has a simple and an advanced view of its matrix: the simple view joins Track and Arc (with their keep-outs) as one entry and Fill, Poly and Region (with their keep-outs) as one Copper entry; a cell is the clearance of one pair of object kinds, and a scope narrows which cells apply. Hole is a row of its own: it gives the clearance from a hole to copper on signal layers, and it governs a pad whose hole is at least as large as the pad only when an option is set, the larger of the Hole and TH Pad cells otherwise. The page says nothing of an unplated pad | S-2249 | INFERRED | H-A-RULE-CLEARANCE-CELLS, H-A-RULE-MATRIX-NPTH |
| Board Outline Clearance gives the clearance from objects to the board's edges, as a matrix of object kinds against edge kinds: the outer edge (`Outline Edge`), the edge of a cavity, the edge of a cutout, a Split Line that bounds a layer (`Split Barrier`), and a Split Line a layer continues across (`Split Continuation`, where 0 lets the object cross). One minimum value is copied to every cell, and cells may differ | S-2217 | INFERRED | H-A-RULE-CLEARANCE-CELLS |
| The edge kinds of the public Board Outline Clearance matrices are written `OutlineEdge`, `CavityEdge`, `CutoutEdge`, `SplitBarrior` and `SplitContinuation`, each paired with an object kind (`ClearanceObj_Poly-ClearanceObj_OutlineEdge:<count>`); three of the 8 public rows hold one such matrix (1, 5 and 5 entries) | S-1654 | CORPUS-VERIFIED (2026-11-06; test_altium_rule_kinds_c0462.py) | H-A-RULE-CLEARANCE-CELLS |
| Hole To Hole Clearance, Silk To Silk Clearance, Silk To Solder Mask Clearance, Minimum Solder Mask Sliver and Layer Pairs are checked by the DRC; an option of Hole To Hole Clearance allows stacked micro vias | S-1830 | INFERRED | H-A-RD-RULE-C0424 |
| Short Circuit reports touching primitives of different nets unless it allows the short; Net Antennae reports open-ended stubs up to its tolerance; Un-Routed Net checks routing completion | S-1831 | INFERRED | H-A-RD-RULE-C0424 |
| Routing Layers allows routing per signal layer; Differential Pairs Routing holds the least, preferred and greatest gap, per-layer widths, an impedance profile and the greatest uncoupled length; Routing Topology, Routing Priority, Routing Corners and Fanout Control guide the router | S-1832 | INFERRED | H-A-RD-RULE-C0424 |
| Component Clearance holds a horizontal and a vertical clearance between components, measured on their 3D bodies by default or on their boundaries; Height holds a component height range | S-1833 | INFERRED | H-A-RD-RULE-C0424 |
| Plane Clearance, Plane Connect Style, Solder Mask Expansion and Paste Mask Expansion apply when outputs are generated, not in the DRC | S-1834, S-1835 | INFERRED | H-A-RD-RULE-C0424 |
| The fabrication and assembly test point rules are checked by the DRC | S-1836 | INFERRED | H-A-RD-RULE-C0424 |
| A disabled rule is not considered; within one rule type the lower priority number wins and the first rule whose scope matches applies | S-1837 | INFERRED | H-A-RD-RULE-C0424 |
| The keys of the records of the public documents: `SILKTOSILKCLEARANCE` (Silk To Silk Clearance); `GAP`, `VERTICALGAP`, `COLLISIONCHECKMODE`, `SHOWDISTANCES` (Component Clearance); `MINLIMIT`, `MOSTFREQGAP`, `MAXLIMIT`, `MAXUNCOUPLEDLENGTH`, `<LAYER>_MINWIDTH`, `<LAYER>_MAXWIDTH`, `<LAYER>_PREFWIDTH` and the `IMPEDANCE…` keys (Differential Pairs Routing); `MINSOLDERMASKWIDTH`; `MINSILKSCREENTOMASKGAP`, `CLEARANCETOEXPOSEDCOPPER`; `EXPANSION` (mask and paste); `CLEARANCE` (Plane Clearance); `ALLOWED` (Short Circuit); `NETANTENNAETOLERANCE`; `MINHEIGHT`, `PREFHEIGHT`, `MAXHEIGHT`. Silk To Board Region Clearance and Unpoured Polygon records hold header keys only | S-1838, S-0297 | INFERRED | H-A-RD-RULE-C0424 |
| A Routing Layers record holds one key per signal layer: `TOP LAYER_V5` (layer id 1), `MID LAYER <n>_V5` (id n + 1) and `BOTTOM LAYER_V5` (id 32), each `TRUE` or `FALSE`; an internal plane has no key | S-1838, S-1832 | INFERRED | H-A-RD-RULE-ROUTINGLAYERS |
| A Short-Circuit rule reports two touching copper primitives of different nets; with "Allow Short Circuit" the nets under its two scopes may short (the example: two ground systems in one design). How several such rules combine by priority is not stated | S-2241 | INFERRED | H-A-RULE-SHORT |
| A Net Antennae rule reports, per net, an open-ended track or arc, or one ending in a via, whose stub is longer than its tolerance (the maximum permissible stub length). Where the stub is measured, and whether a stub of exactly the tolerance passes, are not stated | S-2240 | INFERRED | H-A-RULE-ANTENNA |
| The public ShortCircuit records (rule-kind number 15) hold one own key, `ALLOWED` (`FALSE` in all 8); the NetAntennae records (rule-kind number 56) hold `NETANTENNAETOLERANCE` (`0mil` in 6, `1mil` in 2); every one is enabled with scopes `All` and `All` | S-2243 | CORPUS-VERIFIED (8 rows; 2026-11-06) | H-A-RULE-SHORT, H-A-RULE-ANTENNA |
| `Arc` and `Track` are the tracks and arcs of the import, `SMDPad` and `THPad` its pads, `Via` its vias, and `Poly` the poured copper of a polygon, which the import reads as the fills of a zone; `Fill` and `Region` the free fills and regions, which the copper check judges on copper as `graphic` items (change c0462); `Text` and `Hole` are objects the copper check holds no item of | S-0558 | INFERRED | H-A-RULE-CLEARANCE-CELLS |

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
| `Width` | `track_width` | `MINLIMIT` | `PREFEREDWIDTH` | `MAXLIMIT` | `AnyNet` | per-layer keys as in "Per-layer values"; `CHECKCONNECTEDCOPPER` absent or `FALSE` (`TRUE` is refused with `connected-copper`); `IMPEDANCEPROFILEDRIVEN` absent, `FALSE` or `TRUE`; `IMPEDANCEPROFILEID`, `IMPEDANCEPROFILEVALUE`, `MINIMP`, `MAXIMP` and `FAVIMP` allowed and unused |
| `RoutingVias` | `via_diameter` | `MINWIDTH` | `WIDTH` | `MAXWIDTH` | `AnyNet` | `VIASTYLE` is `Through Hole`; `USEVIATEMPLATES` absent or `FALSE` (`TRUE`: "Via templates"); `VIATEMPLATEGUID#<n>` and `VIATEMPLATENAME#<n>` allowed and unused |
| `RoutingVias` | `via_drill` | `MINHOLEWIDTH` | `HOLEWIDTH` | `MAXHOLEWIDTH` | `AnyNet` | as the row above: `VIASTYLE`, `USEVIATEMPLATES` |
| `HoleSize` | `hole_size` | `MINLIMIT` | — | `MAXLIMIT` | `AnyNet` | `ABSOLUTEVALUES` is `TRUE`; `MINPERCENT` and `MAXPERCENT` allowed and unused |
| `BoardOutlineClearance` | `edge_clearance` | `GAP` | — | — | `DifferentNets` | `OBJECTCLEARANCES` absent, blank or a matrix of exact cells against the edges (each one more rule, change c0462); `GENERICCLEARANCE` absent or equal to `GAP`; `IGNOREPADTOPADCLEARANCEINFOOTPRINT` absent or `FALSE` |
| `NetAntennae` | `antenna` | — | — | `NETANTENNAETOLERANCE` | `AnyNet` | — |
| `HoleToHoleClearance` | `hole_to_hole` | `GAP` | — | — | `AnyNet` | `ALLOWSTACKEDMICROVIAS` is `FALSE` or `TRUE` (with `TRUE` the record is also kept: "Kept rule records") |
| `MinimumAnnularRing` | `annular_width` | `MINIMUMRING` | — | — | `AnyNet` | — |
| `SilkToSilkClearance` | `silk_clearance` | `SILKTOSILKCLEARANCE` | — | — | `AnyNet` | — |
| `ComponentClearance` | `courtyard_clearance` | `GAP` | — | — | `AnyNet` | `VERTICALGAP`, `COLLISIONCHECKMODE` and `SHOWDISTANCES` allowed and unused |
| `DiffPairsRouting` | `diff_pair_gap` | `MINLIMIT` | `MOSTFREQGAP` | `MAXLIMIT` | `AnyNet` | per-layer gap keys as in "Per-layer values"; `IMPEDANCEPROFILEDRIVEN` absent, `FALSE` or `TRUE`; `IMPEDANCEPROFILEID` and `IMPEDANCEPROFILEVALUE` allowed and unused |
| `DiffPairsRouting` | `diff_pair_uncoupled` | — | — | `MAXUNCOUPLEDLENGTH` | `AnyNet` | as the row above: `IMPEDANCEPROFILEDRIVEN`, `IMPEDANCEPROFILEID`, `IMPEDANCEPROFILEVALUE`; no per-layer key |

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

## Per-layer values

Change c0462 (design D5) reads the per-layer keys of Width and Differential Pairs Routing
(`rules.LAYER_VALUE_KEY`, `KindMap.layer_values`). The routing rules page sets the limits for all layers or
per layer (S-2248); the public records hold them as below (S-2219).

| fact | source | label | hypothesis |
|---|---|---|---|
| A per-layer key is `<LAYER>_<LIMIT><QUANTITY>`: `<LAYER>` is `TOPLAYER` (layer id 1), `MIDLAYER<n>` (id n + 1, n from 1 to 30) or `BOTTOMLAYER` (id 32); `<LIMIT>` is `MIN`, `PREF` or `MAX`; `<QUANTITY>` is `WIDTH` (Width, and the unused pair widths of Differential Pairs Routing) or `GAP` (Differential Pairs Routing) | S-2248, S-2219 | INFERRED | H-A-RULE-LAYER-VALUES |
| A layer holds only the limits that differ from the record's general ones: a Width record of a public row holds `MIDLAYER<n>_MINWIDTH` and `_PREFWIDTH` and leaves out `_MAXWIDTH` on every layer where that equals `MAXLIMIT`; another holds `_MAXWIDTH` only | S-2219 | INFERRED | H-A-RULE-LAYER-VALUES |
| With "Use Impedance Profile" the values of a layer come from the profile, and the grid shows the profile's layers only; the record holds the profile's id and impedance (`IMPEDANCEPROFILEID`, `IMPEDANCEPROFILEVALUE`), not the profile. The 3 public pair records with `IMPEDANCEPROFILEDRIVEN=TRUE` hold gap keys on some signal layers of their board only | S-2248, S-2219 | INFERRED | H-A-RULE-LAYER-VALUES |
| `MINIMP`, `MAXIMP` and `FAVIMP` of a Width record are impedances (two public records hold `50.000000` with no profile key) | S-2219 | INFERRED | H-A-RULE-LAYER-VALUES |

The reading:

- Each signal layer of the board (ids 1 to 32) takes each limit from its per-layer key, or else the
  general one. A layer with at least one limit that differs from the general one gives one rule of the
  record's neutral kind, `and(scope, layer L)` (just `layer L` for the scope `All`), named
  `<record name>/<L>` and at the record's priority, so it governs on its layer (`checks.clearance.rule_precedence`
  sorts names within one priority). A layer whose limits equal the general ones gives no rule.
- A per-layer key of a layer the board does not hold applies to no object: the record maps and the mapper
  gives one info `altium.rules.layer-absent` that names those layers.
- With `IMPEDANCEPROFILEDRIVEN=TRUE`, a signal layer of the board for which the record holds no value of the
  quantity is refused with `impedance-profile`: the record does not say whether the layer is outside the
  profile or holds the general values. Fenolite's impedance targets are not inferred from the record.
- `MINIMP`, `MAXIMP` and `FAVIMP` without a profile key are read and unused: the widths the record holds
  are the rule. `CHECKCONNECTEDCOPPER=TRUE` judges the width of connected copper (tracks, arcs, fills, pads
  and vias together), which no neutral rule says: the record is refused with `connected-copper` and stays
  carried. It is not mapped as a track rule.
- Without the Altium ids of the board's copper layers (a rule file), a record whose per-layer values differ
  from the general ones, or that is profile-driven, is refused with `scope`.
- A record that holds per-layer keys is kept for an Altium write ("Kept rule records"): the lowering writes
  one form per rule and no per-layer key.

## Via templates

| fact | source | label | hypothesis |
|---|---|---|---|
| A Routing Via Style takes its sizes from its limits ("Min/Max preferred", whose minimum and maximum the check obeys) or from one or more enabled via templates ("Template preferred"); the page does not say what the check tests in template mode | S-2248 | INFERRED | H-A-RULE-VIA-TEMPLATE |
| A record in template mode holds `USEVIATEMPLATES=TRUE` and, per template, `VIATEMPLATEGUID#<n>` and `VIATEMPLATENAME#<n>`; it still holds its own limits, which differ from the template's sizes (`50mil` and `28mil` beside a template of 16 mil and 8 mil). One public record holds the template keys without `USEVIATEMPLATES` | S-2219 | INFERRED | H-A-RULE-VIA-TEMPLATE |
| The document holds the templates in `PadViaLibraryCache/Data`: one block of the library's header keys, then one block per template after one lead byte, each with `TEMPLATE.TEMPLATEID` (the GUID a record names), `TEMPLATE.TEMPLATENAME`, `TEMPLATE.VIA.HOLESIZE`, `TEMPLATE.VIA.STACKDATA0.DIAMETER` and `TEMPLATE.TOLERANCE.POSITIVE` and `.NEGATIVE` (`214748.3647mil` in every public template); a template can be listed twice | S-2219 | INFERRED | H-A-RULE-VIA-TEMPLATE |
| A record in template mode whose named template Altium does not resolve (shown as library `<Unknown>`: absent from the document, or an authored cache block without `TEMPLATE.HASH`, which Altium ignores and drops at its save) checks no via: vias of the template's sizes, of the record's sizes and of neither pass alike, where the same record without template mode flags every via outside its limits. A save keeps the record and `USEVIATEMPLATES=TRUE`. What the check tests for a resolved template is not measured | S-2247 | INFERRED (one agent run on 24.5.2, which raises no level) | H-A-RULE-VIA-TEMPLATE |

A record with `USEVIATEMPLATES=TRUE` is refused with `template`: its vias take the sizes of the templates,
and no permitted source says whether the check tests those sizes (with a tolerance the document holds), the
record's own limits, or nothing. A template Altium does not resolve makes the record check nothing (S-2247);
a resolved one is not measured, so neither reading is taken, and the refusal stays for both. The template keys
of a record without `USEVIATEMPLATES=TRUE` are allowed and unused: its own limits are the rule.

## Rule kinds and their reading

Change c0462 (design D6). The table is closed: `tests/corpus/test_altium_rule_kinds_c0462.py` fails when a
rule kind of a public Altium row is not in it, and `rules.RULE_KIND_MAP`, `rules.READ_KINDS`,
`rules.CHECKED_KINDS` and `rules.CARRIED_KINDS` hold exactly its rows. A record of a kind outside every
table is reported with `no-counterpart`.

- **neutral**: the kind maps onto the neutral rules named ("Rule kinds that map").
- **read**: another part of the backend reads the record (named); the mapper reports it with
  `read-elsewhere`.
- **checked**: `fenolite check` performs the check by itself (the finding named); the mapper reports the
  record with `checked`.
- Short-Circuit and Net Antennae (change c0465, design D5) are **neutral** kinds that relax a check
  `fenolite check` performs (`rules.ALLOWANCE_KINDS`). Their enabled records map only when one of them
  relaxes it: a Short-Circuit with `ALLOWED=TRUE`, a Net Antennae with `NETANTENNAETOLERANCE` above zero.
  Otherwise each is reported with `checked`, since a rule that forbids a short or allows no antenna is the
  check Fenolite performs anyway. The warning `altium.rules.check-relaxed` of change c0462 is withdrawn.
- **carried**: no neutral rule takes the kind; the record is carried (change c0434) and reported with
  `no-counterpart`, with the reason named.

| RULEKIND | reading | rules, part or reason |
|---|---|---|
| `AcuteAngle` | carried | a minimum angle of track corners: the model holds no rule of corner angles |
| `AssemblyTestPointUsage` | carried | test point usage for assembly: no copper geometry |
| `AssemblyTestpoint` | carried | test point style for assembly: no copper geometry |
| `BoardOutlineClearance` | neutral | `edge_clearance` |
| `Clearance` | neutral | `clearance` |
| `ComponentClearance` | neutral | `courtyard_clearance` |
| `ComponentOrientations` | carried | allowed component rotations: no copper geometry |
| `DiffPairsRouting` | neutral | `diff_pair_gap`, `diff_pair_uncoupled` |
| `FabricationTestPointUsage` | carried | test point usage for fabrication: no copper geometry |
| `FabricationTestpoint` | carried | test point style for fabrication: no copper geometry |
| `FanoutControl` | carried | guidance of the fanout router: no check |
| `Height` | carried | a component height range: no copper geometry |
| `HoleSize` | neutral | `hole_size` |
| `HoleToHoleClearance` | neutral | `hole_to_hole` |
| `LayerPairs` | carried | the drill pairs vias must use: the model holds no rule of drill pairs |
| `MatchedLengths` | neutral | `skew` or `diff_pair_skew` ("Matched Lengths"); the 15 public records use delay units and are refused with `delay-units` |
| `MinimumAnnularRing` | neutral | `annular_width` |
| `MinimumSolderMaskSliver` | carried | a minimum solder mask web: no copper geometry |
| `NetAntennae` | neutral | `antenna`, `max` = `NETANTENNAETOLERANCE`, over the first scope (change c0465); mapped only when one enabled record of the document has a tolerance above zero, else `checked` (KiCad's dangling tracks) |
| `PasteMaskExpansion` | read | `convert.openings`: the paste margin of each pad (c0440) |
| `PlaneClearance` | read | the internal planes: a conversion to KiCad counts each plane lost with its rules (c0461) |
| `PlaneConnect` | read | the internal planes: a conversion to KiCad counts each plane lost with its rules (c0461) |
| `PolygonConnect` | read | `connectstyle`: each zone and pad takes the style of the record governing it (c0409) |
| `RoutingCorners` | carried | guidance of the router's corners: no check |
| `RoutingLayers` | neutral | `no_tracks` on the layers its keys close |
| `RoutingPriority` | carried | the router's order of nets: no check |
| `RoutingTopology` | carried | the router's order of connections: no check |
| `RoutingVias` | neutral | `via_diameter`, `via_drill` |
| `SMDToCorner` | carried | a distance from a surface pad to a track corner: the model holds no rule of it |
| `SMDToPlane` | carried | a distance from a surface pad to a plane connection: the model holds no rule of it |
| `ShortCircuit` | neutral | `short` over the two scopes, `ignore` for `ALLOWED=TRUE` and `error` for `FALSE` (change c0465); mapped only when one enabled record of the document has `ALLOWED=TRUE`, else `checked` (`copper.short`, and KiCad's shorting items) |
| `SilkToBoardRegionClearance` | carried | a silkscreen to board region clearance: no copper geometry |
| `SilkToSilkClearance` | neutral | `silk_clearance` |
| `SilkToSolderMaskClearance` | carried | a silkscreen to solder mask clearance: no copper geometry |
| `SolderMaskExpansion` | read | `convert.openings`: the mask margin of each pad and via, and `Board.mask_margin` (c0440, c0445) |
| `UnRoutedNet` | checked | KiCad's unconnected items |
| `UnpouredPolygon` | checked | `zone.unfilled` |
| `ViasUnderSMD` | carried | whether vias may sit in surface pads: the model holds no rule of it |
| `Width` | neutral | `track_width`; `CHECKCONNECTEDCOPPER=TRUE` is refused with `connected-copper`: Altium's connected-copper width check, which no neutral rule expresses |

## Matched Lengths

| fact | source | label | hypothesis |
|---|---|---|---|
| A net of the scope passes when its length lies between the longest net's length less the tolerance and the longest length; the options group the matched lengths, match within a differential pair, and use delay units; a target length comes only from a source target of an xSignal scope | S-2218 | INFERRED | H-A-RULE-MATCHED |
| A record holds `TOLERANCE` (a length), `CHECKNETSINDIFFPAIR`, `CHECKDIFFPAIRVSDIFFPAIR`, `CHECKXSIGNALS`, `CHECKOTHERS` (`TRUE` or `FALSE`), `USEDELAYUNITS` and `DELAYTOLERANCE` (a number, the delay); all 15 public records hold `USEDELAYUNITS=TRUE` and no target length | S-2219 | INFERRED | H-A-RULE-MATCHED |

The reading (`rules._matched_lengths`):

- `USEDELAYUNITS=TRUE`: the tolerance is the delay `DELAYTOLERANCE`; a length rule holds no delay and the
  record holds no propagation speed, so the record is refused with `delay-units`.
- Otherwise `TOLERANCE` is the maximum of one rule: `diff_pair_skew` on the scope's differential pairs when
  only `CHECKNETSINDIFFPAIR` is `TRUE`, `skew` on the scope's nets when only `CHECKOTHERS` is `TRUE`
  (neutral `skew` compares each net with the longest of the nets it selects). Any other set of groups
  (pairs against pairs, xSignals, several groups at once) is refused with `keys`.
- No record gives `length`: no public record holds a target length.

The 15 public records, all refused with `delay-units` (`tests/corpus/test_altium_rule_kinds_c0462.py` keeps the
count):

| row | rules (`NAME`) |
|---|---|
| `altium-third-party-pcbdoc-07` | `Schematic Matched Net Lengths`, `DifferentialPairs` |
| `altium-third-party-pcbdoc-08` | `XSIG-USB_DOWNLOAD`, `XSIG-USB_CONNC`, `XSIG_PCIe`, `DIFF_PAIR_INTRA`, `MIPI_RX3`, `MIPI_RX2`, `MIPI_RX4`, `MIPI_RX5`, `MIPI_RX0/1`, `XSIG-USB_M.2`, `XSIG-USB`, `XSIG-IMU`, `XSIG-SPI` |

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
| `MatchedLengths` | export (1) | S-0297 | yes: `skew` or `diff_pair_skew` (change c0462) |
| `MinimumAnnularRing` | PCB documents (4 in 3 documents) | S-0174, S-0199, S-0200 | yes: `annular_width` |
| `MinimumSolderMaskSliver` | export (4) | S-0297 | no |
| `NetAntennae` | export (1) | S-0297 | yes: `antenna` (change c0465) |
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
| `ShortCircuit` | export (1); summary (2 files) | S-0297, S-0298, S-0188 | yes: `short` (change c0465) |
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

A build writes a condition of two terms on one side in parentheses, `(A.Type == 'Via' && A.NetName ==
'VCC')`, where the conversion wrote it without them (S-2162). So property schema
`fenolite.altium-rules.v2` keys a condition by its parsed form when KiCad's closed grammar reads it, else
by its text without balanced outer parentheses (`rulecarrier.condition_key`). Version 1 keys are still
compared as they were written.

The import writes the board setup minimums of the converted document as `design.rules.minimum(...)`, and
a build writes them as rules `fenolite_0_min_<constraint>` without a condition, holding a `min` alone. A
conversion of a board that carries the records does not lower such a rule (`rulecarrier.board_minimum`):
the records hold the board's limits. When another rule without a condition holds the same `min` of that
constraint, the minimum adds nothing. Otherwise it is a reported loss (`to_altium.BOARD_MINIMUM`), never
a refusal.

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
| `no-counterpart` | the kind is in none of `RULE_KIND_MAP`, `PENDING_KINDS`, `READ_KINDS` or `CHECKED_KINDS` ("Rule kinds and their reading") |
| `read-elsewhere` | the kind is in `READ_KINDS`: another part reads it |
| `checked` | the kind is in `CHECKED_KINDS`: `fenolite check` performs it |
| `no-verified-keys` | the kind is in `PENDING_KINDS` (empty since c0084) |
| `disabled` | `ENABLED` is not `TRUE` |
| `net-scope` | `NETSCOPE` differs from the table |
| `layer-kind` | `LAYERKIND` is not `SameLayer` |
| `keys` | a key outside the header keys, the keys before `RULEKIND` and the keys of the kind, or a further condition fails |
| `value` | a limit the table needs is missing (`GAP`; at least one limit otherwise) or is not a length |
| `impedance-profile` | the record takes per-layer values from an impedance profile it does not hold ("Per-layer values") |
| `template` | `USEVIATEMPLATES=TRUE`: the vias take the sizes of the via templates the record names, and no permitted source says what the rule check tests then ("Via templates") |
| `connected-copper` | a Width record with `CHECKCONNECTEDCOPPER=TRUE`: Altium's connected-copper width check, which no neutral rule expresses ("Per-layer values") |
| `matrix-kind` | an object matrix tells apart object kinds that one neutral kind holds (an arc and a track, a fill and a region, the outline and a cutout), or names an object or edge kind outside the table ("Cells of an object matrix") |
| `delay-units` | a Matched Lengths record gives its tolerance as a delay ("Matched Lengths") |
| `scope` | a scope is outside the closed grammar and the two are no layer condition that maps, or `SCOPE2EXPRESSION` is not `All` for a unary kind |
| `no-layer` | the two scopes are a layer condition for a kind of layer the board does not hold: the rule applies to no object ("Layer scopes of Clearance") |

## Closed scope grammar

`scope.parse_scope` accepts only these forms, spelled as written, and returns a neutral selector; any
other text is refused with a reason (`scope.Refusal`, whose `reason` is `grammar`, `type`, `unit`,
`undefined`, `document`, `syntax` or one of the reasons of "Scope functions that read the document" below) and the rule is reported with the reason `scope`.

| expression | selector |
|---|---|
| `All` | `all` |
| `InNet('v')` | `net v` |
| `InNet('v1', 'v2', …)` | `or(net v1, net v2, …)` |
| `InNet('No Net')` | `not(all)` (`NOTHING`; no object) |
| `InAnyNet` | `net *` (so `Not InAnyNet` is `NO_NET`) |
| `InNetClass('v')` | `netclass v` |
| `InComponent('v')` | `ref v` |
| `InComponent('v1', 'v2', …)` | `or(ref v1, ref v2, …)` |
| `IsTrack` | `item_kind track` |
| `IsVia` | `item_kind via` |
| `IsPad` | `item_kind pad` |
| `InPolygon` | `item_kind zone` |
| `InPoly` | `item_kind zone` |
| `x And y`, `x && y` | `and(x, y, …)` |
| `x Or y`, `x \|\| y` | `or(x, y, …)` |
| `x Xor y` | `or(and(x, not(y)), and(not(x), y))` |
| `Not x` | `not(x)` |
| `x = True`, `x = 'True'`, `x <> False` | `x` |
| `x = False`, `x = 'False'`, `x <> True` | `not(x)` |
| `(x)` | `x` |

The operators are read in any letter case: `and` and `AND` are `And`, `or` and `OR` are `Or`, `not`
and `NOT` are `Not` (change c0377; `H-A-RD-PRJ-SCOPE-CASE`, INFERRED). No public source states Altium's letter-case
rule (S-1531 states none); the public documents, which Altium saved, hold scopes written with `not` and
`AND` (S-0580), and Altium's pages spell `And`, `AND` and `Not` in their examples. Change c0462 reads
`Xor`, `Div`, `Mod`, `Between`, `Like`, `True` and `False` the same way.

**Order of precedence** (change c0462; S-2211; `H-A-RD-PRJ-SCOPE-PREC`, INFERRED). Altium's Query Language page
gives the order, tightest first: brackets; `Not`; `^ * / Div Mod And`; `+ - Or Xor`; the comparisons
`= <> < > <= >=`; `&& ||`. Equal levels are read from left to right, and the page advises brackets
wherever a reading could be doubted. `parse_scope` is a precedence-climbing parser over that table. So
`InNet('A') Or InNet('B') And IsTrack` is `or(net A, and(net B, item_kind track))`, and `Not IsVia And
IsTrack` is `and(not(item_kind via), item_kind track)`. Operands of one operator next to each other merge
(`a And b && c` is one `and`), and a bracketed group stays one operand. This replaces the reading of change
c0042, which refused mixed operators because S-0296 did not give the order.

The parse is typed. A value is a set of objects (a selector), a number, a string, a boolean string
(`True`, `False`, bare or quoted) or a numeric field of the objects. An operator applied to the wrong types
is refused with the reason `type`, naming it, and the query is never bracketed again. `And` binds tighter
than a comparison, so `HoleDiameter > 1 And IsPad` is `HoleDiameter > (1 And IsPad)`, refused; `HoleDiameter
> 1 && IsPad` reads as written. `x Between a And b` takes the bound `a` up to its `And`; the bound `b` binds as
any operand at the comparison level, so `x Between 1 And 2 And IsPad` is refused too. `Xor` is written with
`and`, `or` and `not`. The arithmetic operators and `Like` are outside the grammar.

**Numbers and units** (change c0462; S-2212, "Membership Checks"). `AsMils(field)` and `AsMM(field)` compare a
length field in mils or millimetres. Without them a number is in the workspace's units, which a saved
document does not state, so a number other than 0 compared with a length is refused with the reason
`unit` unless the caller's `ScopeDocument` gives the unit. A comparison becomes a closed interval of
nanometres: `> v` is `v + 1` upward, `= v` is `v..v`, `<> v` is `not(v..v)`, `Between a And b` is `a..b`.

**Wildcards** (change c0462; S-2211, S-2212; `H-A-RD-PRJ-SCOPE-WILD`, INFERRED). Altium's wildcards are `*` and
`?`. The Membership Checks page gives `InNet('V*')` as the nets whose names start with V, and `InComponent('U*')`
as the components whose names start with U. Both functions take one or more names. So their values become
globs, `*` and `?` kept as wildcards and `[` and `]` escaped (`[[]`, `[]]`), so that a bracket matches itself.
`InNetClass` takes one class name with no wildcard in the page's examples, so every glob character of it is
escaped. The design of change c0462 asked for `InNet` values escaped whole; that would select another set
of nets than Altium does, so the reading follows S-2212.

`InNet('No Net')` selects no object (change c0462 task 5.1; `H-A-RD-PRJ-SCOPE-NONET-2`, INFERRED). An object without a
net shows the Net property `No Net` (S-1680), and change c0409 (B7) read the scope as the objects without a net
(`H-A-RD-PRJ-SCOPE-NONET`, now refuted). Altium's PCB filter, run on rows `-04` and `-07` of the public corpus, which
hold netless copper, selects nothing for it (S-2214). It is read as `NOTHING`, `not(all)`: `Not InNet('No Net')` reads
as `all`, and `'No Net'` among other values of `InNet` adds no net. The objects without a net are `Not InAnyNet`,
below, which the Altium writer has written for `model.rules.NO_NET` since change c0420.

`InAnyNet` selects the objects that are on a net, so `Not InAnyNet` selects those without one (change c0420, B7;
`H-A-RD-PRJ-SCOPE-NONET-2`, INFERRED): Altium's Attribute Checks page states that `Not InAnyNet` returns the objects
that are not nets or their primitives (S-1680). It is read as `net *`, so `Not InAnyNet` is `NO_NET` and a scope
such as `IsPad And (Not InAnyNet)` maps without a `scope` refusal. The Altium writer lowers `net *` to `InAnyNet`, so
`NO_NET` is written `Not InAnyNet` and `IsPad And (Not InAnyNet)` reads back as the same rule
(`backends/altium/rulemap.py`).

`InPolygon` (alias `InPoly`; change c0412) without an argument is the clearance query for the copper of a polygon pour: Altium's Object
Type Checks page says a clearance rule for a pour names `InPolygon` rather than `IsPolygon`, because the
clearance applies to the primitives of the pour (S-1702; change c0412, `H-A-RULE-SCOPE`, INFERRED).
KiCad's `A.Type == 'Zone'` (`item_kind zone`) names the same copper in a clearance. `InNamedPolygon('n')`,
which names one pour, stays outside the grammar.

### Scope functions that read the document

Change c0462 (task 2; S-2212, `H-A-RD-PRJ-SCOPE`, INFERRED) reads the functions below when the caller gives a
`scope.ScopeDocument`, which `read.scopedoc.scope_document` gathers from the read PCB document: the copper layers,
whether any via spans part of the stack, the nets, the differential pairs (`DifferentialPairs6`, `NAME`,
`POSITIVENETNAME`, `NEGATIVENETNAME`), the classes, the components with their designators, footprints, kinds,
rotations and pads, the polygon names, and whether the pads without a hole are plated. A function expands to
the neutral leaves of the objects it selects in that document; a function whose selection no leaf holds
exactly is refused with a named reason, never widened. An expansion that selects no object is `not(all)`
(`scope.NOTHING`). Names are compared in any letter case, `*` and `?` as wildcards (`H-A-RD-PRJ-SCOPE-WILD`);
the leaves carry the document's own names, every glob character escaped.

| function | selector | refused (reason) |
|---|---|---|
| `OnTopLayer`, `OnBottomLayer`, `OnOutside`, `OnMid` | `and(layer…, not(MULTI_LAYER))`, the layers of id 1, 32, both, or the inner signal layers | a board without the layer (`undefined`) |
| `OnMultiLayer` | `MULTI_LAYER` = `or(item_kind via, pad_type th, pad_type npth)` | — |
| `ExistsOnLayer('L')`, `OnLayer('L')` | `or(layer L, MULTI_LAYER)` | `L` no copper layer (`undefined`); a via spanning part of the stack (`via-span`) |
| `InDrillLayerPair('A - B')` | `item_kind via` for the pair of the top and bottom layers, else `NOTHING` | a via spanning part of the stack (`drill-pair`) |
| `InDifferentialPair('P', …)`, `InAnyDifferentialPair` | `or(net positive, net negative, …)` of the pairs | — |
| `InDifferentialPairClass('C')` | the nets of the class's pairs | `C` not defined once (`undefined`) |
| `IsDifferentialPair` | the same nets, for a rule that judges pair objects | any other rule (`object-kind`) |
| `HasFootprint('F')` | `or(ref …)` of the components whose footprint matches | a designator shared with another component, or empty (`designator`) |
| `IsComponent`, `IsNetTieComponent`, `InComponentClass('C')`, `IsBGA`, `IsSOIC`, `IsLCC` | `or(ref …)`, for a rule that judges component objects | any other rule (`object-kind`); a component kind not known to be Net Tie or not (`undefined`); a package check that cannot decide (`package-check`) |
| `CompPinCount` compared with a number | `or(ref …)` of the components whose pad count complies; for a comparison that a free object meets (its count is 0), `not(or(ref …))` of the components that do not comply, or `all` | as `HasFootprint` |
| `HoleDiameter`, `HoleSize` compared with a length | `hole lo..hi` | an interval that holds 0 (`hole-zero`); a pad on one layer with a hole size (`document`) |
| `PadIsPlated = True`, `PadIsPlated = False` | `or(pad_type th, …)` of the plated pads, or of the unplated ones | pads without a hole that are neither all plated nor all unplated (`pad-plated`) |
| `InNamedPolygon('P')` | `zone P` | `P` not in the document (`undefined`) |
| `IsNamedPolygon('P')` | `zone P`, for a rule that judges pour objects | any other rule (`object-kind`); as `InNamedPolygon` |
| `InxSignal`, `InxSignalClass` | — | always (`xsignal`): an xSignal runs between two pads, which no leaf holds |
| `InNamedUnion` | — | always (`union`) |
| `WithinRoom` | — | always: a room the document holds is `room-membership` (a pad or via is in a room by its centre, any other object only wholly inside, S-2212; the neutral `area` leaf selects by touch, `H-K-AREA-COND`), one it does not hold `undefined`. The rooms are read as rule areas (`read.rooms`, c0462 task 2.3) |

**Layer property and Multi-Layer** (`H-A-RD-PRJ-SCOPE-MULTI`, INFERRED). The Layer Checks page says `OnOutside` returns
no object on Multi-Layer and points to `ExistsOnLayer` to include them (S-2212). So an `On…` check reads an
object's Layer property, and vias and pads with a hole, whose Layer is Multi-Layer, are not on the top layer;
`ExistsOnLayer` returns them, and they exist on every copper layer only when every via spans the whole stack, so a
document with blind or buried vias refuses it. The design of change c0462 wrote `OnTopLayer` as `layer F.Cu`; that
would take the vias too, so the reading follows S-2212.

**Parents and children.** `IsNamedPolygon`, `IsComponent`, `IsNetTieComponent`, `InComponentClass`, `IsBGA`, `IsSOIC`,
`IsLCC` and `IsDifferentialPair` return the parent object without its children (S-2212). A neutral rule judges copper
primitives, so they map only for a rule kind whose subject is that parent: `ComponentClearance` and `FanoutControl`
(components), `PolygonConnect` (pours) and `DiffPairsRouting` (pairs) (`scope.PARENTS`, `scope.for_kind`).
`InDifferentialPair`, `InDifferentialPairClass` and `InNamedPolygon` return the parent with its children, and the
children are the objects of the pair's two nets and the copper of the pour. Change c0462 read
`InDifferentialPairClass` as parent-only; Altium's PCB filter on rows `-07` and `-08` selects the tracks, vias and
pads of the class's pairs (S-2214), so it maps for every rule kind. A pair maps to `net` leaves, not `diff_pair`: a
primitive's subject does not carry its pair, and the nets select the same primitives.

**Units of a number** (`H-A-RD-PRJ-SCOPE-UNIT`, INFERRED). A number compared with `HoleDiameter` without `AsMils` or
`AsMM` is in the document's measurement unit (S-2212, "Fields"). `scope_document` takes it from the board record's
`DISPLAYUNIT` (1 mil, 0 mm; `pcb-document.md`); that the query reads this unit is not stated by a source.
The bound `0` needs no unit: it is the same length in every unit, so `HoleDiameter > 0` maps to `hole 1..` whatever
the document's unit, and a non-zero bare number on a document without `DISPLAYUNIT` is refused. On the public rows
(2026-11-06) the only scopes that compare a hole size are the two Hole Size records of row 05, both
`HoleDiameter > 0` (with `PadIsPlated` `True` and `False`): both map, and no row holds a non-zero bare number, so the
corpus can neither confirm nor refute the unit.

**Package checks** (`read.packages`; `H-A-RD-PRJ-SCOPE-PACKAGE`, INFERRED). The Attribute Checks page defines the three
checks by rows and columns of a component's pads, all surface mount (S-2212): `IsBGA` at least 10 rows and 10 columns,
rows and columns differing by less than 6, and at least half of rows times columns pads; `IsSOIC` exactly 2 rows and at
least 3 columns, or the converse, every place of the grid holding a pad; `IsLCC` two rows and two columns of at least 4
pads each. The page does not say how pads are grouped into rows. `read.packages` groups pad centres along the
board's axes into lines within 100 file units (`LINE_TOLERANCE`) and refuses a component turned by an angle
that is not a multiple of 90 degrees (`package-check`). `tests/unit/backends/altium/test_scope_packages_c0462.py`
holds an authored SOIC of 8, an LCC of 16 on four sides, a BGA of 10 by 10 and a two-pad chip; each check selects
only its own.

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
| `WithinRoom`, `InNamedUnion`, `InxSignal`, `InxSignalClass`; and, outside the rule kinds that judge them, `IsDifferentialPair`, `InComponentClass`, `IsNamedPolygon` | no neutral leaf holds a room, a union or an xSignal, and a rule on copper primitives does not judge a parent object (since change c0462 the other functions map, "Scope functions that read the document") |
| `OnLayer`, `ExistsOnLayer` on a board with blind or buried vias | the neutral subject holds no via span (`via-span`; since change c0462 the layer functions map when joined with other terms) |
| Clearance with `NETSCOPE=AnyNet` | a neutral clearance holds between different nets; a clearance between objects of one net has no counterpart, so mapping the record would drop half of it |
| HoleToHoleClearance with `ALLOWSTACKEDMICROVIAS=TRUE` | the neutral rule has no exception for stacked micro-vias |
| Clearance with `IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE`; an object matrix that tells apart an arc and a track, or a fill and a region; an edge matrix that tells the outline from a cutout | the neutral rule cannot leave out the pads of one footprint (change c0125), and no neutral kind tells those objects apart (change c0462) |
| Width with per-layer widths or impedance keys (`FAVIMP`, `MAXIMP`, `<LAYER>_MINWIDTH`) | read since change c0462 ("Per-layer values"); a profile-driven record without every layer stays `impedance-profile` |
| RoutingVias with via template keys | since change c0462 the keys alone are unused; template mode stays `template` ("Via templates") |
| PlaneConnect, PolygonConnect | no neutral rule; the board keeps Polygon Connect Style records (change c0215) |
| SolderMaskExpansion, PasteMaskExpansion | no neutral rule; the pad's expansion modes are `INFERRED` (`pcb-read.md`, `PadRecord`), so a pad following the rule cannot be told apart |
| FanoutControl, ShortCircuit, UnRoutedNet, RoutingTopology, RoutingPriority, RoutingLayers, RoutingCorners, DiffPairsRouting, MatchedLengths, test point kinds, silk and mask sliver kinds, Height, LayerPairs, NetAntennae, UnpouredPolygon, ComponentClearance, PlaneClearance | no neutral rule kind holds them (`no-counterpart`); since change c0462 each kind's reading is in "Rule kinds and their reading" |

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

A matrix with an entry of another length is read cell by cell ("Cells of an object matrix", changes
c0130 and c0462); it stays unmapped (`matrix-kind`) when it tells apart object kinds that are one neutral
kind. A record with
`IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE` stays unmapped (`keys`): no selector says "two pads of one
component". Any other value of a cell key stays unmapped (`keys`): a cell for a named class is in no
public file, so its scope text is not known.

### Cells of an object matrix

Change c0130, widened by change c0462 (design D5). `rules.read_matrix` reads a matrix of differing
clearances in the neutral kinds (`rules.MATRIX_CLASSES`, by `rules.MATRIX_KINDS`). The value of a pair
of object kinds is its entry, or `GAP` without one.

| object kind | neutral kind | selector |
|---|---|---|
| `Arc`, `Track` | `track` | `item_kind track` (the copper check sees an arc as a track, as KiCad's `Track` type does) |
| `SMDPad`, `THPad` | `pad`, or `smd` and `th` when the two differ | `item_kind pad`; `pad_type smd`; `or(pad_type th, pad_type npth)` (`H-A-RULE-MATRIX-NPTH`) |
| `Via` | `via` | `item_kind via` |
| `Poly` | `zone` | `item_kind zone` (the poured copper of a polygon) |
| `Fill`, `Region` | `graphic` | `item_kind graphic` (a free fill or region on copper is a copper graphic of the import) |
| `Text` | `text` | `item_kind text`: no item of the copper check, but a rule `all` selects copper text on another target, so a text cell is a rule of its own; the KiCad writer reports it as a loss of that rule |
| `Hole` | none | a hole cell governs only a pad without annular ring, and only under an option of Altium (S-2249); no neutral `clearance` rule holds the clearance of a hole, the rule of a plain record included |

- A pair of neutral kinds is a cell when its value differs from `GAP`, and gives one more `clearance`
  rule: name `<NAME>/<kind>-<kind>`, the record's priority, the kinds' selectors on both sides (joined with
  `and` to the record's scope on its side). It governs above the rule of `GAP` of its record: among rules
  of one priority the later name governs, and the selectors of two kinds select no object in common, so
  no two cell rules of a record meet. A record with two different scopes gets a second rule with the kinds
  exchanged for a cell of two kinds. The cell rules hold the record's priority, so no rule of another
  record changes rank.
- Object kinds of one neutral kind (`Arc` and `Track`, `Fill` and `Region`) that differ for some
  partner are said by no neutral rule: the record stays unmapped (`matrix-kind`), and the detail names the
  first two entries that differ, for example `Arc-Poly 0 mm and Track-Poly 0.25 mm`. A surface pad and a
  through-hole pad that differ become the kinds `smd` and `th`. An object kind outside the table is
  refused too (`matrix-kind`, naming the cell). Part of a record is never mapped.
- An entry of `Hole` changes no rule; the rule of `GAP` keeps such entries as written in its bag
  (`cells_not_lifted`).
- `RuleMapping.matrix_cells` counts, per enabled Clearance record with entries, those a rule holds and
  those none holds; the copper stage of a document check reports the sums as `summary.clearance_cells`.
- A cell of 0 is a rule of 0: no clearance is asked of the pair, and a short is still a short.
- A record whose matrix holds an entry is kept (`adapter.rules.kept_indexes`): the Altium writer writes an
  empty matrix and no scope of a kind of object, so it writes the record back as read.
- The unit test `tests/unit/backends/altium/test_rule_keys_c0462.py -k matrix` evaluates every pair of
  object kinds against the rules of an authored matrix, cells above and below `GAP`; the corpus test
  `tests/corpus/test_altium_rule_kinds_c0462.py::test_every_matrix_holds_its_cells` does it for every
  matrix of the 8 public rows read alone, three of which are refused (`matrix-kind`).

A Board Outline Clearance record holds a matrix of object kinds against edge kinds (S-2217). Its entries
pair an object kind of the table above with an edge kind, in either order:

| edge kind | judged as |
|---|---|
| `OutlineEdge` (the board's outer edge), `CutoutEdge` (a cutout's edge) | the board's edge: the edge check of Fenolite judges both rings with one `edge_clearance` rule |
| `CavityEdge`, `SplitBarrior`, `SplitContinuation` (a cavity, a split line of a layer stack region, spelled as written) | none: the model holds no cavity and no layer stack region, so the entry changes no rule (`cells_not_lifted`) |

An object kind whose entry against the outline differs from its entry against a cutout is said by no
neutral rule (`matrix-kind`). Each object kind whose value differs from `GAP` gives one more
`edge_clearance` rule, name `<NAME>/<kind>`, selector the kind's joined to the record's scope. The edge
matrices are not counted in `matrix_cells`.

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
| `OnMid` | no internal signal layer | unmapped with `no-layer`: no object is on such a layer, so the rule applies to nothing. The record is no unread rule (`rules.NOT_APPLYING`), and its info is `altium.rule.applies-to-nothing`, not `altium.rule.unmapped` (c0462) |
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
