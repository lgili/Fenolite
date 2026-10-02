## ADDED Requirements

### Requirement: Copper check function
`fenolite.checks.copper.check_copper(design, *, pads, min_clearance=None, rules_over_classes=True, floor_over_rules=True, arc_tol=ARC_TOL_NM, inputs=()) -> CopperReport` SHALL judge the copper of `design.board` for shorts and clearance, and SHALL be a pure function: it MUST read no file, run no subprocess and write nothing.
- `pads` MUST be the board-frame pad records of c0028's `BoardFrame.board_pads(design)` (`backend-protocol`), or `None` when no frame is available.
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
- A pad: for each `PadCopper` entry of its c0028 `BoardPad` record, `Thick(entry.core, entry.width, entry.filled)` on `entry.layer`, with the pad's net. An entry with `exact=False` is a superset of the pad (c0028, "Pad copper entries"): it is judged as given, so no clearance violation is missed, a short it gives carries ` (approximated pad shape)` in its message, and such entries are counted in `summary.approximated`.
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
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on the top of a two-layer board, whose unnumbered `np_thru_hole` pad has no copper entry (c0028, "Pad copper entries")
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
`fenolite.checks.clearance.ClearanceResolver(design, *, min_clearance=None, rules_over_classes=True, floor_over_rules=True)` SHALL return, through `resolve(a, b)` for two `RuleSubject`s on the same layer, a `Clearance(value, severity, source)`:
- **Subjects.** `item_kind` is `track` for tracks and arcs, `via`, `pad` or `zone` (fills); `net` is the net name; `netclass` is the name of the net's class, or `Default` when its `netclass_id` is `None`; `ref` is the component reference for a pad and `None` otherwise; `layer` is the shared layer.
- **Rules.** The candidates MUST be the rules of `design.rules` with `kind == "clearance"`, a `min` limit, and empty `layers` or `layers` holding the shared layer. A rule MUST match the pair when `selector_a` matches one subject and `selector_b` (or every subject, when it is `None`) matches the other, in either order. Leaf values and subject names MUST be compared without regard to letter case (`H-K-DRU-COND`).
- **Precedence.** The governing rule MUST be the last matching rule in the order of `rule_precedence(rules)`, which MUST equal c0018's `rulemap.rule_order`: priority 0 first, then descending priority, ties by name, then id.
- **Value.** Let `k` be the larger `clearance` of the two nets' classes that set one, the class of a net whose `netclass_id` is `None` being the class named `Default` when `design.circuit.netclasses` holds one, and let `f` be `min_clearance` when it is positive.
  - A governing rule with severity `ignore` MUST give `value=None` and `severity=None`, so the pair is not judged for clearance.
  - Without a governing rule, the value MUST be the larger of `k` and `f` that exist, with severity `error` and source `class:<name>` or `floor` (`H-K-PRO-FLOOR`, `H-K-PRO-MIN-KEYS`).
  - With a governing rule of `min` `r`, the value MUST start at `r` with the rule's severity and source `rule:<name>`; when `rules_over_classes` is false, the larger of it and `k` MUST be taken (`H-K-PRO-MIN-CLASS`); when `floor_over_rules` is true, the larger of the result and `f` MUST be taken (`H-K-PRO-MIN-RULE`). The source names whichever value governs, and the severity is the rule's when its `min` governs and `error` otherwise.
  - `rules_over_classes` and `floor_over_rules` carry c0026's measured tables `lowering.RULES_OVER_CLASSES` and `lowering.FLOOR_OVER_RULES["min_clearance"]` for the major being judged; both default to true, the claims those tables ship with.
- **Unset.** When nothing gives a value, `value` MUST be `None` and the pair is judged for shorts only; `check_copper` MUST count such pairs in `summary.unset_pairs` and report one `copper.clearance-unset` info with the count.
- `max_value` MUST be the largest value `resolve` can return for the design, or 0.

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
- **THEN** the first gives 0.15 mm with source `floor`, the second gives `value is None`, and with `floor_over_rules=False` the first gives 0.1 mm

#### Scenario: Letter case ignored
- **GIVEN** a rule on `net gnd` and a track on net `GND`
- **WHEN** the pair is resolved
- **THEN** the rule governs

### Requirement: Clearance findings
`check_copper` SHALL report one `copper.clearance` finding for each judged item pair that does not short and whose shapes are closer than the clearance in force on a shared copper layer (`thick_closer_than(a, b, value)`, a strict comparison). For a pair that involves an arc, the arc's shape MUST first be widened by twice its band, so that no violation is missed.
- The severity MUST be the governing rule's severity, and `error` for a class or floor value.
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
`docs/formats/kicad/copper.md` SHALL hold a table of the cases this check supports and how they compare with KiCad's DRC, with a hypothesis id or the word "documented difference" per row. It MUST state at least: tracks, vias and pads exact; arcs within their band; vias and through-hole pads on every spanned layer, with unused-layer removal not modelled (Fenolite may report more); net-tie pad groups reported as shorts; zone fills checked as stored, outlines only for overlaps; the zone's own clearance not applied, although KiCad's DRC applies it to fills (0.5 mm when the zone sets none), a v0.2a follow-up to c0029; graphics, texts, holes, edges, mask and silkscreen not checked; KiCad project severity overrides and exclusions not applied; opaque custom rules not applied (`copper.rules-incomplete`); a project without net classes gives no clearance in force. The parity proven on canaries (`kicad-oracle`, "Copper verdict parity canaries") MUST be stated per row and per major.

#### Scenario: Table checked
- **GIVEN** `docs/formats/kicad/copper.md`
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** every fact row has an S-id, a valid label and a hypothesis below `CORPUS-VERIFIED`, and the supported-cases table has a hypothesis id or "documented difference" in every row

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
