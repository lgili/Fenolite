## ADDED Requirements

### Requirement: Footprint fields pass the field oracle
`tests/kicad/board/test_field_oracle.py` (markers `needs_kicad`, major-aware) SHALL settle the field frames, the DRC items of fields and `place_outside` with `pcb drc` canaries on the running `kicad-cli`, and `tests/kicad/board/test_field_probes.py` SHALL record the same facts first, on boards written as text in the test.
- **Benches.** Boards MUST be built in the test through the model: `Mini_R_0603` and `Mini_QFP-32_7x7mm_P0.8mm` placed with `place_footprint` (from `Mini_v9.pretty` for target 9 and from `Mini.pretty` for target 10), references of ten characters in 1 mm text, fields set with `set_field` or `place_outside`, and an outline with optional cut-outs, written with `write_board` for target 9 on both majors and also for target 10 on 10.0.6. A bench MAY hold several footprints, each with its own cut-out, since every verdict is read from the items of one field. Each folder MUST hold a project file whose `board.design_settings.rules.min_silk_clearance` is 0.1 mm, and `KICAD_CONFIG_HOME` MUST be empty. Benches MUST NOT be committed.
- **Reading the report.** DRC MUST run through `KicadCli.drc`. A field's item MUST be matched by its uuid, the field's `native_ids["kicad"]`, and only `silk_edge_clearance` violations are judged.
- **Anchors.** A `Reference` that crosses the board edge, on top footprints at 0°, 30° and 90° and on bottom footprints at 0°, 30° and 90°, MUST give one `silk_edge_clearance` whose field item has the description `Reference field of <reference>` and the position that `field_anchor` gives, within 10 nm per axis (`H-K-FIELD-FRAME`, `H-K-FIELD-DRC`).
- **Moved inside.** Each of those fields moved inside the board with `set_field` MUST give no violation, in a report that holds the violation of a crossing control on the same board.
- **Angle.** On a footprint at 90° whose field anchor lies 2 mm below the top edge, a `Reference` at board angle 0° MUST give no violation, and one at board angle 90° MUST give one.
- **Justification and mirror.** With the anchor 1 mm inside the left edge, `h_justify` `left` MUST give no violation and `right` one on the top side, and the reverse for a mirrored field on the bottom side (`H-K-FIELD-JUSTIFY`).
- **Keep-upright.** A left-justified `Reference` at board angle 180°, with its anchor 1 mm inside the left edge, MUST give no violation, and one when the test inserts `(unlocked yes)` into its node.
- **Hidden.** A hidden `Reference` that crosses the edge MUST give no violation for it.
- **Outside.** For each `side`, on top and bottom footprints at 0°, 30° and 90°, a field set by `place_outside` with the default gap MUST give no violation on a board whose outline holds a cut-out equal to the box `B` of that footprint ("Footprint field helpers"), and a control MUST give one: its anchor lies 0.1 mm inside `B` on the top and bottom sides, and 1 mm inside `B` on the left and right sides, because sideways the ink of a text starts about 0.27 mm from its anchor (`H-K-FIELD-OUTSIDE`).
- **Silence on 9.0.** The crossing control written with `min_silk_clearance` 0 MUST be recorded under the probe `field-edge-zero`; the outcome expected is `absent` on 9.0.9 and `present` on 10.0.6, and it MUST NOT fail the test.
- **Re-save.** On 10.0.6, a target-10 bench whose fields were moved, turned, hidden, resized and justified MUST read back with equal fields after `pcb upgrade --force`, compared by the uuid of each property, since a re-save may write the footprints in another order (`H-K-FIELD-RESAVE`).
- **Probes.** Every outcome MUST be recorded under a `field-*` probe id of c0017's `PROBES` and compared with `docs/evidence/kicad/probes/<version>.json` in both KiCad jobs. When a probe contradicts the frame of `design-model` "Footprint fields", the change MUST stop until its design is amended.

#### Scenario: Anchor of a bottom field
- **GIVEN** `kicad-cli` 10.0.6 and a bottom `Mini_R_0603` at 30° whose `Reference` crosses the left edge
- **WHEN** `uv run pytest tests/kicad/board/test_field_oracle.py -k anchors` runs
- **THEN** the report holds one `silk_edge_clearance` whose item with the field's uuid lies within 10 nm of `field_anchor`

#### Scenario: Moved inside with a live control
- **GIVEN** the same bench on 9.0.9, with the field moved inside the board and a second footprint whose `Reference` crosses the edge
- **WHEN** the test runs
- **THEN** the report holds the control's violation and none for the moved field

#### Scenario: Mirror reverses the justification
- **GIVEN** a bottom footprint whose mirrored `Reference` has its anchor 1 mm inside the left edge
- **WHEN** DRC runs on each major with `h_justify` `left` and then `right`
- **THEN** `left` gives one violation and `right` none

#### Scenario: Outside the courtyard on both majors
- **GIVEN** the outside benches written for target 9
- **WHEN** `uv run pytest tests/kicad/board/test_field_oracle.py -k outside` runs on 10.0.6 and inside the 9.0.9 image
- **THEN** no field set by `place_outside` gives a violation, and every control gives one

#### Scenario: Silent edge check on 9.0
- **GIVEN** `kicad-cli` 9.0.9 and the crossing control with `min_silk_clearance` 0
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs
- **THEN** `field-edge-zero` matches the outcome recorded for 9.0.9, and no field test fails because of it
