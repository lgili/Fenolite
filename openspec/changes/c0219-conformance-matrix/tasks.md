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

- [x] 0.4 Parent approved current underlying evidence derivation: view combines actual scene level
  with existing real view hypothesis, kit uses actual passing verdict IDs, analysis lowering remains;
  DirectRouter never receives DSN hypotheses. Route's mechanical-only authored hypothesis requires
  its own negative controls before runtime. NO_CLAIM question remains separate.

- [x] 2.2a Preserve actual view/source lowest-wins evidence with the existing H-G-VIEW-SCENE;
  add actual passed verdict hypotheses to kit verify/record and retain synthetic/failed lowering.
  Proof: six authored controls failed before runtime and pass after; complete view command component
  33 passed. Source-level planted UNKNOWN/UNVERIFIED controls explicitly disable caching so each
  asserted source level is actually evaluated; no input is written.
- [x] 2.2b Implement/prove route mechanical-scope inference without attributing DSN to DirectRouter,
  and preserve analysis incomplete/unsupported lowering; main 2.2 remains open until both pass.

- View/kit checkpoint: six authored controls pass; corrected complete view component 33 pass;
  agent guide 102 pass; staged private residue zero hits across eight files. Initial combined
  view/kit run started before the cache-disabled authored correction and retains its two initial
  source-cache failures in the external log; no complete green kit run is claimed until it finishes.
  Root check-fast/CI and final types remain separate gates.

- Route/analysis checkpoint: 119 affected command tests pass; 11 authored provenance/unsupported
  controls pass. Four earlier successful-route expectations now explicitly require mechanical
  inference and its actual hypothesis; external-session positive also requires its existing DSN ID.
  Analysis incomplete/unsupported results remain UNVERIFIED; no analysis result was promoted.
- Corrected guide 103 passed, corrected hypothesis/evidence registers 43 passed. Initial register
  placement outside its table and a prohibited hypothesis ID in guide prose were caught and fixed;
  original failures remain in external logs. Guide budgets/style guards were not weakened.
  Whole task 2.2 and root check-fast/CI remain open until their full exact-candidate selection passes.

- [x] 2.2c Reconcile combined-source guards after actual view-context and route-scope integration: retain the exact mock keyword context, explicit named route hypothesis, and mechanical-only plain route expectation. Keep original low-evidence/source-immutability and native-gate assertions. Proof: full affected view/gate/route/hypothesis components,52 passed (2026-11-03).
- [x] 0.5 Parent approved B's formal amendment before runtime: closed incomplete-state-plus-issue
  receipts and exact hidden `_echo` fixture exemption, with planted negatives; public NO_CLAIM
  remains the original ten and edit/mcp require the maintainer's separate pending decision.
- [x] 2.1a Implement/prove strict/production evidence framework before staging and replay, original
  public NO_CLAIM, exact hidden fixture exemption and closed incomplete receipts. Do not claim full
  strict examples green while real edit/mcp decision is missing.

## B current-source focused proof (public decision still pending)

- Framework: 55 authored controls pass, including exact hidden fixture bounds, no stage/target writes
  on unsound computation or replay, strict and ordinary modes, UNKNOWN detection, named experimental
  modes, and state-plus-issue receipts with planted false/missing/completed controls.
- Current pick bounded fix: an actual selected UNKNOWN item remains UNKNOWN in its row while its
  known-file reply lowers to UNVERIFIED and names the actual row. A fresh lock is unchanged. Combined
  pick/framework 69 passed; schema-checked capability/explanation/framework/pick selection 139 passed.
- A real missing-thickness analysis exposed a stale receipt assumption: current distance summaries
  do not publish a missing counter. The bounded receipt now requires the existing positive pair count,
  actual null creepage pair, explicit absent thickness/source inputs and matching missing-thickness
  issue. Marker/state-only, completed measurement, supplied thickness and zero-count negatives reject;
  57 framework/actual-thickness controls pass. No report producer or physical result was altered.
- Strict JSON example census: 112 pass and exactly four fail, edit/mcp under each v0/v1 wire case.
  Their public NO_CLAIM decision is still pending; no green full-example/CI/closure claim is made.
- Brief compaction was reviewed before runtime: actual complete result is 18,961 bytes under the
  unchanged literal 19,100 bound at 57 commands. Every key/claim/count remains; full help/command-view
  controls pass. Only six curated brief-only summaries change. No budget subtraction or increase.

- B final checkpoint: 57 framework/actual-thickness controls pass, 139 capability/explanation/
  framework/pick tests pass, corrected agent guide 103 pass; Pyright reports zero errors/warnings.
  Ruff, strict OpenSpec and schema/guide/surface generation checks pass. Private staged residue:
  zero hits across twenty files. No full-example or CI green claim: the four known edit/mcp strict
  failures remain real and await the actual maintainer decision. Root must not integrate this
  checkpoint as a passing final release gate before resolving them and rerunning exact-head checks.

## Maintainer decision, 2026-11-03

The coordinator received and relayed the maintainer's actual approval of
NO_CLAIM for edit and mcp. Add precisely these two names to the prior ten;
publish remains a claiming producer with its actual snapshot hypothesis.
The earlier failed edit/mcp strict receipts remain historical failures.

- [x] B.6 Apply the actual edit/mcp decision, test exact public list and
  capabilities claims, preserve higher-evidence/hypothesis guards, and rerun
  the complete strict JSON envelope census without exclusions. Root combined
  fast and exact-head CI remain separate.

Approved B.6 actual complete evidence/capabilities/CLI-consistency selection:792passed,41explicit mutating skips in120.97s; no edit/mcp deselection, all strict JSON envelope cases now pass. The skips are pre-existing confirmation-protocol cases exercised in their focused command tests, not edit/mcp exemptions. Earlier112pass/4fail receipt remains historical. Source CLIv0 and all higher-label/hypothesis negatives retained.
