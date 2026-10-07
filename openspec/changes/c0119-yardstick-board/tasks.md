## 0. Entry check

- [ ] 0.1 Read the living `release-gate` and `ci-baseline` specs, `openspec list` and `openspec/changes/archive/`. Write under this task, with the date: which changes of each stage (design, Decision 3) are archived, and so the first stage the example can take; whether an open change now holds a delta of `release-gate`, or of a `ci-baseline` requirement named like the one this change adds (then the one archived second re-bases, Decision 16); whether `fenolite inspect` still exits 1 on a project folder (Decision 14); whether c0076 and c0077 are archived (Open Questions, the catalog). Proof: `openspec validate c0119-yardstick-board --strict --no-interactive` passes.

## 1. Probe and register

- [ ] 1.1 Add the rows `H-K-YARD-STAGE1` to `H-K-YARD-STAGE5`, `H-K-YARD-LIBREAD`, `H-K-YARD-HEAVY` (backend `kicad`) and `H-G-DSN-YARD` (backend `specctra`) to `docs/hypotheses.md`, level `INFERRED`, with the tests and criteria of `design.md` and the measurements of 2026-10-05 as first record. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`; `grep -cE '^\| (H-K-YARD-(STAGE[1-5]|LIBREAD|HEAVY)|H-G-DSN-YARD) ' docs/hypotheses.md` prints `8`.
- [ ] 1.2 Write `docs/evidence/yardstick.md` with its five sections (requirement "Yardstick record"): every stage `waiting` with the changes it waits for; the measurements of the design's Context under `Budgets`, as the source of the provisional values; the heavy boards and target 9 under `Not measured`; no row in `Runs` yet. Proof: `uv run pytest tests/residue tests/unit/test_repo_layout.py`.
- [ ] 1.3 With the maintainer's consent (about 155 MB): fetch the two heavy demo boards with `uv run python tools/corpus_fetch.py --uses heavy --only kicad-demo-10-0-6-pcb-06 kicad-demo-10-0-6-pcb-18`, run `fenolite inspect <board>` and `fenolite roundtrip <board> --level rt1` on each under `/usr/bin/time -l`, and write the seconds and the peak resident memory under this task and into the page. If a read fails or needs more than 8 GB, record it and apply cut 3 of the design. Proof: the four command lines and their results under this task.

## 2. The example, stage 1

- [ ] 2.1 Write `examples/yardstick/design.py` at `STAGE = 1` (design, Decisions 1, 4, 5 and 6): the sections as functions, `channel(n, x, y)` called eight times, references `n·100 + k`, the floor plan, the zones, classes, minimums and rules, the `USB2` interface, every value at the top, the CC0 header; and its row in `examples/README.md`. Proof: `FENOLITE_LIBS_CACHE=<cache> uv run fenolite build examples/yardstick/design.py --out build/yard --kicad-version 10 --dry-run --json` exits 0 with no `error` issue; `uv run pytest tests/residue`.
- [ ] 2.2 Build, fill and check the example on the local `kicad-cli` 10.0.6. Set the `creepage` minimum to the largest value, rounded down to 0.5 mm, for which `drc.kicad` reports no `creepage` violation, and write the value and the report under this task (Decision 6). Adjust the floor plan until `check`'s only error type is `unconnected_items`. Proof: `uv run fenolite check build/yard --format concise --json` shows every stage `ok` except `drc.kicad`, whose errors are `unconnected_items` only.
- [ ] 2.3 Extend `tests/unit/test_examples.py` (scenarios "Structure without a build" and "Stage and copper disagree") and write `tests/libs/test_yardstick_build.py` (`needs_libs`; scenario "Builds with the official libraries"). Proof: `uv run pytest tests/unit/test_examples.py -k yardstick`; `FENOLITE_LIBS_CACHE=<cache> uv run pytest tests/libs/test_yardstick_build.py -rA`.

## 3. The runner

- [ ] 3.1 Write `tools/yardstick.py` with `read_stage`, the stage table, `steps_for` and `peak_mib`, and the first tests of `tests/unit/test_yardstick.py` (scenarios "Stage read without running the script", "Stage without its changes", "Steps of stage 1", "Peak memory units"). Proof: `uv run pytest tests/unit/test_yardstick.py -k "stage or steps or peak"`; `uv run ruff check tools/yardstick.py`.
- [ ] 3.2 Add `run`: one child process per step, the heavy steps once per board, the measures, the acceptance rules, the skip rule after a failed `build` or `fill`, the exit codes; tests with a fake `fenolite` (scenarios "A passing run", "A DRC error other than unconnected items", "A rebuild that changes the board", "A failed build", "No kicad-cli"). Proof: `uv run pytest tests/unit/test_yardstick.py -k "passing or drc or rebuild or failed or kicad"`.
- [ ] 3.3 Add the record, the Markdown summary and `row` (scenarios "Record shape" and "Row from a record"), and the target `make yardstick`. Proof: `uv run pytest tests/unit/test_yardstick.py -k "record or row"`; `make -n yardstick`.

## 4. Budgets and the page

- [ ] 4.1 Write `tools/yardstick_budgets.toml` with `[stage1]` provisional (design, Decision 10), the budget judgement in `run`, and `rebase` (scenarios "A step over its budget", "Budgets from three runs", "No table for the stage", "Provisional budgets of stage 1"). Proof: `uv run pytest tests/unit/test_yardstick.py -k "budget or rebase"`.
- [ ] 4.2 Add the page guard (scenario "Page guard"), then run the runner once on stage 1 with the local `kicad-cli` 10.0.6 and add its record to the page's `Budgets` section, not to `Runs`. Proof: `uv run pytest tests/unit/test_yardstick.py -k page`; `FENOLITE_LIBS_CACHE=<cache> uv run python tools/yardstick.py run --out build/yardstick --record build/yardstick/record.json` exits 0.

## 5. The scheduled job

- [ ] 5.1 Add the job `yardstick` to `.github/workflows/nightly.yml` (requirement "Yardstick nightly job") and its checks to `tests/unit/test_ci_workflow.py` (scenarios "Workflow shape checked", "Unpinned image rejected", "Upload only on success rejected"); register the source of `actions/upload-artifact` in `docs/evidence/sources.md` with the next free id; name the job in `docs/roadmap.md`. Proof: `uv run pytest tests/unit/test_ci_workflow.py -k "yardstick or macos_app"`; `uv run pytest tests/unit/test_provenance.py`.
- [ ] 5.2 After the merge, run the job by `workflow_dispatch`, then on its schedule. After three runs of stage 1, run `rebase` on their records, commit the budgets with `source` naming the runs, add the rows to `Runs`, and set `H-K-YARD-STAGE1`, `H-K-YARD-LIBREAD` and `H-K-YARD-HEAVY` from them. Proof: `gh run list --workflow nightly.yml --limit 3` shows three completed runs of the job; `uv run pytest tests/unit/test_yardstick.py -k "budgets_file or page"`.

## 6. Stage 2

- [ ] 6.1 When c0100 and c0101 are archived: six copper layers with the stack-up of the design (Decision 3), `STAGE = 2`, a `[stage2]` table copied from stage 1 as provisional, and one local run. Proof: `uv run pytest tests/unit/test_examples.py -k yardstick tests/unit/test_yardstick.py -k stage_needs`; the local run of `tools/yardstick.py run` exits 0; three scheduled runs then set `H-K-YARD-STAGE2`.

## 7. Stage 3

- [ ] 7.1 When c0102, c0103 and c0104 are archived: the rounded outline, the slot under the isolator, the mounting holes as `design.hole`, the high-voltage rule area and the keep-outs, the pair's class values and rules; the creepage minimum raised to a value that only the slot meets (Decision 6). Proof: a local run exits 0, and `check` shows the stages of those changes `ok`.
- [ ] 7.2 When c0105, c0111, c0112, c0113 and c0114 are archived: the impedance target and the `impedance` step, thermal arrays with their protection, `near` rules and part heights, the net tie; `STAGE = 3`. A change still open at that date is named `waiting` or `not reached (cut: c<id>)` in the page. Proof: a local run exits 0; three scheduled runs set `H-K-YARD-STAGE3`.

## 8. Stage 4

- [ ] 8.1 When c0106 to c0110 and c0115 are archived: the steps `route-pairs` (KiCadRoutingTools, the pair and the controller's escape), `route` (Freerouting, `--timeout 3600` and tiers), `fill-routed`, `check-routed`, `net` and `analyze`; the router steps of the job; `STAGE = 4`; the ratchets from three runs. Proof: `uv run pytest tests/unit/test_ci_workflow.py -k yardstick`; three scheduled runs set `H-K-YARD-STAGE4` and `H-G-DSN-YARD` with their ratchets.

## 9. Stage 5

- [ ] 9.1 When c0061, c0064, c0065 and c0116 to c0118 are archived: the steps `export-package`, `bom` and `pnp`; `STAGE = 5`. Proof: a local run exits 0 with every artefact in the manifest; three scheduled runs set `H-K-YARD-STAGE5`.

## 10. Documentation

- [ ] 10.1 Update `examples/README.md`, `tools/README.md` (the runner, the budgets, the record) and `docs/roadmap.md` (the job; the line `library-read-speed` if the maintainer accepts it). If c0080 is archived, add one tested line to its guide page: `tools/yardstick.py run` and how to read its summary. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 11. Closing

- [ ] 11.1 Run the residue and the tests of every touched file. Proof: `make check-fast`; `uv run pytest tests/unit/test_yardstick.py tests/unit/test_examples.py tests/unit/test_ci_workflow.py -q`; `uv run python tools/residue/scan.py` exits 0; `openspec validate c0119-yardstick-board --strict --no-interactive` passes. The full `make check` is the coordinator's, once, at the merge.
- [ ] 11.2 Update the evidence labels: each `H-K-YARD-*` row and `H-G-DSN-YARD` at the level its runs reached, or what was refuted; the page's `Stages` names each stage's state. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_yardstick.py -k page`.
- [ ] 11.3 Add to `CHANGELOG.md` under Unreleased: "A yardstick example of about 370 parts (`examples/yardstick`), taken through the loop every night by `tools/yardstick.py` with time and memory budgets per step, and a record of its runs in `docs/evidence/yardstick.md`". Update `docs/roadmap.md` (row c0119). Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.

TODO(resume): `openspec validate c0119-yardstick-board --strict` has not been run on this change.
TODO(resume): re-read proposal, design, specs and these tasks against BRIEF rules 1 to 8; check that the task numbers the design cites (1.2, 1.3, 2.2, 5.1) still match, and that tasks 7.1, 7.2 and 8.1 each fit in one day.
