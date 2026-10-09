# specctra-dsn Specification

## Purpose
Fenolite's own writer of Specctra design files and reader of Specctra session files: the exchange format that lets an external autorouter such as Freerouting route a board without Fenolite importing its code. The capability states which part of the format is written and read, how units and names map to the model, and what is refused.

## Requirements

### Requirement: Specctra codec package
`fenolite.backends.specctra` SHALL be a codec package that writes Specctra design files and reads session files. It MUST NOT be registered in `fenolite.backends.registry`, MUST import only `core`, `model`, `geometry` and `backends.base`, and MUST hold a `PROVENANCE.md` naming each source and how it was used. No text, table, grammar production or example of S-0224 MUST appear in the repository.

#### Scenario: Not a registered backend
- **WHEN** `registry.all_backends()` is called
- **THEN** no backend is named `specctra`

#### Scenario: Layering holds
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; a module under `backends/specctra/` importing `fenolite.backends.kicad` makes it fail

### Requirement: Specctra syntax
`backends.specctra.lexer.parse(text, *, file="") -> SNode` SHALL read parenthesised lists of words and quoted strings, and `dumps(node)` SHALL print them.
- The quote character MUST be the one the file declares with `string_quote`, and `"` before any declaration. Blanks inside a quoted string MUST be kept only after `(space_in_quoted_tokens on)`; otherwise a blank ends the string.
- Malformed input MUST raise `FormatError` with a byte offset.
- The writer MUST declare `(string_quote ")` and `(space_in_quoted_tokens on)`, and MUST quote every name that is not a plain word: a word holds no blank, parenthesis, semicolon, quote character or line end.

#### Scenario: Round trip of an authored file
- **GIVEN** `tests/data/specctra/two_pads.dsn`, authored for Fenolite
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_lexer.py` parses it and prints it
- **THEN** parsing the printed text gives an equal tree

#### Scenario: Unbalanced input
- **WHEN** `parse("(pcb x (unit um)")` is called
- **THEN** `FormatError` is raised with an offset

#### Scenario: Declared quote character
- **GIVEN** a file whose `parser` section says `(string_quote $)` and `(space_in_quoted_tokens on)`
- **WHEN** it holds the net name `$A (1)$`
- **THEN** `parse` gives the name `A (1)`, and `dumps` quotes it again with `$`

### Requirement: Design files are written from the model
`backends.specctra.dsn.write_dsn(design, *, pads, outline, selected, defaults, plane_layers=(), net_layers={}, others="declared") -> DsnResult` (`others` is change c0109's, "Nets outside the routing job in design files") SHALL write a design file for the board, from the model, the board-frame pads of `BoardFrame.board_pads` and the outline rings.
- **Units.** `(resolution um 10)` and `(unit um)`: the database unit is 100 nm. Every length MUST be rounded to `u = round_half_even(nm / 100)` database units and written in micrometres as `u / 10`, with at most one decimal and no trailing `.0`; Y is negated. Lengths that were not multiples of 100 nm MUST be counted in one `specctra.rounded` (info).
- **Structure.** One layer per copper layer in stack order, of type `signal`, or `power` for a layer of `plane_layers` ("Plane layers in design files"); a `rect` boundary on the layer `pcb` with the bounding box of `outline[0]`, and a `path` boundary of width 0 on the layer `signal` with the ring `outline[0]`; the planes of "Plane layers in design files"; a keep-out polygon on `signal` per cut-out ring; a `keepout`, `wire_keepout` or `via_keepout` polygon per copper layer of each model keep-out that forbids tracks, vias or both; one via padstack per distinct diameter and drill among the selected nets; a default rule with `defaults`' width and a clearance of at least `defaults.clearance`, raised as "Routing rules in design files" states.
- **Components.** One image per placed footprint, placed at the footprint's position with rotation 0 on the front and locked; pins at each pad's rounded board-frame position minus the footprint's rounded position; padstack shapes per layer from the pad's `PadCopper` entries: a `circle` for a disc, a `path` for an open polyline with a width, a `polygon` for a ring (the outer hull when a convex ring has a width). A ring with a width that is not convex MUST be written as its bounding rectangle grown by half the width. That case, and a pad with an entry flagged `exact == False`, MUST give `specctra.pad-approximated` (warning). Equal padstacks MUST be shared.
- **Network.** Every net with pads, its pins as `REF-PIN`, but a net of one pad whose name starts with `unconnected-(`, the name KiCad gives a pin on no net: such a net MUST NOT be declared, and its pad MUST be written as a pin on no net, so a router gets the same board with and without those names (the writer does this since c0061; this sentence records it). One class per net class with its nets, width, clearance and via, written once per layer set of its nets with `use_layer` ("Routing layers in design files"), and the values, `layer_rule` and `class_class` lists of "Routing rules in design files".
- **Wiring.** Every existing track and via, with type `protect`. An arc MUST be written as one wire whose path stays within the kernel's arc error bound.
- **Names.** `DsnResult.names` MUST map each emitted net, component, pin, layer and via-padstack name to the model's, and MUST hold each component's written position and the protected wiring. A name the syntax cannot carry (empty, or holding the quote character or a line end) MUST be replaced and reported with `specctra.renamed` (info). Pin ids MUST be unique in their image, references MUST be unique in the file, and neither MUST hold a hyphen: a repeated name, an empty one and a hyphen are replaced the same way.
- The text MUST be deterministic: equal inputs give equal bytes, with nets, classes, images, padstacks, planes and keep-outs in a fixed order.
- A call without `plane_layers` and `net_layers`, for a design whose `RuleSet` holds no rule, MUST write the text that the writer wrote before change c0107.
- With `others="netless"` (c0109) two kinds of nets outside the job MUST stay declared with their class: a net of a plane this file holds (`_Writer.plane_nets()`, the hook c0109 left, returns the nets of the `plane` lists), and a net whose clearance as the file writes it is above the default rule's: its class clearance after "Routing rules in design files" raised it, or a `class_class` list that pairs its class with the class of a selected net.

#### Scenario: Two-pad board
- **GIVEN** the authored two-pad board of c0016 and its board pads
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k two_pads` calls `write_dsn`
- **THEN** the text equals `tests/data/specctra/two_pads.dsn`, parses with `lexer.parse`, and holds one net with two pins and two images

#### Scenario: Y is negated and rounded
- **GIVEN** a pad at (10.00005 mm, 5 mm)
- **WHEN** `write_dsn` runs
- **THEN** its component is placed at `10000 -5000` (micrometres; half-even rounding of 100000.5 database units), and the result holds `specctra.rounded`

#### Scenario: One decimal
- **GIVEN** a pad at (10.0001 mm, 5 mm)
- **WHEN** `write_dsn` runs
- **THEN** its component is placed at `10000.1 -5000`, and the result holds no `specctra.rounded`

#### Scenario: Pads sharing a number
- **GIVEN** a footprint with two pads numbered `1` on one net
- **WHEN** `write_dsn` runs
- **THEN** the image holds the pins `1` and `1@2`, the net lists both, and the result holds `specctra.renamed`

#### Scenario: Bottom-side pad
- **GIVEN** a footprint on the bottom side with one SMD pad
- **WHEN** `write_dsn` runs
- **THEN** its image is placed on the front with rotation 0, and the pad's padstack names only the bottom copper layer

#### Scenario: Existing copper is protected
- **GIVEN** a board with one track and one via on net `A`
- **WHEN** `write_dsn` runs
- **THEN** the wiring section holds one protected wire and one protected via on `A`

#### Scenario: One-pad net of a pin on no net
- **GIVEN** a board with the nets `unconnected-(R1-Pad1)` on one pad and `unconnected-(R9-Pad1)` on two pads
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k unconnected` calls `write_dsn`
- **THEN** the network declares the second net with its two pins and not the first, and the image of `R1` still holds its pin `1`

#### Scenario: Same text without planes, layers and rules
- **GIVEN** the four-layer bench of `tests/routing/_planebench.py` with its rules removed, and the blink of target 10
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k unchanged` calls `write_dsn` without `plane_layers` and `net_layers`
- **THEN** each text equals the text recorded from the writer of the commit before this change (`tests/data/specctra/c0107_before_*.dsn`), and every layer is written `(type signal)`

#### Scenario: Nets outside the job with planes and pairs
- **GIVEN** the bench with `selected=("SIG1", "SIG2")`, `plane_layers=("In1.Cu", "In2.Cu")` and `others="netless"`
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn_planes.py -k netless` calls `write_dsn`
- **THEN** the declared nets are `GND`, `VCC` (their planes are written), `HV1`, `HV2` (class clearance above the default, and paired with `SIG`), `SIG1` and `SIG2`, and no other net of `SIG`

### Requirement: Session files are read into copper
`backends.specctra.ses.read_session(text, *, file="") -> Session` SHALL read the routed wires and vias of a session file in the session's own resolution, and `ses.to_copper(session, names, *, selected)` SHALL turn them into model tracks and vias in nanometres, with Y negated back. Session numbers are database units: under `(resolution <unit> <n>)` a value `v` is `v / n` units.
- Each wire of a selected net MUST become one `Track` per segment, with the wire's width and layer; zero-length segments MUST be dropped.
- Each via MUST become a `Via` with the diameter and drill of the padstack that `write_dsn` defined under its name; an unknown padstack name MUST give `specctra.unknown-padstack` (error) and no copper.
- Wires and vias of nets that were not selected MUST be ignored.
- A session with a `place` entry that differs from what `write_dsn` wrote (position, side `front`, rotation 0), a `place` of an unknown component, or a `was_is` entry MUST give `specctra.session-moved` (error) and no copper. A `place` entry equal to the written one is no change.
- A wire or via equal to protected input wiring MUST be ignored.
- Lists the reader does not know MUST be ignored, with one `specctra.unknown-list` (info) per head.
- Ids MUST be `core.ids.derived_id` over the net name and the item's geometry.

#### Scenario: Authored session
- **GIVEN** `tests/data/specctra/two_pads.ses`, authored for Fenolite, with one wire of three points and one via
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_ses.py -k authored` reads it and calls `to_copper`
- **THEN** the result holds two tracks and one via on the net, in nanometres, with the via's diameter and drill from the written padstack

#### Scenario: Unselected net ignored
- **GIVEN** a session with wires on nets `A` and `B` and `selected=("A",)`
- **WHEN** `to_copper` runs
- **THEN** only `A`'s wires become tracks

#### Scenario: Session that moves a component
- **GIVEN** a session whose placement section moves `R1`
- **WHEN** `to_copper` runs
- **THEN** it reports `specctra.session-moved` and returns no copper

#### Scenario: Session that repeats the placement
- **GIVEN** a session whose placement section lists `R1` where `write_dsn` placed it
- **WHEN** `to_copper` runs
- **THEN** it reports no `specctra.session-moved`

### Requirement: Specctra issue codes and facts
`backends.specctra.dsn.ISSUE_CODES` SHALL map every `specctra.*` code to one severity: `specctra.unknown-padstack` (error), `specctra.session-moved` (error), `specctra.pad-approximated` (warning), `specctra.plane-skipped` (warning), `specctra.rounded` (info), `specctra.renamed` (info), `specctra.unknown-list` (info), `specctra.rule-not-sent` (info), `specctra.rule-widened` (info). `docs/formats/specctra/dsn.md` and `ses.md` SHALL record every fact the code relies on, in Fenolite's own words, each with a source, a label and a hypothesis; a fact confirmed by no probe MUST be labelled `INFERRED`.

#### Scenario: Fact rows checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes with the two pages

#### Scenario: Closed table of codes
- **WHEN** `uv run pytest tests/unit/backends/specctra -k codes` collects every `specctra.*` literal under `src/fenolite/backends/specctra/`
- **THEN** each is a key of `ISSUE_CODES` with the severity above, and every key is produced by at least one test

### Requirement: Specctra and Freerouting decision record
`docs/adr/0006-specctra-and-freerouting.md` SHALL record: facts from S-0224 in Fenolite's own words only, each also checked against a tool; Freerouting used only across a process boundary and never read for format knowledge; no cloud mode; and the black-box fallback. The change MUST write it with `Proposed` under `## Status`; only the maintainer MAY set `Accepted (<date>)`, with a `LEGAL-ANNEX.md` row, and the change MUST NOT be archived before that. `tests/unit/test_adrs.py` MUST list it in `REQUIRED`.

#### Scenario: ADR present
- **WHEN** `uv run pytest tests/unit/test_adrs.py` runs
- **THEN** it passes with `0006-specctra-and-freerouting.md` in `REQUIRED`

### Requirement: Plane layers in design files
`write_dsn` SHALL write each copper layer named in `plane_layers` with `(type power)`, and SHALL write one `plane` per zone of a net on such a layer, so that a router keeps its wires off those layers and counts as joined every pin that reaches the plane (`H-G-DSN-LAYERS`, `H-G-DSN-PLANE`).
- `plane_layers` MUST name copper layers of the board; another name MUST raise `ValueError`.
- For each zone of `design.board.zones`, in model order, whose net has pins in the file, and for each of its layers that is in `plane_layers`, in stack order, the structure MUST hold `(plane <net> (polygon <layer> 0 <outline>))` after the boundaries, with the zone's outline rounded and negated as other points.
- A zone that would give a plane but whose outline holds fewer than three points MUST give no plane and one `specctra.plane-skipped` (warning) naming the zone and the layer. A zone whose net has no pin in the file MUST give no plane and no issue.
- Via padstacks MUST keep a shape on every copper layer, plane layers included, so a protected via touches the plane.
- No other list of the file changes because of `plane_layers`.

#### Scenario: Two plane layers
- **GIVEN** the bench of `tests/routing/_planebench.py`: four copper layers, a zone of `GND` on `In1.Cu` and a zone of `VCC` on `In2.Cu`, both over the board
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn_planes.py -k two_planes` calls `write_dsn(…, plane_layers=("In1.Cu", "In2.Cu"))`
- **THEN** the structure holds `(layer In1.Cu (type power))`, `(layer In2.Cu (type power))`, `(layer F.Cu (type signal))` and `(layer B.Cu (type signal))`, then one `plane GND` on `In1.Cu` and one `plane VCC` on `In2.Cu`, each a polygon of the board's four corners, and the result holds no `specctra.plane-skipped`

#### Scenario: Zone without an outline
- **GIVEN** the same bench whose `GND` zone has an empty outline
- **WHEN** `write_dsn` runs with the same plane layers
- **THEN** the file holds no `plane GND`, one `plane VCC`, and the result holds one `specctra.plane-skipped` naming the zone `GND` and `In1.Cu`

#### Scenario: Unknown plane layer
- **WHEN** `write_dsn` is called with `plane_layers=("In3.Cu",)` on the four-layer bench
- **THEN** `ValueError` is raised naming `In3.Cu`

### Requirement: Routing layers in design files
`write_dsn` SHALL keep each net named in `net_layers` to its layers with `use_layer` (`H-G-DSN-LAYERS`).
- `net_layers` maps model net names to non-empty tuples of copper layers that are not in `plane_layers`; any other value MUST raise `ValueError`. A declared net absent from `net_layers` may use every signal layer and gets no `use_layer`.
- The nets of one model class MUST be grouped by layer set, a set being the tuple of `net_layers` or "every signal layer". The group that may use every signal layer keeps the class's name; when every net of the class has a set, the group of the class's first net in name order keeps it. Each other group, in the name order of its first net, is written as a class of its own, named `<class>@<n>` by the writer's namer (which reports the name with `specctra.renamed`). Each group MUST carry the class's width, clearance, `use_via` and the lists of "Routing rules in design files"; a group with a set MUST add `(use_layer <layers in stack order>)` to its `circuit`.
- The nets without a model class that have a set MUST be written in classes of their own, one per layer set, named by the namer from `CLASS`, with the default rule's width and clearance.

#### Scenario: A class kept on the top layer
- **GIVEN** the bench, whose class `SIG` holds `SIG1` to `SIG6`
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn_planes.py -k use_layer` calls `write_dsn` with `net_layers` mapping each `SIG` net to `("F.Cu",)`
- **THEN** the class `SIG` holds the six nets and a `circuit` with its `use_via` and `(use_layer F.Cu)`, and no other class is added

#### Scenario: A class split by layer set
- **GIVEN** the same bench with `net_layers` mapping `SIG1` and `SIG2` to `("F.Cu",)` only
- **WHEN** `write_dsn` runs
- **THEN** the file holds a class `SIG` with `SIG3` to `SIG6` and no `use_layer`, and a class `SIG@2` with `SIG1`, `SIG2`, `(use_layer F.Cu)` and the same width and clearance

#### Scenario: Plane layer in a layer set
- **WHEN** `write_dsn` is called with `plane_layers=("In1.Cu",)` and `net_layers={"SIG1": ("In1.Cu",)}`
- **THEN** `ValueError` is raised naming `SIG1` and `In1.Cu`

### Requirement: Routing rules in design files
`write_dsn` SHALL lower the rules of `design.rules` that the Specctra subset can carry, by this closed table, and SHALL report every other rule (`H-G-DSN-CLEARANCE`, `H-G-DSN-EDGE-2`). A rule of severity `ignore` MUST be skipped without an issue.

| model rule | written as |
|---|---|
| `clearance`, A `all`, B absent or `all` | the default rule's clearance and every class clearance raised to at least `min` |
| `clearance`, one side a class or an `or` of classes, the other absent or `all` | those classes' clearances raised to at least `min`; `netclass Default`, when the design holds no class of that name with nets, raises the default rule |
| `clearance`, A and B classes or `or`s of classes | one `(class_class (classes <a> <b>) (rule (clearance <min>)))` in the network per pair of written classes, a class paired with itself raising its own clearance |
| `track_width`, A `all` or classes, with `opt` | without a layer clause, those classes' width becomes `opt`; with one, each of its layers gives `(layer_rule <layer> (rule (width <opt>)))` in those classes |
| `track_width`, A `all` or classes, without `opt` | each of those class widths clamped into `[min, max]` |
| `edge_clearance` | nothing: reported with `specctra.rule-not-sent` (Decision 11's fallback, `H-G-DSN-EDGE-2`) |
| `no_tracks` | nothing here; "Routing layers in design files" carries it through `net_layers` |

- Values MUST be combined by maximum: the router keeps at least what any applicable rule asks. A class split by "Routing layers in design files" MUST get the values and lists of its class, and a `class_class` pair MUST be written for every pair of their groups.
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

### Requirement: Nets outside the routing job in design files
`backends.specctra.dsn.write_dsn` SHALL take `others: Literal["declared", "netless"] = "declared"`, which says how the nets that are not in `selected` are written. With `"declared"` the file MUST be the one that "Design files are written from the model" states, byte for byte. That requirement, as c0107 leaves it, already writes one family of nets as pins on no net in every mode: a net of one pad whose name starts with `unconnected-(`. The mode `"netless"` does the same for every net outside the job: a net that has pads, is not in `selected`, is not the net of a `plane` the file holds, and whose class clearance is not larger than `defaults.clearance`:
- MUST NOT appear in the network section, neither as a `net` nor as a member of a `class`; a class left without members MUST NOT be written;
- MUST keep its pins in their images, as netless pins;
- MUST have its tracks, arcs and vias written as wiring of type `protect` without a `net`, as copper on a net without pads already is;
- MUST NOT be a key of `DsnResult.names.nets` or `DsnResult.names.net_ids`.

A net outside the job whose class clearance is larger than `defaults.clearance` MUST stay declared with its class, as with `"declared"`: Freerouting 2.4.1 keeps only the default rule from copper and pins without a net, and KiCad asks for the larger clearance of the two classes (`H-G-DSN-NETLESS`, outcome `dsn-netless` = `present`, measured on 2026-10-08).

The via list, the default rule, the components and every other part of the file MUST be as with `"declared"`. A value other than the two MUST raise `ValueError`.

#### Scenario: Unselected net left out
- **GIVEN** an authored board with nets `A` and `B`, two pads each, one track on `B`, and `selected=("A",)`
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k netless` calls `write_dsn(..., others="netless")`
- **THEN** the network section holds `(net A …)` and no `(net B …)`, the images still hold the pins of `B`, the track of `B` is a protected wire without a `net`, and `names.nets` maps `A` only

#### Scenario: A pin on no net in both modes
- **GIVEN** a board with the selected net `A` and the net `unconnected-(R1-Pad1)` on one pad
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k "netless and unconnected"` calls `write_dsn` with `others="declared"` and with `others="netless"`
- **THEN** neither text declares `unconnected-(R1-Pad1)`, both keep the pin of `R1` in its image, and the two texts are equal

#### Scenario: Declared mode unchanged
- **WHEN** `write_dsn` runs on the two-pad board of c0016 with `others="declared"` and without the argument
- **THEN** both texts equal `tests/data/specctra/two_pads.dsn`

#### Scenario: A class emptied by the mode
- **GIVEN** a class `PWR` without a clearance of its own, whose only members `GND` and `VCC` are not selected
- **WHEN** `write_dsn` runs with `others="netless"`
- **THEN** no `(class PWR …)` is written, and the class of the selected nets is written as with `"declared"`

#### Scenario: A wider class stays declared
- **GIVEN** a net `VCC` in a class whose clearance is 0.3 mm, a default rule of 0.2 mm, and `selected=("A",)`
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k "netless and wider"` calls `write_dsn(..., others="netless")`
- **THEN** the network section declares `A` and `VCC`, the class of `VCC` is written with its clearance, and a net of a class whose clearance equals the default rule is left out

### Requirement: Differential pairs in design files
`backends.specctra.dsn.write_dsn` SHALL write no `pair` list: the two nets of a differential pair are written as two nets, as every other net. `docs/formats/specctra/dsn.md` SHALL record, in Fenolite's own words, that the reference describes a `pair` list in the network section naming two nets (S-0224), and that Freerouting 2.4.1 writes the same routes for a design file with such lists, with or without a rule inside them, as for the file without them (`H-G-DSN-PAIR`, labelled by the outcome `dsn-pair-ignored`).
- A later pin of Freerouting MUST run the probe again before the writer emits the list; the writer emits it only after a recorded outcome shows routes coupled at the pair's gap.

#### Scenario: No pair list
- **GIVEN** an authored design with the nets `USB_P` and `USB_N` in a class with pair values, both selected
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k pair` calls `write_dsn`
- **THEN** the parsed network section holds the two nets and no list whose head is `pair`

#### Scenario: Fact row
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes with the row of the `pair` list in `docs/formats/specctra/dsn.md`, whose hypothesis is `H-G-DSN-PAIR`
