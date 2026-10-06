## ADDED Requirements

### Requirement: Zone clearance parity canaries
`tests/kicad/copper/test_copper_parity.py` SHALL also compare the verdicts of `check_copper` with those of `kicad-cli pcb drc` on fills whose zone has a clearance of its own, on 9.0.9 and 10.0.6 (`H-K-COPPER-ZONECLR`), with the benches, the canary and the verdict rules of "Copper verdict parity canaries".
- **Benches.** The rows MUST be on benches written through the triad path with the scoped canary; the `floor-above-zone` case MUST be on the bench that sets the board minimum, because that minimum would govern the rows of the other cases. Each zone takes its clearance from the model (`ZoneSettings.clearance`) and holds its stored fill; no token edit sets it. `_rulebench.Builder` gains `fill_via` and `fill_pad` rows beside `fill_track`.
- **Cases.** Each case has one row per edge gap `c − 10 µm`, `c` and `c + 10 µm`, on probe nets of its own, `c` being the value that governs:

| case | zone | class | rule on the pair | board minimum | `c` | pairs |
|---|---|---|---|---|---|---|
| `zone-above-class` | 0.4 mm | 0.3 mm | none | none | 0.4 mm | fill–track, fill–via, fill–pad |
| `class-above-zone` | 0.1 mm | 0.3 mm | none | none | 0.3 mm | fill–track |
| `rule-below-zone` | 0.5 mm | 0.3 mm | 0.2 mm | none | 0.2 mm | fill–track |
| `floor-above-zone` | 0.3 mm | 0.2 mm | none | 0.4 mm | 0.4 mm | fill–track |

- **Probes.** Each case MUST be recorded as `copper-zoneclr-<case>` for majors 9 and 10: `equal` when every row has the same verdict in KiCad and in Fenolite, `different` otherwise.
- **Two fills.** Two zones of different nets, each with a clearance of 0.5 mm, whose stored fills are 0.1 mm apart, both nets in a class of 0.3 mm, MUST be recorded only, as `copper-fill-fill` for majors 9 and 10: `absent` when no violation names both zone uuids, `present` otherwise. `check_copper` reports that pair with the class value; the difference is documented (`copper-check`, "Supported cases are documented against KiCad's DRC") and MUST NOT be compared.
- **Fallback.** A case that records `different` on a major MUST stop the copper-check part of this change at that point: the rule of "Clearance in force" is corrected to what the rows show for that major, through the switches that `DesignRules` already carries per major, before the part merges.
- **Hermetic half.** `tests/kicad/copper/test_parity_bench.py` MUST check without `kicad-cli`, for targets 9 and 10, that `check_copper` gives a clearance finding on every row below `c` and none on the others.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and copied into the supported-cases table of `docs/formats/kicad/copper.md`.

#### Scenario: Zone clearance parity on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_copper_parity.py -k zone_clearance` runs on 9.0.9 and on 10.0.6
- **THEN** every `copper-zoneclr-*` probe records `equal`, and the bench's canary violation is present

#### Scenario: Rule below the zone clearance
- **GIVEN** a fill and a track of another net 0.21 mm apart, a zone clearance of 0.5 mm and a rule of 0.2 mm on the pair
- **WHEN** the row runs
- **THEN** neither KiCad nor `check_copper` reports a clearance violation on it, and both report one on the row at 0.19 mm

#### Scenario: Two fills are recorded, not compared
- **WHEN** `uv run pytest tests/kicad/copper/test_copper_parity.py -k fill_fill` runs on either major
- **THEN** the probe `copper-fill-fill` records `absent` or `present`, and the test passes on either outcome

#### Scenario: Hermetic rows
- **WHEN** `uv run pytest tests/kicad/copper/test_parity_bench.py -k zone_clearance` runs without `kicad-cli`
- **THEN** on targets 9 and 10 every row below `c` has a `copper.clearance` finding whose source is `zone`, `class:<name>`, `rule:<name>` or `floor` as its case says, and no other row has one

### Requirement: Fresh fills stay clean under the zone clearance
`tests/kicad/zones/test_zone_oracle.py` SHALL prove on 10.0.6 that a fill which KiCad has just made is not reported by `check_copper` for its zone's own clearance (`H-K-COPPER-ZONECLR`): the value the check applies is the value KiCad's filler cuts to.
- **Bench.** One pour whose zone clearance (0.5 mm) is above the class clearance (0.2 mm), around copper of other nets of every kind the check shapes: a track, an arc track, a via, an SMD pad, a round and a rectangular through-hole pad, and a through-hole pad whose drill has an offset. The board MUST be written without fills and refilled on copies with `pcb drc --refill-zones --save-board`, as "Zone settings pass the oracle" refills its benches.
- `check_copper` on the refilled board, read back with `read_board` and judged with the bench's project and rules texts, MUST report no `copper.clearance` whose source is `zone`. The probe `copper-zoneclr-fresh` MUST record `absent` for major 10, and `present` otherwise.
- **Fallback.** When the probe records `present`, the smallest shortfall and the kind of the other item MUST be written into the register row, and a margin MUST be taken from the zone's value in "Clearance in force": the smallest whole number of nanometres that makes the bench clean, at most 1 000 nm, which is the bound of KiCad's own tolerance at the boundary (`copper-boundary-1um`). A shortfall above that bound MUST stop the copper-check part of this change.
- `tests/corpus/test_zone_clearance_census.py` (marker `needs_corpus`) MUST count, on the readable non-heavy demo boards with their own project and rules files where the corpus holds them, the `copper.clearance` findings whose source is `zone`, per kind of the other item, and write the counts through `tests/_boards.py::census` into `docs/evidence/copper-check.md`. Stored fills of a demo may be stale, so the test MUST NOT fail on any count.

#### Scenario: A refilled pour is clean
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k fresh_fill` runs on 10.0.6
- **THEN** the refilled board holds fills, `check_copper` reports no `copper.clearance` whose source is `zone`, and `copper-zoneclr-fresh` records `absent`

#### Scenario: A stale fill is still reported
- **GIVEN** the refilled bench, after which its track is moved 0.3 mm towards the fill by token edit, the fill kept
- **WHEN** `check_copper` runs on that board
- **THEN** it reports one `copper.clearance` between the fill and the track with source `zone`, as `kicad-cli pcb drc` does without a refill

#### Scenario: The corpus census is recorded
- **GIVEN** the `rt0` corpus cached
- **WHEN** `uv run pytest tests/corpus/test_zone_clearance_census.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** the census file holds, per demo board with filled zones, the number of findings with source `zone` by kind of the other item

### Requirement: Arcs and via kinds pass the oracle
`tests/kicad/frame/test_copper_oracle.py` SHALL prove on the running `kicad-cli` that the arcs and the via kinds that script copper creates load, keep their uuids and connect what they join, with the probe rules of "Script copper passes the oracle".
- **Arc** (`H-G-FRAME-ARC`), on a build of the routed blink in which one script track is replaced by a track, an arc step and a track:
  - `pcb-frame-arc` (majors 9 and 10): `absent` when the report holds no `unconnected_items` entry and no violation that names the arc;
  - `pcb-frame-arc-cut` (majors 9 and 10): the same board without the arc MUST give exactly one unconnected item, `present`;
  - `pcb-frame-arc-keep` (major 10): after `pcb upgrade --force` the arc keeps its uuid, `equal`.
- **Via kinds** (`H-K-COPPER-VIAKINDS`), on a build with four copper layers in which each via joins a track on each of its two layers, the via sizes at or above the project minimums:
  - `pcb-frame-via-blind` and `pcb-frame-via-micro` (majors 9 and 10) and `pcb-frame-via-buried` (major 10): `absent` when the board loads, no violation names the via, and no unconnected item is reported between its two tracks;
  - without `kicad-cli`: the build of the buried via for target 9 MUST be refused by the board writer, with a message naming `via buried` and KiCad 10.
- A `reject`, `present` or `different` outcome of an arc or via probe MUST stop that part of the change; the kind is then left out of the DSL and recorded in the register row.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and built files MUST NOT be committed.

#### Scenario: An arc connects its ends
- **WHEN** `uv run pytest tests/kicad/frame/test_copper_oracle.py -k arc` runs on 10.0.6 and in the `kicad-9` job
- **THEN** on both majors `pcb-frame-arc` is `absent` and `pcb-frame-arc-cut` is `present`, and on 10.0.6 `pcb-frame-arc-keep` is `equal`

#### Scenario: Via kinds load and connect
- **WHEN** `uv run pytest tests/kicad/frame/test_copper_oracle.py -k via_kinds` runs on 10.0.6 and in the `kicad-9` job
- **THEN** `pcb-frame-via-blind` and `pcb-frame-via-micro` are `absent` on both majors, and `pcb-frame-via-buried` is `absent` on 10.0.6

#### Scenario: Buried via refused for target 9
- **WHEN** `uv run pytest tests/unit/lens/test_build_copper.py -k buried_target_9` builds a four-layer design with a buried via for target 9
- **THEN** the build exits 7 and writes nothing, and the error names `via buried`

### Requirement: Pad shape offset passes the oracle
`tests/kicad/frame/test_pad_offset.py` (markers `needs_kicad`, major-aware) SHALL prove on 9.0.9 and 10.0.6 that the `(offset X Y)` of a pad's drill moves the pad's copper and not its hole (`H-G-FRAME-OFFSET`), by comparing the verdicts of `check_copper` with those of `kicad-cli pcb drc` on a bench with the scoped canary and a class clearance of 0.2 mm.
- **Rows.** Each row holds one through-hole pad and one track of another net, the track at a known edge gap from the pad's copper as it lies without an offset:

| row | offset | gap without the offset | gap with the copper moved | expected verdict |
|---|---|---|---|---|
| `towards` | 0.4 mm towards the track | 0.5 mm | 0.1 mm | `clearance` |
| `short-of` | 0.25 mm towards the track | 0.5 mm | 0.25 mm | `clean` |
| `away` | 0.5 mm away from the track | 0.1 mm | 0.6 mm | `clean` |
| `turned` | 0.4 mm towards the track, the footprint placed at 90° | 0.5 mm | 0.1 mm | `clearance` |

- The verdict of `check_copper` MUST equal KiCad's on every row, and KiCad's MUST be the expected one. The probe `pcb-frame-pad-offset` MUST record `equal` for majors 9 and 10 when both hold, and `different` otherwise.
- A `different` outcome MUST stop the board-frame part of this change: the living rule stays, and the register row records what KiCad showed.
- `tests/corpus/test_copper_offset_census.py` (marker `needs_corpus`) MUST count, on the readable non-heavy demo boards with their own project and rules files, the `copper.clearance` findings that name a pad whose drill has an offset, and write the counts through `tests/_boards.py::census` into `docs/evidence/kicad-frame.md`. The test MUST NOT fail on any count.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`.

#### Scenario: Offset rows agree on both majors
- **WHEN** `uv run pytest tests/kicad/frame/test_pad_offset.py` runs on 9.0.9 and on 10.0.6
- **THEN** `pcb-frame-pad-offset` records `equal`, KiCad reporting `clearance` on `towards` and `turned` and nothing on `short-of` and `away`

#### Scenario: The census is recorded
- **GIVEN** the `rt0` corpus cached
- **WHEN** `uv run pytest tests/corpus/test_copper_offset_census.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** the census file holds, per demo board, the number of pads with an offset drill and the number of clearance findings that name one

## MODIFIED Requirements

### Requirement: Copper verdict parity canaries
`tests/kicad/copper/test_copper_parity.py` (markers `needs_kicad`, major-aware) SHALL compare the verdicts of `check_copper` with those of `kicad-cli pcb drc` on authored benches, on 9.0.9 and 10.0.6 (`H-K-COPPER-SHAPES`, `H-K-COPPER-RESOLVE`) and on 10.0.6 for zone fills (`H-K-COPPER-ZONES`).
- **Benches.** A bench whose rows need a project setting (net classes or the board minimum) MUST be written through c0010's triad path with the canary of c0010's `tests/_netclass_bench.py`, scoped by a `net` condition to `CANARY_A`, as c0010's net-class oracle does, because the unconditional canary rule would govern every pair over the classes; a custom rule of such a bench MUST come after the canary rule. Every other bench MUST follow "Rules proofs carry a canary" with `_rulebench.Builder` and a `{}` project, its rules selecting the probe nets only, so the canary pair stays under the canary rule. This change extends `_rulebench.Builder` with `arc_pair`, `via_pair`, `pad_track`, `tht_track` and `fill_track` rows, and with net classes and model rules, which both kinds of bench use. Every bench MUST fail with "rules file not loaded" when its canary violation is missing.
- **Rows.** Per pair kind (track–track, arc–track, via–track, via–via, SMD pad–track with `Mini_R_0603`, pad–pad of two footprints, through-hole pad–track on `B.Cu` with `Mini_LED_THT_3mm`, and, on 10.0.6 with a target-10 board, zone fill–track), one row per edge gap: `c − 10 µm`, `c` and `c + 10 µm`, each pair on two probe nets of its own. An arc pair has no row at `c`: at exactly the clearance its band may report (`copper-check`, "Clearance findings").
- **No overlapping or touching row.** KiCad's verdict on copper of two nets that touches is not repeatable: without a pad on both nets it treats the copper as one net and reports nothing, and with one 10.0.6 reports the short in about half of its runs ("Via re-net probe"). Such rows MUST NOT be compared or pinned; `check_copper`'s shorts are proved by its own exact tests, and the re-net probes record KiCad's side.
- **Zone clearance of the fill rows.** The zone of a fill row MUST carry `(connect_pads (clearance 0))` and `(filled_areas_thickness no)`, inserted by token edit into the written board, so that KiCad's verdict rests on `c` alone: without them KiCad applies its default zone clearance of 0.5 mm to the fill, and so does `check_copper` (`copper-check`, "Clearance in force"). The zone's own clearance is proved by "Zone clearance parity canaries".
- **Clearance sources.** `c` is given once by a clearance rule on the probe nets (0.2 mm), once by the net class of both nets (0.3 mm), and once by the project's `board.design_settings.rules.min_clearance` above the classes (0.4 mm), set as c0010's `test_netclass_drc.py::test_floor` sets it. The three values differ from each other, and the last two from the template's `Default` class clearance of 0.2 mm, so each source is told from the others.
- **Resolution rows.** A rule below the class value, a rule above it, two classes (the larger governs), a floor above a rule (the rule governs on both majors, `H-K-PRO-MIN-RULE-2`), a rule with severity `ignore`, and an `item_kind track` rule on an arc pair. Each case MUST hold a row that KiCad reports and a row that it does not.
- **Verdicts.** KiCad's verdict for a row MUST be `short` when a `shorting_items` violation names both items' uuids, `clearance` when a `clearance` violation does, and `clean` otherwise (`H-K-DRC-TYPES`, `H-K-DRC-UUID`). Fenolite's verdict MUST come from `check_copper` on the board read back with `read_board`, with the bench's project and rules texts applied by `design_rules_from_texts` for the running major (so the switches follow c0026's tables) and the pads of c0028's frame. They MUST be equal on every row.
- **Boundary.** Rows at `c − 1 µm` and `c − 1 nm` MUST be recorded only, as `copper-boundary-1um` and `copper-boundary-1nm` (`present` when KiCad reports the violation).
- **Zones.** Two filled zones of different nets and equal priority whose outlines overlap on `F.Cu` MUST be recorded on 10.0.6 as `copper-zone-overlap` (`present` when a violation names both zone uuids), as supporting data for the Fenolite rule "Zone outline overlaps" (`copper-check`), which does not depend on it.
- **Probes.** Each pair kind and each resolution case MUST be recorded as `copper-parity-<kind>` or `copper-resolve-<case>`: `equal` when every row agrees, under each clearance source for a pair kind, and `different` otherwise.
- **Hermetic half.** `tests/kicad/copper/test_parity_bench.py` MUST check without `kicad-cli`, for targets 9 and 10, that `check_copper` gives a clearance finding on every row below `c` and none on the others.

#### Scenario: Parity on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_copper_parity.py` runs on 9.0.9 and on 10.0.6
- **THEN** every `copper-parity-*` and `copper-resolve-*` probe records `equal` (the fill row on 10.0.6 only), and every bench's canary violation is present

#### Scenario: Rule below the class value
- **GIVEN** a pair 0.3 mm apart, both nets in a class of 0.5 mm, and a rule of 0.1 mm on the pair after the canary rule, on a class bench with the scoped canary
- **WHEN** the resolution row runs
- **THEN** KiCad's verdict and that of `check_copper` are equal, and the probe `copper-resolve-rule-below-class` records `equal`

#### Scenario: Missing canary fails
- **GIVEN** a `DrcReport` without the canary violation, as DRC gives when KiCad drops the rules file
- **WHEN** the hermetic `uv run pytest tests/kicad/copper/test_parity_bench.py` passes it to the parity test's verdict helper
- **THEN** the call fails the test with a message saying the rules file was not loaded, and neither passes nor skips
