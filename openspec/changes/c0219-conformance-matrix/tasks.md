## 0. Entry check

- [ ] 0.1 Read `openspec/specs/cli-contract/spec.md` ("Evidence matrix in capabilities"),
  `openspec/specs/verification-evidence/spec.md`, `docs/evidence/matrix.md` and the open questions of the
  design; record the maintainer's answers under this task. Proof: `openspec validate c0219-conformance-matrix --strict`.
  - 2026-10-27: the maintainer accepted every recommended answer (roadmap, "Open decisions", row 49): `NO_CLAIM` is
    the list of Decision 4, `route` answers `INFERRED` with the `H-G-DSN-*` rows it relies on, and `UNKNOWN` comes
    only from the detection of an unknown file.

## 1. Versions in the matrix

- [x] 1.1 `VersionEvidence` and `MatrixRow.versions`; the KiCad `claims` declare the versions of the pinned oracle
  jobs with their test files (scenario "Board versions listed"). Proof:
  `uv run pytest tests/unit/cli/test_capabilities_matrix.py tests/unit/backends -q -k "matrix or claims"`.
- [x] 1.2 The Altium and Specctra `claims` declare their versions: an Altium cell names its kit run where a
  register row has a kit label, and none otherwise. Proof: as 1.1.
- [x] 1.3 `tools/gen_evidence_matrix.py`: `conformance.json`, `conformance.md` and the source check (scenario
  "A source that does not exist"). Proof: `uv run python tools/gen_evidence_matrix.py --check`;
  `uv run pytest tests/unit/test_evidence_matrix_page.py -q`.
- [x] 1.4 `release.yml` attaches `conformance.json` (scenario "The release attaches the matrix"). Proof:
  `uv run pytest tests/unit/test_ci_workflow.py -q`.

## 2. Evidence of every reply

- [ ] 2.1 `NO_CLAIM` (by the answer to open question 1), `claims` in `capabilities`, the two rules in
  `cli/output.py`, `FENOLITE_CONTRACT_CHECK` and `cli.evidence-unsound` in `fenolite explain` (scenarios "INFERRED
  without a hypothesis is caught", "A no-claim command may be UNVERIFIED"). Proof:
  `uv run pytest tests/unit/cli -q -k "evidence or capabilities or explain"`.
- [ ] 2.2 The gaps: `kit`, `view`, `analyze` and `route` give the level and the hypotheses of Decision 6 and of
  open question 2, with new register rows where needed. Proof: `uv run pytest tests/unit/cli -q -k "kit or view or analyze or route"`;
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 2.3 The consistency suite runs every example with `FENOLITE_CONTRACT_CHECK=1` (scenario "Every example
  follows the rules"); `docs/cli-contract.md` describes the rules and `versions`; the agent guide names them.
  Proof: `uv run pytest tests/consistency tests/unit/agent/test_pages.py -q`.

## 3. Closing

- [ ] 3.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [ ] 3.2 Update the evidence labels: the new rows of 2.2 at the level their tests reached; no other label
  changes. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_evidence_register.py -q`.
- [ ] 3.3 Update `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit/test_release_record.py -q`.

## Current-source preparation

- [x] 0.2 Parent reviewed the selective packet and approved isolated iteration A: typed scopes,
  existing-source validation and conformance/release generation only, without evidence upgrades.
  Historical implementation/receipts are reference material; current proofs must run again.
- [x] 0.3 Complete A authored negative controls before runtime; retain B reply/evidence work pending
  actual output census and review of remaining NO_CLAIM questions.

## Current-source A proof

- Before runtime the authored selection failed collection twice because VersionEvidence did not
  exist. After focused port: 28 matrix/generator tests pass; 46 backend claims/matrix tests pass;
  ten source/native negative controls pass; release source-copy/checksum-order control passes.
- Conformance contains 62 operation rows with 29 explicit scopes. KiCad pins match CI's immutable
  9.0.9/10.0.6 image declarations. Altium scopes require validated non-synthetic matching AD26.5
  records, current kit-labelled hypotheses and current passing native observations. Missing scopes
  remain explicit. A separate invariant proves every generic operation's evidence and experimental
  declaration is unchanged from the current original matrix.
- Guide/schema/register/release selection: 345 passed with three initial guide placement/budget
  failures. Version teaching was moved to the existing Altium page; corrected guide rerun 102 passed.
  No budget was increased. Pyright reports zero errors/warnings; strict OpenSpec and generator checks
  pass. Final root check-fast/CI remains open.
- Actual seven-command output census is external and read-only. edit/mcp NO_CLAIM disposition is
  still awaiting the maintainer; publish already supplies H-G-SNAPSHOT-STABLE. Neither B reply guard
  nor C underlying evidence fixes are included in this A checkpoint.
