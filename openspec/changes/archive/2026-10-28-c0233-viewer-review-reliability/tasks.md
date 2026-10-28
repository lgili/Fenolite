## 1. Scope

- [x] 1.1 Validate this OpenSpec strictly before implementation.

## 2. Live scene publication

- [x] 2.1 Add generation-safe rebuild/refinement publication and deterministic race regressions; pass focused server and model tests.

## 3. Keyboard context

- [x] 3.1 Isolate shortcuts from form/editing focus and browser modifiers; pass actual browser regressions and existing interaction tests.
- [x] 3.2 Keep narrow-sidebar Escape dismissal available for table documents and while no scene is loaded, after the editing/modifier guard and before CAD shortcuts; pass actual browser regressions and the interaction tests.

## 4. Narrow review

- [x] 4.1 Add narrow-screen sidebar toggle and adaptive toolbar without changing desktop geometry; pass browser viewport/toggle checks and visually inspect narrow output.

## 5. Documentation and proof

- [x] 5.1 Correct mask and Draftsman support wording, document keyboard and narrow-screen behavior; run focused tests, lint/format and strict validation. Parent records changelog and combined fast gate.
- [x] 5.1a Coordinator: record the shared Unreleased entry and pass combined make check-fast, strict validation and diff checks.
- [x] 5.2 Run complete CI on the published batch commit before archive; no local full-suite claim.

- 2026-10-28: task 5.1a passed in the combined audit batch: make check-fast (8 workers, worksteal) completed with 14123 passed and 77 skipped in 318.21s. Ruff, guide generators, format, Pyright, residue scan, strict OpenSpec and diff checks passed. Unreleased records c0224. The coordinator also inspected fresh 390-by-844 sidebar open/closed captures; the 19 browser interaction proofs remain separate from the fast suite. The initial batch's two documentation failures and fixes are recorded in c0207. Complete CI remains pending; no commit or publication occurred.


## Focused proof record — 2026-10-27

- Strict OpenSpec validation passed before implementation and after the completed changes.
- Generation/race change: 7 server/model tests passed. Tests deterministically delay an old worker before entry and pause its serialization while a newer rebuild publishes.
- Keyboard change: 14 actual Chromium interaction tests passed. A separate native keyboard check focused Highlight and pressed M: mode changed to Mask while Measure stayed false.
- Narrow layout: all 17 interaction tests passed, including widths 390, 760 and 1100. Inspected closed/open sidebar captures at 390 by 844; no page errors.
- Combined focused unit proof: 35 tests passed across server, models, page, documentation scenes, Altium layers and Draftsman drawing.
- Ruff check, Ruff format check, Pyright on server.py and git diff --check passed. No visual reference image was rewritten.
- Desktop before/after at 1100 by 700 in Chromium 148.0.7778.96: 2 of 770000 pixels differ by one level in one channel; zero exceed the visual suite threshold of two levels. Geometry is unchanged; stored screenshot references remain untouched.

## Follow-up proof — 2026-10-28

- The two new browser regressions failed before the Escape guard-order correction, for a table document and for an unloaded scene. After the correction, all 19 Chromium interaction tests passed (`uv run pytest tests/visual/test_interaction.py -q` with the local browser configured).
- The 35 focused unit tests passed again across server, models, page, documentation scenes, Altium layers and Draftsman drawing. Focused Ruff check/format, Pyright on server.py, strict OpenSpec validation and git diff --check passed.
- Full CI remains pending; no stored visual reference was changed.

- Allocation note, 2026-10-28: renamed the uncommitted draft from `c0206-viewer-review-reliability` to `c0224-viewer-review-reliability` after a remote change occupied the old number. Earlier proof records refer to the same implementation under its former ID.

- Final integration allocation, 2026-10-28: this draft is now `c0224-viewer-review-reliability`, previously `c0211-viewer-review-reliability`. Earlier IDs in checkpoints/proofs name the same implementation. The final numbering avoids all fetched committed allocations through c0222 and preserves the other agent's work.

- Implementation CI proof, 2026-10-29: GitHub run 40743806475 completed successfully with all 13 jobs on 8c2fa27048cf36543b93ee01c873aec0673f5d7d (https://github.com/lgili/Fenolite/actions/runs/40743806475). That revision tested this implementation as `c0224-viewer-review-reliability`; its final identity is `c0233-viewer-review-reliability` after the fetched-ref collision audit. Prior proof IDs are retained as aliases. The final archived revision has its own CI gate before dev advances.
