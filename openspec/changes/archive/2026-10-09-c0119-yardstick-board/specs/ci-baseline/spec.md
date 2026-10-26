## ADDED Requirements

### Requirement: Yardstick nightly job
`.github/workflows/nightly.yml` SHALL contain a job `yardstick` that runs `tools/yardstick.py run` on `examples/yardstick` (release-gate, "Yardstick runner") on the workflow's `schedule` and on `workflow_dispatch`. It is NOT a check of pull requests and NOT a merge gate (change c0119).
- It MUST run on `ubuntu-latest` inside the image `kicad/kicad:10.0.6` pinned by the same SHA-256 as the `kicad-10` job of `ci.yml`, with the container option `--user 0`, and MUST set `timeout-minutes`.
- It MUST run these steps in this order:
  1. `actions/checkout@v4`
  2. `astral-sh/setup-uv` with Python 3.12
  3. `uv sync --locked --extra dev`
  4. `kicad-cli version`, failing unless it prints `10.0.6`
  5. `actions/cache` of the official library cache, keyed on the pin of tag 10.0.6, then `uv run python tools/kicad_libs_fetch.py --tag 10.0.6 --cache <folder>`
  6. `actions/cache` of the corpus rows of the two heavy demo boards, keyed on the hash of `tests/corpus/manifest.toml`, then `uv run python tools/corpus_fetch.py --uses heavy --only` with the two board ids
  7. from stage 4 of the example on, Java 25, the Freerouting jar of `freerouting.PINNED_VERSION` and KiCadRoutingTools at `routingtools.PINNED_TAG`, installed and checked by SHA-256 as the `routing` job of `ci.yml` installs them
  8. `uv run python tools/yardstick.py run` with `--out` and `--record` under `$RUNNER_TEMP`, `--summary "$GITHUB_STEP_SUMMARY"`, and `FENOLITE_LIBS_CACHE` set to the folder of step 5
  9. `actions/upload-artifact@v4` of the record and the replies, with `if: always()` and `retention-days: 90`
- The job MUST fail when the runner exits non-zero. It MUST NOT run `pytest`, and MUST NOT write to the repository.
- `tests/unit/test_ci_workflow.py` SHALL check the job textually: the job exists in `nightly.yml` and in no other workflow; the image digest equals that of `kicad-10`; the order of the steps; `--tag 10.0.6`; the `--only` filters of the heavy fetch; the upload step with `if: always()`; and, once the example reaches stage 4, the router steps with their digests.
- `docs/roadmap.md` MUST name the job among the CI jobs and say that it is not a merge gate.

#### Scenario: Workflow shape checked
- **WHEN** `uv run pytest tests/unit/test_ci_workflow.py -k yardstick` runs
- **THEN** it passes only if `nightly.yml` holds the job `yardstick` in the pinned 10.0.6 image with the nine steps in order, and no workflow triggered by `push` or `pull_request` holds it

#### Scenario: Unpinned image rejected
- **GIVEN** a `nightly.yml` whose `yardstick` job names `kicad/kicad:10.0.6` without a digest
- **WHEN** the same test runs
- **THEN** it fails naming the job `yardstick` and the image

#### Scenario: Upload only on success rejected
- **GIVEN** a `yardstick` job whose upload step has no `if: always()`
- **WHEN** the same test runs
- **THEN** it fails naming the upload step

#### Scenario: First run by hand
- **WHEN** the job runs on `workflow_dispatch` after the change merges
- **THEN** its log shows `kicad-cli version` printing `10.0.6` and the runner's verdict, the run's artefact holds the record, and a row of `docs/evidence/yardstick.md` names the run
