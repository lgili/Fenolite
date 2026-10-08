## 0. Entry check

- [ ] 0.1 Read the release change of `0.3.0` (c0150, archived) and of `0.2.2` (c0149), `docs/release/v0.3.md` and `v0.2.md`, the living `release-gate` spec, the roadmap's section of v0.4 and its Open decisions, and `openspec list`; write here which changes of v0.4 are on the base and which of them have open tasks. Proof: `openspec list` prints the open changes, and the list written under this task equals the changes of v0.4 in it.

## 1. The record and its guard

- [ ] 1.1 Write `docs/release/v0.4.md`: the table `## Verdict per change` with one row per change of v0.4, each with what it ships, the test that proves it, its job, its open tasks and its result (design, decision 2); `## Deferred to the next release` and `## Pending on the release branch` with one entry per such row; `## Follow-ups found on 2026-10-08` (decision 5); the Altium write, what is not in `0.4.0`, the runs with `TODO(coordinator)` placeholders, the limits, the build, the archive order (decision 6), the deferred list, the steps and a verdict left `pending`. Write no test of behaviour. Proof: `uv run pytest tests/unit/test_release_record_v04.py -k consistent`.
- [ ] 1.2 Write `tests/unit/test_release_record_v04.py` (requirements "Release record of v0.4", "Sections of the record of v0.4", "Version 0.4.0" and "History row and roadmap of 0.4.0"). Proof: `uv run pytest tests/unit/test_release_record_v04.py tests/unit/test_release_record_v03.py tests/unit/test_release_record_v02.py tests/unit/test_release_record.py`.
- [ ] 1.3 Run the residue scan over the history with the public gate and add the row `v0.4.0` to `docs/evidence/residue-history.md`. Proof: `uv run python tools/residue/scan.py --history` exits 0 with `0 hit(s)`; `grep -c '| v0.4.0 |' docs/evidence/residue-history.md` prints `1`.

## 2. README, roadmap and the id

- [ ] 2.1 Rewrite the status paragraph of `README.md` for version 0.4, name the v0.4 work under `## What version 0.4 does`, and move the README checks of `tests/unit/test_agent_skill.py` to 0.4. Proof: `uv run pytest tests/unit/test_agent_skill.py`.
- [ ] 2.2 Name the release change in the status lines, the row of v0.4 and its section of `docs/roadmap.md` (released as `0.4.0`, pending publication), with the line of c0141 that its task 4.3 asks for and the maintainer's decision as a row of Open decisions; add the row `c0154` to `openspec/README.md`. Proof: `uv run pytest tests/unit/test_release_record_v04.py -k roadmap tests/unit/test_adrs.py`; `grep -c '| c0154 |' openspec/README.md` prints `1`.

## 3. Version and changelog

- [ ] 3.1 Cut `CHANGELOG.md`: the entries of Unreleased go under `## [0.4.0] - 2026-10-08`, one `### Added`, `### Changed` and `### Fixed` each, no entry lost and none twice (design, decision 7); an empty `## [Unreleased]` above. Proof: `uv run pytest tests/unit/test_release_record_v04.py tests/unit/test_release_record_v03.py tests/unit/test_release_record_v02.py tests/unit/test_release_record.py -k changelog`.
- [ ] 3.2 Set the version to `0.4.0` in `src/fenolite/__init__.py`, and the version and the `fenolite==0.4.0` pin in `packaging/phenolite/pyproject.toml`, as c0150 did for `0.3.0` (the other mentions of `0.3.0` are about that release and stay). Do not tag and do not publish. Proof: `uv run pytest tests/unit/test_release_record_v04.py tests/unit/test_pyproject_invariants.py`; `uv run fenolite --version` prints `0.4.0`.

## 4. Closing checks

- [ ] 4.1 Run the closing checks. Proof: `make check-fast PYTEST_WORKERS=3`; every `tools/gen_*.py --check`; `uv run pytest tests/residue tests/corpus/test_manifest.py`; `openspec validate c0154-release-0-4-0 --strict --no-interactive` passes and `openspec validate --all --strict --no-interactive` adds no error to the known ones (c0084, c0085 twice, c0086, c0128); `python3 tools/dco_check.py 367cdf8..HEAD`.
- [ ] 4.2 The CI runs of the release branch (push and pull request) and the first run of the `yardstick` job replace the placeholders `TODO(coordinator)` of the record; the pending tasks of other changes whose proofs passed there are ticked and their rows changed. Proof: `grep -c 'TODO(coordinator)' docs/release/v0.4.md` prints `0`; `uv run pytest tests/unit/test_release_record_v04.py`.
- [ ] 4.3 The full `make check` once, on the rebased branch, before the merge (the coordinator). Proof: `make check` exits 0.

_Note: the CI runs of the release branch, the first run of the `yardstick` job, the full `make check`, the verdict, the pull request to `main`, the tag `v0.4.0`, the build from the tagged commit and the publication are the coordinator's and the maintainer's actions (`docs/release/v0.4.md`, "Maintainer's steps"). The change is archived after the maintainer's verdict, as c0150 was; the changes of v0.4 are archived later, in the order of "Archive order"._
