## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`specctra-dsn`, `cli-contract`, `routing`, `board-analyses`, `design-dsl`, `assembly-test-features`, `design-conversion`, `manufacturing-exports`, `kicad-oracle`). Write under this task, with the date: which open change holds a delta of "Routing rules in design files", "Route command budget and tiers" or "Analyze command" (regenerate the MODIFIED blocks from the living text if one was archived); the maintainer's answers to the three open questions of `design.md`; and which packages the maintainer splits into their own changes, with their ids. Proof: `openspec validate c0175-board-engineering-tools --strict --no-interactive`.

## 1. Router input fidelity (package 1)

Moved on 2026-10-26 to change c0197 (`openspec/changes/archive/2026-10-27-c0197-router-input/`), with its tasks 1.1 to 1.4 and its
deltas of `specctra-dsn` and `cli-contract`, by the maintainer's choice to start the package alone.

## 2. Ground ties (package 2)

Moved on 2026-10-26 to change c0198 (`openspec/changes/archive/2026-10-27-c0198-ground-ties/`), with its tasks 2.1 to 2.3 and its
two ADDED requirements of `board-analyses` ("Ground ties", "Sense nets and isolation islands"), by the
maintainer's choice to take the packages one at a time. The options of `ties` and `domains` in this change's
MODIFIED "Analyze command" are those c0198 adds. `analysis.sense-entry` is left out there (c0198's design,
decision 5).

## 3. Barrier crossings (package 3)

Moved on 2026-10-26 to change c0199 (`openspec/changes/archive/2026-10-27-c0199-barrier-crossings/`), with its tasks 3.1 and 3.2
and its ADDED requirement "Barrier crossings" of `board-analyses`, by the maintainer's choice to take the
packages one at a time. `--render` is left out there, because `analyze` is read-only (c0199's design,
decision 5); this change's MODIFIED "Analyze command" still lists it with `--width`.

## 4. File safety (package 9)

Tasks 4.1 to 4.5 moved on 2026-10-26 to change c0201 (`openspec/changes/archive/2026-10-27-c0201-file-safety/`), with the
requirements "Stable snapshot", "Publish guarded by receipts", "Open sessions and placeholders" and
"Project references" of `file-safety`, by the maintainer's choice of 2026-10-26 to do file safety first.
Task 4.6 and "Gated and three-way differences" stay here.

- [ ] 4.6 Add `diff --allow` and `--three-way`, and classify resave differences of Altium documents (scenario "A change outside the allowed set"). Proof: `uv run pytest tests/unit/checks/test_diff_gate.py -q`.

## 5. Practice checks (package 7)

- [ ] 5.1 Add the simulated pour and the three copper states to the copper model of the analyses (scenario "A pin left open by a cut-out"). Proof: `uv run pytest tests/unit/analysis/test_practice.py -k "cutout or states" -q`.
- [ ] 5.2 Add the kinds `connectivity` and `dead`. Proof: `uv run pytest tests/unit/analysis/test_practice.py -k "connectivity or dead" -q`.
- [ ] 5.3 Add the kind `bodies` and the table `[[body_copper]]` (scenario "Copper of a class under a can"). Proof: `uv run pytest tests/unit/analysis/test_practice.py -k bodies tests/unit/analysis/test_requirements.py -q`.
- [ ] 5.4 Add the kind `decoupling` and the table `[[decoupling]]` (scenario "Decoupling distance reported without a finding"). Proof: `uv run pytest tests/unit/analysis/test_practice.py -k decoupling -q`.
- [ ] 5.5 Add the kinds `relief` and `necks`, and the table `[[neck]]`. Proof: `uv run pytest tests/unit/analysis/test_practice.py -k "relief or necks" -q`.
- [ ] 5.6 Add the kinds `loops` and `balance`, and the table `[[loop]]`. Proof: `uv run pytest tests/unit/analysis/test_practice.py -k "loops or balance" -q`.
- [ ] 5.7 Add `--kinds power --split`: a resistive solve on a raster of the copper, giving the share of each parallel path and via. Bracket it with the interval bounds of `power` on the same bench. Proof: `uv run pytest tests/unit/analysis/test_power_split.py -q`.
- [ ] 5.8 Add the kind `coupling` (scenario "A sense net beside a phase track"). Proof: `uv run pytest tests/unit/analysis/test_coupling.py -q`.

## 6. Native Altium edit sessions (package 12)

- [ ] 6.1 Write the hypotheses of the edit session and of the integrity rules into `docs/hypotheses.md`, each with its kit case. Build kit phase A, with documents authored for Fenolite and the cases to open, save and reopen in Altium. No write code before this task is ticked. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_verification_docs.py -q`.
- [ ] 6.2 **Maintainer, in Altium Designer.** Run the kit cases and send back the saved files with their hashes. Record the report. OPEN until Altium was run. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -q`.
- [ ] 6.3 Add the integrity check stage, with warnings for unconfirmed rules (scenario "A gap in polygon sub-indices"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_integrity.py -q`.
- [ ] 6.4 Add the session with `delete`, `move`, `rotate` and `set_property`, the assertions, the cloning and the index upkeep, behind a gate that is off by default (scenario "A move refused on a wrong old value"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_session.py -q`.
- [ ] 6.5 Add the commit gates (scenario "An undeclared connectivity change"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_commit.py -q`.
- [ ] 6.6 Add `flip`, `clone`, `add_component`, `remap_layer` and `set_rule`, each behind its own gate. Proof: `uv run pytest tests/unit/backends/altium/edit -q`.
- [ ] 6.7 Add the schematic session with the net-signature guard. Proof: `uv run pytest tests/unit/backends/altium/edit/test_schematic.py -q`.

## 7. Copper tidy (package 5)

- [ ] 7.1 Add `tidy.prune` (scenario "A stub after routing"). Proof: `uv run pytest tests/unit/tidy/test_prune.py -q`.
- [ ] 7.2 Add `tidy.straighten`, with the lattice search and the turn costs (scenario "A staircase becomes one corner"). Proof: `uv run pytest tests/unit/tidy/test_straighten.py -q`.
- [ ] 7.3 Add `tidy.chamfer` for tracks and zone outlines (scenario "A right angle"). Proof: `uv run pytest tests/unit/tidy/test_chamfer.py -q`.
- [ ] 7.4 Add the style report and `--compare` (scenario "Acute joints reported"). Proof: `uv run pytest tests/unit/tidy/test_report.py -q`.
- [ ] 7.5 Add the command `fenolite tidy`, with DRC on the written board (scenario "Dry run of the three steps"). Proof: `uv run pytest tests/unit/cli/test_tidy_cmd.py tests/consistency -q`; `FENOLITE_KICAD_CLI=docker:kicad/kicad:9.0.9 uv run pytest tests/kicad/tidy -rA` and the same with `10.0.6`.
- [ ] 7.6 Add the routing plugin `octilinear`, with pairs (scenarios of "Octilinear router plugin"). Proof: `uv run pytest tests/unit/routing/test_octilinear.py -q`.

## 8. Layout reuse (package 4)

- [ ] 8.1 Add `reuse.fit_block` (scenarios "A mirrored reference is found" and "A part without a fit"). Proof: `uv run pytest tests/unit/reuse/test_fit.py -q`.
- [ ] 8.2 Add `reuse.copy_copper` (scenario "Copper that ends nowhere is pruned"). Proof: `uv run pytest tests/unit/reuse/test_copper.py -q`.
- [ ] 8.3 Add the command `fenolite reuse` (scenario "Dry run of a block"). Proof: `uv run pytest tests/unit/cli/test_reuse_cmd.py tests/consistency -q`.
- [ ] 8.4 Add `place --turn`, `--shift` and `--pose-search` (scenario "A module turned with its satellites"). Proof: `uv run pytest tests/unit/cli/test_place_cmd.py -k "turn or shift or pose" -q`.

## 9. Assembly marks (package 8)

- [ ] 9.1 Add `silk.extents` with its cache and its estimate (scenario "Extent of a designator"). Proof: `FENOLITE_KICAD_CLI=docker:kicad/kicad:10.0.6 uv run pytest tests/kicad/silk/test_extents.py -rA`.
- [ ] 9.2 Add `fenolite silk --designators` (scenario "Dense row of resistors"). Proof: `uv run pytest tests/unit/silk/test_designators.py -q`.
- [ ] 9.3 Add `fenolite silk --clip` (scenario "Outline over a pad"). Proof: `uv run pytest tests/unit/silk/test_clip.py -q`.
- [ ] 9.4 Add `testpoints --place` (scenarios of "Test-point placement"). Proof: `uv run pytest tests/unit/exports/test_testpoint_place.py -q`.

## 10. Library fidelity (package 10)

- [ ] 10.1 Give imported pads their mask and paste layers and margins (scenario "Openings after conversion"), and correct `docs/conversion.md`. Proof: `uv run pytest tests/unit/convert/test_pad_layers.py -q`.
- [ ] 10.2 Add the model placement to the footprint model and to the KiCad writer; extract embedded models (scenario "A rotated body"). Proof: `uv run pytest tests/unit/convert/test_model_placement.py -q`.
- [ ] 10.3 Add `fenolite library` with `--diff` (scenario "Silkscreen edited on the board"). Proof: `uv run pytest tests/unit/cli/test_library_cmd.py tests/consistency -q`.
- [ ] 10.4 Add body copy by pad fit, with one model-store entry per rotation (Altium, behind the gates of package 12), and a coverage report against a house library that the user names. Proof: `uv run pytest tests/unit/reuse/test_bodies.py tests/unit/catalog/test_coverage.py -q`.

## 11. Generated copper (package 6)

- [ ] 11.1 Add `band` (scenario "A band keeps its clearance"). Proof: `uv run pytest tests/unit/dsl/test_generate.py -k band -q`.
- [ ] 11.2 Add `keepout_ring`, `barrier` and `body_keepout` (scenarios "A ring holds the circle" and "A barrier in pieces is refused"). Proof: `uv run pytest tests/unit/dsl/test_generate.py -k "ring or barrier or body" -q`.
- [ ] 11.3 Add `fanout_zone` and `stitch_pieces`, with fill and DRC on both majors. Proof: `FENOLITE_KICAD_CLI=docker:kicad/kicad:10.0.6 uv run pytest tests/kicad/dsl/test_generate_fill.py -rA` and the same with `9.0.9`.

## 12. Release checks (package 11)

Task 12.1 moved on 2026-10-27 to change c0203 (`openspec/changes/archive/2026-10-27-c0203-fabrication-readback/`), with the
requirement "Fabrication read-back" of `manufacturing-exports`, by the maintainer's order of 2026-10-26
(item 5 of the consolidation list). Tasks 12.2 to 12.4 stay here.

- [ ] 12.2 Add `api.trial` and `--gate drc` (scenario "One offending track dropped"). Proof: `uv run pytest tests/kicad/test_trial.py -rA`.
- [ ] 12.3 Add `check --exclude` (scenario "An accepted unconnected item"), and reconcile a stored DRC report with the accepted exceptions. Proof: `uv run pytest tests/kicad/test_exclusions_write.py -rA`.
- [ ] 12.4 Add `render --region` (scenario "Open connections in a region"). Proof: `uv run pytest tests/unit/exports/test_region_render.py -q`.

## 13. Teaching

- [ ] 13.1 Add a tested line for each new command and DSL name to the closest page of the agent guide. Point the practice pages of c0174 to the commands that now answer their checks. Run `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 14. Closing

- [ ] 14.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch.
- [ ] 14.2 Update the evidence labels: the hypotheses of packages 1, 2, 7 and 12 in `docs/hypotheses.md`, and the matrix. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 14.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` once the maintainer has opened the version after 0.5.0. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q`.
