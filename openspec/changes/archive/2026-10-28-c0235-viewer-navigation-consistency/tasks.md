## 1. Scope and reproduction

- [x] 1.1 Validate this OpenSpec strictly before implementation; record the deterministic Chromium reproductions.
- [x] 1.2 Add focused browser regression tests and prove the relevant cases fail on the current page.

## 2. Implementation

- [x] 2.1 Guard scene cache publication, navigation completion and deferred selection continuations by request generations; pass focused browser tests for late success/failure/empty responses and repeated selection.
- [x] 2.2 Guard version polling and refresh completion by selected document, navigation and request order; pass focused polling/cache browser regressions.
- [x] 2.2a Revalidate the first version response rather than adopting it over an older scene, including return to a cached document and refinement before the first poll; skip polls during current scene loading and prove slow refreshes complete without duplicate reads.
- [x] 2.3 Document navigation behavior and pass all navigation/interaction browser tests, affected unit tests, lint/format, strict OpenSpec and diff checks.

## 3. Batch proof

- [x] 3.1 Coordinator: record Unreleased and pass the combined make check-fast, strict validation and diff checks.
- [x] 3.2 Verify complete CI on the authorized published commit before archive or merge.

## Proof record

- 2026-10-28: strict OpenSpec validation passed before any page edit. The Chromium reconnaissance reproduced a schematic selection with a board displayed, a stale read-error card covering the new document, and an old poll assigning its version/status to the new document.
- 2026-10-28: the first 16 deterministic browser regressions all failed on the pre-c0226 page (35.71s). They cover late success/failure/empty scenes, repeated selection, cache decode order, poll order/navigation, and delayed cross-probe/BOM/mark continuations. Fixtures are authored Fenolite data; no visual reference changed.
- 2026-10-28: two additional loading/startup-selection tests failed before implementation. After task 2.1, all 11 non-polling browser regressions passed (25.22s), including cache publication, loading identity and deferred selections.
- 2026-10-28: task 2.2 passed all 18 initial navigation browser tests (40.53s), including seven polling races. Independent review then identified the first-version adoption gap; four regressions for initial/revisited scenes and slow reads failed before task 2.2a and passed after it (11.35s). A further building-version regression also failed before adding the no-adoption gate.
- 2026-10-28: the final focused browser run passed 45 tests (26 navigation and 19 existing interaction tests) in 99.66s. It also covers live response cache order, invalidated decoding, failed-refresh retry and startup selection. The focused page/server/models/library/drawing unit run passed 32 tests in 0.82s. Ruff, format, strict OpenSpec and git diff --check passed. A fresh 390-by-844 loading capture was visually inspected; the correct document is named and the old canvas is hidden, with no page errors. No screenshot reference, fixture, CAD file, command, runtime dependency or evidence level changed.
- 2026-10-28: task 3.1 passed in the final combined batch: `make check-fast PYTEST_PARALLEL='-n 8 --dist worksteal'` completed with 14139 passed and 78 skipped in 376.70s. Ruff, guide generators, format, Pyright, residue scan, strict validation of all six audit changes and diff checks passed. Unreleased records c0226. The first quick run's catalog-layering failure and correction are recorded in c0225; no navigation change was needed. Complete CI remains pending; no commit, push, archive or merge occurred.

- Final integration allocation, 2026-10-28: this draft is now `c0226-viewer-navigation-consistency`, previously `c0213-viewer-navigation-consistency`. Earlier IDs in checkpoints/proofs name the same implementation. The final numbering avoids all fetched committed allocations through c0222 and preserves the other agent's work.

- Implementation CI proof, 2026-10-29: GitHub run 40743806475 completed successfully with all 13 jobs on 8c2fa27048cf36543b93ee01c873aec0673f5d7d (https://github.com/lgili/Fenolite/actions/runs/40743806475). That revision tested this implementation as `c0226-viewer-navigation-consistency`; its final identity is `c0235-viewer-navigation-consistency` after the fetched-ref collision audit. Prior proof IDs are retained as aliases. The final archived revision has its own CI gate before dev advances.
