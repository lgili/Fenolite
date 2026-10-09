## Why

Milestone v0.4 (written as "v0.2c" before the renaming of 2026-10-07); the statements about the code were checked against `origin/dev` at `9aba2dff`.

**Split on 2026-10-07** (maintainer's decision 6 of that day). The DRC report limits, this proposal's former Decision 11, are now c0141-drc-report-limits, a change of their own that lands early. What stays here is the rest: staged plans, all-or-nothing writes, no write beside an error, signals, progress and resumable routes. Until that day this folder held a proposal and a design only; its `specs/` and `tasks.md` were written on 2026-10-07 from the design.

The complex-board review of 2026-10-05 found that the agent loop breaks on long steps. Measured on 2026-10-05 (review branch, `27ef3ad7`; the dispatcher code they describe is unchanged on `dev`):

- `--confirm` runs the command again. After `export --dry-run` of a 100-part board it wrote 15 of 17 files with other bytes than planned: Gerber and drill files carry their creation time. `route` routed the 40-part example twice, 29 s and 37 s.
- A failed write ends in a traceback without an error object. A 100-part build into a folder whose `lib/` was read-only wrote 8 of 20 files, `.fenolite/` included, and no board.
- `route` prints nothing until it ends. Stopped after 12 s, it left nothing to reuse; stopped by a signal to its own process, it left Freerouting running.

## What Changes

- **Staged plans.** A dry run, and a run refused with exit 4, keep the planned bytes in a state folder and return `result.plan_id`. `--confirm --plan ID` writes them without a second run, once folder, command, inputs and targets are checked; else `FEN-4002`, exit 4.
- **All-or-nothing writes.** A failure restores what was replaced, removes what was created, and gives `FEN-1002` (exit 1, retryable).
- **No write beside an error finding**, in the dispatcher; `place --force` stays the exception.
- **Interrupted commands** stop their tool processes, write nothing, and give `FEN-1003`.
- **Progress.** `--progress` writes JSON records on stderr: one per unit of `check`, `route`, `fill`, `export` and `render`, and one at least every 10 s.
- **Resumable routes.** `route` records the copper of each finished router process; the same call made again reuses it.

Size: 6.0 design-days (6.25 before the split, less the 0.5 day of the report limits, plus 0.25 for the inputs of the seven mutating commands the first design did not name).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `cli-contract`: MODIFIED "Mutation protocol", "Typed errors on stderr"; ADDED "Staged plans", "All-or-nothing writes", "Error findings plan no write", "Interrupted commands write nothing and stop their tools", "Progress on stderr", "Resumable route jobs".
- `core-primitives`: ADDED "Atomic writes of several files".
- `routing`: ADDED "Router runs reported for progress and resumption".

Moved to c0141 with the split, and no longer part of this change: `backend-protocol` "DRC report limits of an oracle"; `verification-loop` "DRC report limits in check" and the modification of "Check output is deterministic"; `kicad-oracle` "DRC report limits are probed".

## Non-goals

- Paging and concise replies: c0066 (archived).
- DRC report limits: c0141.
- Open connections above KiCad's limit: c0108, which adds the count from the copper to the `net` command that c0066 brought; no connectivity stage (c0141, Decision 5).
- Resumable `check`, `fill`, `export`: nowhere, because their longest unit is one tool run.
- A detached job: nowhere in v0.4; an agent's shell runs commands in the background.
- Tool log lines as progress: nowhere; no tool's log is a contract.
- Locks for two writers: nowhere in v0.4; `--plan` refuses a target changed after review.
- Guide pages and recovery recipes: c0080.
- **Limits.** SIGKILL keeps finished router runs but can leave temporary files and a tool process. A Freerouting run without tiers (c0109) is one unit. Windows cannot handle a forced stop.

## Evidence level required

- Plans, writes, signals, progress and job records: mechanical, by hermetic tests. No hypothesis is registered: nothing here is a fact about KiCad or another tool. `route` results stay `UNVERIFIED`.

## Impact

- New: `core/state.py`, `core/progress.py`, `cli/plans.py`, `cli/jobs.py`, `cli/progress.py`, `cli/codes.py`.
- Changed: `core/io.py`, the dispatcher and the fifteen mutating commands, the routing protocol and plugins, `checks/stages.py` (the progress argument), the envelope schema.
- New names: CLI flags `--plan` and `--progress`; error codes `FEN-1002`, `FEN-1003`, `FEN-4002`; issue codes `plan.not-staged` and `route.resumed`; result keys `result.plan_id`, `receipt.plan`, `result.resumed`; the environment variable `FENOLITE_STATE_DIR`. No model field, no hypothesis, no source id.
- Dry runs write under `~/.cache/fenolite/state`. Exit 1 can be retryable.

## Prerequisites

- `0.3.0` is released from `dev`: the fifteen mutating commands of `dev` then include `kit` (c0091) and the Altium build of `build` (c0085 to c0088), whose inputs "Staged plans" names.
- c0078 (`fetch`, deferred writes) lands first, as the smaller change of the same dispatcher; task 3.4 then plans its deferred writes again under `--plan`. If this change lands first, c0078 regenerates its dispatcher part on "Staged plans" and "All-or-nothing writes".
- c0109 and c0108: either order (design, Decision 12). c0141: independent; it lands early and this change does not wait for it.
- Already on `dev` (archived): c0062, c0066 (`restore`, receipts, paging).
- c0096: its constrained placement refuses `--force` and reports `place.incomplete` as a warning, so "Error findings plan no write" does not change it; both edit `cmd_place.py`, and the later one takes the other's text. c0097 and c0099: nothing here touches them.
- Waiting for this change: c0108 (relies on "Error findings plan no write"), c0116 (its dry-run hashes of non-repeatable kinds equal the written ones only under `--plan`), c0080 (recovery lines for the three codes).
