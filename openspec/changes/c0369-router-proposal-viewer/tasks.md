# Implementation tasks

Planning note (2026-11-03): all tasks below are open. Proof paths name tests to create.
Set CI_RUN_ID to the exact-head run when executing the closing CI proof.
Each task is at most one design-day; split oversized work before starting it. Run proofs in order.
A passing focused test does not replace required exact-head CI or maintainer-only evidence.

- [x] 1. Add typed proposal scene contracts and unknown-family/escaping fixtures without redesigning the shell.
  Proof: `uv run pytest tests/unit/view/test_proposal_scene.py -q`.
  2026-11-03: exit 0; 18 authored scene/escaping/unknown/invalid-geometry tests passed; focused pyright exit 0. No browser/native claim.

- [x] 2. Draw subject and candidate overlays, per-layer vias/locks/relaxations and accessible facts.
  Proof: `make viewer && uv run pytest tests/unit/view/test_viewer_bundle.py -q`.
  2026-11-03: exit 0; committed assets rebuilt from TypeScript/CSS, 10 bundle/model tests passed, including one-time geometry conversion, unknown facts and inner-layer through-via visibility. Browser interaction proof follows in task 3.

- [x] 3. Add compare/toggle/focus, measurement and cross-probing interaction tests.
  Proof: `uv run pytest tests/visual/test_proposal_interactions.py -q`.
  2026-11-03: exit 0; 4 local Chromium interaction tests passed with Playwright 1.63.0 (explicit development-tool install outside the repository). Includes keyboard Enter, cross-probing, preserved measurement, real canvas toggles, escaped payloads and no preselected acceptance. A local preview is not a pinned CI reference; task 6 stays open.

- [x] 4. Connect reviewed served accept/reject, static read-only behavior, stale-input refusal and error recovery.
  - [x] 4.1 Structured regeneration controls, strict server allowlists and current-board binding.
    2026-11-03: focused action proof exit 0; 20 tests passed, including real server/CLI preview, changed confirmation and stale-source refusal.
  - [x] 4.2 Explicit preview-only UI actions and existing plan-dialog confirmation/error recovery.
  Proof: `uv run pytest tests/unit/view/test_proposal_actions.py -q`.
  2026-11-03: exit 0; 22 server/action tests and 6 browser action/interaction tests passed. Includes real reviewed writes, FEN-4002 preservation, stale choice invalidation after record-only rejection and explicit fresh-run context replacement. Static pages expose no write controls.

- [x] 5. After c0367, implement whole-bundle inspection and atomic selection without member-only acceptance.
  Proof: `uv run pytest tests/unit/view/test_proposal_bundle_actions.py -q`.
  2026-11-03: exit 0; 11 backend bundle tests passed, including real complete-unit writes and member/parent refusal. Combined scene/model/backend/browser proof: 44 passed; four browser cases verify unit-only payloads, inspection focus and explicit confirmation/stale recovery.

- [ ] 6. Capture references with pinned CI Chromium, review screenshots and difference overlays, and record the artifact/run identity.
  Proof: `uv run pytest tests/visual/test_proposals.py -q`. Add a dated result note only after success.

  2026-11-03: pending pinned CI screenshots, artifact identity and difference-overlay review. Local Chromium interactions are not golden evidence; no push is authorized. Independent documentation can advance.
  2026-11-04: references captured from CI run 41947475460 (head 515ddc6a, artifact `viewer-differences` 13380217763), reviewed against the board-viewer requirements and committed (`docs/evidence/router-proposal-viewer.md`). Tick after the pinned viewer job passes on the exact head.

- [x] 7. Document every new public option, result field and finding in the user docs and tested agent guide; regenerate it and keep each page within 12000 bytes.
  Proof: `uv run python tools/gen_agent_guide.py && uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-11-03: generator exit 0; 57 guide tests passed, with structured controls and viewer decisions covered. The route-proposals page is 11882 bytes. Initial guide proof failed on the final Read next line; corrected before the fresh passing proof.

- [ ] 8. Run focused proofs and make check-fast, inspect exit codes, then record required full CI jobs green on the exact head before merge/archive; keep implementation unclosed until CI is available.
  Proof: `make check-fast && git diff --check && test "$(gh run view "$CI_RUN_ID" --json headSha --jq .headSha)" = "$(git rev-parse HEAD)" && test "$(gh run view "$CI_RUN_ID" --json conclusion --jq .conclusion)" = success && gh run view "$CI_RUN_ID" --json headSha,status,conclusion,jobs`. Add a dated result note only after success.

  2026-11-03: local make check-fast exit 0; 15893 passed, 43 skipped in 818.23 s on the stabilized combined tree. Exact-head full CI is unavailable without an authorized push; this task remains open. Skips are not passing native checks.

- [ ] 9. Update evidence hypotheses/labels with authored inputs, hashes, oracle versions, limitations and the exact CI run; keep unperformed native or maintainer checks explicitly open.
  Proof: `uv run python tools/gen_evidence_matrix.py --check`. Add a dated result note only after success.

- [ ] 10. Update CHANGELOG under Unreleased for delivered behavior only and strictly validate the change; if the destination release guard requires an empty Unreleased, leave this task open until the maintainer authorizes reconciliation.
  Proof: `npx -y @fission-ai/openspec validate c0369-router-proposal-viewer --strict && git diff --check`. Add a dated result note only after success.

