## 0. Entry check

- [x] 0.1 Read `openspec list` and the living specs that this change touches: `net-roles`, `design-dsl`, `cli-contract` and `altium-build`. Write under this task the date and the base commit the implementation starts from, and record:
  - whether c0222 is merged into `dev`, and the commits since `ff9d9e4c` that touch `src/fenolite/roles/`, `backends/kicad/generate.py`, `lens/build.py`, `cli/cmd_build.py` or `backends/altium/connectstyle.py`, and whether a signature named in `design.md` has changed;
  - which open change holds a delta of "Role issue codes", "Generated copper codes" or "Script copper in an Altium build". If one was archived, regenerate the MODIFIED block from the living text;
  - the state of `c0244-critical-routes`: whether its interface still matches decision 8 (corridor names, key ownership, order). Reconcile both changes before task 1.1;
  - that S-0860 to S-0863 are still the rows this proposal registered, and that S-0864 to S-0889 are still free;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0243-role-copper --strict --no-interactive`; `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.

  2026-10-29: the implementation starts from `origin/dev` at `dedad4c7` (c0222 merged into `dev` there; `dev` is
  cut at `0.6.0`, not published). Since `ff9d9e4c` only `dedad4c7` came in, which trims the `board-power`
  guide page; no commit touches `src/fenolite/roles/`, `backends/kicad/generate.py`, `lens/build.py`,
  `cli/cmd_build.py` or `backends/altium/connectstyle.py`, and no signature named in `design.md` changed. No
  other open change holds a delta of "Role issue codes", "Generated copper codes" or "Script copper in an
  Altium build" (c0222 is archived: the MODIFIED blocks were written from the living text). S-0860 to S-0863
  are the rows this proposal registered, and S-0864 to S-0889 are free. `c0244-critical-routes` (proposal at
  `b36d7244`) disagreed with decision 8 (run order, corridor names `role-corridor:`); the maintainer settled
  the interface on 2026-10-29: the hot loop is phase 1's, as pours; phase 2 runs first and phase 1 pours
  around it, the other order still working; both write corridors `role.corridor.<group>.<net>`, which phase
  1 treats, with every locked item, as obstacles and never edits, writing its own provisional ones only
  when it runs first. Decision 8, open question 2, the requirements "Corridors for critical routes" and
  "Phase 2 copper kept" and task 2.7 are updated. The maintainer decided "implement when the spec is
  written": every recommended answer of the open questions 1 to 11 is accepted on 2026-10-29 (question 2 as
  settled above). Both proofs passed (`openspec validate --strict`: valid; 46 passed).

## 1. Generator extensions (`backends/kicad/generate.py`)

- [x] 1.1 Band records with a `group` are united into one locked zone with the Clipper union, and a single chain needs no union. The c0224 tests stay unchanged. Proof: `uv run pytest tests/unit/dsl/test_generate.py tests/unit/backends/kicad/test_generate_group.py -q`.
  2026-10-29: `_united` in `generate.py` resolves the bands of a `group` one by one and unites them with the Clipper union (one band: no union; no `geo` extra: `kicad.generate.unknown`); an optional `connection` sets the zone's pad connection. The c0224 tests are unchanged; 29 passed.
- [x] 1.2 A barrier over a net set (`nets`), resolved after the bands, and stitching records limited to a `patch`. Proof: `uv run pytest tests/unit/backends/kicad/test_generate_group.py -k "barrier or patch" -q`.
  2026-10-29: a barrier with `nets` is ranked after the bands and holds those nets' zones; a stitching record with `patch` and `avoid` keeps its candidates inside the patch and out of the rings, and counts `stitch-short` within the patch; 2 passed.

## 2. Planner (`roles/copper.py`, `roles/spine.py`)

- [x] 2.1 Width from current by both methods (scenario "Both methods"). Proof: `uv run pytest tests/unit/roles/test_copper_width.py -q`.
  2026-10-29: `required_width`, `rule_of_thumb` and `fit_width` in `roles/copper.py`; a rise without a copper thickness falls back to the rule of thumb (spec amended), and each band is drawn one pour grid cell (0.1 mm) wider so the simulated pour measures the required width (new requirement "Bands drawn for the pour"); 3 passed.
- [x] 2.2 Pad clusters, the rectilinear spine tree with the hot-loop legs first, obstacles and corridors, and `roles.copper-blocked` (scenario "One zone per net and layer"). Proof: `uv run pytest tests/unit/roles/test_spine.py tests/unit/roles/test_copper_plan.py -k zones -q`.
  2026-10-29: `roles/spine.py` (candidates, then a grid search with a turn penalty; trees with given first edges) and the per-net plan: hot-loop legs first in every order of up to four legs, high-voltage nets first, other nets' planned bases as obstacles, loose ends joined by a band or a locked `role.join.*` track (new requirement "Loose ends joined", with its test); band ends square, extended over the terminal copper; the proof as written selects 1 test (`-k zones` applies to both files); the two files and the ground test run whole: 14 passed.
- [x] 2.3 The switch node: no widening, the `role.sw.*` rules, avoidance on the adjacent layer, and `roles.copper-placement` (scenario "Sense pair not under the switch node"). Proof: `uv run pytest tests/unit/roles/test_copper_plan.py -k "victims or placement" -q`.
  2026-10-29: the switch node does not widen, gets `role.sw.<net>` only when it has victims (spec amended), avoids victim copper on the adjacent layer grown by the distance, and a placement bound over `loop_max` gives `roles.copper-placement`; 2 passed.
- [x] 2.4 Ground zones, stitching and pad connections per role (scenarios "Ground joined in pieces" and "Ground reliefs on through-hole pads"). Proof: `uv run pytest tests/unit/roles/test_copper_ground.py tests/unit/roles/test_copper_plan.py -k connection -q`.
  2026-10-29: planes on the ground layers, one stitching record per ground net, connections per kind. The scenario board changed to the half-bridge with planes on `In1.Cu` and `B.Cu` (spec amended: the BMS has no inner layer). A stitching via keeps off every other net's band by its clearance on every layer, and the stitching clearance is the largest class clearance (new requirement "Stitching vias keep off other bands"; without it the `SW` fill narrowed to 0.9 mm and the run was refused). A ground hot-loop leg that no band can route lands on the plane through a via array at each pad (design, decision 5); the proof selects `test_connection` (1 passed); `test_copper_ground.py` alone: 1 passed.
- [x] 2.5 Via arrays at layer changes (scenario "Five vias for one ampere"). Proof: `uv run pytest tests/unit/roles/test_copper_vias.py -q`.
  2026-10-29: a transition lands through a rectangular via patch beside the terminal (`role.via.*`), `min_vias = ceil(milliamps / milliamps_per_via)`; 1 passed.
- [x] 2.6 High-voltage rules and barriers, and `roles.limit-missing` without a row (scenario "The bus keeps the user's distance"). Proof: `uv run pytest tests/unit/roles/test_copper_hv.py -q`.
  2026-10-29: `role.hv.<net>` rule and a barrier over the net's copper at the largest user row; high-voltage nets are planned first and do not widen, and their convex envelope is an obstacle of the other spines (spec amended); without a row nothing and `roles.limit-missing`; 2 passed.
- [x] 2.7 Provisional corridors `role.corridor.<group>.<net>`, locked items and existing `role.corridor.*` areas as obstacles, and `roles.corridor-blocked` (scenarios "Corridors keep pours out" and "Phase 2's corridors are kept"; the interface decided by the maintainer on 2026-10-29). Proof: `uv run pytest tests/unit/roles/test_copper_corridors.py -q`.
  2026-10-29: provisional corridors follow the net's own tracks, clipped at pad boxes; a gate return with a copper role of its own and a loose-ended Kelvin branch get none (new requirement "No corridor over planned copper"); locked copper of other nets and every `role.corridor.*` area are obstacles and never edited; 2 passed.
- [x] 2.8 The eight codes in `roles/codes.py`, with their entries in `explain.toml` (scenario "Copper codes in the table"). Proof: `uv run pytest tests/unit/roles/test_codes.py tests/unit/cli/test_explain_cmd.py -k roles -q`.
  2026-10-29: the eight codes with their severities and explanations (25 codes in all); 21 passed.

## 3. Verification, kept copper and repeat runs

- [x] 3.1 The judge before and after, on the simulated pour, and `roles.copper-worse` (scenario "A worse result is refused"). Proof: `uv run pytest tests/unit/roles/test_copper_verify.py -q`.
  2026-10-29: the judge runs before and after on the simulated pour (`with_simulated_fills` traces the pour into fills, which c0222's path and loop analyses read); the topological findings (where a Kelvin branch or a gate return attaches) are reported and not counted as worse (spec amended); the scenario's test planner joins `VL` with a 0.2 mm track; 1 passed.
- [x] 3.2 Key-derived ids, the manifest `.fenolite/role-copper.json`, kept edits, `keep` and `regenerate` (scenario "Second run and a user edit"). Proof: `uv run pytest tests/unit/roles/test_copper_repeat.py -q`.
  2026-10-29: `roles/rolemanifest.py` (content fingerprints without ids, named items by name); `apply_plan` restores the uuids of the rule areas, texts, graphics and dimensions the board held, so a run on its own output plans no change; 1 passed.

## 4. Surfaces

- [x] 4.1 `Design.role_copper`, `fenolite.dsl.role_copper`, the protocol `lens.rolecopper.RoleCopperPlanner`, and the build hook that `cmd_build` passes (scenario "Recorded and built"). The import-graph test is unchanged. Proof: `uv run pytest tests/unit/dsl/test_role_copper.py tests/unit/test_import_graph.py -q`.
  2026-10-29: `Design.role_copper(..., requirements=)` (spec amended: the requirements file of the high-voltage distances), `fenolite.dsl.role_copper`, `lens.rolecopper` and the planner that `cmd_build.role_planner` binds; the import graph is unchanged; 63 passed.
- [x] 4.2 `fenolite copper` with the plan protocol, `--gate drc` and its documentation in `docs/cli-contract.md` (scenarios "Plan, then write" and "Confirmation and refusals"). Proof: `uv run pytest tests/unit/cli/test_copper_cmd.py -q`.
  2026-10-29: `fenolite copper` writes the board, the manifest and, when the plan holds role rules, the project's `.kicad_dru`; a plan without change writes nothing (spec amended, new requirement "Copper command without change"); `docs/cli-contract.md`, "copper"; 3 passed.
- [x] 4.3 The Altium hand-over for generated and role copper, and `kicad.generate.altium` only with `--copper-from` (scenarios "Generated copper reaches Altium" and "Role copper built for Altium"). Proof: `uv run pytest tests/unit/lens/test_altium_generated.py tests/unit/cli/test_build_altium_script_copper.py -q`.
  2026-10-29: `_run_altium` runs the in-memory KiCad build for generated records and the role-copper record too, and `SCRIPT_COPPER_CODES` passes `kicad.generate.*` and `roles.*`; `kicad.generate.altium` is given only with `--copper-from` (its explanation and `docs/copper.md` updated). c0224's test `test_altium_target_refuses_generated_copper` in `tests/unit/dsl/test_generate.py` contradicted the new requirement and moved into `tests/unit/lens/test_altium_generated.py`. The buck's Altium build holds the 6 role zones of its KiCad build; 13 passed.

## 5. Acceptance gate: the reference boards

- [ ] 5.1 Add `good_roles.py` and `bad_roles.py` to each of `examples/roles/buck_shunt`, `half_bridge` and `bms`. Each leaves out the power, switch-node, ground and high-voltage copper of its variant and calls `design.role_copper()`. Signal, gate and Kelvin copper stay. Proof: `uv run pytest tests/unit/roles/test_copper_reference.py -k build -q`.
- [ ] 5.2 Measure `H-G-ROLE-COPPER-CLEAN`, `-REPAIR` and `-SW` (scenario "Copper findings cleared"). Also check that `fenolite copper` on the unchanged `good` variants plans only `user-copper` skips. Proof: `uv run pytest tests/unit/roles/test_copper_reference.py -q`.
- [ ] 5.3 Compare the KiCad and Altium builds of the six scripts (`H-G-ROLE-COPPER-ALTIUM`). Proof: `uv run pytest tests/unit/roles/test_copper_backends.py -q`.
- [ ] 5.4 Refill with `kicad-cli` and run DRC on KiCad 10 (scenario "DRC on the bench"). The `kicad-9` job measures the same in CI. Proof: `uv run pytest tests/kicad/roles/test_copper_drc.py -q`, run in CI's KiCad jobs.

## 6. Closing

- [ ] 6.1 Docs: add the sections "Role copper" and "Copper defaults" to `docs/roles.md`, with sources and the S-0863 pitch method; describe the record in `docs/dsl.md`; note generated copper on Altium in `docs/copper.md`. Proof: `uv run pytest tests/unit/roles/test_profile.py tests/unit/test_public_presentation.py -q`.
- [ ] 6.2 Agent guide (AGENTS.md rule 6):
  - a tested line for `copper` on `board-power`, in a `fenolite-cmd` block;
  - `design.role_copper` on `board-power`, in a `fenolite-design` block;
  - one line on `board-grounds` (ground layers and stitching) and one on `board-insulation` (distances are the user's).

  Then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [ ] 6.3 Residue: the six scripts carry their authored-for-Fenolite line, and every new `.py` file starts with its SPDX and copyright lines. Proof: `make residue`.
- [ ] 6.4 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Do not run the full suite on the maintainer's Windows PC. Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 6.5 Evidence: the six `H-G-ROLE-COPPER-*` hypotheses go into `docs/hypotheses.md` with their measurements; S-0860 to S-0863 go into `src/fenolite/roles/PROVENANCE.md`; regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.6 Changelog. `dev` is cut at `0.6.0` and not yet published, and the v0.6 release guard requires `## [Unreleased]` to be empty, so this proposal adds no line. Once `0.7.0.dev0` opens, add the implemented phase 1 under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
