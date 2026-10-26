# Native Altium acceptance backlog

## Why

Native acceptance requests from the 0.2 line through c0160 remain scattered across
the evidence pages. Some release summaries predate later reports and incorrectly
make completed checks look pending. The maintainer has authorized executing the
remaining checks on the licensed Windows PC, recording results and fixing defects.

## What Changes

- Consolidate the pending native checks, retaining their existing hypothesis ids.
- Restore the local verification prerequisites and investigate every failed gate.
- Execute the authored/public cases on disposable copies, record actual outcomes,
  and repair defects through focused OpenSpec tasks with regression proofs.
- Finish and archive eligible changes only after their own outstanding proofs pass;
  make separate signed commits for independent fixes and acceptance results.

## Impact

Evidence documentation, test prerequisites and any explicitly recorded follow-up
defects. No new public command or automatic graduation of experimental writers.
Native files stay outside version control; only sanitized results are committed.
