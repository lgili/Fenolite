## 1. Entry

- [x] 1.1 Inspect existing check/report/view contracts and validate this OpenSpec strictly before code.
  - 2026-10-28: inspected StageResult statuses, check input hashes and stage summaries, conversion equivalence/experimental fields, export receipts and check-overlay/navigation. Strict validation passed before implementation. Existing export replies lack affirmative readback attestation; their status will retain that limitation.

## 2. Status and scope

- [x] 2.1 Implement viewer-owned status composition and authored regression tests for missing/failed/skipped/capped/partial stages, evidence and report-to-document hash binding. Proof: `uv run pytest tests/unit/view/test_project_review.py tests/unit/test_import_graph.py -q`.
  - 2026-10-28: 63 authored status/import-graph regressions passed, including malformed command/stage types, partial connectivity coverage, stale live hashes and conversion/export limitations. Focused Ruff passed. No module-layer exception added.
- [x] 2.2 Preserve check hints/stages/source metadata, add repeatable convert/export report loading to the CLI, and attach status after cached reads for summary, offline and live viewing. Proof: focused check-overlay, view CLI and server tests, including dry-run/replay and stale source hashes.
  - 2026-10-28: 40 focused report/overlay/status/server tests passed, including byte replay with the report loader disabled, refusal when a report changes after dry-run, invalid/duplicate input and reclassification after a live save. Existing view/overlay/status tests also passed (50). Focused Ruff and Pyright passed; one initial live test was corrected to suppress its incidental log in the JSON-only test harness.

## 3. Review interaction

- [x] 3.1 Add the project review entry/panel, stage details and severity/stage/text filters, previous/next findings, original hints and Locate. Prove empty/unplaced cases, keyboard controls, narrow layout and navigation/live changes in Chromium without changing findings or evidence.
  - 2026-10-28: four focused Chromium review tests passed, then the combined 60-test interaction/navigation/catalog/review run passed in 107.15s. Native Playwright key presses separately proved Enter opening and Escape closing with a focused filter at 390/1100 widths. Fresh status/finding captures were visually inspected. Locate restores hidden markers; stale/unbound report warnings remain visible in both Messages and selected-finding details. A late error without its stage record is still failed (authored regression).

## 4. Teaching and validation

- [x] 4.1 Update viewer/CLI docs, executable agent guide and Unreleased; regenerate the command guide. Proof: focused agent/CLI tests and generator check.
  - 2026-10-28: 109 focused agent-guide/skill/report/status/page tests passed and the generated command guide is current. One initial guide-writing-rule failure was corrected by stating the map's INFERRED status directly; no writing rule changed.
- [x] 4.2 Run focused lint/format/Pyright, browser proofs, strict OpenSpec, diff checks and the combined make check-fast after the catalog-selection batch.
  - 2026-10-28: final combined `make check-fast PYTEST_PARALLEL='-n 8 --dist worksteal'` passed: 14174 passed, 78 skipped in 267.15s. Ruff, both guide generators, format, full src Pyright and residue scan passed. All eight current audit changes validate strictly; diff checks passed. Browser proof is separately 60 passed, plus eight accepted same-platform screen comparisons and native key/capture checks. The canonical screenshot limitation is recorded below and remains for CI. No commit, push, merge or archive occurred.
- [x] 4.3 Verify full CI on the authorized committed revision before archive/merge.

## Visual comparison scope

- 2026-10-28: the stock screenshot suite completed with 8 screenshot failures and 5 passed checks on this macOS host. Re-rendering HEAD's unmodified template with identical authored scene data on the same host also differed from committed references by 6.11–10.05 percent; the differences are in platform fonts/controls. No reference, tolerance or screenshot test was changed. After keeping the new Review entry within the existing heading height, all eight final screens compared with that same-platform HEAD baseline passed the existing 0.1 percent tolerance (0.03026–0.03052 percent, no page errors). This is a same-host regression proof, not a claim that the canonical screenshot suite passed; canonical CI remains pending.
- 2026-10-28: the offline preview at build/project-review.html was produced through actual check and reviewed view-export plans from Fenolite's authored two-layer fixture. It truthfully shows a clearance failure, limited/model scope and missing ERC/DRC stages; no sample result was certified or fabricated. The check's findings exit was expected.

- Final integration allocation, 2026-10-28: this draft is now `c0230-project-review-status`, previously `c0218-project-review-status`. Earlier IDs in checkpoints/proofs name the same implementation. The final numbering avoids all fetched committed allocations through c0222 and preserves the other agent's work.

- Implementation CI proof, 2026-10-29: GitHub run 40743806475 completed successfully with all 13 jobs on 8c2fa27048cf36543b93ee01c873aec0673f5d7d (https://github.com/lgili/Fenolite/actions/runs/40743806475). That revision tested this implementation as `c0230-project-review-status`; its final identity is `c0239-project-review-status` after the fetched-ref collision audit. Prior proof IDs are retained as aliases. The final archived revision has its own CI gate before dev advances.
