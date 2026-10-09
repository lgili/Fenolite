# copper-check Specification

## Purpose
Give Fenolite its own check of the copper of a board for shorts and clearance, without `kicad-cli`: tracks, arcs, vias, pads and zone fills become exact integer thick shapes, pairs of different nets on a shared layer are judged against the clearance in force (classes, custom rules and board minimums), and the findings are deterministic, located, documented case by case against KiCad's DRC and labelled with their evidence.

## Requirements

### Requirement: Copper check function
`fenolite.checks.copper.check_copper(design, *, pads, min_clearance=None, rules_over_classes=True, floor_over_rules=False, arc_tol=ARC_TOL_NM, inputs=()) -> CopperReport` SHALL judge the copper of `design.board` for shorts and clearance, and SHALL be a pure function: it MUST read no file, run no subprocess and write nothing.
- `pads` MUST be the board-frame pad records of c0028's `BoardFrame.board_pads(design)` (`backend-protocol`, "Board-frame protocol"), or `None` when no frame is available.
- `min_clearance`, `rules_over_classes` and `floor_over_rules` MUST be passed to `ClearanceResolver` ("Clearance in force"); callers take them from `DesignRules` (`backend-protocol`, "Design rules source").
- `inputs` MUST be the evidence of the inputs that the caller read: the board reader, the rules source and the frame.
- `ARC_TOL_NM` MUST be `1_000`. `arc_tol` below 1 MUST raise `ValueError`.
- `CopperReport` MUST be a frozen dataclass holding `findings` (`CopperFinding` records), `issues` (one `Issue` per finding, then the other issues of this capability), `summary` and `evidence`.
- `fenolite.checks` MUST import only `core`, `model`, `geometry` and `backends.base` (`package-layering`).

#### Scenario: Pure and repeatable
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb` and `subprocess.run`, `subprocess.Popen` and `open` patched to raise
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k pure` calls `check_copper(design, pads=None)` twice
- **THEN** both calls return equal reports and nothing raised

#### Scenario: Invalid arc tolerance
- **WHEN** `check_copper(design, pads=None, arc_tol=0)` is called
- **THEN** a `ValueError` is raised

### Requirement: Copper items and their shapes
`check_copper` SHALL turn each copper item of the board into one or more `Thick` shapes (`geometry-kernel`, "Thick shapes"), each on one copper layer and on one net:
- A `Track`: the segment `start`–`end` with its `width`, on its `layer`.
- An `Arc`: the polyline of `geometry.Arc(start, mid, end).polygonize(arc_tol)` with its `width`, on its `layer`. Its band is `arc_tol + 1` nm, the bound within which the polyline follows the true arc (`geometry-kernel`, "Deterministic polygonisation with a chord-error bound").
- A `Via`: a point at `position` with width `diameter`, on every copper layer of its span. The span MUST be the copper layers of `Board.layers`, in table order, from `layers[0]` to `layers[1]` inclusive; a `through` via, or a via whose `layers` does not name two copper layers of the board, MUST span every copper layer.
- A pad: for each `PadCopper` entry of its c0028 `BoardPad` record, `Thick(entry.core, entry.width, entry.filled)` on `entry.layer`, with the pad's net. An entry with `exact=False` is a superset of the pad (`board-frame`, "Pad copper entries"): it is judged as given, so no clearance violation is missed, a short it gives carries ` (approximated pad shape)` in its message, and such entries are counted in `summary.approximated`.
- A `ZoneFill`: its `polygon` as a filled ring of width 0, on the fill's `layer`, with the zone's net.
- Zone outlines, rule areas (`Keepout`), graphics, texts, holes and pads of kind `np_thru_hole` MUST NOT be copper.
- An item that cannot be shaped MUST be left out and counted per kind in `summary.unsupported`, with one `copper.item-unsupported` warning per kind naming the count: a pad of a kind other than `np_thru_hole` whose `layers` name a copper layer but whose record holds no copper entry, a pad whose copper entry `Thick` refuses (`GeometryError`), every pad of a kind other than `np_thru_hole` when `pads` is `None`, a fill whose polygon `Polygon` refuses, and an arc whose points `geometry.Arc` refuses. A pad without a copper layer, and every `np_thru_hole` pad, is not copper and is not counted.

#### Scenario: Via span on four layers
- **GIVEN** a four-layer board whose copper layers are `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` in table order, a blind via with `layers == ("F.Cu", "In1.Cu")` and a through via
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k span` builds the copper items
- **THEN** the blind via has shapes on `F.Cu` and `In1.Cu` only, and the through via on all four layers

#### Scenario: Outline is not copper
- **GIVEN** a zone on net `GND` on `F.Cu` without fills whose outline covers a track of net `VIN`
- **WHEN** `check_copper` runs
- **THEN** it reports no `copper.short` and no `copper.clearance`

#### Scenario: Pads without a frame
- **GIVEN** a board with two footprints of two pads each
- **WHEN** `check_copper(design, pads=None)` runs
- **THEN** `summary.unsupported` holds `pad: 4`, and the issues hold one `copper.item-unsupported` warning naming 4 pads

#### Scenario: Mounting holes are not unsupported
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on the top of a two-layer board, whose unnumbered `np_thru_hole` pad has no copper entry (`board-frame`, "Pad copper entries")
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k npth` runs `check_copper` with the pads of `KicadBackend().board_pads(design)`
- **THEN** `summary.unsupported` holds no `pad` count, and no `copper.item-unsupported` warning names a pad

### Requirement: Pairs that are judged
`check_copper` SHALL judge every pair of copper shapes that share a copper layer and belong to two different items whose nets differ. Two items whose `net_id` are equal MUST NOT be judged, and two items without a net MUST NOT be judged; an item without a net and an item with a net MUST be judged.
- Candidate pairs MUST come from one `SpatialIndex` per copper layer, built from the `thick_bbox` of each shape grown on every side by `⌈max_value / 2⌉`, `max_value` being the largest value that `ClearanceResolver` can return for the board, so that no pair closer than its clearance is missed.
- Each item pair MUST give at most one finding: a short when its shapes touch on any shared layer, otherwise a clearance finding when they are too close on any shared layer. The finding MUST name the first such layer in copper table order.

#### Scenario: Same net never judged
- **GIVEN** two overlapping tracks on net `GND` on `F.Cu`
- **WHEN** `check_copper` runs
- **THEN** it reports no finding

#### Scenario: One finding for a pair on two layers
- **GIVEN** two through vias of nets `A` and `B` whose discs overlap on a two-layer board
- **WHEN** `check_copper` runs
- **THEN** it reports exactly one `copper.short`, on `F.Cu`

#### Scenario: Index agrees with brute force
- **GIVEN** 300 generated tracks and vias on two layers and four nets with a 0.2 mm class clearance
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k brute_force` compares the findings with those of a check that judges every pair
- **THEN** the two finding lists are equal

### Requirement: Shorts
`check_copper` SHALL report one `copper.short` error for each judged item pair whose shapes touch or overlap on a shared copper layer (`thick_touch`), whatever the clearance in force. For a pair that involves an arc, the arc's shape MUST first be narrowed by its band (width reduced by twice the band, not below 0), so that a short is reported only when the true copper touches.
- The `CopperFinding` MUST hold the code, the severity, the layer, a point (`thick_witness`), both items as `CopperRef(kind, where, entity_id, net)`, a gap of 0, and the clearance in force with its source when one exists.
- The message MUST name both nets (`<no net>` for an item without a net), the layer and the point in millimetres.

#### Scenario: Via touching a track of another net
- **GIVEN** a via of net `GND` with diameter 0.6 mm whose centre is 0.425 mm from the centre line of a 0.25 mm track of net `VIN` on `F.Cu`
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k touch` runs `check_copper`
- **THEN** it reports one `copper.short` error naming `GND`, `VIN` and `F.Cu`, and with the centre 1 nm farther it reports no short

#### Scenario: Short reported without any clearance
- **GIVEN** the same overlap in a design without rules, net classes or board minimum
- **WHEN** `check_copper` runs
- **THEN** it still reports the `copper.short`

### Requirement: Clearance in force
`fenolite.checks.clearance.ClearanceResolver(design, *, min_clearance=None, rules_over_classes=True, floor_over_rules=False)` SHALL return, through `resolve(a, b, *, zone_clearance=None)` for two `RuleSubject`s on the same layer, a `Clearance(value, severity, source)`:
- **Subjects.** `item_kind` is `track` for tracks and arcs, `via`, `pad` or `zone` (fills); `net` is the net name; `netclass` is the name of the net's class, or `Default` when its `netclass_id` is `None`; `ref` is the component reference for a pad and `None` otherwise; `layer` is the shared layer; `areas` holds the names of the rule areas the item lies in on that layer ("Rule areas in the copper check") and is empty for a subject built without them. `ClearanceResolver.subject(kind, net_id, *, ref, layer, areas=frozenset())` builds a subject.
- **Rules.** The candidates MUST be the rules of `design.rules.rules` (none when `design.rules` is `None`) with `kind == "clearance"`, a `min` limit, and empty `layers` or `layers` holding the shared layer. A rule MUST match the pair when `selector_a` matches one subject and `selector_b` (or every subject, when it is `None`) matches the other, in either order. Leaf values and subject names MUST be compared without regard to letter case (`H-K-DRU-COND`), except `area` leaves and area names, which MUST be compared with letter case and with `*` as a glob, as KiCad compares them (`H-K-AREA-COND`).
- **Precedence.** The governing rule MUST be the last matching rule in the order of `rule_precedence(rules)`, which MUST equal c0018's `rulemap.rule_order`: priority 0 first, then descending priority, ties by name, then id.
- **Value.** Let `k` be the larger `clearance` of the two nets' classes that set one, the class of a net whose `netclass_id` is `None` being the class named `Default` when `design.circuit.netclasses` holds one, let `f` be `min_clearance` when it is positive, and let `z` be `zone_clearance` when it is positive.
  - A governing rule with severity `ignore` MUST give `value=None` and `severity=None`, so the pair is not judged for clearance.
  - Without a governing rule, the value MUST be the largest of `k`, `z` and `f` that exist, with severity `error` and source `class:<name>`, `zone` or `floor` (`H-K-PRO-FLOOR`, `H-K-PRO-MIN-KEYS`, `H-K-COPPER-ZONECLR`). Among equal values the source MUST be the class, then the zone, then the floor.
  - With a governing rule of `min` `r`, the value MUST start at `r` with the rule's severity and source `rule:<name>`; when `rules_over_classes` is false, the largest of it, `k` and `z` MUST be taken (`H-K-PRO-MIN-CLASS`), so `z` is kept wherever a class value is kept and replaced wherever a class value is replaced; when `floor_over_rules` is true, the larger of the result and `f` MUST be taken (the claim of `H-K-PRO-MIN-RULE`, which c0026 refuted on 9.0.9 and 10.0.6: `H-K-PRO-MIN-RULE-2`). The source names whichever value governs, and the severity is the rule's when its `min` governs and `error` otherwise.
  - `rules_over_classes` and `floor_over_rules` carry c0026's measured tables `lowering.RULES_OVER_CLASSES` and `lowering.FLOOR_OVER_RULES["min_clearance"]` for the major being judged. The defaults are the values those tables ship with for 9 and 10: `rules_over_classes` true (`H-K-PRO-MIN-CLASS`) and `floor_over_rules` false, because a custom rule governs below the board minimum (`H-K-PRO-MIN-RULE-2`).
- **Unset.** When nothing gives a value, `value` MUST be `None` and the pair is judged for shorts only; `check_copper` MUST count such pairs in `summary.unset_pairs` and report one `copper.clearance-unset` info with the count.
- **Zone clearance.** `zone_clearance` is the `settings.clearance` of the zone of a fill. `check_copper` MUST pass it for a pair of one fill and one item that is not a fill, and MUST pass `None` for every other pair, two fills included. KiCad's DRC judges a stored fill against a track, a via or a pad with the zone's clearance as it does a class value, lets a governing custom rule replace it, and judges no pair of two fills (`H-K-COPPER-ZONECLR`, measured on 9.0.9 and 10.0.6). The zone's clearance is not written into a rule and changes no file.
- `max_value` MUST be the largest value `resolve` can return for the design, the `settings.clearance` of every zone of the board that has fills included, or 0.

#### Scenario: Rule overrides the classes
- **GIVEN** nets `HV` and `LV` in classes with clearances 0.5 mm and 0.2 mm, and a `clearance` rule `hv_lv` with `selector_a = net HV`, `selector_b = net LV` and `min = 1 mm`
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k rule` resolves an `LV` track against an `HV` pad
- **THEN** it returns 1 mm, severity `error` and source `rule:hv_lv`; without the rule it returns 0.5 mm with source `class:<HV class name>`

#### Scenario: Classes above a rule where KiCad keeps them
- **GIVEN** the same nets and a rule of 0.1 mm on the pair
- **WHEN** the pair is resolved with `rules_over_classes=True` and with `rules_over_classes=False`
- **THEN** the first gives 0.1 mm with source `rule:<name>`, and the second 0.5 mm with source `class:<HV class name>`

#### Scenario: Later rule governs
- **GIVEN** two matching clearance rules `a` (priority 1, 0.1 mm) and `b` (priority 2, 0.3 mm)
- **WHEN** the pair is resolved
- **THEN** the value is 0.1 mm, because `rule_order` puts `a` last

#### Scenario: Floor and ignore
- **GIVEN** a governing rule of 0.1 mm and `min_clearance = 0.15 mm`, and then the same rule with severity `ignore`
- **WHEN** the pair is resolved
- **THEN** the first gives 0.1 mm with source `rule:<name>`, the second gives `value is None`, and with `floor_over_rules=True` the first gives 0.15 mm with source `floor`

#### Scenario: Letter case ignored
- **GIVEN** a rule on `net gnd` and a track on net `GND`
- **WHEN** the pair is resolved
- **THEN** the rule governs

#### Scenario: Zone clearance above the class
- **GIVEN** nets `A` and `B` in a class with a clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k zone` resolves a fill of `A` against a track of `B` with `zone_clearance=300_000`, and again with `zone_clearance=100_000`
- **THEN** the first gives 0.3 mm, severity `error` and source `zone`, and the second 0.2 mm with source `class:<class name>`

#### Scenario: Rule replaces the zone clearance
- **GIVEN** the same nets, a `clearance` rule of 0.2 mm on the pair and `zone_clearance=500_000`
- **WHEN** the pair is resolved with `rules_over_classes=True` and with `rules_over_classes=False`
- **THEN** the first gives 0.2 mm with source `rule:<name>`, and the second 0.5 mm with source `zone`

#### Scenario: Board minimum above the zone
- **GIVEN** the same nets without a rule, `min_clearance = 0.4 mm` and `zone_clearance=300_000`
- **WHEN** the pair is resolved
- **THEN** the value is 0.4 mm with source `floor`; with `min_clearance = 0.25 mm` it is 0.3 mm with source `zone`

#### Scenario: Fill against a track and against another fill
- **GIVEN** a board whose zone of net `A` has a clearance of 0.5 mm and a stored fill, a track of net `B` 0.3 mm from that fill, and a second zone of net `B`, also with a clearance of 0.5 mm, whose stored fill is 0.3 mm from the first fill, both nets in a class with a clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_clearance` runs `check_copper`
- **THEN** it reports exactly one `copper.clearance`, between the first fill and the track, with clearance 500 000 nm and source `zone`

#### Scenario: Rule scoped to an area
- **GIVEN** a clearance rule `hv` with `selector_a = area HV` and `min = 2 mm`, and two tracks of nets `A` and `B` in a class with a clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k area` resolves the pair with `areas={"HV"}` on the first subject, and again with no areas
- **THEN** the first gives 2 mm with source `rule:hv`, and the second 0.2 mm with source `class:<class name>`

#### Scenario: Area names keep their case
- **GIVEN** the same rule and a subject whose `areas` is `{"hv"}`
- **WHEN** the pair is resolved
- **THEN** the rule does not govern

### Requirement: Clearance findings
`check_copper` SHALL report one `copper.clearance` finding for each judged item pair that does not short and whose shapes are closer than the clearance in force on a shared copper layer (`thick_closer_than(a, b, value)`, a strict comparison). For a pair that involves an arc, the arc's shape MUST first be widened by twice its band, so that no violation is missed. When the value in force of such a pair comes from a zone (`source == "zone"`), the pair MUST be judged twice: the widened shape with the value that `resolve` gives without `zone_clearance`, and the arc's shape narrowed by twice its band, never below a width of 0, with the zone's value. The pair is a finding when either is too close; it carries the zone's value and source when the narrowed shape is, and the other value and its source otherwise. KiCad's filler cuts a fill to the zone's clearance around the true arc, so the widened shape judged with the zone's value would report fills that KiCad just made; with this rule no finding of the earlier rule is lost.
- The severity MUST be the governing rule's severity, and `error` for a class, zone or floor value.
- The finding MUST hold the gap rounded down to a whole nanometre (`thick_gap_floor`, a lower bound for arcs), the clearance value and its source.
- The message MUST name both nets, the layer, the point, the gap and the clearance in millimetres, and the source.

#### Scenario: Strict comparison
- **GIVEN** two 0.25 mm tracks of nets `A` and `B` on `F.Cu` whose edges are 0.2 mm apart, and a class clearance of 0.2 mm on both nets
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k strict` runs `check_copper`
- **THEN** it reports no finding, and with the edges 1 nm closer it reports one `copper.clearance` error with gap 199 999 nm, clearance 200 000 nm and source `class:<class name>`

#### Scenario: Warning rule
- **GIVEN** the same pair at 0.15 mm and a governing rule of 0.2 mm with severity `warning`
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` warning naming the rule

#### Scenario: Arc band never hides a violation
- **GIVEN** a 0.25 mm arc track and a track of another net whose true edge gap is 5 µm below a 0.2 mm clearance
- **WHEN** `check_copper` runs with the default `arc_tol`
- **THEN** it reports one `copper.clearance` finding

#### Scenario: A fill cut around an arc is not reported
- **GIVEN** a 0.25 mm arc track of net `B` and a fill of net `A` whose zone has a clearance of 0.5 mm, the fill's edge following the arc at a true distance of exactly 0.5 mm, both nets in a class of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_arc` runs `check_copper` with the default `arc_tol`
- **THEN** it reports no finding; with the fill's edge 5 µm closer it reports one `copper.clearance` with source `zone`; and with the fill's edge 0.19 mm from the arc it reports one with clearance 500 000 nm and source `zone`, as a straight track at that distance does

#### Scenario: The widened arc keeps the value without the zone
- **GIVEN** the same arc and fill with a zone clearance of 200 001 nm, 1 nm above the class value, and the fill's edge at a true distance of exactly 0.2 mm from the arc
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_arc` runs `check_copper` with the default `arc_tol`
- **THEN** it reports one `copper.clearance` with clearance 200 000 nm and source `class:<class name>`, the finding the check reports for that pair without a zone value

### Requirement: Zone outline overlaps
`check_copper` SHALL report one `copper.zone-overlap` warning for each pair of zones with different `net_id`, the same `priority` and a shared copper layer whose outlines, as `Polygon`s, intersect (`polygons_intersect`), because the fill of the overlap then depends on the filler's order. Zones with an empty outline, or with an outline that `Polygon` refuses, MUST be counted in `summary.unsupported` as `zone-outline` and left out of this check.

#### Scenario: Equal priorities overlap
- **GIVEN** zones `GND` and `VIN` on `F.Cu`, both of priority 0, whose rectangular outlines overlap
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_overlap` runs `check_copper`
- **THEN** it reports one `copper.zone-overlap` warning naming both zones and `F.Cu`, and none when the `VIN` zone has priority 1

### Requirement: Locations and deterministic output
Each copper finding SHALL locate both items and a point, and the report SHALL be the same for the same input.
- **Items.** `CopperRef.where` MUST be `<ref>-<number>` for a numbered pad, `<ref>` for a pad without a number, and otherwise the entity's `provenance.locator` when it has one, else its id. A fill, which is not an entity, MUST be located by its zone, with kind `fill`. `Issue.where` MUST be the two `where` values joined with `, `, in `(kind, where)` order.
- **Point.** The point MUST be written in the message as `(<x>, <y>) mm`, each an exact decimal without trailing zeros (`format_length`).
- **Order.** `findings` and `issues` MUST be sorted by code, then `where`, then message, as "Check output is deterministic" requires of a stage. `summary` MUST hold `layers`, `items` (counts per kind), `pairs` (candidate pairs), `judged` (exact tests), `shorts`, `clearance`, `zone_overlaps`, `unset_pairs`, `unsupported`, `approximated`, `arc_tol` and `max_clearance`, with sorted keys.

#### Scenario: Pad and via located
- **GIVEN** a via of net `GND` overlapping pad 2 of `R1` on net `VIN`, read from a board file
- **WHEN** `check_copper` runs
- **THEN** the short's `where` is `R1-2`, then `, `, then the via's `provenance.locator`, and its message holds the point in millimetres

#### Scenario: Same input, same bytes
- **GIVEN** a board with several findings
- **WHEN** `check_copper` runs twice and both reports are serialised with `json.dumps(…, sort_keys=True)`
- **THEN** the two texts are equal

### Requirement: Supported cases are documented against KiCad's DRC
`docs/formats/kicad/copper.md` SHALL hold a table of the cases this check supports and how they compare with KiCad's DRC, with a hypothesis id or the word "documented difference" per row. It MUST state at least: tracks, vias and pads exact; arcs within their band; vias and through-hole pads on every spanned layer, with unused-layer removal not modelled (Fenolite may report more); net-tie pad groups reported as shorts; zone fills checked as stored, outlines only for overlaps; the zone's own clearance applied between a fill and a track, a via or a pad as KiCad's DRC applies it, a governing custom rule replacing it (`H-K-COPPER-ZONECLR`); pairs of two fills judged with the rule, class and board-minimum values only, although KiCad's DRC judges no pair of fills (Fenolite may report more); graphics, texts, holes, edges, mask and silkscreen not checked; KiCad project severity overrides and exclusions not applied; opaque custom rules not applied (`copper.rules-incomplete`); a project without net classes gives no clearance in force. The parity proven on canaries (`kicad-oracle`, "Copper verdict parity canaries") MUST be stated per row and per major.

#### Scenario: Table checked
- **GIVEN** `docs/formats/kicad/copper.md`
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** every fact row has an S-id, a valid label and a hypothesis below `CORPUS-VERIFIED`, and the supported-cases table has a hypothesis id or "documented difference" in every row

#### Scenario: Zone rows of the table
- **GIVEN** `docs/formats/kicad/copper.md` after this change
- **WHEN** `uv run pytest tests/unit/test_format_facts.py -k copper` reads the supported-cases table
- **THEN** the row of the zone's own clearance names `H-K-COPPER-ZONECLR` and its parity on 9.0.9 and 10.0.6, a row for pairs of two fills says "documented difference", and no row says that the zone's clearance is not applied

### Requirement: Copper check evidence
`fenolite.checks.copper.EVIDENCE` SHALL be `INFERRED` with the hypotheses `H-K-COPPER-SHAPES`, `H-K-COPPER-RESOLVE` and `H-K-COPPER-ZONES`, and MUST stay `INFERRED` when the three rows become `KICAD-VERIFIED`: the canaries cover pair kinds and clearance sources on benches, and fills on 10.0 only, not every board. `CopperReport.evidence` MUST be `Evidence.combine` of `EVIDENCE` and every item of `inputs`, and MUST be `UNVERIFIED` when the report holds `copper.rules-incomplete` or `copper.item-unsupported`.

#### Scenario: Unsupported item lowers the level
- **GIVEN** a board with one pad and `pads=None`
- **WHEN** `check_copper` runs
- **THEN** `CopperReport.evidence.level` is `UNVERIFIED`

#### Scenario: Evidence constant
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k evidence_constant` reads `EVIDENCE`
- **THEN** its level is `INFERRED` and its hypotheses are `H-K-COPPER-SHAPES`, `H-K-COPPER-RESOLVE` and `H-K-COPPER-ZONES`, in that order

### Requirement: Copper check performance is measured
`tests/corpus/test_copper_perf.py` (markers `needs_corpus`, `slow`) SHALL run `check_copper` on each of the 21 readable non-heavy demo boards of the `rt0` corpus rows at 10.0.6, with `pads` from c0028's frame and one authored test rule added to each design: `clearance`, `selector_a = all`, `min = 200_000` (a measurement setting that reaches no user file). It SHALL record per board the counts of `summary` and the wall time in seconds, rounded to 0.1 s, through `tests/_boards.py::census("copper", <board>, …)` into the JSON file that `FENOLITE_CENSUS_OUT` names, and `docs/evidence/copper-check.md` SHALL be written from that file. The test MUST fail only when a board raises; times are recorded, never asserted, and the page holds counts and timings only.

#### Scenario: Measurement recorded
- **GIVEN** the fetched `rt0` corpus
- **WHEN** `FENOLITE_CENSUS_OUT=copper-census.json uv run pytest tests/corpus/test_copper_perf.py -m slow` runs in a temporary folder
- **THEN** the JSON file holds 21 boards under `copper`, each with its counts and time, and `docs/evidence/copper-check.md`, written from it, passes `uv run python tools/residue/scan.py`

### Requirement: Rule areas in the copper check
`check_copper` SHALL find, for each copper item and each copper layer it is on, the names of the rule areas it lies in, and SHALL pass them to `ClearanceResolver.subject` as `areas`, so that clearance rules scoped to an area are judged where KiCad's DRC applies them (`H-K-AREA-COND`).
- A rule area is a `Keepout` of `design.board.keepouts` with a non-empty `name`. An item lies in it on a layer when the layer is one of the area's `layers` and the item's shape on that layer, narrowed by its band for an arc as for shorts, touches or overlaps the area's outline taken as a filled polygon (`thick_touch`). Fills count as items; zone outlines do not.
- An item lies in a name that two areas carry when it lies in either.
- A `Keepout` whose outline is empty (kept opaque by the reader) or refused by `Polygon` MUST be left out, counted in `summary.unsupported` under `rule-area`, and reported by one `copper.item-unsupported` warning with the count, as "Copper items and their shapes" does for items it cannot shape. Its name then matches no item and its settings are not judged ("Keep-out findings").
- `summary.rule_areas` MUST report the count of rule areas that were used.
- The membership is computed once per item and layer, from a spatial index of the areas' boxes, and changes no shape and no pair of "Pairs that are judged".

#### Scenario: Larger clearance inside a high-voltage area
- **GIVEN** a rule area `HV` on `F.Cu` and `B.Cu`, a clearance rule with `selector_a = area HV` and `min = 2 mm`, and two pairs of tracks of different nets 1 mm apart, one inside the area and one outside
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k area` runs `check_copper`
- **THEN** it reports one `copper.clearance` with source `rule:<name>` for the pair inside and nothing for the pair outside

#### Scenario: Neck-down inside a BGA area
- **GIVEN** a board-wide clearance rule of 0.2 mm, then a rule of priority 1 with `selector_a = area BGA` and `min = 0.1 mm`, and two pairs 0.15 mm apart, one inside the area and one outside
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` for the pair outside and none for the pair inside

#### Scenario: An area on one layer
- **GIVEN** the rule area `HV` on `F.Cu` only, the 2 mm rule, and a pair 1 mm apart on `B.Cu` under the area
- **WHEN** `check_copper` runs
- **THEN** it reports no finding for the pair

#### Scenario: Copper just outside the area
- **GIVEN** the 2 mm rule and a pair whose first track's copper ends 50 µm outside the area, and again with the area reaching 50 µm into that copper
- **WHEN** `check_copper` runs on both
- **THEN** it reports nothing for the first and one `copper.clearance` for the second

#### Scenario: Opaque area outline
- **GIVEN** a board read from a file whose rule area `HV` has an arc in its `pts`
- **WHEN** `check_copper` runs
- **THEN** `summary.unsupported` holds `rule-area: 1`, the issues hold one `copper.item-unsupported` naming it, and no item lies in `HV`

### Requirement: Keep-out findings
`check_copper` SHALL report one `copper.keepout` error for each copper item that lies, on a layer of a `Keepout`, in an area whose settings forbid its kind: a track or an arc where `no_tracks` is true, a via where `no_vias` is true, and a pad where `no_pads` is true (`H-K-AREA-KEEPOUT`). Lying in an area is decided as in "Rule areas in the copper check", for every `Keepout`, named or not.
- One finding MUST be given per item and keep-out, on the first such layer in copper table order. Fills MUST NOT be reported, because KiCad's DRC does not report a stored fill in a copper-pour keep-out and its filler leaves the area out; zone outlines and footprints are not copper items here.
- The `CopperFinding` MUST hold the code, severity `error`, the layer, a point of the overlap (`thick_witness`), the item and the area as `CopperRef("keepout", <the area's name, else its locator>, <its id>, "<no net>")`, a gap of 0, no clearance, and the source `keepout:<name or locator>`. `CopperKind` gains `keepout`, which no rule subject takes.
- The message MUST name the item's kind and net, the area, the setting that forbids it, the layer and the point in millimetres.
- `summary.keepouts` MUST report the count of findings, and the findings MUST follow the order of "Locations and deterministic output".

#### Scenario: Track in a tracks keep-out
- **GIVEN** a keep-out on `F.Cu` with `no_tracks`, a track inside it, a track crossing its edge, a track outside it, and a track on `B.Cu` under it
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k keepout` runs `check_copper`
- **THEN** it reports exactly two `copper.keepout` errors, naming the track inside and the crossing track, on `F.Cu`

#### Scenario: Only the forbidden kind
- **GIVEN** a keep-out on both copper layers with `no_vias` only, holding a via and a track
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.keepout` for the via and none for the track

#### Scenario: Pads and fills
- **GIVEN** a keep-out with `no_pads` and `no_copper_pour` over a placed two-pad footprint and over part of a zone's stored fill
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.keepout` per pad and none for the fill
