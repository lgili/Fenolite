## Why

The snapshot reader validates only the files reread in the latest retry. A save can therefore change a
file that passed the first validation while another file is being reread. The command accepts the old
bytes of the first file with new bytes of the second even when that combination never existed. This
was reproduced on authored two-file inputs during the reliability audit of 2026-10-27.

## What Changes

- Validate the complete requested file set after every read/retry round. Reread only the files whose
  current hashes disagree with the bytes held in the candidate snapshot.
- Preserve the three-retry-round bound, the count of file rereads and the existing `safety.unstable`
  refusal. A mismatch found at the end of the retry budget is reported even if that file was previously
  unchanged.
- Correct the refusal message and document the observed-hash guarantee: no reader locks the source,
  no folder-membership snapshot is taken, and arbitrary concurrent writers can still change data
  after a file's last check or change it and restore it between checks.
- Reconcile this guarantee across command help, the generated agent guide, CLI contract, issue
  explanation and the supporting hypothesis; retain the current evidence level.
- Add deterministic regression cases for cross-file saves, changes across successive retries, final
  budget exhaustion and the command's no-write refusal.

## Capabilities

### Modified Capabilities

- `file-safety`: clarify the complete-set validation and bounded retry behavior of Stable snapshot.

## Non-goals

Filesystem snapshots, locking other applications, detecting newly added project files, changing the
publish command, changing transaction persistence, or adding public commands, options, schemas or codes.

## Impact

`src/fenolite/safety/files.py`, the diagnostic in `src/fenolite/cli/cmd_snapshot.py`,
`tests/unit/safety/test_snapshot.py`, `docs/file-safety.md`, the public help/contract/guide, the issue
explanation, `docs/hypotheses.md` and this change. The batch coordinator records
the shared changelog and integration validation. Evidence remains `INFERRED` under the existing
`H-G-SNAPSHOT-STABLE` hypothesis.
