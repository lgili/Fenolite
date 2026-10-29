## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`verification-loop`, `cli-contract`, `manufacturing-exports`, `check-overlay`, `design-dsl`, `package-layering`). Write under this task, with the date and the base commit: whether c0253 is archived and the name of its stage (`circuit.rules` assumed) and of its codes; whether c0246 (`Range.within`), c0248 (`PartView.device`), c0251 (block paths in `ref()`) and c0252 (rail voltage) are archived; which open change holds a delta of "Render command" or "Allowed import edges" (regenerate the MODIFIED blocks from the living text if one was archived); whether `STAGE_ORDER` or `ORACLE_STAGES` changed; and whether c0245 (viewer) has landed on `dev`. Proof: `npx -y @fission-ai/openspec validate c0256-design-testing --strict`; `uv run pytest tests/unit/test_import_graph.py tests/unit/checks -k "stages or codes" -q`.

## 1. Finding subjects

- [ ] 1.1 Add `checks/subjects.py` (`Subject`, `SUBJECT_KINDS`) and `StageResult.subjects` with its length check (scenarios "Misaligned subjects refused", "Closed kinds"). Proof: `uv run pytest tests/unit/checks/test_subjects.py -k misaligned -q`.
- [ ] 1.2 Fill subjects in `copper.clearance`, `length.rules`, `placement.rules`, `roles.rules` and `circuit.rules`, and write `result.subjects` in `cmd_check` (scenarios "A rating finding names its part and net", "A length finding names its net", "Envelope unchanged"). Proof: `uv run pytest tests/unit/checks/test_subjects.py tests/consistency -k "subjects or envelope" -q`.
- [ ] 1.3 Resolve findings by subject in `view/check_overlay.py` and list the names in the panel (scenario "A finding with an empty where"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -q`.

## 2. Unattached objects

- [ ] 2.1 Add `dsl/_sites.py` (context variable, weak records) and record the creation site in `Part`, `Net` and `Interface`, set only by `run_design_script` (scenario "Helpers report the line in the script folder"). Proof: `uv run pytest tests/unit/dsl/test_sites.py -q`.
- [ ] 2.2 Report `build.unattached` from the build, sorted, with its row in `BUILD_ISSUE_CODES`, `explain.toml` and `docs/cli-contract.md` (scenarios "A part never added", "A complete script is quiet", "Explained"). Proof: `uv run pytest tests/unit/lens/test_unattached.py tests/unit/lens/test_build_issues.py -k "closed_set or lost or quiet" -q`; `uv run fenolite explain build.unattached --json`.
- [ ] 2.3 Measure the cost of the creation sites on the largest example under `examples/` and record it in `design.md` (risk "Creation sites cost a stack walk"). Proof: `uv run pytest tests/unit/lens/test_unattached.py -k cost -q`.

## 3. Net renders

- [ ] 3.1 Add the `net-hi`/`net-dim` classes, `data-render="fenolite.region.v1"` and the `--layers` filter to `analysis/region.py`. Proof: `uv run pytest tests/unit/analysis/test_region_render.py -q`.
- [ ] 3.2 Add `--net` and `--layers` to `render` with the whole-board region, the file names, `result.region.nets`/`highlighted` and the refusals (scenarios "Ground highlighted", "Counts and bytes", "Unknown net", "Option names do not collide", "Highlight needs no tool"). Proof: `uv run pytest tests/unit/cli/test_render_net.py tests/unit/cli/test_render_region.py -q`.
- [ ] 3.3 Accept a design script as `PATH` with `--region` or `--net` (scenarios "Render of a script", "Script without the model forms"). Proof: `uv run pytest tests/unit/cli/test_render_net.py -k script -q`.

## 4. `fenolite.testing`

- [ ] 4.1 Add the `testing` row to the import-graph test, then the package skeleton with `__all__` (scenario "Test helpers stay on top"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 4.2 `load` and `TestDesign` lifecycle (scenarios "Built in a temporary folder", "Same inputs, same model", "Folder removed", "A failing script fails the test"). Proof: `uv run pytest tests/unit/testing/test_load.py -q`.
- [ ] 4.3 `instantiate` for one c0251 block (scenario "A buck block alone"). Proof: `uv run pytest tests/unit/testing/test_instantiate.py -q`.
- [ ] 4.4 `net`, `ref`, `connected` (scenarios "Views of the example", "Unknown names", "Pins on one net, not yet routed"). Proof: `uv run pytest tests/unit/testing/test_queries.py -q`.
- [ ] 4.5 `findings` (scenarios "Circuit findings in a test", "Oracle stage refused"). Proof: `uv run pytest tests/unit/testing/test_findings.py -q`.
- [ ] 4.6 `svgdiff.py` and `assert_render` (scenarios "A moved track fails the golden test", "Same bytes, same verdict"). Proof: `uv run pytest tests/unit/testing/test_golden.py -q`.

## 5. Example, docs and guide

- [ ] 5.1 `examples/testing/`: an authored design (catalog parts only), its `test_design.py` using every helper, and its golden `gnd.svg` written by `fenolite render --confirm`; the example tests run in `make check-fast`. Proof: `uv run pytest examples/testing -q`; `make residue`.
- [ ] 5.2 Docs: `docs/testing.md` (new, linked from `docs/index.md` and `docs/dsl.md`), `docs/exports.md` ("Net renders"), `docs/viewer.md` (subjects), `docs/cli-contract.md` (`render --net`, `result.subjects`, `build.unattached`). Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.3 Agent guide: a tested line for `render --net` on `checks` and for `fenolite.testing` and `build.unattached` on `design-script`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch (Linux, macOS and Windows unit jobs carry `H-G-RENDER-DETERMINISTIC`). Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 6.2 Evidence: register `H-G-RENDER-DETERMINISTIC` in `docs/hypotheses.md` with its measurement and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.
