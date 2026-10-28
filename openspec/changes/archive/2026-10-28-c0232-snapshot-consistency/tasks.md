## 1. Scope and reproduction

- [x] 1.1 Inspect `read_stable`, its snapshot/publish callers and the living file-safety spec; record the authored cross-file reproduction and validate this change before editing code. Proof: the reproduction reports stale mixed bytes on the base; `openspec validate c0223-snapshot-consistency --strict` passes.

  - 2026-10-27, base `ffc4027d`: strict validation passed. The authored two-file reproduction returned A0/B2 with no unstable path although the files held A1/B2, with A1 saved before B2. Inspected the sole `read_stable` caller (`snapshot`) and the separate receipt-guarded `publish` reader.

## 2. Complete-set validation

- [x] 2.1 Add deterministic regressions for a formerly stable file changed during a retry, successive cross-file changes, stable/empty sets and bounded retries. Revalidate every requested file after each round, preserving reread counts and source order. Proof: `uv run pytest tests/unit/safety/test_snapshot.py -q`.
  - 2026-10-27: the three new cross-file regressions failed on the base (3 failed, 11 passed), then all 14 snapshot tests passed after complete-set validation. Existing single-file retry behavior, empty/unchanged sets, shared budget and reread counts remain covered.
- [x] 2.2 Correct the exhausted-budget diagnostic and test CLI refusal when a file first changes on the last round; check the accepted manifest after a cross-file save settles. Proof: `uv run pytest tests/unit/safety/test_snapshot.py tests/unit/safety/test_publish.py -q`.

  - 2026-10-27: snapshot and publish tests passed together (19). The CLI test accepts the settled A1/B2 and verifies manifest byte hashes; a different test makes A change only in the final retry, reports A without claiming four reads, and creates no destination folder. Publish has no source changes.

## 3. Documentation and focused proof

- [x] 3.1 Document the complete-set observation and its limits, including fixed membership, later saves and restored bytes. Proof: strict OpenSpec validation and `uv run pytest tests/unit/safety -q`; inspect the wording against the implemented loop.
- [x] 3.2 Run formatting, lint and affected consistency proofs; record results here and hand the batch changelog/quick gate to the coordinator. Proof: Ruff for changed Python files; focused safety/consistency tests; `git diff --check`.
  - 2026-10-27: all 35 safety tests passed; focused snapshot/publish CLI consistency passed (20 passed, 2 intentional mutating-command skips, 430 deselected). Strict OpenSpec, Ruff check/format and git diff --check passed. Documentation now distinguishes complete-set hash observations from an atomic filesystem snapshot. No command arguments, schemas, error codes or evidence labels changed.
- [x] 3.2a Reconcile the command help, generated agent guide, CLI contract, safety.unstable explanation and H-G-SNAPSHOT-STABLE hypothesis with observed complete-set validation and a shared retry budget; remove claims of one-moment/no-intervening-save guarantees. Proof: focused safety, explain and agent-guide tests; `uv run python tools/gen_agent_guide.py --check`; strict OpenSpec and diff checks.
  - 2026-10-28: 107 tests passed across `tests/unit/safety`, `tests/unit/cli/test_explain_cmd.py`, `tests/unit/agent/test_pages.py` and `tests/unit/test_agent_skill.py`. The generated guide is current; focused Ruff/format, strict OpenSpec and diff checks passed. The public docs/help scan found no remaining no-save-interrupted, one-moment-project or each-of-four-reads claim. The living OpenSpec is reconciled at archive, not rewritten early.
- [x] 3.3 Batch integration: the coordinator records the shared Unreleased entry and passes make check-fast, strict validation and diff checks.
- [x] 3.4 After authorization to commit/push, verify complete CI on the exact committed revision before merge or archive.

- 2026-10-28: task 3.3 passed in the combined audit batch: make check-fast (8 workers, worksteal) completed with 14123 passed and 77 skipped in 318.21s. Ruff, guide generators, format, Pyright, residue scan, strict OpenSpec and diff checks passed. Unreleased records c0223 and corrects the earlier snapshot guarantee. The initial batch's two documentation failures and fixes are recorded in c0207. Complete CI remains pending; no commit or publication occurred.

- Allocation note, 2026-10-28: renamed the uncommitted draft from `c0205-snapshot-consistency` to `c0223-snapshot-consistency` after a remote change occupied the old number. Earlier proof records refer to the same implementation under its former ID.

- Final integration allocation, 2026-10-28: this draft is now `c0223-snapshot-consistency`, previously `c0210-snapshot-consistency`. Earlier IDs in checkpoints/proofs name the same implementation. The final numbering avoids all fetched committed allocations through c0222 and preserves the other agent's work.

- Implementation CI proof, 2026-10-29: GitHub run 40743806475 completed successfully with all 13 jobs on 8c2fa27048cf36543b93ee01c873aec0673f5d7d (https://github.com/lgili/Fenolite/actions/runs/40743806475). That revision tested this implementation as `c0223-snapshot-consistency`; its final identity is `c0232-snapshot-consistency` after the fetched-ref collision audit. Prior proof IDs are retained as aliases. The final archived revision has its own CI gate before dev advances.
