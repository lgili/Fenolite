## 0. Entry check

- [x] 0.1 Read the release change of `0.4.0` (c0154, archived), `docs/release/v0.4.md` and its guard, the living `release-gate` spec, the roadmap's rows of v0.5a and its Open decisions (rows 38 to 42), and `openspec list`; write here which changes of the release are on the base and which of them have open tasks. Proof: `openspec list` prints the open changes, and the list written under this task equals the changes of the release in it.
  - 2026-10-15, on `5b86b6e` (`origin/dev`): open folders c0081 (13/15), c0092 (13/16), c0105 (24/25), c0146 (11/12), c0159 (16/18), c0160 (20/23), c0161 (14/18), c0162 (15/17), c0166 (34/45), c0167 (16/18), c0168 (0/19), c0169 (13/14), c0170 (0/14). Archived after `0.4.0` with every task ticked: c0155, c0156, c0157, c0158, c0163, c0164 `native-altium-template`; with open tasks: c0164 `altium-schematic-layout` (3.2, 3.3) and c0165 (4.1), the gates of their merge. Of these, c0168 and c0170 are not in `0.5.0` (the maintainer's decision of 2026-10-15), and c0081, c0105 and c0146 are open changes of earlier releases. No c0171 exists on `dev` or on any `origin/codex/*` branch.

## 1. CI evidence

- [x] 1.1 Make `tools/corpus_fetch.py` ask again after HTTP 429 and 500, 502, 503 and 504 (the server's `Retry-After`, else a doubling pause from 5 s, at most 120 s, six attempts), so the `kicad-10` job does not lose rows to a rate limit when its cache key changes (runs 38758153887 and 38767993162). Proof: `uv run pytest tests/corpus/test_manifest.py -q`.
  - 2026-10-15: `download_with_retry` with an injectable download and sleep; `test_fetch_asks_again_after_a_rate_limit`; `uv run pytest tests/corpus/test_manifest.py -q`: 48 passed.
- [ ] 1.2 Read the CI runs of `dev` (`5b86b6e`, `a496312`, `e6c42a8`) and of the release branch; tick each task of another change whose proof a green run on the current tree covers, citing the run, and diagnose and fix a failure. Proof: every ticked task cites a run whose jobs named by its proof passed; `uv run pytest tests/unit/test_release_record_v05.py`.

## 2. The record and its guard

- [ ] 2.1 Write `docs/release/v0.5.md`: `## Verdict per change` with one row per change of the release (design, decisions 2 and 3); `## Deferred to the next release`, `## Pending on the release branch` and `## Open changes of earlier releases` with one entry per such row or change; the Altium write, what is not in `0.5.0`, the runs with `TODO(coordinator)` placeholders, the limits, the build, the archive order, the deferred list, the steps and a verdict left `pending`. Proof: `uv run pytest tests/unit/test_release_record_v05.py -k consistent`.
- [ ] 2.2 Write `tests/unit/test_release_record_v05.py` (requirements "Release record of v0.5", "Open tasks in the record of v0.5", "Sections of the record of v0.5", "Version 0.5.0" and "History row and roadmap of 0.5.0"). Proof: `uv run pytest tests/unit/test_release_record_v05.py tests/unit/test_release_record_v04.py tests/unit/test_release_record_v03.py tests/unit/test_release_record_v02.py tests/unit/test_release_record.py`.
- [ ] 2.3 Run the residue scan over the history with the public gate and add the row `v0.5.0` to `docs/evidence/residue-history.md`. Proof: `uv run python tools/residue/scan.py --history` exits 0 with `0 hit(s)`; `grep -c '| v0.5.0 |' docs/evidence/residue-history.md` prints `1`.

## 3. README, roadmap and the id

- [ ] 3.1 Rewrite the status paragraph of `README.md` for version 0.5, name the v0.5 work under `## What version 0.5 does`, and move the README checks of `tests/unit/test_agent_skill.py` to 0.5. Proof: `uv run pytest tests/unit/test_agent_skill.py`.
- [ ] 3.2 Name the release change in the status lines, the row of v0.5a and its section of `docs/roadmap.md` (released as `0.5.0`, pending publication); add the row `c0171` to `openspec/README.md`. Proof: `uv run pytest tests/unit/test_release_record_v05.py -k roadmap tests/unit/test_adrs.py`; `grep -c '| c0171 |' openspec/README.md` prints `1`.

## 4. Version and changelog

- [ ] 4.1 Cut `CHANGELOG.md`: the entries of Unreleased go under `## [0.5.0] - 2026-10-15`, one `### Added`, `### Changed` and `### Fixed` each, no entry lost and none twice (design, decision 7); an empty `## [Unreleased]` above. Proof: `uv run pytest tests/unit/test_release_record_v05.py tests/unit/test_release_record_v04.py tests/unit/test_release_record_v03.py tests/unit/test_release_record_v02.py tests/unit/test_release_record.py -k changelog`.
- [ ] 4.2 Set the version to `0.5.0` in `src/fenolite/__init__.py`, and the version and the `fenolite==0.5.0` pin in `packaging/phenolite/pyproject.toml`, as c0154 did for `0.4.0`. Do not tag and do not publish. Proof: `uv run pytest tests/unit/test_release_record_v05.py tests/unit/test_pyproject_invariants.py`; `uv run fenolite --version` prints `0.5.0`.

## 5. Archive

- [ ] 5.1 Archive each change of the release whose tasks are all ticked and whose archive order allows it, one commit each; write the order of the rest into the record. Proof: `openspec validate --all --strict --no-interactive` reports 0 errors after each archive.

## 6. Closing checks

- [ ] 6.1 Run the closing checks. Proof: `make check-fast PYTEST_WORKERS=3`; every `tools/gen_*.py --check`; `uv run pytest tests/residue tests/corpus/test_manifest.py`; `openspec validate --all --strict --no-interactive` reports no error; `python3 tools/dco_check.py 5b86b6e..HEAD`.
- [ ] 6.2 The CI runs of the release branch replace the placeholders `TODO(coordinator)` of the record; the pending tasks of other changes whose proofs passed there are ticked and their rows changed. Proof: `grep -c 'TODO(coordinator)' docs/release/v0.5.md` prints `0`; `uv run pytest tests/unit/test_release_record_v05.py`.
- [ ] 6.3 The full `make check` once, on the rebased branch, before the merge (the coordinator). Proof: `make check` exits 0.

_Note: the CI runs of the release branch, the full `make check`, the verdict, the pull request to `main`, the tag `v0.5.0`, the build from the tagged commit and the publication are the coordinator's and the maintainer's actions (`docs/release/v0.5.md`, "Maintainer's steps"). The change is archived after the maintainer's verdict, as c0154 was._
