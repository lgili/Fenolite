## 0. Entry check

- [ ] 0.1 Read `openspec list` and the changes and living specs this change touches, and record under this task, with the date and the base commit:
  - whether c0275 is archived: both change "Zones in the DSL" (c0275 adds `key=`, this change adds arcs); the later one rebases its MODIFIED copy on the archived text;
  - the current writer of the token inventory and `check_emittable`, and which coverage tokens are already inventory rows;
  - the KiCad file-format documentation pages (S-0001) for teardrops, groups, images, dimension types, zone arcs, footprint clearances and model nodes, and whether each token is listed for 9.0 and 10.0;
  - the maintainer's answers to the open questions of `design.md`.

  Record a byte baseline: the SHA-256 of every file every example builds for targets 9, 10 and `altium` with fixed `--seed` and `--timestamp`, as `tests/data/build_bytes.json`.

  Proof: `openspec validate c0277-dsl-board-coverage --strict`; `make check-fast`; `uv run pytest tests/unit/test_build_bytes.py -q`.

  Recorded 2026-10-30 on base commit `8dab89d6` (branch `circuits-as-code`; working branch `cac/c0277-dsl-gaps`):
  - c0275 is not archived (`openspec/changes/c0275-board-to-code`); its "Zones in the DSL" copy and this change's stay as written until one archives.
  - The token inventory is `backends/kicad/data/tokens.toml` (rendered by `tools/gen_token_docs.py`); `check_emittable` is in `backends/kicad/versions.py`. Coverage tokens already rows: `teardrops/curved_edges` (since 20241228), `gr_text_box/knockout`, `table*`. The other names a created board writes and the 8.0 format has are `pcb.FLOOR_HEADS`.
  - S-0001 (read 2026-10-30) documents `image`, `gr_text … knockout`, `net_tie_pad_groups`, footprint groups and the dimension types; it says nothing of `teardrops`, whose children come from the demo boards of 10.0.6 (S-0058, `board.md`, "Teardrop settings").
  - No answer of the maintainer to the open questions of `design.md` is recorded; the recommended answers are used.
  - Byte baseline: `tests/data/build_bytes.json` (`tests/_buildbytes.py`), 16 examples × targets 9, 10, `altium`; `make check-fast` on the base: 16 542 passed, 52 skipped.
  - Priority set by the maintainer on 2026-10-30, from the boards of `fenolite-library` (`boards/ISSUES.md`): teardrops, via spans, texts, dimensions, net ties, `dnp`, groups, duplicate references, outlines closed by footprint edges (section 6).
  - Proof so far: `uv run pytest tests/unit/test_build_bytes.py -q` and `make check-fast` pass on the branch; `openspec validate` was not available in the environment of this record (no `openspec` command), so the task stays open until it runs.

  Integration review 2026-11-01 on base `7c2f1df2`: recommended decisions are confirmed in
  `design.md`. Rebuilt every pre-existing example from that clean base and the merged sources with
  fixed inputs: all 72 example/target rows are byte-identical. The baseline now contains those
  independently measured rows and the three new `board_coverage` rows. The baseline, catalog golden
  output and explain proofs pass (93 tests); source-integration regressions pass (118 tests).
  Strict validation passes. This task remains open because its full `make check-fast` proof is
  reserved for the maintainer's serial batch gate.

  Entry refresh 2026-11-02, integration base `697cdf02b39c570b7827bd2b7b5419dfcf6bdea6`:
  c0275 remains active and implemented; its key addition and c0277's arc addition
  both modify "Zones in the DSL". No newly archived owner triggers regeneration, and the
  integrated implementation retains both. The inventory is still backends/kicad/data/tokens.toml,
  generated docs use tools/gen_token_docs.py, and emit gating is backends/kicad/versions.py.
  Existing rows include teardrops/curved_edges since major 9 (20241228), table forms since
  major 9 (20240202), and gr_text_box/knockout plus table/uuid since major 10. The existing
  board/libraries fact pages distinguish S-0001
  common syntax (images, groups, dimension types, footprint clearances/model nodes) from
  teardrop corpus facts (S-0058) and zone-arc probes (S-0018); the unversioned documentation
  is not a 9/10 acceptance matrix. This refresh claims no new source-page fetch or native run.
  The three accepted decisions still refuse copper=1 unless both majors load it, defer the
  stated reader promotion until independent read-write proof, and allow kicad_dru verbatim
  content with its checks. The existing baseline has 75 example/target maps; its original
  fixed seed/time recipe is unchanged and no digest is updated by this bookkeeping.

  Available proof: `openspec validate c0277-dsl-board-coverage --strict` passes without warnings
  (OpenSpec 1.16.0). The literal `uv run pytest tests/unit/test_build_bytes.py -q` also passes
  (76 tests, all 75 maps plus inventory); it does not replace the full gate.
  The literal `make check-fast` is not run by this worker and has no applicable passing
  serialized receipt yet. Task 0.1 remains unchecked for that actual proof; independent
  CI, native/manual and release criteria are unchanged.


## 1. Copper counts

- [x] 1.1 Run the layer-table probes for every even n from 2 to 32 and for n = 1 on both majors; update `H-K-PCB-LAYERS` and register `H-K-PCB-ONE-COPPER` in `docs/hypotheses.md`, and record the facts in `docs/formats/kicad/board.md` (scenarios "Tables on KiCad 10", "Tables on KiCad 9", "Probe tables follow the writer"). Proof: `uv run pytest tests/kicad/board/test_layer_tables.py -rA` (in CI, both majors); `uv run pytest tests/unit/test_hypotheses_register.py -q`. (2026-10-30: run in the pinned images of 9.0.9 and 10.0.6, local; every even count to 32 loads, the tables of 1 and 3 are refused, so 1 is not a count.)
- [x] 1.2 Extend `COPPER_COUNTS` and `CREATED_COPPER_COUNTS` (with 1 only if 1.1 recorded `load` on both majors) and the refusal message (scenarios "Unsupported copper count", "Thirty-two copper layers", "Counts outside the table"). Proof: `uv run pytest tests/unit/dsl/test_board.py tests/unit/backends/kicad/test_layers.py -q`.
- [x] 1.3 Consequences: zones, planes, script copper, copper guard, exports, Specctra hand-off and the viewer palette on 16 and 32 layers (scenario "Sixteen layers with planes"). Proof: `uv run pytest tests/unit/lens/test_build_layers.py tests/unit/routing -k layers -q`.
- [x] 1.4 The Altium limit (scenarios "Twenty layers without planes", "Twenty layers with four planes"); register `H-A-STACK-32` with its kit step. Proof: `uv run pytest tests/unit/cli/test_build_altium.py -k stack -q`. (2026-10-30: the row is registered with its kit request; the twenty-layer sample joins the kit with its next version, so the row stays `INFERRED`.)
- [x] 1.5 The KiCad builds of 10, 16 and 32 layers; register `H-K-BUILD-LAYERS-32` (scenario "Thirty-two layers on KiCad 10"). Proof: `uv run pytest tests/kicad/build/test_layer_builds.py -rA` (in CI). (2026-10-30: run in the pinned image of 10.0.6, local, and the stack-up defaults of 10, 16 and 32 on both majors.)

## 2. Board items

- [x] 2.1 Copper text and graphics, the copper guard rule and `copper.text-unchecked` (scenarios "Copper text and a copper shape on a net", "A copper shape across a pad of another net"; graphics also take `width=None`). Proof: `uv run pytest tests/unit/dsl/test_drawings.py tests/unit/checks -k "copper_art or drawings" -q`.
- [x] 2.2 Dimensions `radial`, `leader`, `center` (scenario "Three new kinds"). Proof: `uv run pytest tests/unit/dsl/test_dimensions.py -q`.
- [x] 2.3 Zone arcs in the DSL, model, writer, copper check and Altium lowering, and in the import (scenario "Zone with an arc edge"; board-to-code, "Zone arcs in an import"); Fenolite has no fill engine of its own, KiCad fills the zone. Proof: `uv run pytest tests/unit/dsl/test_zones.py tests/unit/lens -k zone_arc -q`.
- [x] 2.4 Groups (scenario "A labelled block"; members of copper intents, images and verbatim items join with their tasks). Proof: `uv run pytest tests/unit/dsl/test_groups.py -q`.
- [x] 2.5 Images, read by the build as declared inputs (scenario "Logo image"); the test PNG is authored for Fenolite. Proof: `uv run pytest tests/unit/dsl/test_images.py -q`.
- [x] 2.6a Teardrop settings of vias: `teardrop()`, `teardrop=` of `via` and `via_table`, `Teardrop` on `Pad` and `Via`, the writer's `teardrops` child and its replacement on a read item (scenarios "Settings on a via and a table", "Refused settings"). Proof: `uv run pytest tests/unit/dsl/test_teardrops.py tests/unit/backends/kicad/test_teardrops.py tests/unit/lens/test_build_teardrops.py -q`.
- [x] 2.6b `Design.teardrops(where=…)` over pads and vias of the built board (scenario "Teardrops on a class"). Proof: `uv run pytest tests/unit/dsl/test_teardrops.py -k where -q`.

## 3. Footprints and instances

- [x] 3.1 Shaped pads in authored footprints (scenarios "Four shaped pads", "Refused shape values", "Footprints without the arguments"). Proof: `uv run pytest tests/unit/dsl/test_footprint_pads.py -q`.
- [x] 3.2 Instance overrides and pad edits (scenario "Override and an edited pad"). Proof: `uv run pytest tests/unit/dsl/test_overrides.py -q`.
- [x] 3.3 Field fonts (scenario "Bold reference"). Proof: `uv run pytest tests/unit/dsl/test_fields.py -k font -q`.
- [x] 3.4 Model references (scenario "Model by name"). Proof: `uv run pytest tests/unit/dsl/test_models.py -q`.

## 4. Verbatim items and writers

- [x] 4.1 `Design.verbatim`, `Part.verbatim` and the build rules (`backends/kicad/verbatim.py`; scenarios "Recorded, not parsed", "Barcode kept", "Refused heads", "Too new for target 9"), the rules-file target, the Altium report, and the import of root items no call says (board-to-code, "Verbatim items in an import"). Proof: `uv run pytest tests/unit/dsl/test_verbatim.py tests/unit/lens/test_build_verbatim.py tests/unit/importer/test_verbatim.py -q`.
- [x] 4.2 KiCad writer and inventory rows for every item (scenarios "Read back what was written", "Created coverage tokens are known"). Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k coverage -q`.
- [x] 4.3 Altium reports (scenario "Every item accounted for"). Proof: `uv run pytest tests/unit/cli/test_build_altium.py -k coverage -q`.
- [x] 4.4 The KiCad oracle for every item; register `H-K-COPPER-ART`, `H-K-PAD-SHAPES`, `H-K-TEARDROP`, `H-K-GROUP`, `H-K-IMAGE`, `H-K-DIM-KINDS`, `H-K-ZONE-ARC`, `H-K-FP-OVERRIDE`, `H-K-MODEL-REF` and `H-K-VERBATIM` (scenarios "Items on KiCad 10", "Items on KiCad 9"). Proof: `uv run pytest tests/kicad/board/test_coverage_items.py -rA` (in CI, both majors).
- [x] 4.5 Byte guard against the baseline of 0.1 (scenarios "Examples keep their bytes", "Designs without tables are unchanged" where c0275 is merged). Proof: `uv run pytest tests/unit/test_examples.py tests/unit/test_build_bytes.py -q`.
  Combined integration 2026-11-01: independently compare the six families/picks rows with clean root
  `51c877b8`. The complete file maps match; only their circuit.json model digests were stale in the
  older table. Every native digest is retained. The refreshed byte guard and cross-sheet group,
  declared-user-layer and existing loss-report proofs pass in the focused compatibility group (90).
- [x] 4.6 Author `examples/board_coverage/design.py` using every call, with its build test. Proof: `uv run pytest tests/unit/test_examples.py -k board_coverage -q`.
  Combined integration 2026-11-01: the design, both mini-library tables and original PNG are declared
  as authored CC0 in the fixture manifest with their actual SHA-256 values. The committed-data proof
  passes in the focused 303-test byte/manifest group. Altium's every-example test explicitly holds
  this example to its measured refusal (unsupported shaped pads, then missing PCB for script copper),
  rather than claiming that its PCB was written or judged at RT-A2.

## 6. Import coverage (priority of the `fenolite-library` boards, 2026-10-30)

Each task makes one kind that `fenolite import --to python` leaves out (c0275, `importer/coverage.py`) expressible, or reports it as regenerated, with its import test.

- [x] 6.1 Teardrops: via settings into `teardrop=` of their tables, `padvia` zones reported as `import.teardrops-regenerated`, lost settings as `teardrop-setting` (board-to-code, "Teardrops in an import"). Proof: `uv run pytest tests/unit/importer/test_teardrops.py -q`.
- [x] 6.2 Via spans: a blind via over both outer layers as a table row (design-dsl, "Blind vias over the board in via tables"; board-to-code, "Blind vias over the board in an import"). Proof: `uv run pytest tests/unit/importer/test_teardrops.py tests/unit/lens/test_build_teardrops.py -q`.
- [x] 6.3 Texts: a text on a copper layer with `knockout`, `bold`, `italic`, `face`, a size of two values, several lines and an empty text in the DSL, the model, the writer and the import; `copper.text-unchecked`; the Altium writer reports the new styles (design-dsl, "Board drawings in the DSL", scenario "Copper text and text styles"; board-to-code, "Texts and dimensions in an import"). Copper graphics with a net stay with task 2.1. Proof: `uv run pytest tests/unit/dsl/test_board_texts.py tests/unit/dsl/test_drawings.py tests/unit/importer/test_drawn_items.py -q`.
- [x] 6.4 Dimensions: `extension_offset` in the DSL and the model, and the aligned and orthogonal dimensions written by the import (`dimension-style` for a format or style the DSL does not say); the kinds radial, leader and centre stay with task 2.2. Proof: `uv run pytest tests/unit/importer/test_drawn_items.py -q`.
- [x] 6.5 Net ties of board footprints (`net-tie`): they come back with the vendored footprint, so the kind is no longer counted (board-to-code, "Parts not populated and net ties in an import"). Proof: `uv run pytest tests/unit/importer/test_unfitted.py -q`.
- [x] 6.6 `dnp` parts (`dnp`): `Part(..., dnp=True)` in the DSL (design-dsl, "Parts not populated in the DSL"), written by the import. Proof: `uv run pytest tests/unit/dsl/test_dnp.py tests/unit/importer/test_unfitted.py -q`.
- [x] 6.7 Groups (task 2.4; `group`): a group whose members the code writes becomes `design.group()` (board-to-code, "Groups in an import"). Proof: `uv run pytest tests/unit/importer/test_groups.py tests/unit/importer/test_coverage.py -q`.
- [x] 6.8 Footprints that share a reference (`duplicate-ref`, `footprint-ref`): board-only parts (design-dsl, "Board-only parts in the DSL"; board-to-code, "Board-only parts in an import") and references paired by placement (design-equivalence, "Level 1 compares components"). Proof: `uv run pytest tests/unit/dsl/test_board_only.py tests/unit/importer/test_board_only.py tests/unit/checks/equivalence/test_levels.py -q`.
- [x] 6.9 Board outlines closed by the edge lines of a footprint (`outline`; board-to-code, "Outlines closed by a footprint in an import"): the code declares the closed outline, the writer leaves out the edges a footprint draws. Proof: `uv run pytest tests/unit/importer/test_notched.py -q`.
- [x] 6.10 Board items of the demo boards (board-to-code, "Board items in an import"): user layers (design-dsl, "User layers in the DSL"), copper graphics with their net, filled shapes without an outline, free vias (design-dsl, "Free vias in the DSL"), smoothed zones, dimensions in mils or automatic units, and the material of a silkscreen (`stack.silkscreen(material=)`). Proof: `uv run pytest tests/unit/importer/test_board_items.py tests/unit/dsl/test_user_layers.py tests/unit/dsl/test_board_coverage_items.py tests/unit/dsl/test_stackup_dsl.py -q`.
- [x] 6.11 Placement rule areas (design-dsl, "Placement rule areas in the DSL"), area names with a slash, chamfered pads of bottom footprints, and pads of one number on two of KiCad's unconnected nets, for `multichannel`, `RoyalBlue54L-Feather` and `CM5_MINIMA_3`. Proof: `uv run pytest tests/unit/dsl/test_placement_areas.py tests/unit/backends/kicad/test_chamfer_flip.py tests/unit/importer/test_verbatim.py -q`.

- [x] 6.12 Refresh current source-emission coverage expectations from the real reader/emitter ledger,
  separately from the historical full-conversion census. Record date, input SHA-256 and measurement
  SHA-256; keep historical equivalence/counts/timings intact. Prove the helper matches the complete CLI
  `unexpressed` result on authored fixtures and a small public board before measuring all 18 declared
  demo boards, including heavy rows. Full corpus tests MUST still require exit 0 and equivalent=true.
  Proof: `uv run pytest tests/unit/importer/test_import_coverage_measurement.py -q`;
  `uv run pytest tests/corpus/test_import_coverage_measurement.py -q` with the small public row cached;
  `uv run python tools/measure_import_coverage.py --cache "$FENOLITE_CORPUS_CACHE" --date 2026-11-01 --write`.
  2026-11-01: both authored complete imports and public row 03 agree with the helper; the measurement
  completed all 18 rows against `7e592c5867a24eca6d013eb3312a824232dc6000` (packet 5 plus c0315), including
  both heavy inputs. Collection SHA-256: `c4b9f1e57c6bdefaf1db380800eed6012f7518344a8c31565a79468a83cbdd07`.
  The final focused proof passed all 7 cases (5 unit guards, the public agreement, and the original full
  conversion assertion on row 03). Historical full-conversion rows remain byte-identical, including the
  separately dated heavy CI observations. This is emission-only evidence; complete heavy conversions and
  exact-commit CI remain the batch's independent gates under 5.5.

## 5. Closing

- [x] 5.1 Docs: `docs/dsl.md` (copper counts and their consequences, copper art, pads, teardrops, groups, images, dimensions, zone arcs, overrides, fonts, models, verbatim items and when to use them), `docs/formats/kicad/board.md` facts with sources and labels, `docs/altium.md` (limits and reports). Proof: `uv run pytest tests/unit -k docs -q`.
- [x] 5.2 Agent guide: a tested line for each new public DSL name (`teardrops`, `group`, `image`, `radial_dimension`, `leader`, `center_mark`, `override`, `edit_pad`, `model`, `verbatim`) and for the new codes, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [x] 5.3 Residue and evidence: every fixture authored for Fenolite, the evidence matrix regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. The integrated development base permits the entry. Proof: `uv run pytest tests/unit/test_release_record*.py tests/unit/test_release_tool.py -k changelog -q` (2026-11-01: 7 passed).
- [ ] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
