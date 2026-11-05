## MODIFIED Requirements

### Requirement: Board graphics and keep-out records
Board graphics on the non-copper layers of the board layer map SHALL be written as track, arc and region records without a net. Board graphics on a signal layer of the written stack SHALL be written as copper records on that layer with the net index of their net (change c0412). Keep-outs SHALL be written as region records with the keep-out flag and the restriction set of the model, on the Keep-Out layer when they name every copper layer of the board, else one per copper layer.
- A filled rectangle or polygon on a signal layer MUST be one region record with `KIND=0`, its layer's id and its net's index in the common prefix (`0xFFFF` for a shape without a net), in `Regions6` and in `ShapeBasedRegions6`. A drawn line, arc, circle, rectangle or polygon outline on a signal layer MUST be tracks and arcs of its width with that net. No fill record is written: `docs/formats/altium` records no field after offset 37 of a fill, whose saved lengths are 46 and 50.
- A shape on an internal plane, a filled circle, a shape that `pcbdoc.graphic_problem` refuses, and a shape whose net no net record holds MUST give `altium.not-lowered` with the kind `copper-shape` and `where` `graphic/<id>`; `copper-shape` stays a loss kind, which `FEN-7001` refuses without `--allow-lossy`.
- A keep-out record MUST hold its restrictions value in two keys, `KEEPOUTRESTRICTIONS` (the key saved documents hold) and after it `KEEPOUTRESTRIC` (the key KiCad's importer reads; not a key Altium writes), both with the same value (the maintainer's decision of 2026-10-06), so that KiCad imports the keep-out with exactly the restrictions written. That Altium accepts the pair stays `INFERRED` until step X11 of Part X.
- A restriction that the record cannot carry (`no_footprints`) MUST give `altium.not-lowered` with `where` `keepout/<id>` naming the restriction; the keep-out is written with the others, and not at all when it has no other.
- A graphic that has no record (a layer outside the map, a drawn shape without a positive width, a filled circle, a shape without an extent) MUST give `altium.not-lowered` with `where` `graphic/<id>`. A graphic on `Edge.Cuts` is the outline and counts as written.
- The board outline MUST stay as written before this change.

#### Scenario: Keep-out with two restrictions
- **GIVEN** a keep-out that forbids tracks and vias in a rectangle on all copper layers
- **WHEN** the document is written and read back
- **THEN** one keep-out region with those two restrictions is read, its value 3 in `KEEPOUTRESTRICTIONS` and in `KEEPOUTRESTRIC`

#### Scenario: Copper polygon with a net
- **GIVEN** a KiCad board with a filled `gr_poly` on `F.Cu` on the net `VIN`, a filled `gr_rect` on `B.Cu` without a net and a drawn `gr_line` on `F.Cu` on `GND`
- **WHEN** it is converted with `convert --to altium` without `--allow-lossy`
- **THEN** the write succeeds, the document holds one region on the top layer with the index of `VIN`, one region on the bottom layer with no net and one track on the top layer with the index of `GND`, the report has no `copper-shape` loss, and KiCad's import of the document holds the shapes on their layers and nets

#### Scenario: Copper on a plane stays a loss
- **GIVEN** a filled polygon on an internal plane layer
- **WHEN** the board is converted without `--allow-lossy`
- **THEN** `FEN-7001` names `copper-shape` for that graphic

### Requirement: Scoped rule records
Rule records SHALL carry the scope of their rule as an expression of the closed scope grammar of `altium-project-reader` ("Closed scope grammar"): all objects (`All`), a net (`InNet('<net>')`), a net class (`InNetClass('<class>')`), a component (`InComponent('<ref>')`), an item kind (`IsTrack`, `IsVia`, `IsPad`, and `InPolygon` for `zone`), and their combinations with `And`, `Or` and `Not` (change c0412); a `clearance` rule with a second selector uses both scope fields, and every other kind writes `All` as its second scope. Every written scope MUST be one that `read.scope.parse_scope` turns back into the rule's selector.
- An operand that is itself a conjunction, a disjunction or a negation MUST be written in parentheses, because the grammar holds one kind of operator per parenthesis level.
- A layer is not a written scope: the closed grammar refuses layer functions, so a rule with `layers` or a `layer` selector MUST give `scope-unsupported`.
- Rules of one Altium kind MUST be written from the most governing neutral rule to the least (priority 1, 2, … and then priority 0; ties by falling name, then id), with `PRIORITY` from 1 in that order within the kind. This is the reverse of the order of a KiCad rules file, where the last rule governs.
- A selector outside the written forms (a glob, a value that holds `'` or cannot be written, an `area` or `diff_pair` leaf, an item kind other than `track`, `via`, `pad` and `zone`, a second selector for a kind other than `clearance`) MUST give the reason `scope-unsupported` for that rule only; the other rules of the kind are written.
- Rule names MUST be unique in the document and derived from the kind and the scopes (`<Kind>`, `<Kind>_<class>`, `<Kind>_net_<net>`, `<Kind>_ref_<ref>`, `<Kind>_<item>` for an item kind, `_and_`, `_or_` and `not_` for the operators, `_to_` before the second scope; a repeated name gets `_2`, `_3`…), so that two builds give equal names.

#### Scenario: Class rule above the general rule
- **GIVEN** a design with a track width (minimum, preferred and maximum) for all nets and another, of priority 1, for the class `PWR`
- **WHEN** the PCB document is written and read back
- **THEN** two Width rules exist, `Width_PWR` with the scope `InNetClass('PWR')` and `PRIORITY=1`, and `Width` with the scope `All` and `PRIORITY=2`

#### Scenario: A scope outside the grammar
- **GIVEN** a `track_width` rule on the net glob `PWR_*`, a second on the layer `F.Cu` and a third on the class `PWR`
- **WHEN** `lower` runs
- **THEN** one record `Width_PWR` is written, and the two others are named with the reason `scope-unsupported`

#### Scenario: Composite clearance scopes
- **GIVEN** clearance rules on `and(ref J1, item_kind pad)`; on `net A` against `or(net B, net C)`; on `netclass HV` against `and(item_kind zone, not(netclass HV))`; and on `and(item_kind pad, net SENSE)` against `not(netclass HV)`
- **WHEN** `lower` runs and the records are lifted again
- **THEN** four Clearance records are written with the scopes `InComponent('J1') And IsPad`; `InNet('A')` and `InNet('B') Or InNet('C')`; `InNetClass('HV')` and `InPolygon And (Not InNetClass('HV'))`; `IsPad And InNet('SENSE')` and `Not InNetClass('HV')`, and the lifted rules equal the lowered ones

#### Scenario: Pads without a net
- **GIVEN** a single-sided clearance rule on `or(and(or(ref R1, ref R2), item_kind pad), and(ref U1, item_kind pad, not(or(net A, net B))))`
- **WHEN** `lower` runs and the record is lifted again
- **THEN** one Clearance record is written with the first scope `((InComponent('R1') Or InComponent('R2')) And IsPad) Or (InComponent('U1') And IsPad And (Not (InNet('A') Or InNet('B'))))` and the second `All`, and the lifted rule equals the written one

#### Scenario: Limit combinations
- **GIVEN** `track_width` rules with min, opt and max (scoped `all` and by a class), with min only and with min and max; `via_diameter` rules with min, opt and max beside a `via_drill` rule of the same selector, alone (scoped `all` and by a class) and with min only; and `hole_size` rules with min and max and with min only
- **WHEN** `lower` runs on each
- **THEN** the full Width rules, the via pair and the min-and-max Hole Size rule are written, and every other rule is one `value-unsupported` loss whose detail names the missing limit, or the missing partner rule, because no record read leaves a limit out

### Requirement: Mechanical layers of KiCad drawings
`lower.KICAD_MECHANICAL` SHALL map `User.1` to `User.8` to Mechanical 1 to 8, `Dwgs.User` to Mechanical 9, `Cmts.User` to Mechanical 10, and `Eco1.User` and `Eco2.User` to Mechanical 11 and 12; the fabrication and courtyard layers keep Mechanical 13 to 16. A user layer whose KiCad user name is `Mech.<n>` or `Mechanical <n>`, n from 1 to 16, SHALL be written on Mechanical n instead, whatever its number (change c0412).

#### Scenario: Detailed contract for mechanical layers of kicad drawings
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

`lower.KICAD_MECHANICAL` SHALL map `User.1` to `User.8` to Mechanical 1 to 8, `Dwgs.User` to Mechanical 9, `Cmts.User` to Mechanical 10, and `Eco1.User` and `Eco2.User` to Mechanical 11 and 12; the fabrication and courtyard layers keep Mechanical 13 to 16. A `User.<k>` layer of `Board.layers` whose `kicad` bag holds the user name `Mech.<n>` or `Mechanical <n>` (1 ≤ n ≤ 16) MUST be mapped to Mechanical n, replacing its fixed position; another layer that the fixed map puts on Mechanical n keeps it. A graphic or text on a mapped layer MUST be written there and the document MUST name the layer after its KiCad name. A text on a copper layer MUST be written as a text record on that copper layer. A layer outside the map, a user layer above `User.8` without such a name among them, MUST stay a reported loss.

#### Scenario: Drawing on Dwgs.User
- **GIVEN** a board with one line on `Dwgs.User` and one text on `F.Cu`
- **WHEN** it is written and read back
- **THEN** the line is on Mechanical 9, the text on the top copper layer, and the report loses neither

#### Scenario: User layer named after a mechanical layer
- **GIVEN** a board whose layer `User.11` has the user name `Mech.13` and holds a line, and whose `User.12` has no user name and holds a line
- **WHEN** it is converted with `convert --to altium`
- **THEN** the first line is on Mechanical 13 and the report holds no loss for it, and the second is reported as a `graphic` loss naming `User.12`

### Requirement: Imported boards are written from the model
`backends.altium.lower.from_design(design, *, issues, options=None, corner_ratios=None, rewrite=False, bodies="off")` SHALL return the inputs of the PCB and schematic writers (`AltiumInputs`) from a `Design`: footprints with their pads, graphics, fields and texts taken from the board's footprint instances (no library is read), placements, copper, zones, free items, rules, the stack and the classes.
- A footprint instance MUST be written as a component with its own pads: its footprint definition holds exactly the pads of the instance that the pad record can hold. Its graphics, its fields `Reference` and `Value` and its texts are written as "Footprint items of a written component" says. An instance that holds none (a model stored before change c0126, a design read from KiCad without the projection) is written with its pads alone, as before. The definition holds no body: the bodies of an instance are written into the document (change c0121), not into a library.
- A footprint without a reference and a footprint link whose one pad stands alone (the import's reading of a free pad) MUST be written as a free pad, with its net.
- Native ids of the model that are Altium unique ids MUST be reused: the record's `UNIQUEID` is the id of `fp:<id>`, and `SOURCEUNIQUEID` and the unique id of the schematic part are the last part of `cmp:<source unique id>` (`project.native_unique_id`) when one component alone holds it; the instances of a repeated sheet share that id and get derived ones.
- A board read from an Altium document (`"altium" in board.native_ids`) MUST be written in the document's own frame (`pcbdoc.Frame.document()`: Y negated, nothing moved) with the origin that the import kept, so every coordinate keeps its units; any other board is written in the frame of a build.
- An `Arc` of the board, and a graphic of kind `arc`, whose `altium` bag holds the pair `arc` (`altium-import`, "Extension bags"; change c0127) MUST be written with the centre, the radius and the two angles of that pair when the pair still says the entity's three points. `lower.kept_arc(entity, points, frame)` decides: it converts the pair as the import does (`adapter.units.arc_points`) and returns the record's geometry (`pcbrecords.ArcGeometry`) when each of the three points it gives lies within `lower.ARC_TOLERANCE` (2 nm per axis, the length tolerance of the written scope) of the entity's point in the frame of the written document; `from_design` puts it into `PcbDocSpec.arc_records` under the entity's id. It returns `None`, and the arc is written from its three points as an arc without the pair is, with no issue, when the pair is stale or unusable: a point lies further away (the arc was moved or reshaped in the model, or the board is written in another frame than the document's), the pair does not parse into three integers of 32 bits and two doubles, the radius is 0 or less, an angle is not finite, or the angles make a full turn. An arc that is written from its kept record MUST NOT be refused because its three points lie on one line: the record holds its circle.
- `rewrite=True` (change c0128) says that `design` is the reading of an Altium document and that the write gives that document back. A via whose drill equals its diameter MUST then be written (`PcbDocSpec.allow_full_drill`): a document that Altium saved holds such vias (`pcb-copper.md`, "Via"; `H-A-PCBX-VIA-FULL`). Without `rewrite` such a via is left out and counted, as before: a design from a script, from a KiCad board or from any other source is written with the rule of a build. `rewrite=True` for a design whose board was not read from an Altium document (`"altium"` is no key of `board.native_ids`) MUST raise `ValueError`; a design without a board takes the argument without effect. The argument changes nothing else: the frame, the kept arc records and every other item are written the same with and without it; component bodies are written by `bodies` alone, in a rewrite as in any other write.
- The outline MUST be `Board.outline`, else the first closed ring of the `Edge.Cuts` graphics (an arc gives its start, middle and end), else the box of the board's items; each approximation is counted under `outline`.
- An item that the writers do not carry MUST be left out, counted per kind in `AltiumInputs.not_lowered` with its id, and reported once per kind with `altium.not-lowered`: a pad with a per-layer padstack, a custom or trapezoid shape, a slot, no copper layer, no number, or a rounded rectangle without a known corner ratio; a track or arc on a layer that is no signal layer of the written stack; an arc whose three points lie on one line and that is not written from a kept record; a via that `pcbdoc.via_span` refuses or whose drill is not below its diameter (in a rewrite: is above its diameter), or is 0 or less; a zone without an outline in the model; a text, graphic or keep-out that `pcbdoc` refuses or whose layer has no layer in the document; a shape on a copper layer that "Board graphics and keep-out records" does not write (`copper-shape`: a shape on a plane, a filled circle, a shape that `pcbdoc.graphic_problem` refuses; change c0412); the poured copper of a zone (`zone-fill`: a polygon is written unpoured); a component body that "Component bodies are reported" does not write, which is every body when `from_design` is called without `bodies="extruded"` (change c0121); a graphic or a text of a footprint that the records do not carry (`footprint-graphic`, `footprint-copper`, `footprint-text`); a rule that `rulemap.lower` does not write; a net or net class whose name no record holds; an internal plane without a net of the document (`plane`); stack-up values that do not fit (`stackup`); and of the circuit (change c0083), each as an info: the pin-to-pad map of a component (`pin-pad-map`: `Component.pin_pad_map` with the bag key `pin_pads`), a module (`module`: the generated schematic is one sheet) and the channel of a repeated sheet (`channel`: the bag keys `sheet_symbol` and `channel_index` of a module).
- `AltiumInputs.written` MUST count the model items that the PCB document holds, per kind of `lower.KINDS`, which are the kinds of `lens.altium_copper.KINDS`.
- The schematic's design (`lower.schematic_design`) MUST give every component with a reference a symbol link, a value and pins, so that the schematic writer can generate a sheet from the circuit; a part of a link that no record holds is replaced by a generic one.

#### Scenario: Footprints without a library
- **GIVEN** a design read from a KiCad board whose footprint libraries are not present
- **WHEN** `lens.altium.write_model` runs
- **THEN** the PCB document holds every footprint as a component with its pads, and no library file is read

#### Scenario: Own documents
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k own_document` writes the models of `blink.PcbDoc`, `routed.PcbDoc` and `board6.PcbDoc`
- **THEN** each written project holds a PCB document, a schematic, its library and the project file, the reading of each PCB document equals the first reading inside the written scope, and the unique ids of the components are those of the first document

#### Scenario: Arc written from its record
- **GIVEN** the reading of a document with a free copper arc of centre (1 000 000, 2 000 000) units, radius 100 units and angles 30 to 35 degrees, whose three points give another centre and a radius of 93 units when a record is derived from them, and a second arc of the same centre and radius from 0 to 1 degree, whose three points lie on one line
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k kept_arc` writes the model with `AltiumBackend().write` and reads the written document
- **THEN** `PcbDocSpec.arc_records` names both arcs, both are counted as written, the two arc records of the written document hold the centre, the radius and the angles of the first document, and the second reading holds the same six points as the first

#### Scenario: Stale record ignored
- **GIVEN** the same reading with the first arc moved by 1 µm in the model, its bag unchanged
- **WHEN** `from_design` runs
- **THEN** `PcbDocSpec.arc_records` does not name that arc, no issue names it, and the written record's centre is the one derived from the moved points

#### Scenario: Full drill in a rewrite only
- **GIVEN** the reading of `tests/data/altium/routed/routed.PcbDoc` with the drill of its first via set to the via's diameter, and of a second via set above its diameter
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k full_drill` calls `from_design` without and with `rewrite=True`
- **THEN** without it both vias are counted as not written with the reason `the drill is not below the diameter`; with it the first via is written with a hole equal to its diameter, reads back with that drill, and only the second is counted; and `rewrite=True` on the design read from `tests/data/kicad/board/two_layer.kicad_pcb` raises `ValueError`

#### Scenario: Counted once per kind
- **WHEN** `from_design` runs on the model of `tests/data/altium/board6/board6.PcbDoc`
- **THEN** `counts()` is 1 graphic (the one on the keep-out layer), the one issue is an `altium.not-lowered` info for `graphic`, and `written` counts 27 under `footprint-graphic`

