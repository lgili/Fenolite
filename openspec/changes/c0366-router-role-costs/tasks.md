# Implementation tasks

Planning note (2026-11-03): implementation has started; unchecked tasks remain open. Proof paths name tests to create.
Set CI_RUN_ID to the exact-head run when executing the closing CI proof.
Each task is at most one design-day; split oversized work before starting it. Run proofs in order.
A passing focused test does not replace required exact-head CI or maintainer-only evidence.

- [x] 1. Define typed fields, provenance and evidence using existing role sources; author hard/soft/unknown fixtures.
  Proof: `uv run pytest tests/unit/roles/test_search_fields_contract.py -q`.
  2026-11-03: passed, exit 0, 9 tests; immutable interchange, nonnegative bounds, unknown separation, cache-independent fingerprints and real-register coverage.

- [x] 2. Implement immutable field compilation with user limits, switching exclusions and current-fill reference coverage.
  Proof: `uv run pytest tests/unit/roles/test_search_fields.py -q`.
  2026-11-03: passed, exit 0, 15 tests; current saved fill only, stale/missing/island unknowns, scoped user limits, inferred-role exclusion and fingerprint changes.

- [x] 3. Apply nonnegative search costs and hard constraints without importing roles into routing.
  Proof: `uv run pytest tests/unit/routing/test_search_fields.py -q`.
  2026-11-03: passed, exit 0, 8 tests; nonnegative costs, mandatory exclusions, adjacent-layer switching, ground-backed detour and stale/missing-input refusal.

- [x] 4. Expose measured facts, unknowns, before/after judgments and changed-input refusal.
  Proof: `uv run pytest tests/unit/routing/test_search_role_candidates.py -q`.
  2026-11-03: passed, exit 0, 18 tests; final copper/confirmed-group judges, nonbinding inference, joint-acceptance revalidation, public provenance/facts and changed requirements/roles/profile/project/rules/model plan refusal.

- [x] 5. Prove authored two/four-layer detours, missing limits and stale fills with the KiCad oracle.
  Proof: `uv run pytest tests/kicad/routing/test_search_roles.py -q`.
  2026-11-03: passed, exit 0, 6 tests on native KiCad 10.0.6. Two/four-layer accepted detours reduce opens without increasing DRC counts; stale fill never counts as reference; missing HV limits refuse with no write. Pinned CI majors remain open in tasks 7–8.

- [x] 6. Document every new public option, result field and finding in the user docs and tested agent guide; regenerate it and keep each page within 12000 bytes.
  Proof: `uv run python tools/gen_agent_guide.py && uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-11-03: generated guide and 54 page tests passed, exit 0. All options, field keys and refusal reasons have tested instructions. Written-page byte and generated-page line budgets pass without raising limits.

- [ ] 7. Run focused proofs and make check-fast, inspect exit codes, then record required full CI jobs green on the exact head before merge/archive; keep implementation unclosed until CI is available.
  2026-11-03: first local quick gate exited 2 (one import-graph failure, 15706 passed, 43 skipped); compiler moved to CLI orchestration without relaxing architecture rules. Focused import/field regression: 102 passed, exit 0. Final complete quick gate passed, exit 0: 15707 passed, 43 skipped, 1114.54 seconds (`make check-fast PYTEST_PARALLEL="-n 8 --maxprocesses 8 --dist loadfile -x"`). CI remains unperformed under the no-push instruction; task 7 stays open.
  Proof: `make check-fast && git diff --check && test "$(gh run view "$CI_RUN_ID" --json headSha --jq .headSha)" = "$(git rev-parse HEAD)" && test "$(gh run view "$CI_RUN_ID" --json conclusion --jq .conclusion)" = success && gh run view "$CI_RUN_ID" --json headSha,status,conclusion,jobs`. Add a dated result note only after success.

- [ ] 8. Update evidence hypotheses/labels with authored inputs, hashes, oracle versions, limitations and the exact CI run; keep unperformed native or maintainer checks explicitly open.
  2026-11-03: local source hashes, KiCad version, limits and hypotheses recorded in `docs/evidence/router-role-fields.md`; matrix check passes. Task remains open because no exact-head CI run exists.
  Proof: `uv run python tools/gen_evidence_matrix.py --check`. Add a dated result note only after success.

- [ ] 9. Update CHANGELOG under Unreleased for delivered behavior only and strictly validate the change; if the destination release guard requires an empty Unreleased, leave this task open until the maintainer authorizes reconciliation.
  2026-11-03: delivered behavior has an Unreleased entry; strict validation and diff check pass locally. Closing remains open in sequence after tasks 7–8 and destination-release reconciliation; the change is not archived.
  Proof: `npx -y @fission-ai/openspec validate c0366-router-role-costs --strict && git diff --check`. Add a dated result note only after success.

