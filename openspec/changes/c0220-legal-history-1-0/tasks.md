## 0. Entry check

- [ ] 0.1 Read `openspec/specs/residue-scan/spec.md`, `openspec/specs/licensing-and-notices/spec.md`,
  `LEGAL.md`, `NOTICE` and the open questions of the design; record the maintainer's answers under this task.
  Proof: `openspec validate c0220-legal-history-1-0 --strict`.
  - 2026-10-27: the maintainer accepted every recommended answer (roadmap, "Open decisions", row 49): no lawyer's
    review is a condition of `1.0.0` and the record says so, and a private-gate hit in history is decided per hit.

## 1. History scan

- [ ] 1.1 `--history` in `release.yml` before the build and in `nightly.yml` as a job of its own (scenario "The
  release scans the history"). Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`.
- [ ] 1.2 `make residue-history` (scenario "The private run prints counts"). Proof: `make residue-history`
  without private lists prints the summary with `private gate: skipped`.
- [ ] 1.3 **Maintainer.** Run `make residue-history` with the private lists on the commit to be released, and
  record the summary line and the commit under this task; decide each hit by open question 2. Proof: the
  record under this task.

## 2. Licences

- [ ] 2.1 `tools/gen_licences.py` and `docs/licences.md` from an environment synced with every extra, and the
  copyleft rule (scenarios of "Dependency licence inventory"). Proof: `uv run --all-extras python tools/gen_licences.py --check`;
  `uv run pytest tests/unit/test_legal_docs.py -q`.

## 3. Review

- [ ] 3.1 `docs/release/v1.0-legal-review.md` with every row and its "shown by", and the pointer in `LEGAL.md`
  (scenario "Every row is shown by something that exists"). Proof: `uv run pytest tests/unit/test_legal_docs.py -q`.
- [ ] 3.2 **Maintainer.** Answer every row; the record states that no lawyer's review is a condition (open
  question 1, decided on 2026-10-27); record the answers and the date. Proof: `uv run pytest tests/unit/test_legal_docs.py -q` and no row without an answer.
- [ ] 3.3 The release gate of `1.0.0` refuses a row without an answer (scenario "An unanswered row holds the
  release"); the release change of `1.0.0` calls it. Proof: `uv run pytest tests/unit/test_legal_docs.py -q -k unanswered`.

## 4. Closing

- [ ] 4.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [ ] 4.2 Update the evidence labels: none changes. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 4.3 Update `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit/test_release_record.py -q`.
