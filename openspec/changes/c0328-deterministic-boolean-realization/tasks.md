## 0. Planning before prototype

- [x] 0.1 Verify the ID in src, every OpenSpec and local refs; read AGENTS, the Boolean living/active contracts and the existing exact receipts; record the source and decisions. Strictly validate this plan before new prototype code. Proof: `npx -y @fission-ai/openspec validate c0328-deterministic-boolean-realization --strict`; `git diff --check`.

  2026-11-02, base ea762411: c0328 is free in src/OpenSpecs/refs; c0327 stays reserved. Living
  geometry-boolean-backends and active c0215 were read. The actual source tree is
  1d51b381d12335342c68ec72a17039ed5747e7b9. The earlier exact oracle and actual176 certificates
  remain external and immutable. The seven dated decisions in design.md implement the authorized
  recommended bounded experiment; no production phase is authorized by this planning task.
  Proof passed before new prototype code: OpenSpec1.16.0 strict valid without warnings;
  `git diff --check` passed and each of the six requirement bodies is below500 characters.

- [x] 0.2 Search and register `H-G-BOOLEAN-REALIZATION` as a pending proposed bounded-safety hypothesis, with explicit criterion and external test/receipt names; retain the half-tie limitation and full-input/production gates. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`; strict validation.
  2026-11-02: id search was clear; the pending/proposed row and criterion were added. Register
  proof38 passed; the regenerated matrix/check and strict validation pass. The row stays INFERRED.

## 1. Bounded external proof

- [x] 1.1 Stamp and verify the actual source, inherited oracle,12 controls,23-edge witness,75 counterexample and five source-corner inputs in the external scratch receipt. Proof: `.venv/bin/python "$FENOLITE_REALIZATION_SCRATCH/prove_realization.py" --audit-inputs`.
- [x] 1.2 Implement the scratch signed reference→single half-even→exact normal form→existing debris pipeline. Prove all12 controls and separate exact face losses from coordinate projection. Proof: `.venv/bin/python "$FENOLITE_REALIZATION_SCRATCH/prove_realization.py" --controls`.
- [x] 1.3 Prove faithful23-vertex contexts for all five source turns and the75 counterexample at the actual debris tolerance; preserve retained turns/face adjacency and certify every removed face. Proof: `.venv/bin/python "$FENOLITE_REALIZATION_SCRATCH/prove_realization.py" --witnesses`.
- [x] 1.4 Prove the declared bounded invariances and deterministic integer output hashes; record the half-tie limitation explicitly. A failing obligation remains open. Proof: `.venv/bin/python "$FENOLITE_REALIZATION_SCRATCH/prove_realization.py" --invariances`.
- [x] 1.5 Record commands/exits, exact failure certificates, source/input/output identities, time/count bounds and remaining integer/topology limits. Proof: `.venv/bin/python "$FENOLITE_REALIZATION_SCRATCH/prove_realization.py" --report`; strict validation and `git diff --check`.

  2026-11-02: all five literal modes passed on the source/script identities in validation.md.
  Twelve controls, five faithful23 contexts and the75 counterexample pass; all five protected
  turns remain nonzero.108 declared transformations pass on18 cases. Six collapsed whole faces
  have exact/integer area certificates under the existing policy. An additional18-case repeat
  gives equal integer hashes; the largest declared arrangement has150 input segments (11175
  possible pairs). The half-tie negative control is recorded explicitly. The report permits no
  full176 or production experiment; future index/review gates remain open.

## 2. Later gated work

- [x] 2.1 Only after1.2–1.4 pass, propose and prove conservative integer candidate generation against exhaustive bounded arrangements. Record candidate counts and bounds before considering full176. Proof: a separate reviewed proof command and certificate; no naive full8058-edge Fraction enumeration.
  Current command/algorithm/resource review: `index-plan.md`. Prove the fresh
  exhaustive/indexed split-graph equality before a bounded broad-phase-only
  source census. The unavailable legacy script is not silently reconstructed
  under its old hash; no full face graph or production change is authorized here.
  Passed 2026-11-02 on clean signed ef65b274: fresh source capture matches the
  archived ordered/canonical inputs and all 188 Mac trace operations. All 269
  exhaustive/indexed bounded graphs agree, including operand multiplicities
  and source-edge provenance; a planted T-junction expiry defect changes the
  graph and is detected. All declared resource refusals pass. The permitted
  broad-phase-only census selects 20346 of 32461653 pairs in 0.032 s, with
  178289 integer checks and peak active 75, within every reviewed bound. No
  full Fraction/face arrangement, realization or old-oracle rerun occurred.
  Exact receipts and limits: `validation.md` and `docs/evidence/boolean-candidate-index.json`.
- [x] 2.2 Only after2.1, measure the full source-bound176 input, retaining actual result hashes and topology certificates without selecting a platform hash. Proof: the subsequently approved indexed full-input command, with a complete source-bound receipt.
  The root agent's prerequisite review and the new bounded-first external
  command, signed-face/realization obligations and explicit budgets are in
  `full-plan.md`. Planning alone claims no successful full result.
  Later actual experiment on clean signed fc933419: 84 strengthened analytic,
  winding, invariance, contact and budget controls pass, then the full indexed
  source run exits 1 at realization. Seventeen original turns invert on eight
  retained rings; all original coordinates remain present and none of the 5822
  projected nodes is half-tied. Complete failed neighborhoods and source-bound
  resource certificates are retained; a separate exit-0 audit verifies the
  refusal without making the source gate pass. Keep this task open. See
  `docs/evidence/boolean-full-reference.md` and `validation.md`.
  Re-measured 2026-11-04 on clean 468d8a61 (`docs/evidence/boolean-full-reference-rerun-20261104.json`):
  the archived programs, re-pointed at this head with only path constants and two identity guards
  changed (recorded per line), capture operand 176 with SHA-256 e9dc5cb6… — byte-identical to the
  archive, all 188 traced operations equal — and the index census selects the same 20346 candidates.
  84 controls pass; the full source run exits 1 at realization with the same refusal, and its failure
  certificate, rejected realization and exact loops are byte-identical to the 2026-11-02 run (10.2 s,
  69 MB, 54/83/500 bits). No platform hash is selected. Keep this task open: no valid realization exists.
- [x] 2.3 Obtain root review of the concrete bounded/full findings and a separate production design before any source/model/baseline change. Proof: the recorded explicit review; this task is not satisfied by passing scratch controls or a partial CI job.
  The root agent's actual failed-finding review is in `root-review.md`.
  It rejects shipping the current candidate and requires an explicit contract
  audit before another realization/quantization design. No separate production
  design or successful source realization is claimed; keep this task open.
  Next review proof: `contract-audit.md` maps the living error/normal-form and
  source-vertex obligations before any change of rounding. Its independent
  certificate must retain the strict experiment's failure and all actual
  precision/topology/loss guarantees; audit success is no production approval.

## Re-scope (decided 2026-11-04 by the coordinator, on the maintainer's authority)

Tasks 2.2 and 2.3 close as a recorded negative result, not as a pass:

- 2.2: the full source-bound measurement ran twice (fc933419 and 468d8a61). Both runs exit 1 at
  realization with byte-identical failure certificates, and no platform hash is selected. Under the
  current contract, the realization that the task meant to measure does not exist. That finding is
  the measured outcome. `H-G-BOOLEAN-REALIZATION` stays pending at `INFERRED`.
- 2.3: the root review in `root-review.md` rejects the candidate. Its root decision routes production
  realization through a separately planned implementation: c0332 (certified neck cut), with its
  follow-up c0383. That separate production design is c0332's `design.md`. c0328 changed no source,
  model, tolerance, fixture or baseline.

No success is claimed. The requirements of this change describe the bounded experiment and its gates,
which is what it delivered.

