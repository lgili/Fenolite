## 1. Policy and proof design

- [x] 1.1 Validate the proposal and conservative event/profile policy, including malformed inputs, CI-control paths, integration refs and manual downgrade attempts. Proof: `npx -y @fission-ai/openspec validate c0380-ci-profiles-and-coverage --strict`; `uv run pytest tests/unit/test_ci_profiles.py -q`.

## 2. File-preserving partition and coverage audit

- [x] 2.1 Implement and prove collection/selection/outcome receipts and exhaustive disjoint auditing, including new files, collection failure, empty shards, xdist parity and tampering. Proof: `uv run pytest tests/unit/test_ci_execution.py -q`.

## 3. Workflow integration

- [x] 3.1 Wire profiles, one static job, full matrices, KiCad 10 shards, always-kept artifacts and distinct fail-closed aggregates without removing heavy/native/portable tests. Update old workflow shape controls to test the new contract. Proof: `uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_ci_profiles.py tests/unit/test_ci_execution.py tests/unit/test_parallel_runs.py tests/unit/test_build_byte_diagnostics.py -q`; workflow syntax validation.
- [x] 3.2 Prove actual checked-out commit identity inside a container whose user differs from checkout ownership, without global Git configuration or trusting an unverified SHA environment variable. Proof: focused runner tests with Git's different-owner simulation; remote integration remains task 4.2.
- [x] 3.3 Clear stale receipt/JUnit files before any run preflight can fail, including rejected implicit pytest options. Proof: `uv run pytest tests/unit/test_ci_execution.py -q` with planted stale outputs.
- [x] 3.4 Prove real Git diff handling for valid working pushes, new branches, missing/malformed before SHAs and renamed-away CI controls; cover all pytest configuration names and require every full workflow job in the aggregate. Proof: `uv run pytest tests/unit/test_ci_profiles.py -q` on authored temporary Git checkouts and workflow contracts.
- [x] 3.5 Close the pre-existing native-unit coverage gap: collect resource markers, include whole unit files needing KiCad/corpus/libs in KiCad 10, cross-audit them against the Linux unit inventory and require marked cases to pass. Mark the three public output-job cases as corpus-dependent. Proof: focused receipt/workflow tests, collect-only resource census and exact-head native CI; never run the full native suite locally.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): the complete test coverage audit passed on 5f46b8d7, including the native cross-audit of resource-marked unit cases; CI 41968083051 on 5f46b8d7 (cac/lote-16): every required job green, including unit on five platforms, kicad-9, kicad-10 shards 0-3, routing 9/10, viewer, mcp, wheel, complete test coverage and ci-complete.
- [x] 3.6 Prioritize measured expensive whole files without changing loadfile grouping, selected ids or within-file order. Prove the locked xdist option in actual one-worker runs, including the old count-based control. Proof: focused execution tests and exact-head CI timings; retain the baseline failure without changing its golden.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): exact-head timings recorded in `docs/ci.md` ("Exact-head integration — 2026-11-05"); CI 41968083051 on 5f46b8d7 (cac/lote-16): every required job green, including unit on five platforms, kicad-9, kicad-10 shards 0-3, routing 9/10, viewer, mcp, wheel, complete test coverage and ci-complete.
- [x] 3.7 Isolate authored Git fixtures from host/system configuration and templates. Proof: reproduce the owner-guard fixture failure with host safe.directory=*, then pass both normal/wildcard configurations and all focused controls without modifying the supplied host file.

- [x] 3.8 Reuse identical complete owner-project census measurements within a module, with hash-bound input/environment identity, post-measurement rechecks, isolated metadata copies and explicit reuse receipts. Retain every original sheet case, owner/instance check, failure and cleanup. Proof: authored real-pipeline equivalence and driver controls in `uv run pytest tests/unit/test_ci_corpus_reuse.py tests/unit/test_drawn_context.py tests/unit/test_drawn_census.py -q`; unchanged native collect-only ids. Full exact-head timings/outcome comparison remains task 4.2.

- [x] 3.9 Treat census reuse, owner discovery, pipeline and native driver changes as CI controls on working pushes and explicit manual fast requests. Proof: `uv run pytest tests/unit/test_ci_profiles.py -q`.

- [x] 3.10 Require full validation for changes to CI policy guidance and correct the historical-run availability note: the failed full run is absent; the fast probe is still available. Proof: `uv run pytest tests/unit/test_ci_profiles.py -q` and current API reads.

## 4. Documentation and validation

- [x] 4.1 Update Unreleased, workflow guidance, measured CI baseline and required-check migration. Proof: `make check-fast` (one run, bounded local worker count) and the focused checks above.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): `docs/ci.md` records the measured exact-head baseline; CHANGELOG updated.
- [x] 4.2 Publish the working branch and confirm the complete jobs plus audit on the exact final commit; record durations, failures/skips and any remaining bottleneck. Proof: full CI green on the published head. Do not close or claim complete validation while pending or failed.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): CI 41968083051 on 5f46b8d7 (cac/lote-16): every required job green, including unit on five platforms, kicad-9, kicad-10 shards 0-3, routing 9/10, viewer, mcp, wheel, complete test coverage and ci-complete; durations, skips and the remaining bottleneck are in `docs/ci.md`.

## Closing controls

- [x] 5.1 Run residue checks. Proof: `uv run pytest tests/residue -q`.
- [x] 5.2 Retain INFERRED behavior labels and record exact-commit integration evidence without claiming unmeasured speedups. Proof: review `docs/ci.md` and exact-head job receipts.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): labels stay INFERRED; `docs/ci.md` records the exact-commit receipts without claiming a speedup.
- [x] 5.3 Update CHANGELOG Unreleased. Proof: `git diff -- CHANGELOG.md`.

2026-11-03: tasks 1.1 and 2.1 proved by strict OpenSpec validation and 52 focused tests, including serial/xdist, empty partitions, collection drift and planted coverage omissions.

2026-11-03: task 3.1: 149 focused tests passed, including byte-diagnostic controls and retained serial visual/MCP jobs; actionlint 1.7.12 accepted the workflow. Full exact-head CI remains pending.

2026-11-03: first `make check-fast`: static gates passed; 20,056 passed, 52 skipped, two failures in 26m44s. The workflow-shape control was fixed and passed its focused proof. The remaining Altium byte mismatch reproduces independently on clean source commit c129adba and produces identical PCB bytes on both trees (see docs/ci.md); the recorded golden and assertion are unchanged. Task 4.1 remains open pending the final gate, and task 4.2 requires remote evidence.

2026-11-03: initial published run 41626923688 passed quality, DCO, wheel, viewer and MCP, but native wrappers hit Git's container checkout-ownership guard before collection. Task 3.2 now proves the exact failure condition and scoped fix. All 22 execution controls passed, including task 3.3 stale-output preflight. The in-progress local fast repeat was deliberately interrupted for this correction (not passed); a fresh final gate and remote run are required.

2026-11-03: task 3.4 and combined integration controls: 173 focused tests passed; actionlint and strict OpenSpec validation passed. Git fixtures cover normal/new-branch/manual diffs, missing/malformed/unavailable push SHAs and actual renamed-away controls. Pytest configuration precedence and exhaustive full-job aggregation are covered. The final broad local gate is still running; full exact-head CI remains required.

2026-11-03: task 3.5 local proof: 184 focused tests passed, including actual serial/xdist native-unit inventories, independent omissions/skips and the five documentation-view tests. Collect-only native inventory retained all 4,051 original native ids and added 178 cases from seven unit files, including 38 resource-marked cases. Ruff, actionlint and strict OpenSpec validation passed. Actual native outcomes and full exact-head validation remain pending; no full native suite ran locally.

2026-11-03: task 3.6 local proof: 187 focused tests passed. Actual loadfile execution proves early whole-file ordering, the count-based control without the option, complete membership, original within-file state and unchanged serial order. Ruff, actionlint and strict OpenSpec passed. The bounded legacy local repeat completed in 31m08s with 20,061 passed, 52 skipped and only the same independently reproduced Altium byte failure; the final instrumented fast run and exact-head CI remain pending.

2026-11-03: live fast-profile run 41633688434 emitted no ci-complete check; GitHub left the skipped name expression unevaluated. Executed full aggregate ci-complete failed in run 41631213107 after cancellation, proving the unsuccessful-dependency path. Preserve full validation on cac/lote-* integration batches; all 62 policy controls passed, including push/manual attempts to downgrade batches 12 and 13. Full exact-head validation is still pending.

2026-11-03: final combined focused proof after CAC batch policy: 189 passed. Actionlint and diff checks passed. The instrumented local fast selection and GitHub full/fast runs remain in progress; no validation failure or missing required check is waived.

2026-11-03: task 3.7: a supplied wildcard global Git config reproduced the old fixture failure; 94 execution/policy controls then passed under that host configuration, including explicit normal/wildcard cases and unchanged host config. The final focused bundle passed 265 tests (190 CI/diagnostic/view controls plus all 75 residue tests). Ruff, format, actionlint and strict OpenSpec passed. The measured fast receipt for 8614faf2 recorded 20,090 passed, 51 test skips (plus one collection skip) and the existing Altium byte failure in 18m31s. JUnit comparison removes only the three cases moved to native coverage and adds 32 CI controls. Full final-head/native validation is still pending; the change remains open.

2026-11-03: pre-reuse full run 41637238612 completed at 784092fe in 57m56s; all fourteen exact-head receipts and the complete disjoint native union were present. Product/native failures and five nonpassing required resource cases correctly failed the audit and aggregate. The source-identical fast probe 41637958755 passed and remains available. The failed full-run endpoint later returned 404; captured evidence remains archived outside the repository. Do not infer a passing complete gate from absent remote history.

2026-11-03: tasks 3.8/3.9: 123 focused reuse/census/context/policy controls passed, including 66 policy controls and real extraction/lowering with counted native stubs. The broader integration bundle passed 245 controls before the final unlisted-input guard, which passed its focused repeat. Collect-only inventory matched all 4,229 previous native ids, order and resource metadata exactly. Three focused native cases sch-106/107/108 retained their complete semantic reports and all strict refusals; summed case time was 50.970s before and 20.746s after, with two disclosed reuses. This is not full-suite native validation. Static gates and strict OpenSpec passed; final local fast and exact-head CI are required and remain open.

2026-11-04 (root), found by the first complete native run on lote-14 (CI 41945588359, aa49b069): task 3.5's
cross-audit failed on five resource-marked unit cases in two files that had never run with the KiCad
libraries in CI.
- `test_pages_kicad.py::test_kicad_table_names_every_design_block`: the c0340 guide page `board-practice`
  had no `ERRORS` row. Its script checks clean with kicad-cli 10.0.6, and the row is now `set()`.
- `test_altium_rta2.py`: two failed and two skipped cases. The Altium lens flattened a second time, without
  parents, a derived library symbol that `LibraryResolver.symbol` had already given its root's body, so
  every official KiCad 10.0.6 symbol defined by `extends` was refused with `altium.symbol-off-grid`.
  `resolve_symbols` now clears `extends` on what the resolver returns. The authored regression is
  `tests/unit/lens/test_altium_derived_symbol.py`. Locally with the 10.0.6 libraries, all 103 rta2 cases
  pass with no skip.
Tasks 3.5, 3.6, 4.1, 4.2 and 5.2 close on the exact-head CI of the batch that carries these fixes.

