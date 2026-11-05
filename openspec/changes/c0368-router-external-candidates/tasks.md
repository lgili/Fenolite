# Implementation tasks

Planning note (2026-11-03): tasks were registered open; dated proof notes below record local progress.
Set CI_RUN_ID to the exact-head run when executing the closing CI proof.
Each task is at most one design-day; split oversized work before starting it. Run proofs in order.
A passing focused test does not replace required exact-head CI or maintainer-only evidence.

- [x] 1. Define supported adapter capabilities, scope/delta rules and fake-process contract fixtures.
  Proof: `uv run pytest tests/unit/routing/test_external_candidate_contract.py -q`.
  2026-11-03: exit 0; 8 authored contract tests passed. No external oracle claim.

- [x] 2. Implement scoped dispatch, canonical deltas and topology/protected-copper checks.
  - [x] 2.1 Immutable semantic delta kernel; proof: `uv run pytest tests/unit/routing/test_external_candidates.py -q -k delta`.
    2026-11-03: exit 0; 13 immutable-delta tests passed.
  - [x] 2.2 Scoped dispatch, canonical candidates and required judges; proof: `uv run pytest tests/unit/routing/test_external_candidates.py -q`.
    2026-11-03: exit 0; 24 scoped/delta tests passed. Adapter integration follows in task 3.
  Proof: `uv run pytest tests/unit/routing/test_external_candidates.py -q`.
  2026-11-03: exit 0; 24 tests passed; 32 together with task 1.

- [x] 3. Integrate shared timeout/cancellation, process cleanup and missing/malformed tool handling.
  - [x] 3.1 Shared Budget process-tree and cancellation proof: `uv run pytest tests/unit/routing/test_external_candidate_budget.py -q -k process`.
    2026-11-03: exit 0; 6 process tests passed. POSIX descendants tested with real processes; Windows taskkill contract tested with a fake, native Windows evidence remains open.
  - [x] 3.2 Adapter raw-delta guards and shared-budget preflight; proof: `uv run pytest tests/unit/routing/test_external_candidate_budget.py -q`.
  Proof: `uv run pytest tests/unit/routing/test_external_candidate_budget.py -q`.
  2026-11-03: exit 0; 18 passed. Existing Budget regression: 15 passed; plugin/import-graph regression: 120 passed. No full CI or native external-router claim.

- [x] 4. Add --propose-with, capabilities, tool provenance and reviewed acceptance parity.
  - [x] 4.1 Preserve an explicit internal candidate limit in generated external-decision commands; permit that same limit during their regeneration. Proof: `uv run pytest tests/unit/cli/test_route_propose_with.py -q`.
    2026-11-03: the new limit-parity assertion first failed as expected; after the fix, 113 fresh CLI/guide/workflow tests passed, including equality of proposed and reviewed tool/job provenance.
  Proof: `uv run pytest tests/unit/cli/test_route_propose_with.py -q`.
  2026-11-03: exit 0; 10 CLI tests passed, including unchanged input, tool provenance, reviewed accept/confirm without tool rerun, changed-tool invalidation and missing-tool exit 6. Added disconnected-copper refusal and deduplicated repeated dispatch; final focused routing/CLI/guide/import-graph proof passed 179 tests. An earlier mixed regression run had 65 passes and 3 stale capabilities-schema failures; fresh capabilities proof passed 11 tests after updating the documented additive field.

- [ ] 5. Run supported pinned external tools on authored fixtures in CI, with DRC and unchanged-input assertions.
  Proof: `uv run pytest tests/kicad/routing/test_external_candidates.py -q`.
  2026-11-03: attempted locally, exit 0 with 4 SKIPPED because both real tools are absent; this is not a passing oracle. Authored two/four-layer cases are wired into the existing pinned router CI job. Keep open: no push is authorized, so no exact-head CI is available.

- [x] 6. Document every new public option, result field and finding in the user docs and tested agent guide; regenerate it and keep each page within 12000 bytes.
  Proof: `uv run python tools/gen_agent_guide.py && uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-11-03: exit 0; 56 guide tests passed. Generated commands remain 750 lines; route-proposals is 10956 bytes and every written page stays within 12000 bytes.

- [ ] 7. Run focused proofs and make check-fast, inspect exit codes, then record required full CI jobs green on the exact head before merge/archive; keep implementation unclosed until CI is available.
  2026-11-03: first quick gate failed (make exit 2): 1 stale CI-command assertion, 3563 passed, 36 skipped. The workflow guard now requires both the existing router suite and the new native candidate proof. This run is not a pass. A second gate also failed (make exit 2): a second assertion in the same workflow contract still used the old command; 3564 passed, 36 skipped. Both assertions are now updated, and the focused workflow proof must pass before the fresh gate.
  2026-11-03: complete quick gate then passed, exit 0, 15835 passed and 43 skipped in 628.54 s. A subsequent candidate-limit parity fix passed its 113 focused tests; the final complete quick gate passed that working-tree state: make exit 0, 15835 passed, 43 skipped, 589.63 s. Full exact-head CI remains unavailable without push; keep this closing task open.
  Proof: `make check-fast && git diff --check && test "$(gh run view "$CI_RUN_ID" --json headSha --jq .headSha)" = "$(git rev-parse HEAD)" && test "$(gh run view "$CI_RUN_ID" --json conclusion --jq .conclusion)" = success && gh run view "$CI_RUN_ID" --json headSha,status,conclusion,jobs`. Add a dated result note only after success.

- [ ] 8. Update evidence hypotheses/labels with authored inputs, hashes, oracle versions, limitations and the exact CI run; keep unperformed native or maintainer checks explicitly open.
  Proof: `uv run python tools/gen_evidence_matrix.py --check`. Add a dated result note only after success.

- [ ] 9. Update CHANGELOG under Unreleased for delivered behavior only and strictly validate the change; if the destination release guard requires an empty Unreleased, leave this task open until the maintainer authorizes reconciliation.
  Proof: `npx -y @fission-ai/openspec validate c0368-router-external-candidates --strict && git diff --check`. Add a dated result note only after success.


Combined follow-up note (2026-11-03): c0368 plus c0369 and c0370 task 1 passed the final
local quick gate: make exit 0, 15893 passed, 43 skipped, 818.23 s. Native and exact-head
CI gates remain open; no push or closing claim.
