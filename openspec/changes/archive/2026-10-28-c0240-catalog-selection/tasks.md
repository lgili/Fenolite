## 1. Entry

- [x] 1.1 Inspect resolved catalog/model/Part contracts and validate this OpenSpec strictly before code.
  - 2026-10-28: strict validation passed before implementation. Inspected CatalogItem injection, pad positions/sizes/numbers, SymbolDef pin roles and the existing Part pad_map contract (including multiple pads per pin).

## 2. Selection facts

- [x] 2.1 Add exact symbol/footprint selection metadata, integer centre-spacing metrics and authored/inventory tests while preserving the package boundary. Proof: catalog scene/CLI and import-graph tests; focused Ruff/Pyright.
  - 2026-10-28: 55 catalog/CLI/import-graph tests passed. Every installed entry's pin/pad facts match its injected definition; an authored 3-4-5 pad-centre case excludes an unnumbered mechanical pad and a single centre stays unknown. Existing injected-catalog-unavailable proof is retained. Focused Ruff/Pyright passed.

## 3. Interaction

- [x] 3.1 Implement the selection workspace and parameter filters with explicit invalid/empty states, preserving selected IDs and stale-load guards. Proof: Chromium filter and selection regressions.
  - 2026-10-28: two Chromium tests passed: text/mounting/pad-count/spacing/width filters, invalid ranges, selected IDs retained outside filters, and closing/reopening during asynchronous loading. The unit page contract also passed (11).
- [x] 3.2 Reuse same-document preview frames for the two selected definitions with preview-mode isolation and responsive layout. Proof: both rendered scene kinds and exact selected IDs in Chromium, offline and at narrow width.
  - 2026-10-28: six catalog-selection Chromium tests passed, including actual sandboxed child-frame execution, exact selected symbol/footprint IDs and rendered primitives at 390/1100 widths. Preview mode has no BroadcastChannel, nested frames or catalog dialog. Existing renderer handles both drawings; no second renderer or CAD executable introduced.
- [x] 3.3 Add explicit map editing/equal-number action, structural validation and reviewed Python snippets. Proof: browser regressions for invalid mappings and confirmation resets; execute generated snippets with the installed DSL.
  - 2026-10-28: all eight catalog-selection Chromium tests passed. They cover empty/unreviewed, duplicate, unknown and unused-pad maps, multiple pads on one pin, invalid references and confirmation resets after filtering/component changes. Generated code was executed with the actual Part DSL, preserving quoted values and exact single/multiple pad_map values. One initial test used an absent SOT ID and was corrected to the installed SOT23_3; no catalog definition changed. The combined 60-test browser run also passed, including modal shortcut guards.

## 4. Teaching and close

- [x] 4.1 Update catalog/viewer docs and Unreleased; keep generic/device limitations visible in the actual selection flow. Proof: catalog tests, manual visual review and docs links.
  - 2026-10-28: catalog documentation, agent parts guidance and Unreleased describe selection, geometric measurement limits and explicit datasheet review. Desktop pair/mapping captures and the settled 390-pixel symbol preview were visually accepted; native Enter/Escape worked. The first narrow capture preceded iframe repaint after scrolling; a settled recapture confirmed the renderer's valid canvas and actual geometry. No visual reference was overwritten. Catalog output remains an offline page generated through reviewed CLI plans.
- [x] 4.2 Run focused checks, affected browser regressions, strict OpenSpec/diff checks and one combined make check-fast with c0230. Record platform limitations without overwriting reference images to hide them.
  - 2026-10-28: combined quick gate passed with 14174 passed, 78 skipped in 267.15s; Ruff, generated guides, format, full src Pyright and residue scan passed. All eight audit specs and diff checks passed. Combined Chromium interaction/navigation/catalog/review proof passed 60 tests in 107.15s; native key presses and visual captures were also checked. Canonical references remain unchanged: c0230 records the existing macOS font mismatch and the successful eight same-host baseline comparisons. No full-suite or CI pass is claimed. No commit, publication, merge or archive occurred.
- [x] 4.3 Verify full CI on the authorized committed revision before archive/merge.

- Final integration allocation, 2026-10-28: this draft is now `c0231-catalog-selection`, previously `c0219-catalog-selection`. Earlier IDs in checkpoints/proofs name the same implementation. The final numbering avoids all fetched committed allocations through c0222 and preserves the other agent's work.

- Implementation CI proof, 2026-10-29: GitHub run 40743806475 completed successfully with all 13 jobs on 8c2fa27048cf36543b93ee01c873aec0673f5d7d (https://github.com/lgili/Fenolite/actions/runs/40743806475). That revision tested this implementation as `c0231-catalog-selection`; its final identity is `c0240-catalog-selection` after the fetched-ref collision audit. Prior proof IDs are retained as aliases. The final archived revision has its own CI gate before dev advances.
