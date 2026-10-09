## MODIFIED Requirements

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

### Requirement: Specctra issue codes and facts
`backends.specctra.dsn.ISSUE_CODES` SHALL map every `specctra.*` code to one severity: `specctra.unknown-padstack` (error), `specctra.session-moved` (error), `specctra.pad-approximated` (warning), `specctra.plane-skipped` (warning), `specctra.rounded` (info), `specctra.renamed` (info), `specctra.unknown-list` (info), `specctra.rule-not-sent` (info), `specctra.rule-widened` (info). `docs/formats/specctra/dsn.md` and `ses.md` SHALL record every fact the code relies on, in Fenolite's own words, each with a source, a label and a hypothesis; a fact confirmed by no probe MUST be labelled `INFERRED`.

#### Scenario: Fact rows checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes with the two pages

#### Scenario: Closed table of codes
- **WHEN** `uv run pytest tests/unit/backends/specctra -k codes` collects every `specctra.*` literal under `src/fenolite/backends/specctra/`
- **THEN** each is a key of `ISSUE_CODES` with the severity above, and every key is produced by at least one test

## ADDED Requirements

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
