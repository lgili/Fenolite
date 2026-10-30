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

## 1. Copper counts

- [ ] 1.1 Run the layer-table probes for every even n from 2 to 32 and for n = 1 on both majors; update `H-K-PCB-LAYERS` and register `H-K-PCB-ONE-COPPER` in `docs/hypotheses.md`, and record the facts in `docs/formats/kicad/board.md` (scenarios "Tables on KiCad 10", "Tables on KiCad 9", "Probe tables follow the writer"). Proof: `uv run pytest tests/kicad/board/test_layer_tables.py -rA` (in CI, both majors); `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 1.2 Extend `COPPER_COUNTS` and `CREATED_COPPER_COUNTS` (with 1 only if 1.1 recorded `load` on both majors) and the refusal message (scenarios "Unsupported copper count", "Thirty-two copper layers", "Counts outside the table"). Proof: `uv run pytest tests/unit/dsl/test_board.py tests/unit/backends/kicad/test_layers.py -q`.
- [ ] 1.3 Consequences: zones, planes, script copper, copper guard, exports, Specctra hand-off and the viewer palette on 16 and 32 layers (scenario "Sixteen layers with planes"). Proof: `uv run pytest tests/unit/lens/test_build_layers.py tests/unit/routing -k layers -q`.
- [ ] 1.4 The Altium limit (scenarios "Twenty layers without planes", "Twenty layers with four planes"); register `H-A-STACK-32` with its kit step. Proof: `uv run pytest tests/unit/cli/test_build_altium.py -k stack -q`.
- [ ] 1.5 The KiCad builds of 10, 16 and 32 layers; register `H-K-BUILD-LAYERS-32` (scenario "Thirty-two layers on KiCad 10"). Proof: `uv run pytest tests/kicad/build/test_layer_builds.py -rA` (in CI).

## 2. Board items

- [ ] 2.1 Copper text and graphics, the copper guard rule and `copper.text-unchecked` (scenario "Copper text and a copper shape on a net"). Proof: `uv run pytest tests/unit/dsl/test_drawings.py tests/unit/checks -k "copper_art or drawings" -q`.
- [ ] 2.2 Dimensions `radial`, `leader`, `center` (scenario "Three new kinds"). Proof: `uv run pytest tests/unit/dsl/test_dimensions.py -q`.
- [ ] 2.3 Zone arcs in the DSL, model, writer, fill and guard (scenario "Zone with an arc edge"). Proof: `uv run pytest tests/unit/dsl/test_zones.py tests/unit/lens -k zone_arc -q`.
- [ ] 2.4 Groups (scenario "A labelled block"). Proof: `uv run pytest tests/unit/dsl/test_groups.py -q`.
- [ ] 2.5 Images, read by the build as declared inputs (scenario "Logo image"); the test PNG is authored for Fenolite. Proof: `uv run pytest tests/unit/dsl/test_images.py -q`.
- [x] 2.6a Teardrop settings of vias: `teardrop()`, `teardrop=` of `via` and `via_table`, `Teardrop` on `Pad` and `Via`, the writer's `teardrops` child and its replacement on a read item (scenarios "Settings on a via and a table", "Refused settings"). Proof: `uv run pytest tests/unit/dsl/test_teardrops.py tests/unit/backends/kicad/test_teardrops.py tests/unit/lens/test_build_teardrops.py -q`.
- [ ] 2.6b `Design.teardrops(where=…)` over pads and vias of the built board (scenario "Teardrops on a class"). Proof: `uv run pytest tests/unit/dsl/test_teardrops.py -k where -q`.

## 3. Footprints and instances

- [ ] 3.1 Shaped pads in authored footprints (scenarios "Four shaped pads", "Refused shape values", "Footprints without the arguments"). Proof: `uv run pytest tests/unit/dsl/test_footprint_pads.py -q`.
- [ ] 3.2 Instance overrides and pad edits (scenario "Override and an edited pad"). Proof: `uv run pytest tests/unit/dsl/test_overrides.py -q`.
- [ ] 3.3 Field fonts (scenario "Bold reference"). Proof: `uv run pytest tests/unit/dsl/test_fields.py -k font -q`.
- [ ] 3.4 Model references (scenario "Model by name"). Proof: `uv run pytest tests/unit/dsl/test_models.py -q`.

## 4. Verbatim items and writers

- [ ] 4.1 `dsl/verbatim.py` and the build rules (scenarios "Recorded, not parsed", "Barcode kept", "Refused heads", "Too new for target 9"). Proof: `uv run pytest tests/unit/dsl/test_verbatim.py tests/unit/lens/test_build_verbatim.py -q`.
- [ ] 4.2 KiCad writer and inventory rows for every item (scenarios "Read back what was written", "Created coverage tokens are known"). Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k coverage -q`.
- [ ] 4.3 Altium reports (scenario "Every item accounted for"). Proof: `uv run pytest tests/unit/cli/test_build_altium.py -k coverage -q`.
- [ ] 4.4 The KiCad oracle for every item; register `H-K-COPPER-ART`, `H-K-PAD-SHAPES`, `H-K-TEARDROP`, `H-K-GROUP`, `H-K-IMAGE`, `H-K-DIM-KINDS`, `H-K-ZONE-ARC`, `H-K-FP-OVERRIDE`, `H-K-MODEL-REF` and `H-K-VERBATIM` (scenarios "Items on KiCad 10", "Items on KiCad 9"). Proof: `uv run pytest tests/kicad/board/test_coverage_items.py -rA` (in CI, both majors).
- [ ] 4.5 Byte guard against the baseline of 0.1 (scenarios "Examples keep their bytes", "Designs without tables are unchanged" where c0275 is merged). Proof: `uv run pytest tests/unit/test_examples.py tests/unit/test_build_bytes.py -q`.
- [ ] 4.6 Author `examples/board_coverage/design.py` using every call, with its build test. Proof: `uv run pytest tests/unit/test_examples.py -k board_coverage -q`.

## 6. Import coverage (priority of the `fenolite-library` boards, 2026-10-30)

Each task makes one kind that `fenolite import --to python` leaves out (c0275, `importer/coverage.py`) expressible, or reports it as regenerated, with its import test.

- [x] 6.1 Teardrops: via settings into `teardrop=` of their tables, `padvia` zones reported as `import.teardrops-regenerated`, lost settings as `teardrop-setting` (board-to-code, "Teardrops in an import"). Proof: `uv run pytest tests/unit/importer/test_teardrops.py -q`.
- [x] 6.2 Via spans: a blind via over both outer layers as a table row (design-dsl, "Blind vias over the board in via tables"; board-to-code, "Blind vias over the board in an import"). Proof: `uv run pytest tests/unit/importer/test_teardrops.py tests/unit/lens/test_build_teardrops.py -q`.
- [x] 6.3 Texts: a text on a copper layer with `knockout`, `bold`, `italic`, `face`, a size of two values, several lines and an empty text in the DSL, the model, the writer and the import; `copper.text-unchecked`; the Altium writer reports the new styles (design-dsl, "Board drawings in the DSL", scenario "Copper text and text styles"; board-to-code, "Texts and dimensions in an import"). Copper graphics with a net stay with task 2.1. Proof: `uv run pytest tests/unit/dsl/test_board_texts.py tests/unit/dsl/test_drawings.py tests/unit/importer/test_drawn_items.py -q`.
- [x] 6.4 Dimensions: `extension_offset` in the DSL and the model, and the aligned and orthogonal dimensions written by the import (`dimension-style` for a format or style the DSL does not say); the kinds radial, leader and centre stay with task 2.2. Proof: `uv run pytest tests/unit/importer/test_drawn_items.py -q`.
- [ ] 6.5 Net ties of board footprints (`net-tie`). Proof: `uv run pytest tests/unit/importer -k net_tie -q`.
- [ ] 6.6 `dnp` parts (`dnp`). Proof: `uv run pytest tests/unit/importer -k dnp -q`.
- [ ] 6.7 Groups (task 2.4; `group`). Proof: `uv run pytest tests/unit/importer -k group -q`.
- [ ] 6.8 Footprints that share a reference (`duplicate-ref`). Proof: `uv run pytest tests/unit/importer -k duplicate -q`.
- [ ] 6.9 Board outlines closed by the edge lines of a footprint (`outline`). Proof: `uv run pytest tests/unit/importer -k outline -q`.

## 5. Closing

- [ ] 5.1 Docs: `docs/dsl.md` (copper counts and their consequences, copper art, pads, teardrops, groups, images, dimensions, zone arcs, overrides, fonts, models, verbatim items and when to use them), `docs/formats/kicad/board.md` facts with sources and labels, `docs/altium.md` (limits and reports). Proof: `uv run pytest tests/unit -k docs -q`.
- [ ] 5.2 Agent guide: a tested line for each new public DSL name (`teardrops`, `group`, `image`, `radial_dimension`, `leader`, `center_mark`, `override`, `edit_pad`, `model`, `verbatim`) and for the new codes, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.3 Residue and evidence: every fixture authored for Fenolite, the evidence matrix regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
