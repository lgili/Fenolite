## Why

The audit reproduced a second I/O failure during rollback: after one target was replaced and another
write failed, restoring the first target failed too. The cleanup then deleted its kept original, and
Fenolite returned FEN-1002 even though the target remained changed. That code promises a completed rollback.

## What Changes

- Separate restoration steps from cleanup, continue independent restoration after a failure and preserve
  all remaining recovery material when restoration is incomplete, including with backups disabled.
- Add RecoveryError / FEN-1004 (exit 1, retryable false), with failed paths and preserved files for review.
- Keep FEN-1002 and FEN-1003 for completed rollback; a failed rollback overrides an original interruption.
- Teach manual recovery and qualify the all-or-nothing guarantee in the CLI and agent instructions.
- Add deterministic fault-injection tests for target, backup and interrupted recovery, plus CLI reporting.

## Capabilities

### Modified Capabilities

- core-primitives: Atomic writes of several files.
- cli-contract: Typed errors on stderr; Mutation protocol; All-or-nothing writes; Interrupted commands write nothing and stop their tools.

## Non-goals

Automatic recovery, a recovery CLI, cross-process locking, filesystem transactions, single-file atomic_write
changes, SIGKILL or machine-power-loss guarantees. No design files or format evidence changes.

## Impact

core/io.py; CLI dispatcher, error registry and explain; core/CLI tests; CLI contract; packaged guide;
AGENTS.md error guidance. The coordinator updates CHANGELOG and the change index for the combined batch.
