# Tasks: c0498-check-altium-drc-parity

Rules for every task:

- The maintainer's board is private. Nothing from it (names, nets, coordinates, counts, files) goes into
  tests, fixtures, evidence, commits or messages. Test boards are authored for Fenolite. Format facts come
  from the public corpus rows of the manifest and from kit runs on authored boards.
- Run each touched test file alone with `-n 0`. Run every test file that reads `check` output for Altium
  input, not only those edited.

## 1. Evidence and diagnosis

- [ ] 1.1 Census of the `T…Violation` and `WaivedViolations` storages of the public PCB documents (D1). Write
  the kit case "native DRC" (Part D): an authored board with one planted fault per kind of the D3 table,
  DRC with Create Report File on, saved document and `.drc` as results. Record the record layout, the index
  base, the units and the text report's line form in `docs/formats/altium/pcb-records.md` ("DRC
  violations") and `pcb-document.md`, with sources in `docs/evidence/sources.md` and the rows
  `H-A-DRC-STORED` and `H-A-DRC-TXT` in `docs/hypotheses.md`.
  - Proof: `uv run --extra dev pytest tests/corpus/test_altium_violations_census.py tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py -q -n 0` and
    `uv run fenolite kit status --json` lists the case's result
- [ ] 1.2 Find the keys of `SilkToSolderMaskClearance` and `SilkToBoardRegionClearance` (corpus, the rule
  export S-0297, or the kit board) and what each measures (Altium's documentation, read for facts). Record
  them in `rule-file.md` and `H-A-SILK-RULES`.
  - Proof: `uv run --extra dev pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py -q -n 0`
- [ ] 1.3 Reproduce F40 on authored boards: the four slot cases of D5 step 1 and a keep-out `Clearance`
  rule. Record which give no finding today, in the test as `xfail` with the reason.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/checks/test_copper_cutouts_c0498.py -q -n 0`

## 2. Cut-outs and keep-outs

- [ ] 2.1 Fix each missed case of 1.3 where it fails (D5 step 1); the `xfail` marks go.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/checks/test_copper_cutouts_c0498.py tests/unit/checks/test_copper_edges.py -q -n 0`
- [ ] 2.2 `copper.rules-incomplete` (`where` = `edge`) for unset edge items (D5 step 2); scenario "An edge rule
  that selects nothing".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/checks/test_copper_edges.py -q -n 0`
- [ ] 2.3 Move `pour._keepout_rule` to `read.rules.keepout_clearance_rule`; the pour tests stay green.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_pour_rules.py tests/unit/backends/altium/test_pour_regions.py -q -n 0`
- [ ] 2.4 Give the rule to the copper check in `AltiumBackend.design_rules` and judge keep-out distance in
  `check_copper` (`copper.keepout-clearance`, registered in `checks/codes.py`); scenario "A pour beside a
  keep-out".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/checks/test_copper_cutouts_c0498.py tests/unit/checks/test_document_copper.py -q -n 0`

## 3. Silk rules

- [ ] 3.1 (After c0493 is merged.) `silk_mask_clearance` and `silk_edge_clearance` in `RuleKind`, the
  model's minor version, `RULE_KIND_MAP`, `CARRIED_KINDS` and the KiCad `KIND_SUPPORT`; regenerate the
  schemas.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/test_rulemap.py tests/unit/model/test_rules.py -q -n 0 && uv run python tools/gen_schemas.py --check && uv run python tools/model_review.py --check`
- [ ] 3.2 `silk.board.judge_silk` on the obstacles of the `altium` model and the opt-in stage
  `silk.clearance` (D4); scenarios "Two texts too close", "A text on a mask opening", "Silk over the edge".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/silk/test_judge_silk_c0498.py tests/unit/checks/test_documents.py -q -n 0`

## 4. Altium's own results

- [ ] 4.1 `read/violations.py`: `stored_violations` and `report_violations` (D1, D2), on authored documents
  holding the records that 1.1 recorded and on the kit's `.drc`; unknown layout gives
  `altium.read.violations-unknown`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/test_violations.py -q -n 0`
- [ ] 4.2 `NativeDrcSource`, `checks/native.py`, `rulemap.NATIVE_CODES`, the stage `altium.native-drc` and
  `check --compare-native [REPORT]` (D3); the scenarios of "Comparison with Altium's DRC".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/checks/test_native_compare.py tests/unit/cli/test_check_native.py -q -n 0`
- [ ] 4.3 Run the kit board of 1.1 through `check --compare-native`: every planted fault is matched and
  nothing is Fenolite-only or Altium-only, or each difference is a recorded hypothesis. Count the new
  `copper.keepout-clearance` and edge `copper.rules-incomplete` findings on the public corpus and record
  them in `docs/formats/altium/import.md`.
  - Proof: `uv run --extra geo --extra dev pytest tests/kicad/altium/test_native_kit_c0498.py -q -n 0` and
    `uv run --extra geo --extra dev pytest tests/corpus/test_altium_copper.py -q -n 0`

## 5. Teach and record

- [ ] 5.1 Teach `--compare-native`, the stages `altium.native-drc` and `silk.clearance` and the codes
  `copper.keepout-clearance`, `silk.clearance`, `silk.mask-clearance`, `silk.edge-clearance`,
  `check.native-only`, `check.fenolite-only`, `check.native-stale`, `check.native-missing` on the agent
  guide page `checks.md`; regenerate the command pages; update "check" in `docs/cli-contract.md`.
  - Proof: `uv run python tools/gen_agent_guide.py --check && uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 5.2 Regenerate the schemas for `result.native` and the new codes; declare new files under
  `tests/data` in `tests/data/MANIFEST.toml`.
  - Proof: `uv run python tools/gen_schemas.py --check && uv run --extra dev pytest tests/corpus/test_manifest.py -q -n 0`
- [ ] 5.3 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
