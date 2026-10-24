## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`specctra-dsn`, `cli-contract`, `routing`, `board-analyses`, `design-dsl`, `assembly-test-features`, `design-conversion`, `manufacturing-exports`, `kicad-oracle`). Write under this task, with the date: which open change holds a delta of "Routing rules in design files", "Route command budget and tiers" or "Analyze command" (regenerate the MODIFIED blocks from the living text if one was archived); the maintainer's answers to the three open questions of `design.md`; and which packages the maintainer splits into their own changes, with their ids. Proof: `openspec validate c0175-board-engineering-tools --strict --no-interactive`.

## 1. Router input fidelity (package 1)

- [ ] 1.1 Write a board-wide `track_width` rule with `opt` as the width of classes without one, and keep or clamp class widths (scenario "Board-wide preferred width keeps class widths"). Proof: `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -k width_all -q`.
- [ ] 1.2 Write one-sided clearance rules as class pairs, and resolve a class against itself by the board's rule order (scenario "One-sided clearance writes pairs"). Proof: `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -k "one_sided or class_class" -q`.
- [ ] 1.3 Accept comma-separated globs in `--order` (scenario "Several globs in one tier"). Proof: `uv run pytest tests/unit/cli/test_route_cmd.py -k order -q`.
- [ ] 1.4 Bench: route an authored dense board with Freerouting before and after 1.1 and 1.2. Record the share routed and the new DRC findings in `docs/evidence/routing.md`, and register the two hypotheses of Decision 1 in `docs/hypotheses.md`. Proof: `FENOLITE_KICAD_CLI=docker:kicad/kicad:10.0.6 uv run pytest tests/kicad/routing/test_dsn_bench.py -rA`.

## 2. Ground ties (package 2)

- [ ] 2.1 Add `analysis/ties.py`: the copper graph, removal by ids, the groups, `analysis.tie-parallel` and `analysis.tie-extra` (scenarios of "Ground ties"). Proof: `uv run pytest tests/unit/analysis/test_ties.py -q`.
- [ ] 2.2 Add `--sense` and the kind `domains` (scenarios of "Sense nets and isolation islands"). Proof: `uv run pytest tests/unit/analysis/test_ties.py -k "sense or islands" -q`.
- [ ] 2.3 Wire `--kinds ties,domains` and their options into `analyze`, and document the codes in `docs/analyses.md` and `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/cli/test_analyze_cmd.py tests/consistency -q`.

## 3. Barrier crossings (package 3)

- [ ] 3.1 Add `analysis/crossings.py` with the ways per layer and the demand (scenarios of "Barrier crossings"). Proof: `uv run pytest tests/unit/analysis/test_crossings.py -q`.
- [ ] 3.2 Add `--render FILE.svg` under the mutation protocol, and wire the kind into `analyze`. Proof: `uv run pytest tests/unit/cli/test_analyze_cmd.py -k crossings -q`.

## 4. File safety (package 9)

- [ ] 4.1 Add `fenolite snapshot` (scenario "A file saved during the copy"). Proof: `uv run pytest tests/unit/safety/test_snapshot.py -q`.
- [ ] 4.2 Add `fenolite publish` (scenario "The owner saved one file"). Proof: `uv run pytest tests/unit/safety/test_publish.py -q`.
- [ ] 4.3 Register the KiCad lock-file pattern with its public source. Add `safety.open-session` to every writing command, and add `fenolite doctor --sessions` (scenario "A board open in KiCad"). Proof: `uv run pytest tests/unit/safety/test_sessions.py tests/unit/test_provenance.py -q`.
- [ ] 4.4 Detect online-only files by their documented attributes on macOS and Windows; skip the case on a platform without them. Proof: `uv run pytest tests/unit/safety/test_placeholders.py -q`.
- [ ] 4.5 Add `fenolite refs` with `--repoint` for KiCad projects; report other formats as `refs.not-writable` (scenario "A copied project still points at the old folder"). Proof: `uv run pytest tests/unit/safety/test_refs.py -q`.
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

- [ ] 12.1 Add the Gerber and Excellon readers of the `kicad-cli` subset, and `export --readback` (scenario "A missing slot"). Proof: `uv run pytest tests/kicad/exports/test_readback.py -rA`.
- [ ] 12.2 Add `api.trial` and `--gate drc` (scenario "One offending track dropped"). Proof: `uv run pytest tests/kicad/test_trial.py -rA`.
- [ ] 12.3 Add `check --exclude` (scenario "An accepted unconnected item"), and reconcile a stored DRC report with the accepted exceptions. Proof: `uv run pytest tests/kicad/test_exclusions_write.py -rA`.
- [ ] 12.4 Add `render --region` (scenario "Open connections in a region"). Proof: `uv run pytest tests/unit/exports/test_region_render.py -q`.

## 13. Teaching

- [ ] 13.1 Add a tested line for each new command and DSL name to the closest page of the agent guide. Point the practice pages of c0174 to the commands that now answer their checks. Run `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 14. Closing

- [ ] 14.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch.
- [ ] 14.2 Update the evidence labels: the hypotheses of packages 1, 2, 7 and 12 in `docs/hypotheses.md`, and the matrix. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 14.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` once the maintainer has opened the version after 0.5.0. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q`.
