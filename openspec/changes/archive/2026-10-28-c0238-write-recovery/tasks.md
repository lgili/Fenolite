## 1. Entry

- [x] 1.1 Read the current core/CLI recovery requirements, reproduce the audited failure and validate this change strictly. Proof: `openspec validate c0229-write-recovery --strict`.

## 2. Recovery

- [x] 2.1 Add typed incomplete rollback with retained recovery material and deterministic tests for both backup modes, backup undo failures and interruptions. Proof: `uv run pytest tests/unit/core/test_io.py tests/unit/core/test_io_all.py -q`.
- [x] 2.2 Register FEN-1004 and expose incomplete recovery in CLI results with sanitized error text, including staged plans and progress. Proof: `uv run pytest tests/unit/cli/test_write_failures.py tests/unit/cli/test_interrupt.py tests/unit/cli/test_plans.py tests/unit/cli/test_exitcodes.py tests/unit/cli/test_explain_cmd.py -q`.

## 3. Documentation and verification

- [x] 3.1 Teach FEN-1004 and the recovery procedure in the agent guide and CLI contract; correct AGENTS error guidance. Proof: `uv run pytest tests/unit/agent/test_pages.py tests/unit/test_agent_skill.py -q`.
- [x] 3.2 Run focused lint/type checks, strict OpenSpec and diff checks; report results to the coordinator for combined check-fast, changelog and CI. Proof: `uv run ruff check src/fenolite/core/io.py src/fenolite/cli/main.py src/fenolite/cli/errors.py tests/unit/core/test_io_all.py tests/unit/cli/test_write_failures.py`; `uv run pyright src/fenolite/core/io.py src/fenolite/cli/main.py src/fenolite/cli/errors.py`; `openspec validate c0229-write-recovery --strict`; `git diff --check`.
- [x] 3.2a Keep recovery paths locatable outside cwd and across volumes; prove the output and error privacy. Proof: `uv run pytest tests/unit/cli/test_write_failures.py -q`; focused Ruff and Pyright.
- [x] 3.3 Coordinator: pass combined make check-fast, strict validation and diff checks; record the batch result and Unreleased entry.
- [x] 3.4 After authorization to commit/push, verify complete CI on that exact published commit before archive or merge.

### Proof record

- 2026-10-27: entry strict validation passed; the audit reproducer demonstrated the old failure at base ffc4027d.
- 2026-10-27: task 2.1 core tests passed: 35 tests, including both backup modes, both backup-undo steps, original interruption, interruption during restoration and a blocked removal of a newly written target.
- 2026-10-27: task 2.2 CLI proofs passed: 89 tests. New cases cover staged/direct writes, backup on/off, original interruption, progress, --fields, no absolute paths and no automatic retry claim.
- 2026-10-27: task 3.1 guide and README-agent contract checks passed: 64 tests. AGENTS.md and the packaged guide distinguish FEN-1004 from a software bug and from a completed rollback.
- 2026-10-27: task 3.2 focused Ruff/format and Pyright passed with zero errors. Strict OpenSpec and diff checks passed. A final combined core/CLI/guide run passed 98 tests after the type correction; no full suite was run by this agent.
- 2026-10-28: task 3.2a passed all 29 write-failure tests. Outside-cwd cases cover direct/staged writes, both backup modes and interruptions; a simulated cross-volume relpath failure retains the absolute structured recovery path while error text stays sanitized. Focused Ruff, format, Pyright and strict OpenSpec validation passed.
- 2026-10-28: final combined focused core, CLI, interruption, plan, exit-code, explain and agent-guide proof passed 197 tests. No full suite was run.
- 2026-10-28: task 3.3 passed in the combined audit batch: make check-fast (8 workers, worksteal) completed with 14123 passed and 77 skipped in 318.21s. Ruff, guide generators, format, Pyright, residue scan, strict OpenSpec and diff checks passed. Unreleased records c0209. The initial batch's two documentation failures and fixes are recorded in c0207. Complete CI remains pending; no commit or publication occurred.

- Allocation note, 2026-10-28: renamed the uncommitted draft from `c0204-write-recovery` to `c0209-write-recovery` after a remote change occupied the old number. Earlier proof records refer to the same implementation under its former ID.

- Allocation follow-up, 2026-10-28: renamed `c0209-write-recovery` to `c0229-write-recovery` after the committed remote collision. Earlier proof records retain their original IDs and refer to this same implementation.

- Final integration allocation, 2026-10-28: this draft is now `c0229-write-recovery`, previously `c0217-write-recovery`. Earlier IDs in checkpoints/proofs name the same implementation. The final numbering avoids all fetched committed allocations through c0222 and preserves the other agent's work.

- Implementation CI proof, 2026-10-29: GitHub run 40743806475 completed successfully with all 13 jobs on 8c2fa27048cf36543b93ee01c873aec0673f5d7d (https://github.com/lgili/Fenolite/actions/runs/40743806475). That revision tested this implementation as `c0229-write-recovery`; its final identity is `c0238-write-recovery` after the fetched-ref collision audit. Prior proof IDs are retained as aliases. The final archived revision has its own CI gate before dev advances.
