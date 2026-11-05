# Implementation tasks

Planning note (2026-11-03): implementation has started; unchecked tasks remain open. Proof paths name tests to create.
Set CI_RUN_ID to the exact-head run when executing the closing CI proof.
Each task is at most one design-day; split oversized work before starting it. Run proofs in order.
A passing focused test does not replace required exact-head CI or maintainer-only evidence.

- [x] 1. Record the authored search contract, state model, primary-source algorithm evidence and independent tiny-graph oracle; register evidence hypotheses before implementation.
  Proof: `uv run pytest tests/unit/routing/test_search_contract.py -q`.
  2026-11-03: source S-1309 and three hypothesis statements authored before kernel implementation; the quick gate later found their rows outside the parsed table. Placement corrected and parser coverage added; all 5 contract tests pass within the 58-test register/contract rerun, exit 0.

- [x] 2. Implement bounded integer A* and deterministic ordering against an independently authored Dijkstra oracle.
  Proof: `uv run pytest tests/unit/routing/test_search_grid.py -q`.
  2026-11-03: passed, exit 0, 16 tests, including independent Dijkstra comparisons, reopened states, stable ties, caps and interruption.

- [x] 3. Connect world geometry, endpoint stubs, cutouts, diagonal sweeps and through-via barrel checks.
  Proof: `uv run pytest tests/unit/routing/test_search_geometry.py -q`.
  2026-11-03: passed, exit 0, 13 tests; authored maze, exact off-grid endpoints, diagonal/cutout sweep, full four-layer barrel, layer/via/length limits and atomic pair refusal.

- [x] 4. Integrate search as candidate family, opt-in options, explicit unsupported reasons and shared cancellation/budget handling.
  Proof: `uv run pytest tests/unit/routing/test_search_candidates.py tests/unit/cli/test_route_search.py -q`.
  2026-11-03: passed, exit 0, 20 initial tests; default/fallback/only, stable candidate IDs, strict preflight, state/cancel/shared budget and reviewed CLI acceptance. Additional pair-fallback and named half-pair regressions passed in the 39-test candidate/geometry/CLI run; final broad gate passed (task 7 local note); pinned CI remains pending.

- [x] 5. Add authored two/four-layer obstacle boards, read-only proposals and reviewed acceptance/rollback oracle checks.
  Proof: `uv run pytest tests/kicad/routing/test_search.py -q`.
  2026-11-03: passed locally on KiCad 10.0.6, exit 0, 4 tests; authored two/four-layer mazes with same-face detours and mandatory through vias, DRC no-growth and one fewer open, read-only proposal/preview, injected decision-write rollback and successful retry. Pinned exact-head CI remains task 7.

- [x] 6. Document every new public option, result field and finding in the user docs and tested agent guide; regenerate it and keep each page within 12000 bytes.
  Proof: `uv run python tools/gen_agent_guide.py && uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-11-03: generation passed; guide proof exit 0, 53 tests including option/refusal coverage, parsed command examples and page budgets.

- [ ] 7. Run focused proofs and make check-fast, inspect exit codes, then record required full CI jobs green on the exact head before merge/archive; keep implementation unclosed until CI is available.
  Proof: `make check-fast && git diff --check && test "$(gh run view "$CI_RUN_ID" --json headSha --jq .headSha)" = "$(git rev-parse HEAD)" && test "$(gh run view "$CI_RUN_ID" --json conclusion --jq .conclusion)" = success && gh run view "$CI_RUN_ID" --json headSha,status,conclusion,jobs`. Add a dated result note only after success.

  2026-11-03 local prerequisite: `make check-fast PYTEST_MAX_WORKERS=4` passed, exit 0;
  15656 passed, 43 skipped in 1352.98 s on the final pair-protected source. Lint, format,
  guide checks, strict types and residue also passed. Earlier interrupted runs are not passes.
  This task stays open: exact-head CI is unrun. A local commit is authorized on 2026-11-03; push remains unauthorized.

- [ ] 8. Update evidence hypotheses/labels with authored inputs, hashes, oracle versions, limitations and the exact CI run; keep unperformed native or maintainer checks explicitly open.
  Proof: `uv run python tools/gen_evidence_matrix.py --check`. Add a dated result note only after success.

- [ ] 9. Update CHANGELOG under Unreleased for delivered behavior only and strictly validate the change; if the destination release guard requires an empty Unreleased, leave this task open until the maintainer authorizes reconciliation.
  Proof: `npx -y @fission-ai/openspec validate c0365-router-search --strict && git diff --check`. Add a dated result note only after success.

