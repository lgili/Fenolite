## ADDED Requirements

### Requirement: macOS application nightly job
`.github/workflows/nightly.yml` SHALL contain a job `macos-app` that runs on a schedule, once a day, and on `workflow_dispatch`, on a GitHub-hosted macOS runner, and that runs the oracle tests against the `kicad-cli` of the official KiCad 10.0.6 macOS disk image. It repeats in CI what the hypothesis register records as "confirmed with local `kicad-cli` 10.0.6 (macOS)". It is NOT a check of pull requests and NOT a merge gate.
- The disk image MUST be the release asset `kicad-unified-universal-10.0.6.dmg` of the tag `10.0.6` of `https://github.com/KiCad/kicad-source-mirror`, pinned by its SHA-256 written in the workflow as 64 hex digits. The job MUST fail before anything of the image runs when the digest of the downloaded file differs.
- The job MUST run these steps in this order:
  1. `actions/checkout@v4`
  2. `astral-sh/setup-uv`
  3. `actions/cache` of the downloaded image, keyed on the pinned SHA-256
  4. the download of the image, skipped when the cache holds it
  5. the check of its SHA-256 with `shasum -a 256 --check`
  6. `hdiutil attach` of the image, read-only and without opening a window
  7. `"$FENOLITE_KICAD_CLI" version`, with `FENOLITE_KICAD_CLI` set to the `kicad-cli` inside the mounted `KiCad.app`
  8. `uv sync --locked --extra dev`
  9. `uv run pytest tests/kicad -q -n auto --dist loadfile` with `FENOLITE_REQUIRE=kicad`
- The job MUST NOT fetch the corpus and MUST NOT run `tests/corpus`: the `kicad-10` job covers them. It MUST set `timeout-minutes`, and MUST fail if any step fails.
- KiCad is run as a subprocess from the mounted image and is never installed into, copied into or committed to the repository.
- `tests/unit/test_ci_workflow.py` SHALL check the job textually: the schedule and `workflow_dispatch` triggers, the absence of `push` and `pull_request` triggers, the asset URL, a 64-digit digest that the `shasum` step uses, the order of the steps above, `FENOLITE_REQUIRE=kicad` and the parallel options of the pytest step ("Parallel test runs").
- `H-K-CI-MACOSAPP` MUST be settled by the first runs: the image mounts, `kicad-cli` runs from the mounted volume without a display and reports `10.0.6`, and the suite passes. When the binary cannot run from the mounted volume, the fallback MUST be applied and recorded in the register row: step 6 copies the `KiCad` folder of the image to the runner's temporary folder and clears its quarantine attribute, and step 7 uses that copy. When neither runs, the job MUST be removed, and the roadmap MUST say that the macOS application stays a local oracle.
- `docs/roadmap.md` MUST name the job among the CI jobs and say that it is not a merge gate.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k macos_app` runs
- **THEN** it passes only if `nightly.yml` holds the job `macos-app` with a `schedule` trigger and `workflow_dispatch`, no `push` and no `pull_request` trigger, the asset URL of tag `10.0.6`, a 64-digit SHA-256 used by the `shasum` step, and the nine steps in order

#### Scenario: Unpinned image rejected
- **GIVEN** a `nightly.yml` whose `shasum` step is removed
- **WHEN** the same test runs
- **THEN** it fails naming the job `macos-app` and the digest check

#### Scenario: Corpus tests rejected
- **GIVEN** a `macos-app` job whose pytest step also names `tests/corpus`
- **WHEN** the same test runs
- **THEN** it fails naming the job and `tests/corpus`

#### Scenario: First nightly run
- **WHEN** the job runs on `workflow_dispatch` after the change merges
- **THEN** its log shows `kicad-cli version` reporting `10.0.6` and the `tests/kicad` suite passing, and the row of `H-K-CI-MACOSAPP` records the run's URL, or the fallback that was applied
