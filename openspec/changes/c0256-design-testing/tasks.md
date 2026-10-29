## 0. Entry check

- [x] 0.1 Read `openspec list` and the living specs this change touches (`verification-loop`, `cli-contract`, `manufacturing-exports`, `check-overlay`, `design-dsl`, `package-layering`). Write under this task, with the date and the base commit: whether c0253 is archived and the name of its stage (`circuit.rules` assumed) and of its codes; whether c0246 (`Range.within`), c0248 (`PartView.device`), c0251 (block paths in `ref()`) and c0252 (rail voltage) are archived; which open change holds a delta of "Render command" or "Allowed import edges" (regenerate the MODIFIED blocks from the living text if one was archived); whether `STAGE_ORDER` or `ORACLE_STAGES` changed; and whether c0245 (viewer) has landed on `dev`. Proof: `npx -y @fission-ai/openspec validate c0256-design-testing --strict`; `uv run pytest tests/unit/test_import_graph.py tests/unit/checks -k "stages or codes" -q`.

  - 2026-10-29: entry proved on base `3cabfe5a2077a3706a917b0904a9a93848f5913a` (`circuits-as-code`). `openspec list` read; strict validation passed; the import-graph/stage/code proof passed (49 passed, 703 deselected; exit 0). The six living specs and these deltas were read. c0246, c0248, c0251, c0252 and c0253 are unarchived proposals with no implementation on this base. `Range.within`, devices, block paths and rail voltages are unavailable. c0252 will introduce `circuit.rules`; c0253 extends it. Neither that stage nor its `circuit.*` codes exists yet. c0252 plans rail-voltage/current/sources/unset, logic-level/unknown, bus-pullup and port-split; c0253 adds rating-voltage/current/power/temperature, expect-failed/unsure/unknown, value-conflict/unknown, device-changed, rating-missing and policy-missing.
  - 2026-10-29: `STAGE_ORDER` and `ORACLE_STAGES` are unchanged: the tool-free subset is `model.validate,copper.clearance,length.rules,placement.rules,roles.rules,parity,roundtrip`; oracle stages are `erc.kicad,zone.fill,drc.kicad,netlist.assignment_compare,roundtrip.rt2,render`. c0245-engineering-viewer has not landed on inspected `origin/dev` (`da300adf`). Open "Allowed import edges" deltas are c0173, c0195, c0248, c0254, c0256 and c0267; c0256 alone has an open "Render command" delta. None newly archived requires regenerating these MODIFIED blocks. Available work proceeds in order; dependent block and circuit-rating integration stays open.

## 1. Finding subjects

- [x] 1.1 Add `checks/subjects.py` (`Subject`, `SUBJECT_KINDS`) and `StageResult.subjects` with its length check (scenarios "Misaligned subjects refused", "Closed kinds"). Proof: `uv run pytest tests/unit/checks/test_subjects.py -k misaligned -q`.
  - 2026-10-29: proof passed, exit 0 (2 tests); closed subject kinds and alignment are enforced.
- [ ] 1.2 Fill subjects in `copper.clearance`, `length.rules`, `placement.rules`, `roles.rules` and `circuit.rules`, and write `result.subjects` in `cmd_check` (scenarios "A rating finding names its part and net", "A length finding names its net", "Envelope unchanged"). Proof: `uv run pytest tests/unit/checks/test_subjects.py tests/consistency -k "subjects or envelope" -q`.
  - 2026-10-29: available stage/subject and envelope proof passed (54 tests, exit 0). Implemented the four available stages and global indices, including input issues. Remains open for c0252/c0253 circuit.rules and its real rating scenario.
- [x] 1.3 Resolve findings by subject in `view/check_overlay.py` and list the names in the panel (scenario "A finding with an empty where"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -q`.

  - 2026-10-29: overlay proof passed, exit 0 (5 tests), including id-first resolution, name fallback and empty locations.

## 2. Unattached objects

- [x] 2.1 Add `dsl/_sites.py` (context variable, weak records) and record the creation site in `Part`, `Net` and `Interface`, set only by `run_design_script` (scenario "Helpers report the line in the script folder"). Proof: `uv run pytest tests/unit/dsl/test_sites.py -q`.
  - 2026-10-29: proof passed, exit 0 (2 tests), including sibling source locations, weak records and context reset.
- [x] 2.2 Report `build.unattached` from the build, sorted, with its row in `BUILD_ISSUE_CODES`, `explain.toml` and `docs/cli-contract.md` (scenarios "A part never added", "A complete script is quiet", "Explained"). Proof: `uv run pytest tests/unit/lens/test_unattached.py tests/unit/lens/test_build_issues.py -k "closed_set or lost or quiet" -q`; `uv run fenolite explain build.unattached --json`.
  - 2026-10-29: proof passed, exit 0 (2 tests; 5 deselected); explain returns warning and add/connect/delete guidance.
- [x] 2.3 Measure the cost of the creation sites on the largest example under `examples/` and record it in `design.md` (risk "Creation sites cost a stack walk"). Proof: `uv run pytest tests/unit/lens/test_unattached.py -k cost -q`.

  - 2026-10-29: cost proof passed, exit 0 (1 test); largest example is yardstick (388 parts), 3-run median 0.026594 s enabled vs 0.018650 s disabled on this machine.

## 3. Net renders

- [x] 3.1 Add the `net-hi`/`net-dim` classes, `data-render="fenolite.region.v1"` and the `--layers` filter to `analysis/region.py`. Proof: `uv run pytest tests/unit/analysis/test_region_render.py -q`.
  - 2026-10-29: renderer proof passed, exit 0 (7 tests); canonical SVG version, entity keys, highlight and copper-layer filtering preserve holes/edges.
- [x] 3.2 Add `--net` and `--layers` to `render` with the whole-board region, the file names, `result.region.nets`/`highlighted` and the refusals (scenarios "Ground highlighted", "Counts and bytes", "Unknown net", "Option names do not collide", "Highlight needs no tool"). Proof: `uv run pytest tests/unit/cli/test_render_net.py tests/unit/cli/test_render_region.py -q`.
  - 2026-10-29: CLI proof passed, exit 0 (20 tests), including exact --net/--nets parsing, refusals, deterministic bytes, counts and no external tools.
- [x] 3.3 Accept a design script as `PATH` with `--region` or `--net` (scenarios "Render of a script", "Script without the model forms"). Proof: `uv run pytest tests/unit/cli/test_render_net.py -k script -q`.

  - 2026-10-29: script proof passed, exit 0 (1 test), covering deterministic in-memory builds, no persistent build output and missing-board/plot refusals.

## 4. `fenolite.testing`

- [x] 4.1 Add the `testing` row to the import-graph test, then the package skeleton with `__all__` (scenario "Test helpers stay on top"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.
  - 2026-10-29: import-graph proof passed, exit 0 (52 tests); testing is a stdlib-only top layer and no lower layer may import it.
- [x] 4.2 `load` and `TestDesign` lifecycle (scenarios "Built in a temporary folder", "Same inputs, same model", "Folder removed", "A failing script fails the test"). Proof: `uv run pytest tests/unit/testing/test_load.py -q`.
  - 2026-10-29: lifecycle proof passed, exit 0 (3 tests); owned temporary plans/builds removed, caller workdir retained, deterministic model and script error locations preserved.
- [ ] 4.3 `instantiate` for one c0251 block (scenario "A buck block alone"). Proof: `uv run pytest tests/unit/testing/test_instantiate.py -q`.
  - 2026-10-29: deferred: c0251 has not landed. No instantiate stub is exported and no passing block scenario is claimed.
- [x] 4.4 `net`, `ref`, `connected` (scenarios "Views of the example", "Unknown names", "Pins on one net, not yet routed"). Proof: `uv run pytest tests/unit/testing/test_queries.py -q`.
  - 2026-10-29: query proof passed, exit 0 (2 tests); uses model identities, netlist vs physical copper and close-name hints. voltage/device remain None pending c0246/c0248/c0252; c0251 block paths remain deferred.
- [ ] 4.5 `findings` (scenarios "Circuit findings in a test", "Oracle stage refused"). Proof: `uv run pytest tests/unit/testing/test_findings.py -q`.
  - 2026-10-29: available findings proof passed, exit 0 (2 tests), covering filters, evidence, build warnings and oracle refusal before calls. Remains partial/open for the real circuit.* rating scenario of c0252/c0253.
- [x] 4.6 `svgdiff.py` and `assert_render` (scenarios "A moved track fails the golden test", "Same bytes, same verdict"). Proof: `uv run pytest tests/unit/testing/test_golden.py -q`.

  - 2026-10-29: golden proof passed, exit 0 (3 tests); exact bytes, no reference writes, missing-file diagnostics and one-element track changes are covered.

## 5. Example, docs and guide

- [ ] 5.1 `examples/testing/`: an authored design (catalog parts only), its `test_design.py` using every helper, and its golden `gnd.svg` written by `fenolite render --confirm`; the example tests run in `make check-fast`. Proof: `uv run pytest examples/testing -q`; `make residue`.
  - 2026-10-29: available example proof passed, exit 0 (2 tests), and residue scan is clean. Canonical golden is net-GND.svg, generated via reviewed dry-run/confirm; grid-coordinate numeric matches have one exact-file waiver. Example is in check-fast and the platform unit suite. Remains open only for instantiate/block coverage after c0251.
- [x] 5.2 Docs: `docs/testing.md` (new, linked from `docs/index.md` and `docs/dsl.md`), `docs/exports.md` ("Net renders"), `docs/viewer.md` (subjects), `docs/cli-contract.md` (`render --net`, `result.subjects`, `build.unattached`). Proof: `uv run pytest tests/consistency -q`.
  - 2026-10-29: consistency proof passed, exit 0 (572 passed, 35 skipped). Docs distinguish implemented helpers from pending dependencies and describe subjects and model renders.
- [x] 5.3 Agent guide: a tested line for `render --net` on `checks` and for `fenolite.testing` and `build.unattached` on `design-script`; keep every reference page within 12000 bytes by splitting the existing oversized generated command reference into linked pages; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

  - 2026-10-29: agent proof passed, exit 0 (102 tests), and generator --check passed. Every packaged page is <=12000 bytes. Complete command descriptions moved into linked generated pages; the existing start page was shortened while retaining the command loop/recovery rules. The stale native guide expectation table now covers both pre-existing board-power examples; native focused proofs passed. Additional affected-area proof: 757 tests, exit 0.

## 6. Closing

- [ ] 6.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch (Linux, macOS and Windows unit jobs carry `H-G-RENDER-DETERMINISTIC`). Proof: `make check-fast`, and the required jobs green on the exact commit.
  - 2026-10-29: first check-fast finished with exit 2 (10 failed, 15305 passed, 42 skipped); no push made. Failures exposed example discovery/classification and start-page/Makefile invariants. Fixed discovery to exclude test modules, classified the new two-part PCB, retained the required guide statements and command names, and kept example execution through the unit-suite wrapper instead of changing the Makefile recipe. Focused regression proof: 93 passed (4 resource-dependent cases deselected), exit 0. Final quick gate and CI still pending.
  - 2026-10-30: intermediate quick gate exited 0 (15311 passed, 42 skipped). Review then added regressions for merged simulated-zone counts and subject indices after concise/paginated output; those 9 focused tests passed. A fresh quick gate is required for the final edits before pushing.
  - 2026-10-30: fresh final quick gate passed, exit 0 (15313 passed, 42 skipped; 928.23 s with four workers). Includes merged-zone and concise/pagination regressions. This task stays open until the required CI jobs pass on the pushed commit.
  - 2026-10-30: CI run 40910694158 on 302b3bf failed the provenance manifest check in Linux, macOS and Windows: the three authored example files were not declared. Added their authored provenance to tests/data/MANIFEST.toml; all 48 focused manifest tests passed, exit 0. The helpers and committed SVG comparison passed in those platform jobs; this does not close the required CI gate.
  - 2026-10-30: fresh quick gate after the manifest fix passed, exit 0 (15313 passed, 42 skipped, 566.85 s with four workers). Required CI remains pending on the next pushed head.
- [ ] 6.2 Evidence: register `H-G-RENDER-DETERMINISTIC` in `docs/hypotheses.md` with its measurement and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.
