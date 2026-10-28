## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`design-model`, `design-dsl`, `cli-contract`, `verification-loop`, `board-analyses`). Write under this task, with the date and the base commit:
  - which open change holds a delta of "No shipped requirement values" (if one was archived, regenerate the MODIFIED block from the living text);
  - whether a change has inserted a stage between `placement.rules` and `zone.fill`;
  - whether c0175's packages 5 and 6 are split into their own changes, and with which ids;
  - that S-0850 to S-0854 are still the rows this proposal registered;
  - the maintainer's answers to the seven open questions of `design.md`.

  Proof: `openspec validate c0222-net-roles --strict --no-interactive`; `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.

## 1. Model and storage

- [ ] 1.1 Add the role value objects and `RuleSet.roles` to `model/rules.py`, regenerate the schemas, and describe them in `docs/design-model.md` (scenarios "Roles round trip", "Files of an older build", "Refused values"). Proof: `uv run pytest tests/unit/model/test_rules.py -k roles -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 1.2 Add `roles/store.py`: the companion document `fenolite.roles.v0`, its loader and writer, and `--roles FILE` resolution (scenario "Roles beside a hand-routed board"). Proof: `uv run pytest tests/unit/roles/test_store.py -q`.

## 2. Classes and inference

- [ ] 2.1 Add `roles/classify.py` with the class vocabulary and terminal maps (scenario "Classes from pin names"). Proof: `uv run pytest tests/unit/roles/test_classify.py -q`.
- [ ] 2.2 Add `roles/infer.py` with the rule table `SW-1` to `SIG-0`, confidence, conflicts and currents (scenarios "Switching node and hot loop of a buck", "No high voltage from a name", "A power net without a current"). Proof: `uv run pytest tests/unit/roles/test_infer.py -q`.

## 3. Reference boards

- [ ] 3.1 Author the CC0 footprints and symbols in `tests/data/libs`: the power MOSFETs (one with a Kelvin source), the inductor, the two-pad and four-pad shunts, the half-bridge driver, the sense amplifier and the cell monitor. Each file starts with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/roles/test_reference_libs.py -q` (every new footprint and symbol loads, and starts with the authored line); `make residue`.
- [ ] 3.2 Author `examples/roles/buck_shunt`, `half_bridge` and `bms`, each with `good.py` and `bad.py`, and the expected role tables in `tests/unit/roles/test_infer_reference.py`. Register `H-G-ROLE-INFER` with its first measurement (scenarios "One role per net", "Groups of the half-bridge"). Proof: `uv run pytest tests/unit/roles/test_infer_reference.py -q`.
- [ ] 3.3 Build the six variants for KiCad and run DRC on the good ones. Proof: `uv run pytest tests/kicad/roles/test_reference_drc.py -rA` (in CI).

## 4. Profile, limits and codes

- [ ] 4.1 Add `roles/profile.py` with the default table, `RoleLimit` resolution, and `docs/roles.md` with the "Default limits" section (scenarios "Every default has a source", "A net override wins"). Proof: `uv run pytest tests/unit/roles/test_profile.py -q`.
- [ ] 4.2 Add `roles/codes.py` with the eighteen codes, their entries in `fenolite explain`, and the severity rule (scenarios "Codes in the table", "Unconfirmed roles warn only"). Proof: `uv run pytest tests/unit/roles/test_codes.py tests/unit/cli/test_explain_cmd.py -q`.

## 5. Measures and checks

- [ ] 5.1 Add the copper path between pads (scenario "A path through a pour"). Proof: `uv run pytest tests/unit/roles/test_path.py -q`.
- [ ] 5.2 Add the loop area, the bound and the ratio, and register `H-G-ROLE-LOOP-AREA` (scenario "Authored loops"). Proof: `uv run pytest tests/unit/roles/test_loop_area.py -q`.
- [ ] 5.3 Add the hot and gate loop checks, and register `H-G-ROLE-LOOP-RATIO` with the reference measurements (scenario "The bad buck's hot loop"). Proof: `uv run pytest tests/unit/roles/test_reference_boards.py -k loop -q`.
- [ ] 5.4 Add the Kelvin attachment, pair and switching-distance checks. Register `H-G-ROLE-KELVIN-EDGE`, `H-G-ROLE-KELVIN-PAIR` and `H-G-ROLE-NEAR-SW` (scenarios "Sense lines of the bad buck", "A sense pair over the switch node"). Proof: `uv run pytest tests/unit/roles/test_kelvin.py tests/unit/roles/test_reference_boards.py -k "kelvin or switching" -q`.
- [ ] 5.5 Add the current checks by both methods, and register `H-G-ROLE-CURRENT` (scenario "A thin track on a 2 A net"). Proof: `uv run pytest tests/unit/roles/test_current.py -q`.
- [ ] 5.6 Add the return and high-voltage checks (scenario "A high-voltage bus without a requirement"). Proof: `uv run pytest tests/unit/roles/test_returns_hv.py -q`.
- [ ] 5.7 Run the whole check on the six variants (scenario "Good and bad variants"). Proof: `uv run pytest tests/unit/roles/test_reference_boards.py -q`.

## 6. Command line, DSL and stage

- [ ] 6.1 Add `fenolite roles` with show, confirm and `--check`, and its section in `docs/cli-contract.md` (scenarios "Read-only by default", "Write needs confirmation", "Usage error", "Confirm through a plan", "A declaration wins"). Proof: `uv run pytest tests/unit/cli/test_roles_cmd.py tests/consistency/test_cli_consistency.py -q`.
- [ ] 6.2 Add the DSL calls and their section in `docs/dsl.md` (scenarios "Declared roles are built", "A pad of another part is refused"). Proof: `uv run pytest tests/unit/dsl/test_roles.py -q`.
- [ ] 6.3 Add the stage `roles.rules` to both pipelines (scenarios "A board without roles is unchanged", "Confirmed roles are judged"). Proof: `uv run pytest tests/unit/checks/test_roles_stage.py tests/unit/checks/test_stages.py -q`.
- [ ] 6.4 Amend "No shipped requirement values" in `docs/analyses.md` and the facts-page test (scenario "Analyze ignores the role profile"). Proof: `uv run pytest tests/unit/analysis/test_facts_page.py -q`.
- [ ] 6.5 Compare the roles and measures of the KiCad and Altium builds of each variant (scenarios "Same roles from both builds", "Evidence of a check"). Proof: `uv run pytest tests/unit/roles/test_backends.py -q`.

## 7. Closing

- [ ] 7.1 Docs: `docs/roles.md` (roles, inference rules, confirmation, measures, default limits with sources, what has no public source), with links from `docs/analyses.md` and `docs/dsl.md`. Proof: `uv run pytest tests/unit/roles/test_profile.py tests/unit/test_provenance.py -q`.
- [ ] 7.2 Agent guide: add tested lines for `roles` on `checks`, for the six DSL calls on `board-power`, and for `roles.return-gap` and `roles.limit-missing` on `board-grounds` and `board-insulation`. Then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [ ] 7.3 Residue: every authored file carries its authored-for-Fenolite line, and no name, value or layout comes from another project. Proof: `make residue`.
- [ ] 7.4 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 7.5 Evidence: the seven hypotheses are in `docs/hypotheses.md` with their measurements, and the evidence matrix is regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 7.6 Add an entry for the implemented phase 0 to `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
