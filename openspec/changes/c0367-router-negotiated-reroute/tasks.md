# Implementation tasks

Planning note (2026-11-03): implementation has started; unchecked tasks remain open. Proof paths name tests to create.
Set CI_RUN_ID to the exact-head run when executing the closing CI proof. No push is authorized.
Each task is at most one design-day; split oversized work before starting it. Run proofs in order.
A passing focused test does not replace required exact-head CI or maintainer-only evidence.

- [x] 1. Record the clean-room negotiation design, primary-source evidence, bundle schema and legacy compatibility cases.
  Proof: `uv run pytest tests/unit/routing/test_bundle_contract.py -q`.
  2026-11-03: 6 passed, exit 0; schema/input/member identity, immutable grouping, unchanged v0 bytes and future-schema refusal. S-1310 and hypotheses registered before negotiation implementation.

- [x] 2. Implement bounded deterministic occupancy negotiation with protected geometry.
  Proof: `uv run pytest tests/unit/routing/test_negotiate.py -q`.
  2026-11-03: 12 passed, exit 0; deterministic joint detours, shared discovered-state bound, round exhaustion, nonnegative costs, interruption and unchanged locked originals.

- [x] 3. Validate whole bundles, coupled-subject refusal and interruption without exporting overlaps.
  Proof: `uv run pytest tests/unit/routing/test_negotiate_candidates.py -q`.
  2026-11-03: 11 candidate tests plus 52 import-graph tests passed, exit 0. Whole-set geometry, copper and confirmed-role judgments, missing/refusing adapter, coupled subjects and interrupted partial work never emit invalid candidates.

- [x] 4. Implement atomic bundle decision persistence, replay/forget, stale-input refusal and rollback.
  Split before implementation (2026-11-03), because lifecycle/rollback spans several independent iterations:
  - [x] 4.1 Add strict v1 bundle records, v0 byte compatibility and atomic membership helpers.
    Proof: `uv run pytest tests/unit/routing/test_bundle_decisions.py -q`.
    2026-11-03: 11 new record tests and 7 legacy decision tests passed, exit 0; v1 membership/future refusal, atomic forget and v0 byte compatibility.
  - [x] 4.2 Add atomic CLI accept/reject and member refusal.
    Proof: `uv run pytest tests/unit/cli/test_route_bundles.py -k decisions -q`.
    2026-11-03: 2 passed, exit 0; reviewed whole-bundle acceptance, member usage refusals, unit rejection and stable show-rejected behavior.
  - [x] 4.3 Add whole-bundle replay/forget with final validation.
    Proof: `uv run pytest tests/unit/cli/test_route_bundles.py -k lifecycle -q`.
    2026-11-03: 4 passed, exit 0; accepted/rejected whole-unit forget/replay, legacy bare replay argument order and a moved endpoint preventing every member replay.
  - [x] 4.4 Prove stale-input guards and injected write rollback.
    Proof: `uv run pytest tests/unit/cli/test_route_bundles.py -k guard -q`.
    2026-11-03: 8 passed, exit 0; six edited/created input guards, fault-injected board/record rollback plus retry without searching and partial gate refusal.

  Proof: `uv run pytest tests/unit/routing/test_bundle_decisions.py tests/unit/cli/test_route_bundles.py -q`.
  2026-11-03: 25 passed, exit 0, 115.25 seconds; complete record/CLI lifecycle, stale inputs, injected rollback and partial-gate rejection.

- [x] 5. Prove a corridor conflict solved by joint reroute and negative lock/pair cases with KiCad.
  Proof: `uv run pytest tests/kicad/routing/test_negotiate.py -q`.
  2026-11-03: 4 passed, exit 0, on native KiCad 10.0.6; two/four-layer atomic detours reduce opens by two with no DRC count increase, locked barrier and pair negatives preserve original bytes and DRC. Pinned CI remains pending.

- [x] 6. Document every new public option, result field and finding in the user docs and tested agent guide; regenerate it and keep each page within 12000 bytes.
  Proof: `uv run python tools/gen_agent_guide.py && uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-11-03: generated guide, 55 page tests and strict OpenSpec validation passed, exit 0. Dedicated route-proposals page is within 12000 bytes; start page stays below 200 lines without raising budgets. Existing Guide pages scenario identifier is retained for archive compatibility.

- [ ] 7. Run focused proofs and make check-fast, inspect exit codes, then record required full CI jobs green on the exact head before merge/archive; keep implementation unclosed until CI is available.
  2026-11-03: final focused regression passed, exit 0, 210 tests in 174.41 seconds; final native KiCad 10.0.6 proof passed, exit 0, 4 tests in 33.34 seconds. First local quick gate was interrupted after an existing start-page wording failure (exit 130; 10521 passed and 39 skipped before interruption), never a passing gate. Required wording was restored without changing tests/budgets; 92 guide/start-page tests then passed, exit 0. A subsequent quick gate was also interrupted (exit 130, not passed) to fix a proven direct-API gap: negotiation options without proposal subjects were silently ignored. The guard and prior router/architecture regression passed (94 tests, exit 0); the final complete quick gate passed, exit 0: 15774 passed, 43 skipped in 666.28 seconds (`make check-fast PYTEST_PARALLEL="-n 8 --maxprocesses 8 --dist loadfile -x -vv --tb=short"`); exact-head CI is unperformed because push is forbidden. Task remains open.
  Proof: `make check-fast && git diff --check && test "$(gh run view "$CI_RUN_ID" --json headSha --jq .headSha)" = "$(git rev-parse HEAD)" && test "$(gh run view "$CI_RUN_ID" --json conclusion --jq .conclusion)" = success && gh run view "$CI_RUN_ID" --json headSha,status,conclusion,jobs`. Add a dated result note only after success.

- [ ] 8. Update evidence hypotheses/labels with authored inputs, hashes, oracle versions, limitations and the exact CI run; keep unperformed native or maintainer checks explicitly open.
  2026-11-03: local proof-source hashes, native version, limitations and INFERRED/UNKNOWN labels recorded; matrix check passes. Exact-head CI evidence remains missing, so this task stays open.
  Proof: `uv run python tools/gen_evidence_matrix.py --check`. Add a dated result note only after success.

- [ ] 9. Update CHANGELOG under Unreleased for delivered behavior only and strictly validate the change; if the destination release guard requires an empty Unreleased, leave this task open until the maintainer authorizes reconciliation.
  2026-11-03: delivered behavior is under Unreleased; strict OpenSpec validation and diff check pass. Closing remains open after tasks 7–8 and destination-release reconciliation; no archive is performed.
  Proof: `npx -y @fission-ai/openspec validate c0367-router-negotiated-reroute --strict && git diff --check`. Add a dated result note only after success.

