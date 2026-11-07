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
`check_copper` SHALL turn each board copper item into one or more `Thick` shapes, each on one copper layer and one net. A track is its `start`–`end` segment at its `width`; an arc is its exact `geometry.Arc(start, mid, end)` core at its unchanged `width`. Both keep their `layer`. Via, pad and fill shapes and unsupported items MUST follow the requirements below; arc polygonisation bands MUST NOT alter copper boundaries.

#### Scenario: Arc copper retains its width
- **GIVEN** an authored circular arc with integer start, mid, end and width
- **WHEN** the copper items are built with different positive `arc_tol` values
- **THEN** its exact circular core, layer, net and width are unchanged

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
`check_copper` SHALL judge every pair of copper shapes that share a copper layer and belong to two different items whose nets differ, except the pairs of tied pads below. Two items whose `net_id` are equal MUST NOT be judged, and two items without a net MUST NOT be judged; an item without a net and an item with a net MUST be judged.
- Candidate pairs MUST come from one `SpatialIndex` per copper layer, built from the `thick_bbox` of each shape grown on every side by `⌈max_value / 2⌉`, `max_value` being the largest value that `ClearanceResolver` can return for the board, so that no pair closer than its clearance is missed.
- Each item pair MUST give at most one finding: a short when its shapes touch on any shared layer, otherwise a clearance finding when they are too close on any shared layer. The finding MUST name the first such layer in copper table order.
- **Net-tie groups.** Two pads of one footprint instance whose numbers both belong to one group of that footprint's `net_ties` (`design-model`, "Net-tie groups in the model") MUST NOT be judged, neither for a short nor for clearance, because KiCad's DRC does not judge them (`H-K-NETTIE-DRC`). A pad is in a group when its `BoardPad.number` is; every physical pad of a repeated number counts. Two pads of a net-tie footprint that share no group, and a pad paired with any item that is not a pad of the same footprint, MUST be judged as before: KiCad judges no pair of pads of such a footprint, grouped or not, but a touch between a tied pad and a pad outside its group is a defect that KiCad reports only as a solder-mask bridge, so Fenolite may report more. The item pairs left out this way MUST be counted in `summary.net_tie_pairs`, which is 0 on a board without net-tie groups.

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

#### Scenario: Tied pads that touch
- **GIVEN** a footprint `NT1` whose 1 mm square pads `1` (net `A`) and `2` (net `B`) overlap by 0.2 mm on `F.Cu`, with `net_ties == (("1", "2"),)`, and a class clearance of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k net_tie` runs `check_copper` with the pads of the board frame
- **THEN** it reports no finding and `summary.net_tie_pairs` is 1; with `net_ties == ()` it reports one `copper.short` naming `NT1-1` and `NT1-2`

#### Scenario: Tied pads closer than the clearance
- **GIVEN** the same pads 0.1 mm apart, the same group and the same class
- **WHEN** `check_copper` runs
- **THEN** it reports no finding; without the group it reports one `copper.clearance` error with gap 100 000 nm

#### Scenario: A pad outside the group is still judged
- **GIVEN** a footprint with three overlapping pads `1`, `2` and `3` on nets `A`, `B` and `C`, and `net_ties == (("1", "2"),)`
- **WHEN** `check_copper` runs
- **THEN** it reports exactly one `copper.short`, naming pads `2` and `3`, and `summary.net_tie_pairs` is 1

#### Scenario: A track near a tied pad is still judged
- **GIVEN** the tie of "Tied pads that touch" with its pads 0.5 mm apart, and a 0.25 mm track of net `A` ending 0.1 mm from pad `2`, class clearance 0.2 mm
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` error naming `NT1-2` and the track, as KiCad's DRC does

### Requirement: Shorts
`check_copper` SHALL report one `copper.short` error for each judged item pair whose supplied copper shapes touch or overlap on a shared layer (`thick_touch`), whatever the clearance in force. Arc cores MUST retain their true width without narrowing. The finding and message MUST retain the short metadata defined below.

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
`check_copper` SHALL report one `copper.clearance` per judged, non-shorting item pair whose exact gap on a shared layer is strictly below the governing clearance minus the injected `tolerance`. A nonpositive threshold gives no clearance finding. Arc and zone pairs MUST use this same comparison without widening, narrowing or a second zone comparison. Direct calls with `tolerance=0` remain strict; finding metadata MUST follow the requirement below.

#### Scenario: Strict comparison
- **GIVEN** two 0.25 mm tracks of nets `A` and `B` on `F.Cu` whose edges are 0.2 mm apart, and a class clearance of 0.2 mm on both nets
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k strict` calls `check_copper` with its default zero tolerance
- **THEN** it reports no finding, and with the edges 1 nm closer it reports one `copper.clearance` error with gap 199 999 nm, clearance 200 000 nm and source `class:<class name>`

#### Scenario: Warning rule
- **GIVEN** the same pair at 0.15 mm and a governing rule of 0.2 mm with severity `warning`
- **WHEN** `check_copper` runs
- **THEN** it reports one `copper.clearance` warning naming the rule

#### Scenario: Arc band never hides a violation
- **GIVEN** a 0.25 mm arc track and a track of another net whose true edge gap is 5 µm below a 0.2 mm clearance
- **WHEN** `check_copper` runs with different positive `arc_tol` values and zero tolerance
- **THEN** it reports one `copper.clearance` finding with the same exact gap and governing clearance

#### Scenario: A fill cut around an arc is not reported
- **GIVEN** a 0.25 mm arc track of net `B` and a fill of net `A` whose zone has a clearance of 0.5 mm, the fill's edge at a true distance of exactly 0.5 mm from the arc, both nets in a class of 0.2 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_arc` runs `check_copper` with zero tolerance
- **THEN** it reports no finding; with the fill's edge 5 µm closer it reports one `copper.clearance` with source `zone`; and at 0.19 mm it reports clearance 500 000 nm and source `zone`, as for a straight track

#### Scenario: The widened arc keeps the value without the zone
- **GIVEN** the former widened-arc fixture, now using exact cores, with zone clearance 200 001 nm, class clearance 200 000 nm and true edge gap 200 000 nm
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k zone_arc` runs `check_copper` with zero tolerance
- **THEN** it reports clearance 200 001 nm and source `zone`; without a zone value, the class equality is clean

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
`docs/formats/kicad/copper.md` SHALL hold a table of the cases this check supports and how they compare with KiCad's DRC, with a hypothesis id or the word "documented difference" per row. It MUST state at least: tracks, vias and pads exact; arcs within their band; vias and through-hole pads on every spanned layer, with unused-layer removal not modelled (Fenolite may report more); two pads of one net-tie group of one footprint not judged, as KiCad's DRC does not judge them (`H-K-NETTIE-DRC`); two pads of a net-tie footprint that share no group judged, although KiCad's DRC judges no pair of pads of such a footprint and reports only a solder-mask bridge between them (Fenolite may report more); zone fills checked as stored, outlines only for overlaps; the zone's own clearance applied between a fill and a track, a via or a pad as KiCad's DRC applies it, a governing custom rule replacing it (`H-K-COPPER-ZONECLR`); pairs of two fills judged with the rule, class and board-minimum values only, although KiCad's DRC judges no pair of fills (Fenolite may report more); graphics, texts, holes, edges, mask and silkscreen not checked, so the copper of a net tie's bridge is never seen; KiCad project severity overrides and exclusions not applied to copper findings, which a waiver accepts one by one (`verification-loop`, "Waivers in the check"); opaque custom rules not applied (`copper.rules-incomplete`); a project without net classes gives no clearance in force. The parity proven on canaries (`kicad-oracle`, "Copper verdict parity canaries" and "Net-tie parity canaries") MUST be stated per row and per major.

#### Scenario: Table checked
- **GIVEN** `docs/formats/kicad/copper.md`
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** every fact row has an S-id, a valid label and a hypothesis below `CORPUS-VERIFIED`, and the supported-cases table has a hypothesis id or "documented difference" in every row

#### Scenario: Zone rows of the table
- **GIVEN** `docs/formats/kicad/copper.md` after this change
- **WHEN** `uv run pytest tests/unit/test_format_facts.py -k copper` reads the supported-cases table
- **THEN** the row of the zone's own clearance names `H-K-COPPER-ZONECLR` and its parity on 9.0.9 and 10.0.6, a row for pairs of two fills says "documented difference", and no row says that the zone's clearance is not applied

#### Scenario: Net-tie rows of the table
- **GIVEN** `docs/formats/kicad/copper.md` after this change
- **WHEN** `uv run pytest tests/unit/test_format_facts.py -k copper` reads the supported-cases table
- **THEN** a row for pads of one net-tie group names `H-K-NETTIE-DRC` and its parity on 9.0.9 and 10.0.6, a row for pads of a net-tie footprint outside a common group says "documented difference", and no row says that net-tie pad groups are reported as shorts

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
`check_copper` SHALL pass each item's named rule areas per layer to `ClearanceResolver.subject` as `areas` (`H-K-AREA-COND`). An item lies in a named `Keepout` of `design.board.keepouts` on a listed layer when its copper shape touches or overlaps the filled outline (`thick_touch`). Arcs MUST use their true width without narrowing. Fills count; zone outlines do not. Membership of either area carrying a name grants that name.

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

### Requirement: Clearance between the nets of a differential pair
`ClearanceResolver` SHALL apply KiCad's clearance inside a differential pair (`H-K-PRO-PAIR`, `H-K-COPPER-PAIR`). This requirement refines the subjects, the leaf comparison and the class value `k` of "Clearance in force"; everything else there holds.
- **Subjects.** `subject(…)` MUST set `RuleSubject.diff_pair` to the base of the subject's net when the design holds that net's coupled net (`design-model`, "Differential pairs in the model", `net_bases`), and to `None` otherwise.
- **Leaves.** A `diff_pair` leaf MUST be matched as "Differential pairs in the model" states, its value and the subject's base compared with their letter case; the other leaves keep their comparison without letter case.
- **Class value.** For two subjects whose nets are the two nets of one pair and are in one class whose `diff_pair_gap` is set and below its `clearance`, `k` MUST be that `diff_pair_gap`, with the source `pair-gap:<class name>`. A governing rule MUST replace it wherever it replaces a class value, and the board minimum `f` and the zone clearance `z` combine with it as with any `k`.
- `max_value` is unchanged: a pair gap lowers a value and adds none.
- **Explanation.** The explanation of a clearance (`copper-rule-explanation`, "Clearance rule explanation", change c0097, which is on `dev` before this change) MUST show the pair gap as a candidate row of its own, with the source `pair-gap:<class name>`, the gap as value and the severity of a class value, beside the row `class:<class name>` that it replaces. The row MUST come from the resolver's own candidates, with no second matcher, and the explained subjects MUST carry `diff_pair`. Where the pair gap does not apply (the nets are not one pair, the class holds no gap, or the gap is not below the class clearance) no such row is shown.

#### Scenario: Pair below its class clearance
- **GIVEN** nets `USB_P`, `USB_N` and `CLK` in the class `USB`, with a clearance of 0.2 mm and a `diff_pair_gap` of 0.1 mm, and no rule
- **WHEN** `uv run pytest tests/unit/checks/test_clearance.py -k pair` resolves a `USB_P` track against a `USB_N` track, and a `USB_P` track against a `CLK` track
- **THEN** the first gives 0.1 mm with source `pair-gap:USB`, and the second 0.2 mm with source `class:USB`

#### Scenario: Rules over the pair gap
- **GIVEN** the same nets and a board-wide `clearance` rule `board` of 0.2 mm and priority 0
- **WHEN** the pair is resolved with `rules_over_classes=True`
- **THEN** it gives 0.2 mm with source `rule:board`; with a further `clearance` rule `inside` of priority 1, whose two sides are `diff_pair USB_` and whose `min` is 0.1 mm, it gives 0.1 mm with source `rule:inside`

#### Scenario: Board minimum above the pair gap
- **GIVEN** the same nets without a rule, and `min_clearance` 0.12 mm
- **WHEN** the pair is resolved
- **THEN** it gives 0.12 mm with source `floor`

#### Scenario: Letter case of the pair leaf
- **GIVEN** the same nets and a `clearance` rule of 0.5 mm on `diff_pair usb_`
- **WHEN** the pair is resolved
- **THEN** the rule does not govern, and the value is 0.1 mm with source `pair-gap:USB`

#### Scenario: Pair gap in the explanation
- **GIVEN** the nets of "Pair below its class clearance" and a finding between a `USB_P` track and a `USB_N` track 0.08 mm apart
- **WHEN** `uv run pytest tests/unit/checks/test_copper_rule_review.py -k pair_gap` reads the finding's explanation
- **THEN** its candidate rows hold `pair-gap:USB` with 0.1 mm and `class:USB` with 0.2 mm, the governing source is `pair-gap:USB`, and resolving the explained subjects gives the finding's limit; the explanation of a `USB_P` track against a `CLK` track holds no `pair-gap` row

### Requirement: Copper to board edge clearance
`check_copper` SHALL compare every copper shape with every ring of `BoardFrame.board_edges`, each a closed zero-width segment/circular-arc core. Exact gaps strictly below the governing `ClearanceResolver.edge` value MUST give one `copper.edge-clearance` per item and ring. Edge clearance stays strict for every item kind, independently of injected copper tolerance and `arc_tol`; no arc band or fill exception applies. Edge metadata MUST follow the requirement below.

#### Scenario: A rule for one net
- **GIVEN** an `edge_clearance` rule of 1 mm for the net `HV` and a board minimum of 0.5 mm
- **WHEN** a track of `HV` lies 0.8 mm from the board ring and a track of `GND` 0.8 mm from it
- **THEN** only the `HV` track gives `copper.edge-clearance`, whose explanation names the rule as governing

#### Scenario: A fill along a curved edge
- **GIVEN** a board ring whose upper side is an arc, a board minimum of 0.3 mm, a fill and a track on another layer whose edges lie 0.5 µm outside 0.3 mm from the top of the arc
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k curved` runs `check_copper`
- **THEN** neither item gives `copper.edge-clearance`; with both 2 µm inside 0.3 mm, both do

#### Scenario: A pad near a slot
- **GIVEN** the shared fixture with a plated hole part of 2 mm copper whose copper lies 0.47 mm from slot `S1`, and a board minimum of 0.5 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k slot` runs `check_copper`
- **THEN** it gives one `copper.edge-clearance` error naming the part's pad, `slot S1`, 0.47 mm and 0.5 mm, and none at 0.52 mm

### Requirement: Drilled holes against cut-outs and holes
`check_copper` SHALL give `copper.hole-in-cutout` (error) for a pad drill, via drill or board hole whose area overlaps the area of a cut-out or slot or crosses the board ring, and `copper.hole-overlap` (warning) for two drilled holes whose areas overlap. No clearance value is applied to holes.

#### Scenario: A via drilled into a slot
- **GIVEN** the shared fixture with a via whose drill overlaps slot `S1`
- **WHEN** `uv run pytest tests/unit/checks/test_copper_holes.py` runs `check_copper`
- **THEN** it gives one `copper.hole-in-cutout` naming the via and `slot S1`

#### Scenario: Two drilled slots in an L
- **GIVEN** two hole parts with oval NPTH pads that overlap
- **WHEN** `check_copper` runs
- **THEN** it gives one `copper.hole-overlap` warning naming both pads

### Requirement: Arc verdicts use true distances
The copper check SHALL decide copper pairs, rule-area membership and edge clearance with exact circular arc cores. Arc polygonisation bands MUST NOT change these verdicts. The governing copper clearance minus the injected tolerance applies to zone pairs too; edge clearance stays strict. `arc_tol` remains accepted and reported for compatibility.

#### Scenario: Clearance within the previous band
- **GIVEN** authored arc pairs at the exact clearance and at 500 nm and 501 nm below it
- **WHEN** the check runs with 500 nm tolerance and different positive arc_tol values
- **THEN** the first two are clean and the third is a finding, independently of arc_tol

### Requirement: Via copper layer span
A via SHALL be a point at `position` with width `diameter`, on every copper layer of its span. The span MUST follow `Board.layers` table order from `layers[0]` through `layers[1]` inclusive. A `through` via, or a via whose `layers` does not name two board copper layers, MUST span all copper layers.

#### Scenario: Layer span metadata follows the board table
- **GIVEN** copper layers `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` in table order, a blind via with `layers == ("F.Cu", "In1.Cu")` and a through via
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k span` builds the copper items
- **THEN** the blind via has shapes on `F.Cu` and `In1.Cu` only, and the through via on all four layers

### Requirement: Pad copper shape metadata
Each `PadCopper` entry of a pad's `BoardPad` record SHALL yield `Thick(entry.core, entry.width, entry.filled)` on `entry.layer`, with the pad's net. An `exact=False` entry is a superset and MUST be judged as given so no clearance violation is missed. A short it gives MUST carry ` (approximated pad shape)` in its message; such entries MUST count in `summary.approximated`.

#### Scenario: Approximated pad short metadata
- **GIVEN** a pad copper entry with `exact=False` touching another net
- **WHEN** `check_copper` reports the short
- **THEN** its message retains ` (approximated pad shape)` and `summary.approximated` counts the entry

### Requirement: Zone fill copper and exclusions
A `ZoneFill` SHALL be its `polygon` as a filled ring of width 0, on the fill's `layer`, with the zone's net. Zone outlines, rule areas (`Keepout`), graphics, texts, holes and pads of kind `np_thru_hole` MUST NOT be copper.

#### Scenario: Empty zone fill does not create copper
- **GIVEN** a zone on net `GND` on `F.Cu` without fills whose outline covers a track of net `VIN`
- **WHEN** `check_copper` runs
- **THEN** it reports no `copper.short` and no `copper.clearance`

### Requirement: Unsupported copper shape accounting
An item whose shape is refused SHALL be left out, counted by kind in `summary.unsupported`, and reported by one `copper.item-unsupported` warning per kind naming the count. This includes pad entries refused by `Thick` (`GeometryError`), fills refused by `Polygon`, and arc points refused by `geometry.Arc`. Missing pad records and entries MUST follow the unsupported-pad requirement below.

#### Scenario: Refused copper shapes are counted
- **GIVEN** a fill polygon and arc points that their geometry constructors refuse
- **WHEN** `check_copper` runs
- **THEN** both items are left out and counted by kind, with one warning naming each count

### Requirement: Unsupported pad eligibility
A non-`np_thru_hole` pad whose `layers` name a copper layer SHALL count as unsupported when its board-frame record has no copper entry, or when `pads=None`. A pad without a copper layer and every `np_thru_hole` pad MUST be excluded from both copper and unsupported counts. Unsupported pads MUST use the warning and count metadata above.

#### Scenario: Missing frame counts eligible copper pads
- **GIVEN** a board with two footprints of two copper pads each
- **WHEN** `check_copper(design, pads=None)` runs
- **THEN** `summary.unsupported` holds `pad: 4`, and one `copper.item-unsupported` warning names 4 pads

#### Scenario: Nonplated holes stay excluded
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on top of a two-layer board, whose unnumbered `np_thru_hole` pad has no copper entry
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k npth` runs `check_copper` with `KicadBackend().board_pads(design)`
- **THEN** `summary.unsupported` holds no `pad` count, and no unsupported-pad warning is emitted

### Requirement: Short finding metadata
A short `CopperFinding` MUST hold code, severity, layer, a `thick_witness` point, both items as `CopperRef(kind, where, entity_id, net)`, gap 0, and the clearance in force with its source when one exists. Its message MUST name both nets (`<no net>` for an item without a net), the layer and the point in millimetres.

#### Scenario: Short fields survive exact arc checking
- **GIVEN** an authored short involving a circular arc and a governing clearance
- **WHEN** `check_copper` reports it
- **THEN** the finding retains both item references, gap 0, the witness, layer, severity, governing clearance and source, and its message names both nets and the point

### Requirement: Clearance finding metadata
A clearance `CopperFinding` MUST keep code, layer, `thick_witness`, both `CopperRef(kind, where, entity_id, net)` items, gap floored to whole nm (`thick_gap_floor`), original governing clearance and source. Severity MUST be the rule's, or `error` for class, zone or floor. Its message MUST name both nets, layer, point, gap and clearance in millimetres, and source.

#### Scenario: Tolerance preserves the governing metadata
- **GIVEN** a 200 000 nm governing clearance, 500 nm tolerance and exact gap 199 499 nm
- **WHEN** `check_copper` reports the violation
- **THEN** the finding keeps gap 199 499 nm, clearance 200 000 nm, the governing source and severity, both items and the witness

### Requirement: Rule area membership accounting
Rule-area membership SHALL be computed once per item and layer using a spatial index of area boxes, without changing any copper shape or any pair of "Pairs that are judged". `summary.rule_areas` MUST report the number of named rule areas used.

#### Scenario: Membership leaves copper pairs unchanged
- **GIVEN** identical copper with and without a valid named rule area
- **WHEN** the copper items and membership are built
- **THEN** shapes and eligible item pairs are unchanged, membership is layer-specific and the area count is reported

### Requirement: Unsupported rule area accounting
A `Keepout` whose outline is empty or refused by `Polygon` MUST be left out, counted under `summary.unsupported["rule-area"]` and reported by one `copper.item-unsupported` warning naming the count. Its name MUST match no item and its keep-out settings MUST remain unjudged.

#### Scenario: Opaque area settings stay unjudged
- **GIVEN** a board read from a file whose rule area `HV` has an arc in its opaque `pts`
- **WHEN** `check_copper` runs
- **THEN** `summary.unsupported` holds `rule-area: 1`, one warning names it, and no item lies in `HV`

### Requirement: Edge clearance finding metadata
`ClearanceResolver.edge` SHALL use the governing `edge_clearance` rule, else `DesignRules.min_edge_clearance`. An edge-clearance finding MUST retain that severity and name the copper item, ring, gap and limit.

#### Scenario: Slot finding keeps severity and dimensions
- **GIVEN** a plated-hole part with 2 mm copper lying 0.47 mm from slot `S1`, and a board minimum of 0.5 mm
- **WHEN** `uv run pytest tests/unit/checks/test_copper_edges.py -k slot` runs `check_copper`
- **THEN** one `copper.edge-clearance` error names the part's pad, `slot S1`, 0.47 mm and 0.5 mm, and none is reported at 0.52 mm

### Requirement: Clearance tolerance of the tool
`check_copper` SHALL take `tolerance=0` (nm, not negative) and judge a pair too close when its shapes are closer than the value in force minus `tolerance`; edge clearance keeps the strict rule. `DesignRules.clearance_tolerance` SHALL give it: 500 nm from the KiCad rules source (`H-K-COPPER-EPSILON`), 0 from others; the build's copper guard and the `copper.clearance` stage MUST pass it.

#### Scenario: KiCad's tolerance
- **GIVEN** two tracks of nets `A` and `B` whose edges are 500 nm closer than a 0.2 mm class clearance, written as a KiCad project
- **WHEN** `uv run pytest tests/unit/checks/test_copper_tolerance.py` runs the build's copper guard
- **THEN** it reports no finding, and at 501 nm closer it reports one `copper.clearance`; `check_copper` without `tolerance` reports both

#### Scenario: Measured against KiCad
- **WHEN** `uv run pytest tests/kicad/copper/test_drc_tolerance.py -rA` runs in the `kicad-9` and `kicad-10` jobs
- **THEN** KiCad's DRC is clean at `c − 500 nm` and reports `clearance` at `c − 501 nm` for track pairs under a rule, a class, a board minimum and a class pair gap, and the copper guard agrees on every row

### Requirement: Model-only pad geometry of non-plated holes
The model-only pad geometry (`checks.padpath.model_pads`) SHALL give an `np_thru_hole` pad no copper
entries, as the KiCad and Altium pad frames do, and SHALL leave out any copper entry that a copper record
cannot hold, such as a disc of diameter 0. The pad SHALL stay in the result with its position, layers and
net. No check SHALL fail with an internal error because a pad has no copper.

#### Scenario: A non-plated hole without copper
- **WHEN** a board holds an `np_thru_hole` pad of size 0 on `*.Cu` and `fenolite check` runs
- **THEN** the check completes the selected steps without `FEN-1001`
- **AND** `model_pads` lists the pad with no copper entries

#### Scenario: A plated pad of size 0
- **WHEN** a plated pad has a size of 0
- **THEN** `model_pads` lists the pad without the refused copper entry instead of raising

### Requirement: Copper against drilled holes
`check_copper` SHALL judge every drilled hole (pad drills, plated or not, round or slot; via drills on their span; board holes) against the copper of other items on each copper layer it passes, and report `copper.hole-clearance` when the gap to the hole's wall is below the hole clearance in force: the governing `hole_clearance` rule, else `DesignRules.min_hole_clearance` (KiCad: `board.design_settings.rules.min_hole_clearance`). Copper of the hole's own pad or via, copper of the same net as a plated hole, and a pair that already has a `copper.short` or `copper.clearance` finding MUST NOT be reported; without a value the pass MUST be skipped. The build's copper guards and the `copper.clearance` stage of `fenolite check` SHALL pass the value (change c0403, F9).

#### Scenario: Script copper across an unplated hole
- **GIVEN** an authored design script whose track crosses a 3 mm unplated hole of a footprint, on a project with a hole clearance of 0.25 mm
- **WHEN** `uv run pytest tests/unit/cli/test_build_copper_guard.py -k mounting_hole` builds it with `--dry-run`
- **THEN** the reply holds `copper.hole-clearance` and plans no write, and the same track 0.3 mm from the wall builds

### Requirement: Copper narrower than the governing track width
`fenolite build` SHALL judge each track and arc of the planned board against the `min` of the `track_width` rule that governs it (the last match in `rule_precedence` order, its layers holding the item's layer) and report one `copper.track-width` per net and rule, with the rule's severity, the narrowest width, the rule and its `min`. The KiCad copper guard MUST treat it as its other copper errors, so an error plans no write (change c0403, F10).

#### Scenario: A narrow script row
- **GIVEN** a design script with `design.rules.minimum(track_width=mm(0.2))` and a `track_table` row of 0.162 mm
- **WHEN** `uv run pytest tests/unit/cli/test_build_copper_guard.py -k narrow_script_copper` builds it with `--dry-run`
- **THEN** the exit code is 5, the reply holds `copper.track-width` naming the rule and 0.162 mm, and no write is planned

### Requirement: Hole clearance within the tool tolerance
`copper.hole-clearance` SHALL judge the gap to a hole's wall against the hole clearance in force less the `clearance_tolerance` of the rules source (500 nm with KiCad rules, `H-K-COPPER-EPSILON`), as `copper.clearance` does, so a gap that differs from the limit by a declared rounding is no finding; KiCad's hole clearance test allows the same tolerance (change c0420, N4).

#### Scenario: Gaps at the tolerance
- **WHEN** `uv run pytest tests/unit/checks/test_copper_holes.py -k tolerance -q` judges gaps of 5 nm and 500 nm below the limit with a tolerance of 500 nm, 501 nm below it, and 5 nm below it with no tolerance
- **THEN** the first two give no finding and the last two give one each

#### Scenario: KiCad at the same boundary
- **WHEN** `uv run pytest tests/kicad/checks/test_hole_clearance_epsilon.py -q` checks a track beside an unplated hole at 400 nm and 600 nm below a 0.25 mm minimum hole clearance
- **THEN** KiCad reports no `hole_clearance` for the first and one for the second

