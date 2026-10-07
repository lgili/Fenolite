## Why

The review of 2026-10-05 (`docs/roadmap.md`, Gaps to a complex board) found that the agent loop breaks on long steps. Measured on 2026-10-05:

- `--confirm` runs the command again. After `export --dry-run` of a 100-part board it wrote 15 of 17 files with other bytes than planned: Gerber and drill files carry their creation time. `route` routed the 40-part example twice, 29 s and 37 s.
- A failed write ends in a traceback without an error object. A 100-part build into a folder whose `lib/` was read-only wrote 8 of 20 files, `.fenolite/` included, and no board.
- `route` prints nothing until it ends. Stopped after 12 s, it left nothing to reuse; stopped by a signal to its own process, it left Freerouting running.
- KiCad's DRC report stops at 499 entries of `clearance` and `unconnected_items` and at 199 of every other type measured, on 9.0.9 and 10.0.6. `check` reports these counts as complete.

## What Changes

- **Staged plans.** A dry run, and a run refused with exit 4, keep the planned bytes in a state folder and return `result.plan_id`. `--confirm --plan ID` writes them without a second run, once folder, command, inputs and targets are checked; else `FEN-4002`, exit 4.
- **All-or-nothing writes.** A failure restores what was replaced, removes what was created, and gives `FEN-1002` (exit 1, retryable).
- **No write beside an error finding**, in the dispatcher; `place --force` stays the exception.
- **Interrupted commands** stop their tool processes, write nothing, and give `FEN-1003`.
- **Progress.** `--progress` writes JSON records on stderr: one per unit of `check`, `route`, `fill`, `export` and `render`, and one at least every 10 s.
- **Resumable routes.** `route` records the copper of each finished router process; the same call made again reuses it.
- **Report limits.** `check` marks each DRC type that reached KiCad's limit: `summary.limits`, `check.report-limit`.

Size: 6.25 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `cli-contract`: MODIFIED "Mutation protocol", "Typed errors on stderr"; ADDED "Staged plans", "All-or-nothing writes", "Error findings plan no write", "Interrupted commands write nothing and stop their tools", "Progress on stderr", "Resumable route jobs".
- `core-primitives`: ADDED "Atomic writes of several files".
- `routing`: ADDED "Router runs reported for progress and resumption".
- `backend-protocol`: ADDED "DRC report limits of an oracle".
- `verification-loop`: MODIFIED "Check output is deterministic"; ADDED "DRC report limits in check".
- `kicad-oracle`: ADDED "DRC report limits are probed".

## Non-goals

- Paging and concise replies: c0066 (built).
- Open connections above KiCad's limit: c0108's `fenolite net`; no connectivity stage (design, Decision 11).
- Resumable `check`, `fill`, `export`: nowhere, because their longest unit is one tool run.
- A detached job: nowhere in v0.2c; an agent's shell runs commands in the background.
- Tool log lines as progress: nowhere; no tool's log is a contract.
- Locks for two writers: nowhere in v0.2c; `--plan` refuses a target changed after review.
- Guide pages and recovery recipes: c0080.
- **Limits.** SIGKILL keeps finished router runs but can leave temporary files and a tool process. A Freerouting run without tiers (c0109) is one unit. Windows cannot handle a forced stop. An unmeasured type is taken to stop at 199.

## Evidence level required

- `H-K-DRC-LIMITS`: `KICAD-VERIFIED (9.0.x, 10.0.x)` by an authored bench; `REPORT_LIMITS` holds measured values only.
- Plans, writes, signals, progress and job records: mechanical.

## Impact

- New: `core/state.py`, `core/progress.py`, `cli/plans.py`, `cli/jobs.py`, `cli/progress.py`, `cli/codes.py`.
- Changed: `core/io.py`, the dispatcher and mutating commands, routing protocol and plugins, `backends/base.py`, the KiCad oracle, `checks/drc.py`, the envelope schema.
- Dry runs write under `~/.cache/fenolite/state`. Exit 1 can be retryable.
