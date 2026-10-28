## 1. Entry

- [x] 1.1 Validate this OpenSpec strictly before implementation and inspect existing catalog and library viewer contracts.
  - 2026-10-28: strict validation passed. Existing search, library scenes, standalone export and mutation protocol were inspected; an in-memory feasibility check rendered all 49 symbols and 100 footprints without writing files or invoking CAD.

## 2. In-memory preview

- [x] 2.1 Reuse library item construction and implement deterministic catalog scenes/page with exact metadata and geometry. Proof: focused catalog-view and existing library-view unit tests.
  - 2026-10-28: 10 catalog/library viewer tests passed, including every installed definition, metadata, pin and pad counts, pad size/shape/drill and deterministic filtered pages. Existing file-backed libraries use the same extracted footprint-item helper.
- [x] 2.2 Add the view CLI action, argument checks, filters, empty-match refusal and PlannedWrite protocol. Proof: catalog CLI tests including offline execution, dry-run, replay, preserved targets and unchanged list/show.
  - 2026-10-28: 22 combined catalog CLI, catalog-scene and library-scene tests passed; focused Pyright passed. Staged replay was proved with the renderer blocked, and network/subprocess calls were forbidden in the offline CLI test.
- [x] 2.3 Resolve browser-review legibility: suppress symbol metadata fields only in catalog drawings, keep them in details, show footprint fabrication/courtyard layers, and omit the long pad-number list. Proof: catalog/library scene regressions plus coordinator reinspection of resistor and 100-pad LQFP captures.
  - 2026-10-28: implementation and focused regressions passed, including unchanged geometry/bounds under long metadata and unchanged source definitions. Coordinator confirmed corrected geometry and 3 browser tests passed; final capture acceptance follows the collapsed-properties improvement in 2.4.

- [x] 2.4 Coordinator: keep catalog metadata in a keyboard-operable collapsed details panel so the initial drawing is unobstructed, with evidence visible in the summary and ordinary library panels unchanged. Proof: browser selection/expand/collapse tests and desktop/narrow visual inspection.
- [x] 2.5 Correct the catalog/view package boundary discovered by the combined quick gate: resolve catalog entries in the CLI and pass immutable typed metadata/model definitions into the viewer without catalog imports or changes to layering rules. Proof: import-graph tests, catalog and shared-library regressions, focused Ruff/Pyright and identical complete-page bytes before/after the refactor.
  - 2026-10-28: 64 import-graph/catalog/shared-library/CLI tests passed, including independently authored injected symbol and footprint definitions rendered while the catalog module is unavailable. Focused Ruff/format and Pyright passed. Complete before/after HTML is byte-identical: 238303 bytes, SHA-256 `92d39ba2eb1bf60cf589b00ffd72983774e93ee76a3857e9163f82bcad9d1a82`. Existing layering rules are unchanged; coordinator reruns the combined quick gate.

## 3. Guides and proof

- [x] 3.1 Teach catalog view and its limits in the catalog guide, CLI contract and executable agent-guide example. Proof: catalog and agent-guide tests; coordinator regenerates the command guide.
  - 2026-10-28: 71 focused catalog/library/CLI/agent-guide tests passed; regenerated guide check passed. Docs identify the new action as development work after 0.5.0 and explain Properties expansion by pointer or keyboard.
- [x] 3.2 Run focused Ruff/format/Pyright, strict OpenSpec and diff checks, and report to the coordinator for browser review and combined gate.
  - 2026-10-28: focused Ruff check/format, Pyright (0 errors), 71 tests, generated-guide check, strict OpenSpec and diff checks passed. Coordinator owns final browser acceptance, shared changelog and combined gate.
- [x] 3.3 Coordinator: browser review of symbol/footprint selection, filtering, details and narrow layout; shared Unreleased entry; generated guide and combined make check-fast.
- [x] 3.4 After authorization to commit/push, verify complete CI on the exact published revision before archive or merge.

- 2026-10-28: coordinator accepted the final resistor and LQFP100 drawings at 1100 by 700 and the resistor at 390 by 844. The actual catalog browser tests passed (3): symbol/footprint selection, filter/no matches, pad inspection, details expansion/collapse and both viewport widths. Native Chromium keyboard activation also passed: summary focused, Enter opened details, Space closed them. Catalog metadata stays collapsed initially with evidence visible; no visual reference image was changed. These satisfy visual tasks 2.3 and 2.4; combined gate and complete CI remain separately pending.
- 2026-10-28: the first combined quick gate completed with 1 failed, 14137 passed and 78 skipped in 318.97s. Its only failure was the forbidden view-to-catalog import; task 2.5 corrected the dependency without changing the layering rules or accepted HTML bytes. Independent review found no further material issue.
- 2026-10-28: final task 3.3 proof passed: `make check-fast PYTEST_PARALLEL='-n 8 --dist worksteal'` completed with 14139 passed and 78 skipped in 376.70s. Ruff, generated guides, format, Pyright, residue scan, strict validation of all six audit changes and diff checks passed. The three catalog browser tests passed again after the architecture change (10.05s); the separate navigation/interaction proof remains 45 passed. Unreleased and the executable guide document the command. Complete CI remains pending; no commit, push, archive or merge occurred.

- Final integration allocation, 2026-10-28: this draft is now `c0225-catalog-visual-browser`, previously `c0212-catalog-visual-browser`. Earlier IDs in checkpoints/proofs name the same implementation. The final numbering avoids all fetched committed allocations through c0222 and preserves the other agent's work.

- Implementation CI proof, 2026-10-29: GitHub run 40743806475 completed successfully with all 13 jobs on 8c2fa27048cf36543b93ee01c873aec0673f5d7d (https://github.com/lgili/Fenolite/actions/runs/40743806475). That revision tested this implementation as `c0225-catalog-visual-browser`; its final identity is `c0234-catalog-visual-browser` after the fetched-ref collision audit. Prior proof IDs are retained as aliases. The final archived revision has its own CI gate before dev advances.
