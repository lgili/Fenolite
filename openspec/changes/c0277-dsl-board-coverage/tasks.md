## 0. Entry check

- [ ] 0.1 Read `openspec list` and the changes and living specs this change touches, and record under this task, with the date and the base commit:
  - whether c0275 is archived: both change "Zones in the DSL" (c0275 adds `key=`, this change adds arcs); the later one rebases its MODIFIED copy on the archived text;
  - the current writer of the token inventory and `check_emittable`, and which coverage tokens are already inventory rows;
  - the KiCad file-format documentation pages (S-0001) for teardrops, groups, images, dimension types, zone arcs, footprint clearances and model nodes, and whether each token is listed for 9.0 and 10.0;
  - the maintainer's answers to the open questions of `design.md`.

  Record a byte baseline: the SHA-256 of every file every example builds for targets 9, 10 and `altium` with fixed `--seed` and `--timestamp`, as `tests/data/build_bytes.json`.

  Proof: `openspec validate c0277-dsl-board-coverage --strict`; `make check-fast`; `uv run pytest tests/unit/test_build_bytes.py -q`.

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
- [ ] 2.6 Teardrops (scenario "Teardrops on a class"). Proof: `uv run pytest tests/unit/dsl/test_teardrops.py -q`.

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

## 5. Closing

- [ ] 5.1 Docs: `docs/dsl.md` (copper counts and their consequences, copper art, pads, teardrops, groups, images, dimensions, zone arcs, overrides, fonts, models, verbatim items and when to use them), `docs/formats/kicad/board.md` facts with sources and labels, `docs/altium.md` (limits and reports). Proof: `uv run pytest tests/unit -k docs -q`.
- [ ] 5.2 Agent guide: a tested line for each new public DSL name (`teardrops`, `group`, `image`, `radial_dimension`, `leader`, `center_mark`, `override`, `edit_pad`, `model`, `verbatim`) and for the new codes, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.3 Residue and evidence: every fixture authored for Fenolite, the evidence matrix regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
