# CI profiles and coverage

CI separates feedback during development from the complete proof required before integration.
`ci-fast` is never a substitute for `ci-complete`. Nightly runs remain additional evidence, not a
substitute for either. This change is c0380; its authored policy/coverage controls are **INFERRED**.

## Choosing a profile

| Event or ref | Profile |
|---|---|
| Every PR, including drafts; merge queue (`merge_group`) | full |
| `dev`, `main`, `master`, `release/*`, `releases/*`, `cac/lote-*` batch branches | full |
| A change to workflows, CI tools/tests, dependency/build/pytest configuration, agent workflow guidance or conftest files | full |
| Unknown branch/event, unavailable diff/history, malformed event | full |
| Push to `codex/*`, `cac/*`, `feature/*`, `fix/*`, `router-*` with a known non-control diff | fast |
| Manual run | full by default; explicit fast only for a working ref with a known non-control diff |

The original push scope is retained: all branches except `backup/**`, no tag pushes. The release
workflow still handles tags. Branch deletions cannot produce a successful validation. Repository
maintainers can run a full profile explicitly before opening a PR. Once this workflow is on the
repository's default branch, Actions supports the profile input, for example:

```sh
gh workflow run ci.yml --ref codex/example -f profile=full
```

A first push containing CI-control changes runs full automatically. A missing diff never means
"nothing changed". New branches compare their merge base with `origin/dev`; absence of that base
selects full. A manual input cannot downgrade integration refs. Both profiles use locked environments.
Push before SHAs must be valid; only a valid all-zero SHA means a new branch. Renamed-away CI
controls still force full: both sides of each rename are checked. All pytest configuration formats,
including `pytest.toml`/`.pytest.toml`, and root conftest files are controls as well.

## What is retained

Fast runs the **light tool-free selection** (`tests/unit`, `tests/residue`, `tests/consistency`,
`tests/fidelity`, excluding `needs_kicad`, `needs_corpus`, `needs_libs` and whole `long_flow` files) on three Linux/Python 3.13 runners, plus shared
static checks and DCO. Light partitions run concurrently with static checks; the final gate still requires both. All three whole-file partitions must have complete, disjoint exact-commit receipts; the light coverage audit is required by `ci-fast`. This is intentionally conservative: there is no guessed dependency map or
hand-maintained list of affected tests. It may still take minutes; the independent static result is
available first. A source-path impact selector is deferred until its dependency coverage can be proved.

Full retains the five unit combinations (Linux 3.11/3.12/3.13; macOS/Windows 3.12), all old unit collection
ids including declared skips, KiCad 9, all KiCad 10 oracle/corpus tests, `FENOLITE_HEAVY=1`, original
required-resource settings, routing against both majors, visual tests, official MCP client, wheel
installation and DCO. Images, router pins, corpus fetch uses, comparison assertions and expected bytes
are unchanged. The explicitly diagnostic Mac preprobe remains; it does not waive the full unit job.
Platform-independent lint, format, generated-guide checks and current-tree residue checks run once
in `quality` and are required by both aggregates. Linux type checking also runs there once; native
macOS and Windows type checks remain in their unit jobs. Pyright targets Python 3.11 explicitly in
pyproject.toml, so the three Linux runtime versions need no duplicate type invocation.

Routing stays serial within each native-major job: external routers have their own thread policies.
Visual and MCP jobs also retain their original serial execution. Unit, fast and KiCad jobs use
`-n auto --dist loadfile`. We do not switch to worksteal/load: the
suite permits within-file dependencies and has not proved a different scheduling contract.

Three measured expensive files start early in parallel CI: `test_proposal_reference.py`,
`test_route_propose.py` and `test_lower_build_spec.py`. The bounded local repeat measured 1,287.099,
575.700 and 401.445 seconds respectively across 34, 22 and two cases. Starting solely by case count
leaves expensive small groups late. These are authored Fenolite tests; hints change ordering only.
Other files retain count-based scheduling and every file retains original case order. Serial jobs
retain their original collection order.

CI uses `--no-loadscope-reorder` with the locked xdist 3.8.0 loadfile scheduler. Upstream documents the
option for loadscope; loadfile currently inherits that queue builder. An actual one-worker control
proves both the early scheduling and that removing the option restores case-count order. This proof
must protect dependency updates; no private scheduler API is imported or replaced. This is not a
controlled speedup measurement. See the [upstream option](https://pytest-xdist.readthedocs.io/en/stable/changelog.html#pytest-xdist-3-8-0-2025-06-30).

## Four KiCad 10 partitions

Every partition first collects the configured repository in its native container. It retains all
`tests/kicad` and `tests/corpus` items and whole unit files containing `needs_kicad`, `needs_corpus` or
`needs_libs` cases. This closes an existing gap: these unit cases could skip in the portable jobs and
were outside the old native job roots. Libraries are now required alongside KiCad and corpus.
Unrelated tool-free unit files are excluded from duplicate native execution. A stable SHA-256 of the
repo-relative POSIX file path assigns each retained whole file to one of
four independent runners. Each execution validates its own collection and original within-file order
against the plan before running. Unsharded suites retain their compact original root arguments,
including on Windows, rather than passing thousands of file paths on the command line. New tests/files are assigned automatically; there is no exclusion
allowlist and no manual census row to update for selection.

The initial distribution is deliberately simple, not claimed optimal. A single slow file cannot be
split without auditing its internal dependencies. `--durations=30`, JUnit XML and collection/execution
timers provide evidence for a later balancing change rather than inventing weights from private data.

## Receipts and failure behavior

The drawn corpus still collects and asserts every declared sheet, but its complete owner-project
pipeline can be identical for many sheets. An opt-in module-scoped store reuses that measurement
only after hashing every currently copied input. Its key binds owner/root, manifest, complete
input ids/paths/declared and actual hashes, code commit, native major/version, actual tool instance
and configuration, working directory and inherited environment. Every sheet retains its own hash
check, all owner/instance checks, fresh disposable source copy and independent strict report.
Copied sources are deleted after each case, including cache hits and failures. The store retains
only metadata, never CAD bytes, and does not survive a module, worker or run.

Only pytest's current-case label and explicitly isolated empty per-case state/library locations
are normalized in the environment identity. An unset or nonempty state/library location disables
reuse. All other inherited environment values participate in a digest; none is retained in reports.
Copied inputs and execution identity are checked again after measuring. A changed measurement
fails and cannot seed reuse. Internal errors are not cached; refusals and connectivity differences
remain strict failures for every affected sheet. Each context report includes a value-free
`measurement` with owner id, fingerprint and `reused`; `seconds`/stage timings still describe the
original measurement, while the sheet's `total_seconds` is its actual elapsed time. Report copies
are independent. Changes to discovery, pipeline, reuse or its native driver force full CI.

`tools/ci_tests.py run --suite NAME --out DIR` writes a collection, plan, terminal-outcome receipt and
JUnit XML (except a genuinely empty partition, which has an explicit empty receipt). Every receipt
identifies its suite, shard/count, exact git commit, complete baseline and selected node ids. The pytest
plugin is opt-in to this wrapper and does not affect ordinary local pytest runs. Existing skips stay
visible; required-resource mode still converts missing required tools/corpus to failures.

The wrapper refuses implicit `PYTEST_ADDOPTS` overrides, including `-k`, `--lf` or `--ignore` filters
that could otherwise shrink both the baseline and execution inventories. Tracked pytest configuration
remains part of the reviewed CI-control diff.

Only top-level receipt/JUnit files are uploaded as `ci-tests-*`. Temporary fixtures may contain fake
receipts for negative tests and must not be uploaded into the audit input. Receipts/timings are retained for 14 days. Re-running a job replaces only its own named artifact;
receipts from another commit never satisfy the audit. Failure artifacts are kept;
a failed collection, interrupted process or crashed worker cannot reuse an old successful receipt.

`tools/ci_tests.py audit DIR --commit SHA` requires exactly fourteen full receipts: five unit, four
KiCad 10, one KiCad 9, two routing, one viewer and one MCP. It rejects a missing/duplicate/unexpected
suite or shard, changed baseline, wrong commit/count/assignment, missing or extra test outcome, failed
execution and incomplete/overlapping union. Passing job status without complete receipts is not enough.
The authored controls plant those failures and exercise actual serial/xdist runs and empty shards.
Resource markers in the independent Linux/Python 3.12 unit inventory also require each resource-bearing
unit file in the KiCad 10 baseline. Its marked cases must pass in native execution; a native skip cannot
silently satisfy this proof. Authored controls plant a consistently omitted whole file, an omitted
unmarked prerequisite, missing resource metadata and a resource case skipped in otherwise valid shards.
Container commit identification uses the actual checked-out Git HEAD with a checkout-specific,
process-scoped ownership exception. It neither changes global Git configuration nor trusts the SHA
environment variable as a substitute. Receipts and JUnit files are cleared before preflight failures.
Authored temporary Git fixtures isolate global/system config and templates; the normal and supplied
wildcard-trust cases are tested without changing the supplied host configuration.

## Merge check migration

Configure integration branch protection/rulesets to require **`ci-complete`**, not `ci-fast`. This
branch adds the checks but does not change GitHub settings or merge itself. Verify the configured
required check before adopting the new workflow as the integration policy. Existing individual native
and portability checks may also remain required; update names when KiCad 10 becomes a matrix.

The full aggregate explicitly requires success from plan, quality, DCO, every full test matrix, wheel
and coverage audit. A contract test rejects a new full workflow job omitted from the aggregate.
Skipped/cancelled/missing dependencies fail it. If plan fails or its output is
missing, the complete gate runs and fails. A legitimate fast run skips the dynamically named full
aggregate without emitting a `ci-complete` check. GitHub displays the unevaluated expression on that
skipped job; the isolated live fast-profile probe confirmed that `ci-complete` is absent. An executed
full aggregate resolves to the stable `ci-complete` name, including the observed failed/cancelled
full run. PRs always select full. There are no workflow-level path filters that would leave
the required PR workflow pending. Full pushes and PRs have separate concurrency groups because they
may test different commits (branch head versus PR merge commit); obsolete runs within one group cancel.

## Timing evidence and rollout status

Public successful runs measured before this change:

| Run | KiCad 10 job | Routing jobs | Unit matrix jobs |
|---|---|---|---|
| [41294183261](https://github.com/lgili/Fenolite/actions/runs/41294183261), 2026-11-01 | 101.48 min (100.78 test execution) | 28.22 / 35.88 min | 26.65–34.63 min |
| [40987149835](https://github.com/lgili/Fenolite/actions/runs/40987149835), 2026-10-30 | 93.58 min | 29.25 / 31.60 min | 8.83–16.20 min |
| [40951865684](https://github.com/lgili/Fenolite/actions/runs/40951865684), 2026-10-29 | 84.12 min | 22.82 / 31.72 min | 13.82–26.97 min |

These are different commits, not a controlled A/B benchmark. The primary measured delay is execution,
not cache installation. Separate runners can reduce elapsed time while increasing runner-minutes;
shards can queue under account concurrency limits. No fixed speedup is promised. Exact-head full CI
and its coverage audit remain required rollout proof; record that run and its actual timing before
closing c0380. A failing baseline or unrelated portability issue is not waived by a faster workflow.

Local validation on 2026-11-03: static gates passed and 149 focused CI/diagnostic controls passed.
The first bounded `make check-fast` finished in 26m44s with 20,056 passed, 52 skipped and two failures:
the workflow-shape assertion was updated and its focused proof passed; the Altium byte guard for
`board_40parts@altium` also fails on the clean source commit `c129adba`. Both source and CI branch
produce PCB SHA-256 `01fdc8486cd05e964850311b2e473487759ee11f81891da0bfe43220f8698911`,
against recorded `7f49a78f2726633ab31fbe956a187bbd85fee9af8878d42710f10a5930adc6a1` on this
macOS ARM/Python 3.13 environment. This is an open validation failure, not an updated golden or a waiver.
The local tail also involved the Altium whole-example lowering file; collected per-test timings will
determine whether a separately proved decomposition is worthwhile.
The first remote run passed quality, DCO, wheel, viewer and MCP, but exposed Git's checkout ownership
guard in native containers. A focused ownership-simulation proof now covers the fix; remote validation
must be repeated. The local repeat was interrupted to apply that correction and is not passing proof.
The subsequent collection-only resource audit found 38 required unit cases in seven files, including
three public output-job cases now explicitly marked as corpus-dependent. The native baseline retains
all 4,051 original native ids plus 178 unit cases (whole files, including unmarked prerequisites).
This census is collection evidence only; the 38 resource cases still require successful native CI.
The bounded local repeat finished with 20,061 passed, 52 skipped and the same pre-existing Altium byte
failure in 31m08s. Its JUnit measurements identified the three ordering hints above. Shared local load
and different commits make this unsuitable for a controlled speedup claim. The final exact-head CI
and the instrumented fast selection still provide the integration proof for the priority change.
The instrumented local fast selection subsequently completed in 18m31s with 20,090 passed, 52 skipped
and only that same Altium byte failure. Comparing JUnit inventories removed only the three output-job
cases explicitly moved to required native coverage and added 32 CI controls. This is an observed local
reduction, not a controlled benchmark or proof that the complete workflow passes. Its receipt identifies
source commit `8614faf2`; later policy/test-fixture changes still need final-head CI.

References: [GitHub status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks),
[pytest-xdist distribution](https://pytest-xdist.readthedocs.io/en/stable/distribution.html),
[pytest output and JUnit](https://docs.pytest.org/en/stable/how-to/output.html).

The final pre-reuse full run 41637238612 at `784092fe` completed in 57m56s. All fourteen receipts
matched that commit, every planned id had an outcome, and the four native partitions covered all
4,229 ids without overlap. The aggregate correctly failed: product/native failures remained, and
the 38 required resource-unit cases had 33 passes, three failures and two skips. The isolated fast
probe 41637958755 had an identical source tree and passed 20,093 cases in a 47m13s workflow; it did
not emit a complete check. The failed full-run endpoint later returned HTTP 404; the successful
fast probe remains available. Captured reports and JUnit files were retained outside the repository,
rather than treating absent runs as passing.

That full run measured 2,897.8s in `test_drawn_corpus.py` alone. A focused local comparison of public
rows sch-106/107/108 at source base `c129adba` and the reuse implementation retained all three
strict refusals and identical complete semantic reports. Summed case time was 50.970s before and
20.746s after; the first measurement took 20.601s and the next sheets reused it in about 0.073s
each. Authored controls exercise real extraction/lowering with stubbed native partitions and
changed/missing inputs. This is a three-case local measurement, not a full CI speedup or a passing
product gate. Exact-head CI and full-suite outcome comparison remain required.

## Light working pushes (c0381)

The maintainer selected a 5–10 minute target. Fast excludes eleven measured whole-file board flows (proposal, route, copper, lowering, kit, import and view) with `long_flow`, while retaining consistency, fidelity, residue and light unit tests. Full retains every case and all five runtime environments. Every test-file change now forces full, preventing classification edits from validating only the smaller selection. Local `make check-fast` still runs the entire tool-free selection. Times vary between hosted runners; live measurement is required before claiming the target. Integration refs and every PR still require ci-complete.
