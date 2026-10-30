## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`cli-contract`, and `design-testing` once c0256 is archived) and the changes it builds on (c0251, c0253, c0254, c0256, c0268; c0271, c0273). Write under this task, with the date and the base commit:
  - whether c0256 is archived and the final names of `instantiate`, `TestDesign`, `PartView` and `TestingError` (regenerate the ADDED blocks of `specs/design-testing/` against the living text if names changed);
  - c0253's names of `supply`, `sink`, the requirement-table row and its statuses, and whether `circuit.expect-unknown` is the code of an unbounded expectation;
  - c0254's name of `result.generators` and of `gen.achieved`;
  - c0268's record fields (`tests` first), the module that holds its catalog, and the verbs of `fenolite blocks`;
  - whether `examples/` or the guide already use the name `draw`.

  Proof: `openspec validate c0270-block-tests --strict`; `make check-fast`.

## 1. Stimulus and queries in `fenolite.testing`

- [ ] 1.1 `testing/stimulus.py`: `stimulus`, `source`, `draw`, `Stimulus`, the reference rule and its refusals (scenario "Ambiguous reference"). Proof: `uv run pytest tests/unit/testing/test_stimulus.py -k reference -q`.
- [ ] 1.2 `instantiate(..., stimulus=)` writes the rig elements into the throwaway script (scenarios "A divider judged with its input", "Without a stimulus nothing is known"). Author `tests/data/blocks/lib/divider.py` (`Test:divider`), each file with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/testing/test_stimulus.py -q`.
- [ ] 1.3 `requirements`, `achieved` and the `PartView` placement fields; grow `__all__` (scenarios "Rows of a block", "Achieved output range", "Placement read back"). Proof: `uv run pytest tests/unit/testing/test_queries.py -k "requirements or achieved or placement" -q`; `uv run pytest tests/unit/test_import_graph.py -q`.

## 2. The runner

- [ ] 2.1 Convention lookup and the record paths in `fenolite blocks show` (scenario "Paths in the record"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k paths -q`.
- [ ] 2.2 Usage builds through `fenolite.testing.load` with the tool-free stages (scenario "A usage example with an unwired port"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k usage -q`.
- [ ] 2.3 Golden files: the `fenolite.block-golden.v0` object, the canonical writer, the byte comparison and the JSON-path diff (scenarios "A changed value is caught", "Same bytes on every run"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k golden -q`.
- [ ] 2.4 Test functions: loading by path, name order, pass, fail, skip (scenario "Pass, fail and skip"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k functions -q`.

## 3. Command and codes

- [ ] 3.1 The verb `fenolite blocks test` with `--only`, `result.blocks`, exit codes, and the unknown-id hint (scenarios "One block tested", "Unknown block"). Proof: `uv run pytest tests/unit/cli/test_blocks_test.py -q`.
- [ ] 3.2 `--golden` under `--dry-run` and `--confirm --plan`, refused for a failing usage (scenario "Regenerate after review"). Proof: `uv run pytest tests/unit/blocks/test_runner.py -k golden_write -q`.
- [ ] 3.3 The six codes in `explain.toml` and `docs/cli-contract.md`, "Block tests" (scenario "Every block test code is explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`; `uv run fenolite explain blocks.golden-differs --json`.

## 4. Repository suite and CI

- [ ] 4.1 `tests/unit/blocks/test_convention.py` and `tests/unit/blocks/test_shipped_blocks.py` (parametrised over the shipped ids; empty until c0272 lands, then each block) (scenarios "Every shipped block follows the convention", "Shipped blocks in the fast suite"). Proof: `uv run pytest tests/unit/blocks -q`.
- [ ] 4.2 `tests/kicad/blocks/test_usage_boards.py` for targets 9 and 10, and a step `uv run fenolite blocks test --json` in the unit jobs of `.github/workflows/ci.yml` (scenario "Usage boards read back"). Proof: `uv run pytest tests/unit -k workflow -q`; the KiCad jobs green on the pushed head.
- [ ] 4.3 `examples/blocks/` gains a project block laid out under the convention, with its usage example, tests and golden file. Proof: `uv run fenolite blocks test --json` in `examples/blocks/` exits 0; `make residue`.

## 5. Docs and guide

- [ ] 5.1 `docs/testing.md` ("Testing blocks": the convention, `stimulus`, `requirements`, `achieved`, goldens), `docs/cli-contract.md` (`blocks test`). Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.2 Agent guide: a tested line for `fenolite blocks test` and for `stimulus` on `design-script`, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 6.2 Evidence: register `H-G-BLOCK-GOLDEN` in `docs/hypotheses.md` with its measurement on the three unit jobs and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.
