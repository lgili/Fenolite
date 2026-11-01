## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`cli-contract`, and `design-testing` once c0256 is archived) and the changes it builds on (c0251, c0253, c0254, c0256, c0268; c0271, c0273). Write under this task, with the date and the base commit:
  - whether c0256 is archived and the final names of `instantiate`, `TestDesign`, `PartView` and `TestingError` (regenerate the ADDED blocks of `specs/design-testing/` against the living text if names changed);
  - c0253's names of `supply`, `sink`, the requirement-table row and its statuses, and whether `circuit.expect-unknown` is the code of an unbounded expectation;
  - c0254's name of `result.generators` and of `gen.achieved`;
  - c0268's record fields (`tests` first), the module that holds its catalog, and the verbs of `fenolite blocks`;
  - whether `examples/` or the guide already use the name `draw`.

  Proof: `openspec validate c0270-block-tests --strict`; `make check-fast`.

  Entry review, 2026-11-01, base `8d74a798372c3a8c96b96daa97726223e30411ab`: c0256 is
  implemented but unarchived; its public names remain `instantiate`, `TestDesign`, `PartView` and
  `TestingError`. There is no living `design-testing` spec yet. c0253 exports `supply` and `sink`;
  `core.requirement_table.RequirementRow` statuses are pass/fail/unsure/unknown/deferred, and the
  unbounded-expectation code is `circuit.expect-unknown`. Native expectation ids have the prefix
  `circuit.expect:`; the testing view exposes the expectation path, for example `dut/expect#1`.
  c0254 reports `result.generators` and `gen.achieved`; its achieved interval is outward-rounded
  micro-unit text, decoded by the testing query. c0268's `CatalogEntry` in `cli.blocksrc` holds
  definition/source/where and a lazy record; `tests`, `usage`, `golden` are not present yet. Existing
  verbs are list/show/doc/where. c0251/c0253/c0254/c0256/c0268/c0271/c0273 proposals and the living
  CLI contract were reviewed. Neither examples nor the guide exports a helper named `draw`.
  The full `make check-fast` proof is reserved for the integration coordinator, so 0.1 remains open.

## 1. Stimulus and queries in `fenolite.testing`

- [x] 1.1 `testing/stimulus.py`: `stimulus`, `source`, `draw`, `Stimulus`, the reference rule and its refusals (scenario "Ambiguous reference"). Proof: `uv run pytest tests/unit/testing/test_stimulus.py -k reference -q`.
- [x] 1.2 `instantiate(..., stimulus=)` writes the rig elements into the throwaway script (scenarios "A divider judged with its input", "Without a stimulus nothing is known"). Author `tests/data/blocks/lib/divider.py` (`Test:divider`), each file with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/testing/test_stimulus.py -q`.
- [x] 1.3 `requirements`, `achieved` and the `PartView` placement fields; grow `__all__` (scenarios "Rows of a block", "Achieved output range", "Placement read back"). Proof: `uv run pytest tests/unit/testing/test_queries.py -k "requirements or achieved or placement" -q`; `uv run pytest tests/unit/test_import_graph.py -q`.

## 2. The runner

- [x] 2.1 Convention lookup and the record paths in `fenolite blocks show` (scenario "Paths in the record"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k paths -q`.
- [x] 2.2 Usage builds through `fenolite.testing.load` with the tool-free stages (scenario "A usage example with an unwired port"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k usage -q`.
- [x] 2.3 Golden files: the `fenolite.block-golden.v0` object, the canonical writer, the byte comparison and the JSON-path diff (scenarios "A changed value is caught", "Same bytes on every run"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k golden -q`.
- [x] 2.4 Test functions: loading by path, name order, pass, fail, skip (scenario "Pass, fail and skip"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k functions -q`.

## 3. Command and codes

- [x] 3.1 The verb `fenolite blocks test` with `--only`, `result.blocks`, exit codes, and the unknown-id hint (scenarios "One block tested", "Unknown block"). Proof: `uv run pytest tests/unit/cli/test_blocks_test.py -q`.
- [x] 3.2 `--golden` under `--dry-run` and `--confirm --plan`, refused for a failing usage (scenario "Regenerate after review"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k golden_write -q`.
- [x] 3.3 The six codes in `explain.toml` and `docs/cli-contract.md`, "Block tests" (scenario "Every block test code is explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`; `uv run fenolite explain blocks.golden-differs --json`.

## 4. Repository suite and CI

- [x] 4.1 `tests/unit/blocks/test_convention.py` and `tests/unit/blocks/test_shipped_blocks.py` (parametrised over the shipped ids; empty until c0272 lands, then each block) (scenarios "Every shipped block follows the convention", "Shipped blocks in the fast suite"). Proof: `uv run pytest tests/unit/blocks -q`.
- [ ] 4.2 `tests/kicad/blocks/test_usage_boards.py` for targets 9 and 10, and a step `uv run fenolite blocks test --json` in the unit jobs of `.github/workflows/ci.yml` (scenario "Usage boards read back"). Proof: `uv run pytest tests/unit -k workflow -q`; the KiCad jobs green on the pushed head.
- [x] 4.3 `examples/blocks/` gains a project block laid out under the convention, with its usage example, tests and golden file. Proof: `uv run fenolite blocks test --json` in `examples/blocks/` exits 0; `make residue`.

## 5. Docs and guide

- [x] 5.1 `docs/testing.md` ("Testing blocks": the convention, `stimulus`, `requirements`, `achieved`, goldens), `docs/cli-contract.md` (`blocks test`). Proof: `uv run pytest tests/consistency -q`.
- [x] 5.2 Agent guide: a tested line for `fenolite blocks test` and for `stimulus` on `design-script`, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 6.2 Evidence: register `H-G-BLOCK-GOLDEN` in `docs/hypotheses.md` with its measurement on the three unit jobs and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.

## Validation record — 2026-11-01

- Focused implementation run: `uv run pytest tests/unit/testing tests/unit/blocks
  tests/unit/cli/test_blocks_test.py tests/unit/cli/test_blocks_cmd.py tests/unit/cli/test_plans.py
  tests/unit/cli/test_explain_cmd.py tests/unit/test_import_graph.py
  tests/data/blocks/lib/tests/test_divider.py -q`: 186 passed, two expected empty-shipped-library skips.
  Added follow-up proofs cover pull-up achieved units, catalog version refresh, private usage locks,
  actual bottom-resistor default changes, preserved module state and category selection.
- `uv run pytest tests/consistency -q`: 662 passed, 41 expected mutating-example skips.
  `uv run pytest tests/unit/agent -q`: 118 passed, 19 existing target-10 skips.
  The agent guide was regenerated; its `--check` passed. A new `block-testing` page keeps the existing
  `design-script` page within its 12000-byte budget and preserves all previous content.
- `uv run pytest tests/unit -k workflow -q`: 48 passed, one optional-SDK collection skip.
  `uv run pytest tests/unit -k changelog -q`: eight passed, the same optional-SDK skip.
  `uv run pytest tests/unit/test_hypotheses_register.py -q`: 38 passed; evidence matrix regenerated
  and `tools/gen_evidence_matrix.py --check` passed.
- The example's `uv run fenolite blocks test --json` exits 0 with passed usage/tests and equal golden.
  Both committed authored goldens were generated through dry-run and reviewed-plan replay.
- `ruff check .`, `ruff format --check .`, `pyright src`, the focused type recheck of later edits,
  `git diff --check`, strict OpenSpec validation and `make residue` passed. Residue: zero hits in
  5607 scanned files; the optional private-list gate was unavailable.
- 0.1 and 6.1 remain open: the integration coordinator owns the single `make check-fast` run and
  publication/CI on the exact integrated commit; this worktree ran no full gate and pushed nothing.
- 4.2 remains open: CI hooks and target-9/10 usage read-back tests are implemented, and the workflow
  shape proof passed, but the required KiCad jobs have not run on this commit. The shipped library is
  intentionally empty until c0272, as the parametrised suites report.
- 6.2 remains open: Linux stable-byte proofs and the register/matrix checks passed, but Linux/macOS/
  Windows unit-matrix measurements are pending. The hypothesis records that limit without claiming CI.
