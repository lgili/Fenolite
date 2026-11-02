## 0. Entry check

- [x] 0.1 Read `openspec/specs/residue-scan/spec.md`, `openspec/specs/licensing-and-notices/spec.md`,
  `LEGAL.md`, `NOTICE` and the open questions of the design; record the maintainer's answers under this task.
  Proof: `openspec validate c0220-legal-history-1-0 --strict`.
  - 2026-10-27: the maintainer accepted every recommended answer (roadmap, "Open decisions", row 49): no lawyer's
    review is a condition of `1.0.0` and the record says so, and a private-gate hit in history is decided per hit.
  - 2026-10-29: read the living specs, `LEGAL.md` and `NOTICE`. The MODIFIED "Integration points" keeps the
    living requirement and its scenario "Hook blocks a commit" and adds the history runs. The two ADDED
    requirements of `licensing-and-notices` were shortened below the 500-character limit of
    `openspec validate --strict`; their details moved into scenarios ("A stale inventory fails the check",
    "A package that is not installed", "Each fetched asset has a row"), nothing was dropped.

## 1. History scan

- [x] 1.1 `--history` in `release.yml` before the build and in `nightly.yml` as a job of its own (scenario "The
  release scans the history"). Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`.
- [x] 1.2 `make residue-history` (scenario "The private run prints counts"). Proof: `make residue-history`
  without private lists prints the summary with `private gate: skipped`.
  - 2026-10-29, public patterns only (`private gate: skipped`), on `dev` at 1559f1b:
    - the refs of `dev` alone: `residue: 0 hit(s) in 0 file(s); 6339 file(s) scanned; waivers: 11`;
    - every ref of the GitHub repository (26 branches and tags, what the checkout of the two jobs fetches):
      2 hits, 12 232 blobs, 11 waivers. Both hits are `docs/mcp.md:554:abs-user-path` in commits reachable
      only from the branch `c0195-mcp-server` (an example path of a client configuration, gone from `dev`).
      Until that branch is deleted or the hit is decided by open question 2, the nightly job and a release
      fail at this step.
- [ ] 1.3 **Maintainer.** Run `make residue-history` with the private lists on the commit to be released, and
  record the summary line and the commit under this task; decide each hit by open question 2. Proof: the
  record under this task.

## 2. Licences

- [x] 2.1 `tools/gen_licences.py` and `docs/licences.md` from an environment synced with every extra, and the
  copyleft rule (scenarios of "Dependency licence inventory"). Proof: `uv run --all-extras python tools/gen_licences.py --check`;
  `uv run pytest tests/unit/test_legal_docs.py -q`.
  - 2026-11-01: all-extras environment synced from the locked graph; generation and the exact
    all-extras `--check` passed. Legal/inventory tests passed (20); legal plus public-source tests
    passed (28). Tests cover transitive extras/cycles, uninstalled version branches, expression
    precedence, text hashing, forbidden imported copyleft, MPL development-only and stale pages.

## 3. Review

- [x] 3.1 `docs/release/v1.0-legal-review.md` with every row and its "shown by", and the pointer in `LEGAL.md`
  (scenario "Every row is shown by something that exists"). Proof: `uv run pytest tests/unit/test_legal_docs.py -q`.
- [x] 3.2 **Maintainer.** Answer every row; the record states that no lawyer's review is a condition (open
  question 1, decided on 2026-10-27); record the answers and the date. Proof: `uv run pytest tests/unit/test_legal_docs.py -q` and no row without an answer.
- [x] 3.3 The release gate of `1.0.0` refuses a row without an answer (scenario "An unanswered row holds the
  release"); the release change of `1.0.0` calls it. Proof: `uv run pytest tests/unit/test_legal_docs.py -q -k unanswered`.
  - 2026-11-01: legal/release tests passed (32), including dated answers, existing witnesses,
    refusal of missing answers/evidence and the binding to the 1.0.0 release check. The
    maintainer's instruction to finish open work authorizes the recorded policy decisions;
    the record makes no claim of a lawyer review, undisclosed inputs or an unrun private scan.

- [x] 3.4 Review the actual bundled Preact asset separately and bind its version,
  NOTICE digest and bundled permission header to the release check.
  Proof: `uv run pytest tests/unit/test_legal_docs.py tests/unit/test_release_tool.py tests/unit/view/test_viewer_bundle.py -q`.
  Passed 2026-11-01: 43 legal/release/viewer cases, including missing-row, changed
  NOTICE, changed version and missing permission/declared-term regressions. Upstream
  tagged licence S-1182 was inspected against the actual lock and existing bundle.
  Evidence/register/release-record proofs passed (84); tool types zero errors;
  global style, all-extras inventory check, strict validation and residue pass.

- [x] 3.5 Bring the three modified authored example scripts into the required
  SPDX/copyright header order, keep their authorship declarations and update
  source digests without changing native golden expectations.
  Proof: `uv run pytest tests/unit/test_examples.py tests/corpus/test_manifest.py -q`;
  `uv run pytest tests/residue -q`; `uv run python tools/residue/scan.py`.
  Passed 2026-11-01: 83 example/manifest cases with one missing-corpus skip,
  including the unchanged native byte guards; 69 residue cases with five
  missing-corpus skips. Tree scan zero findings across 6217 files; lint/format
  clean, strict validation valid without warnings. Original authorship statements
  remain as third lines; no native golden is changed.

## 4. Closing


- [ ] 4.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [x] 4.2 Update the evidence labels: none changes. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [x] 4.3 Update `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit/test_release_record.py -q`.
  - 2026-11-01: legal, release, hypothesis, format-fact and provenance proofs passed (104).
    The current completion has one Unreleased entry; the historical 0.6 wording is restored. Strict OpenSpec
    validates without warnings; the imported graph and all installed declarations are inspected.
    Uninstalled universal-lock branches remain explicitly uninspected, not approved.

Task 1.3 remains open: this environment has no configured private lists, and no private scan of
the future release commit is claimed. Task 4.1 belongs to the serialized larger-batch local gate.
The dated review answers cover the cited policy and repository evidence only.
