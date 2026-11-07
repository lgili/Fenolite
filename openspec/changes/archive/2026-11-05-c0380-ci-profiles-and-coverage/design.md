## Evidence and alternatives

Public job 124811456715 took 101.48 min, of which 100.78 min was its test step. Its log spent about 30 min after 98% progress. Setup/caches are not the primary measured bottleneck. The five unit jobs took 26.65–34.63 min in that run. These are historical baselines, not promised improvements.

- Retain `--dist loadfile`: ci-baseline explicitly permits dependencies within one file. Switching to worksteal/load without proving those assumptions would be unsafe.
- Do not start with dependency-based test selection: the transitive graph across model, geometry, CLI, conversion and viewer is not proven. Fast initially runs the existing entire tool-free selection on one Linux/Python version; its static result is available separately.
- Do not move existing heavy fidelity tests to nightly: they remain full merge coverage.
- Use four independent KiCad 10 runners rather than more workers on the same runner. Assign whole files by deterministic SHA-256 modulo the shard count. Every shard collects the full baseline in the same environment first. No hand-maintained file allowlist; new tests are assigned automatically. Initial timing artifacts will inform a later measured balancing change.

## Profiles and event identity

A stdlib policy tool reads the event payload and Git refs. PRs (including drafts), merge groups, pushes to dev/main/master/release branches, unknown refs/events and any CI-control path change require full. Recognized `codex/`, `cac/`, `feature/`, `fix/`, `router-` working-branch pushes may run fast. A manual input cannot downgrade an integration ref. Missing/truncated git history, missing diff input and malformed policy inputs fail closed to full. Branch deletions must not produce a full success for a nonexistent commit. Preserve existing push coverage and backup/tag exclusions.
The repository's `cac/lote-*` batch branches retain full integration validation; that exception takes
precedence over the generic `cac/` working prefix.
Validate push before SHAs before considering the all-zero new-branch sentinel. Diff without rename
compression so both old and new paths are checked when a CI control is renamed away.

Separate `ci-fast` and `ci-complete` aggregate jobs prevent a fast green from being mistaken for merge coverage. Full aggregation checks every required job result explicitly, including the coverage audit, and refuses skipped/cancelled/missing results. CI settings must require `ci-complete` on integration PRs; this change does not silently mutate remote branch protection. CI-control changes run full even on this implementation branch.

## Selection and outcome receipts

A stdlib wrapper uses a small opt-in pytest plugin. A serial collect-only subprocess records the full node-id inventory and file identity; the wrapper computes the shard's whole-file selection. Execution validates its own collection against that selection, retains original within-file order and loadfile workers, and records terminal outcomes at the controller. Empty partitions are explicit receipts, not missing artifacts. Collection failures, mismatches, worker crashes and incomplete runs fail closed. Pytest skips remain skips in receipts; required-resource mode remains unchanged.

Each receipt identifies schema, suite, shard/count, commit, full collection, planned selection, observed terminal outcomes and process exit. Auditing requires exactly one receipt for every expected shard of every expected suite, consistent baseline inventories/commit identity, no duplicate ids, a complete disjoint partition, every selected id observed and successful execution. Timing/JUnit files are additional diagnostics, not substitutes for inventory proof. Keep artifacts even on failure, while missing artifacts fail the full gate.

Container checkout ownership may differ from the runner user. Read the actual Git HEAD using a
process-scoped `safe.directory` for this checkout only; do not change global Git configuration or
substitute an unverified environment SHA. Reproduce the ownership guard in an authored runner fixture.
Git fixtures use an empty temporary global config, disable system config and request empty templates.
A supplied safe.directory=* host config reproduced a false fixture failure; both normal and wildcard
host cases must pass without changing the supplied host file or invoking host hooks.
Remove prior receipt and JUnit files before preflight, so even a refused implicit pytest filter cannot
leave a previous successful report available for upload.

## Existing resource-unit coverage gap

The previous unit log skips missing KiCad/corpus/libs in tests/conftest.py; native job roots exclude
tests/unit. Collect-only inspection found 35 marked unit cases plus three unmarked public output-job
cases that depend on corpus. Mark those three explicitly. KiCad 10 collects the whole repository,
then retains every tests/kicad and tests/corpus item plus each entire tests/unit file containing any
needs_kicad/needs_corpus/needs_libs item. Whole-file retention preserves possible internal dependencies;
unrelated tool-free files need no duplicate native execution. Record resource markers in inventories.
Cross-audit the canonical Linux/Python 3.12 unit inventory against KiCad 10: every resource-bearing
unit file's cases must exist in the native baseline, and its resource-marked cases must pass rather
than skip. Require libs as well as kicad/corpus in that container. Keep KiCad 9's original scope and
version-specific skips. This adds coverage; it does not weaken any existing assertion or golden.

## Scope and rollout

Do not change release publication, benchmark/fidelity assertions, native versions/digests, resource requirements, corpus fetch uses or expected model bytes. Document the new full check before any integration. Validate policy downgrade attempts, new/unassigned files, missing/duplicate/tampered reports, collection drift, skipped/missing jobs and xdist/serial outcome parity using authored tiny test suites. Run one serialized local fast gate and publish full exact-head CI; keep the change open until that proof passes. Record measured outcomes rather than extrapolating a speedup.

## Files and interfaces

Create `tools/ci_profiles.py` (plan/gate), `tools/ci_tests.py` (run/audit) and `tools/ci_receipt.py` (opt-in pytest collection/outcome plugin). These are repository maintenance interfaces, not installed Fenolite commands. Add `tests/unit/test_ci_profiles.py` and `tests/unit/test_ci_execution.py`, update `.github/workflows/ci.yml`, existing workflow-shape tests, guidance and changelog. Author-controlled behavior is INFERRED until exact-head workflow execution establishes integration proof.

Platform typing is not assumed independent: Linux types run once in quality; macOS/Windows retain native pyright in their unit jobs. The configured type target is Python 3.11 on all five old jobs.

## Measured whole-file priority

The bounded local gate completed with 20,061 passed, 52 skipped and only the independently reproduced
Altium byte failure. JUnit measured authored Fenolite files: proposal_reference 1,287.099 seconds/34
cases, route_propose 575.700/22 and lower_build_spec 401.445/2. Count-based loadfile scheduling leaves
expensive small groups late. Start these three whole files first; retain original count-based order
for other files and original case order inside every file. Hints affect ordering only, never membership.

Use the existing loadfile scheduler, with worker collection grouping and `--no-loadscope-reorder`.
The option is documented for loadscope; the locked xdist 3.8.0 loadfile implementation inherits its
queue builder. Do not import or subclass private scheduler APIs. Actual one-worker regressions must
prove the hint takes effect and removing the option restores count-based scheduling. This explicit
compatibility proof must fail if a dependency update changes that inherited behavior. Serial jobs
retain their original order. The local measurement is not a controlled cross-platform speedup claim.

## Identical owner-project measurements

Run 41637238612 at 784092fe completed in 57m56s and failed the existing product/native gates.
All fourteen receipts had the exact commit, complete terminal outcomes and a disjoint 4,229-node
native union. The slowest native file was test_drawn_corpus.py: 2,897.8 seconds. Its cases repeatedly
materialize and measure the same complete owner project for different target sheets. The target id
is only a report field in measure(); the actual pipeline depends on the owner root and complete
inputs, native tool/environment, major, version and code commit. These are not independent pipelines.

Add an opt-in test-only module-scoped measurement store. Every sheet still checks its own input,
owner discovery, owner project and target-instance coverage, materializes its own disposable source
copy and reaches the unchanged strict assertion and independent report. Before lookup, hash every
declared copied input; require all hashes to match their declarations. A key binds owner/root,
manifest, input ids/relative paths/expected and actual hashes, major, native version, code commit and
the actual tool instance. Never persist the store across modules, workers, runs or commits. Retain
metadata only, never CAD bytes. Verify the copied input hashes again after measuring; a changed or
missing input cannot seed or retrieve a previous result. Missing/invalid inputs use the ordinary
strict measurement path. Do not cache internal failures. Reuse refused/different results without
turning them into success, so every affected sheet still fails.

The inherited environment and working directory also bind the key. Normalize only pytest's current
case label and explicitly isolated empty per-case state/library locations; unset or nonempty stores
disable reuse. Do not put inherited values or absolute paths in reports. Reuse-control source changes
require the full profile, including explicit manual attempts to select fast.

Return independent deep copies with the requested sheet id. Include value-free owner measurement
identity and a reused flag; original stage timings describe the original measurement, while each
row retains actual total_seconds. Keep the existing measure() unchanged for all other callers.
Authored controls must compare cached/uncached real extraction/lowering/partition reports, count
actual native-export calls, preserve repeated/shared owners and failures, reject altered or missing
libraries/project/sheets and environment identity changes, isolate returned metadata and cleanup,
and prove the actual corpus driver still emits every target-sheet report. Only timing/reuse metadata
may differ in semantic report comparisons. Full exact-head native CI must retain the prior failing
outcomes until their separate source fixes land; task 4.2 remains open while any required gate fails.

## Measured and rejected: reusing identical kicad-cli runs (2026-11-04)
A test-only wrapper of `KicadCli.run` reused the result of a call with identical binary, arguments,
environment, folders, timeout, input bytes and occurrence within its test. Local KiCad 10.0.6, six
native folders (`check`, `export`, `build`, `rules`, `sheets`, `copper`; 656 tests, `-n 6 --dist loadfile`):

| | wall | kicad-cli calls | reused | kicad-cli seconds |
|---|---|---|---|---|
| without | 540 s | 1022 | 0 | 514 |
| with | 544 s | 1022 | 113 (11 %) | 465 (49 saved) |

`kicad-cli` is about a quarter of the summed test time (514 of 1963 s): most of it is Fenolite's own
work (builds, checks of the demo boards). Reuse saved no wall time and changed two outcomes
(`test_export_probes::test_repeat[drill]`, `[gerbers]`: a session helper exports twice from two tests,
and the reused pair hid the date lines). It was not adopted; partitions remain the lever. The heaviest
sampled files were `check/test_check_demos.py` (535 s), `check/test_corpus_rt.py` (259 s) and
`build/test_layer_builds.py` (227 s).
