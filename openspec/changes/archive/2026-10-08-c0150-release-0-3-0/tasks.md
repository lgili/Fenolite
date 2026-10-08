## 0. Entry check

- [x] 0.1 Read the release commits of `0.2.0` and `0.2.1` on `main`, `docs/release/v0.1.md` and `v0.2.md`, the living `release-gate` spec, the two guards, and `openspec list`; write here which changes of the write part of v0.3 are open. Proof: `openspec list` prints the open changes, and the list written under this task equals it.
  - 2026-10-08, on `c3e15ac3` (`dev` at `4bf0c6fb` plus c0148) and the commit of the session of 2026-10-08: open with tasks left are c0083, c0084, c0085, c0086, c0087, c0088, c0090, c0091, c0092 (no task ticked), c0121, c0123, c0124, c0125, c0126, c0130, c0131, c0132, c0138, c0139, c0142, c0143, c0144, c0146, c0147 and c0148; complete and not archived are c0127, c0128, c0134 and c0136. c0089 and c0122 are archived. No v0.3 release change or record existed before this one.

## 1. The record and its guard

- [x] 1.1 Write `docs/release/v0.3.md`: the table `## Acceptance of v0.3` with one row at least per item of the roadmap's block, each with the test whose assertions are the statement, its job and its result; `## Graduation of the Altium write` with the verdict per kind (design, decisions 2 and 3); `## Open rows`; `## Also in this package`; `## Not in 0.3.0` (decision 4); the limits, runs, manual checks, build, deferred list, steps and a verdict left `pending`. Write no test of behaviour. Proof: `uv run pytest tests/unit/test_release_record_v03.py -k consistent`.
- [x] 1.2 Write `tests/unit/test_release_record_v03.py` (requirements "Release record of v0.3" and "Version 0.3.0"). Proof: `uv run pytest tests/unit/test_release_record_v03.py tests/unit/test_release_record_v02.py tests/unit/test_release_record.py`.
  - 2026-10-08: the three guards and the README and alias checks, 76 passed.
- [x] 1.3 Run the residue scan over the history with the public gate and add the row `v0.3.0` to `docs/evidence/residue-history.md`. Proof: `uv run python tools/residue/scan.py --history` exits 0 with `0 hit(s)`; `grep -c '| v0.3.0 |' docs/evidence/residue-history.md` prints `1`.
  - 2026-10-08, at `c293a560`: 0 hits in 6821 blobs, waivers 9, private gate skipped.

## 2. README, roadmap and the id

- [x] 2.1 Rewrite the status paragraph of `README.md` for version 0.3, name the write side under `## What version 0.3 does`, and move the README checks of `tests/unit/test_agent_skill.py` to 0.3. Proof: `uv run pytest tests/unit/test_agent_skill.py`.
- [x] 2.2 Name the release change in the status lines, the row of v0.3 and Phase 4 of `docs/roadmap.md`, and add the row `c0150` to `openspec/README.md`. Proof: `uv run pytest tests/unit/test_release_record_v03.py -k roadmap tests/unit/test_release_record_v02.py -k roadmap`; `grep -c '| c0150 |' openspec/README.md` prints `1`.

## 3. Version and changelog

- [x] 3.1 Cut `CHANGELOG.md`: the entries of Unreleased go under `## [0.3.0] - 2026-10-08`, grouped under `### Added`, `### Changed` and `### Fixed`; the entries about proposals, milestone names, archived specs and the Altium reports folded into one closing entry; an empty `## [Unreleased]` above. Proof: `uv run pytest tests/unit/test_release_record_v03.py tests/unit/test_release_record_v02.py tests/unit/test_release_record.py -k changelog`.
  - 2026-10-08: 41 entries of Unreleased became 11 under `### Added` (one new entry that sums up the release), 19 under `### Changed` (one for the help text of c0136 and the closing entry) and 5 under `### Fixed`; 9 entries were folded into the closing entry. The fix of c0143 says that it is released for the 0.2 series as 0.2.2.
- [x] 3.2 Set the version to `0.3.0` in `src/fenolite/__init__.py`, and the version and the `fenolite==0.3.0` pin in `packaging/phenolite/pyproject.toml`. Do not tag and do not publish. Proof: `uv run pytest tests/unit/test_release_record_v03.py tests/unit/test_pyproject_invariants.py`; `uv run fenolite --version` prints `0.3.0`; `uv build` and `uv build packaging/phenolite` name `0.3.0`.
  - 2026-10-08: the other mentions of `0.2.1` (`git grep -n "0\.2\.1"`) are about that release and stay. The first `make check-fast` after the version failed in 6 tests of `tests/unit/backends/kicad/test_fpitems.py`: its pinned digests of the canonical text (c0126) included the header's `fenolite_version`, which `canonical.dumps` writes from the running version. The test now takes the digest with that field set back to `0.2.1`, the version it was measured with (`PINNED_VERSION`); the pinned values are unchanged. `uv run pytest tests/unit/backends/kicad/test_fpitems.py`: 17 passed.

## 4. Closing checks

- [x] 4.1 Run the closing checks. Proof: `make check-fast`; the unit suite on Python 3.11; every `tools/gen_*.py --check`; `uv run pytest tests/residue tests/corpus/test_manifest.py`; `openspec validate --all --strict --no-interactive` adds no error of this change; `uv build` of both packages; `python3 tools/dco_check.py c3e15ac..HEAD`.
  - 2026-10-08, on the commit of this change, no `kicad-cli` on the machine: `make check-fast` exit 0 (ruff and format clean, pyright 0 errors, residue 0 hits, 9908 passed, 18 skipped); the unit suite on Python 3.11, 9624 passed, 8 skipped; the three `gen_*.py --check` exit 0; `tests/residue tests/corpus/test_manifest.py` with the guards, 173 passed, 5 skipped; `openspec validate c0150-release-0-3-0 --strict` valid, and `--all --strict` reports 5 errors, all in c0084, c0085, c0086 and c0128, none in this change; `uv build` of both packages in a clean worktree reads 0.3.0; `dco_check` prints nothing.
  - 2026-10-08, later: the coordinator relayed that the maintainer approved the residue waiver of `tests/data/model/v0.2.0/blink_2layer.board.json` (c0126) on 2026-10-08; recorded in `tools/residue/scope.toml`, in c0126's tasks and under the residue limit of the record, and removed from "Not in 0.3.0" and the guard's list. The guard and the residue tests were run again after it.

_Note: the merge of `main` (with 0.2.2) into `dev`, the CI run of the release candidate, the verdict, the pull request from `dev` to `main`, the tag `v0.3.0`, the build from the tagged commit and the publication are the maintainer's actions (`docs/release/v0.3.md`, "Maintainer's steps"). The full `make check` is run once by the coordinator at the merge. The change is archived after the maintainer's verdict._
