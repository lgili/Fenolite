# Proposal viewer (c0369)

Recorded 2026-11-03 on codex/router-next-specs, after c0367 commit
640b114724781221a176782ce8c1d7b88f7fa61d. Implementation remains uncommitted.
No push, exact-head CI, native oracle or pinned visual-reference pass is claimed.

## Authored local evidence

H-G-PROP-SCENE and H-G-PROP-VIEW are INFERRED. Scene tests: 19; model/bundle tests: 10;
server/action tests: 22; atomic-bundle server tests: 11. The combined scene/model/backend/browser
bundle proof passed 44 tests (exit 0). Local Chromium functional proofs cover five inspection
interactions and four decision cases (independent/bundle, successful/stale confirmation).
Real server proofs separately verify reviewed board writes, unchanged previews, FEN-4002
preservation, member/parent refusal and full bundle decision records. Stub browser routes are
interaction evidence, not native copper validation.

The optional development browser is Playwright 1.63.0, installed outside the repository. Local
macOS screenshots are previews only. H-G-PROP-REFERENCE remains UNKNOWN: the two new reference tests
exit 1 until the pinned CI screenshots have been reviewed and committed. Their expected missing
reference failures are not counted as passes. No local image is promoted to a golden.
The reference harness captures alternatives and atomic-bundle panels for the existing
viewer-differences artifact; no additional CI job is introduced.

Guide generation and 57 guide tests passed (exit 0); the handwritten proposal page is under
12000 bytes. An initial guide proof failed because Read next was no longer the final line;
that was corrected before the passing proof. Initial lint found overlong lines, fixed before fresh lint/type checks. The first quick gate
exited 2 at lint; the next was intentionally interrupted after 2134 passes (make exit 2)
to fix a malformed bundle-display crash. Neither is a passing gate. The added browser
regression verifies malformed IDs/fingerprints remain inspection-only without crashing. A subsequent quick run found the shell token rule violation (literal proposal-border colour):
1 failed, 9499 passed, 37 skipped before interruption, make exit 2. Reusing the theme token
fixed it; 29 shell/model tests then passed. Complete combined quick validation and exact-head CI must be
recorded independently; older c0368 quick results do not validate c0369 changes.

## Boundaries

Geometry is authored for Fenolite, not from a private project. Scene integer conversion discards
whole malformed polylines rather than connecting remaining vertices. Unknown families are
escaped inspection data and cannot write. Absent facts stay unknown; ordering is not a score.
Structured controls are validated against fixed octilinear arguments. Requirements must remain
inside the project root. Explicit tool paths are not replayed, and no command text is executed.
A project write invalidates displayed decisions, including record-only rejection. A fresh read-only
proposal run refreshes server context. Bundle membership is fenced even when metadata is invalid;
only complete valid b-IDs are writable. Static exports expose no project-writing controls.
No electrical correctness, ranking, routing completeness or production approval is inferred.

## Reproducible inputs and assets

- `tests/data/kicad/board/two_layer.kicad_pcb`: SHA-256 `b7933826a36e88fb73f3fdb1684fb87f00be0f333b9d40bc6fbf0d696f7a3de6`.
- `tests/_proposal_viewer.py`: SHA-256 `1e49671a704fdfc7695fd5337dd73b3397a9d4db5d5e79b0d11d9380c499ac82`.
- `src/fenolite/view/static/viewer.js`: SHA-256 `d43eb9125201fca86b1e2ff4e629786f5b0b15f80b3f8523ad0c110ef9eeafe3`.


## Final combined local gate

The stabilized c0368/c0369 tree plus c0370 task 1 passed make check-fast on 2026-11-03:
make exit 0, 15893 passed, 43 skipped in 818.23 seconds. This is the quick suite only;
skips are not native/maintainer passes. Lint, formatting, source pyright, residue scan,
generated guides and the quick test selection passed. The new workflow recipe additionally
passed its 2 tests together with 57 guide tests. Exact-head full CI, the two reviewed pinned
visual references and native external-router compatibility remain open. No commit or push
was made for this implementation batch.
