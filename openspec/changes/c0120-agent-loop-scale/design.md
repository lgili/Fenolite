## Context

**Scope.** Milestone v0.4, c0120, from the complex-board review of 2026-10-05: "progress and resumable jobs for long steps; `--confirm` writes the reviewed plan without a second run; report limits of KiCad's DRC marked per type; a failed write leaves an error object and no half-written output". The third item left this change on 2026-10-07: it is c0141-drc-report-limits (maintainer's decision 6), which lands early; Decision 11 below is kept only as a pointer. c0066 (archived) owns paging and concise replies; c0078 (agent track) adds deferred writes to the dispatcher; c0079 and c0080 own the packaged guide, `init` and the recovery recipes; c0119 owns the large example and its budgets.

**The code** (`origin/dev` at `9aba2dff`, read on 2026-10-07; the behaviour was first read at `27ef3ad7` and is unchanged, the line numbers are those of `dev`):

- *Mutation protocol* (`cli/main.py`). A command returns `PlannedWrite(path, data, kind)` objects (`cli/api.py:41-46`). Without `--confirm` the dispatcher lists them in `result.plan` as `{path, kind, bytes, sha256, overwrite}` (`main.py:282-289`). With `--confirm` it calls the command again from the start, as every call does, and writes file after file with `core.io.atomic_write` (`main.py:299`), outside any `try`. `main()` catches `CliError` only (`main.py:341`). `atomic_write` is atomic per file (`core/io.py:52`): a temporary file beside the target, then `os.replace`.
- *Writes and findings.* The dispatcher writes whatever the command planned, whatever its issues; each command empties its own writes when it reports an error (`cmd_build.py:666`, `cmd_place.py:356`, `cmd_pnp.py:68`), and `place --force` writes on purpose. `dev` registers fifteen mutating commands: `build`, `place`, `route`, `fill`, `export`, `render`, `fmt`, `template`, `bom`, `pnp`, `manifest`, `sync`, `kit`, `restore` and the hidden `_echo`. An Altium build refuses to replace a PCB document that was edited in Altium (`FEN-7001`, exit 7, `--discard-layout`); it then plans no write.
- *Receipts* (c0066, archived): `Receipt(written, backup, id, undo)` (`cli/output.py:42-50`); the receipt identifies a write after it happened, not a plan before it. `fenolite restore RECEIPT` (c0066) puts the `.bak` files of one receipt back after checking that every written file still has its recorded hash.
- *Errors.* 17 registered codes, `FEN-1001` to `FEN-7003` (`cli/errors.py:28-92`); `FEN-1002`, `FEN-1003` and `FEN-4002` are free. Exit 1 is `FEN-1001`, hint "this is a bug; report it".
- *Long steps.* `route` runs the router in process. KiCadRoutingTools runs one process per net with 600 s each (`routing/plugins/kicad/routingtools.py:58`, `:145`), Freerouting one process with 900 s (`freerouting.py:39`). Nothing is printed while they run, nothing is kept when the process ends early, and no signal is handled.
- *DRC counts.* Now c0141's subject (`CLEARANCE_REPORT_LIMIT = 499`, `backends/kicad/canary.py:53`). Of `check`, this change touches only the progress units: its stages on `dev` are `model.validate`, `erc.kicad`, `copper.clearance`, `zone.fill`, `drc.kicad`, `parity`, `netlist.assignment_compare` and `roundtrip` (`checks/stages.py:33`).

**Bordering changes.** c0108 rejects writing a partial board under `--require-complete` "because a command that reports an error writes nothing today and c0120 makes that an invariant", and leaves "a connectivity stage in `check`, and counts above KiCad's 499" to this change. c0109 bounds a route by one budget, lists `RouterRun`s and says: "c0120 owns progress lines and resumable jobs. The end of a `RouterRun` is the natural progress event." c0116 notes that its `--dry-run` hashes differ from the written ones "until c0120".

**Measured on 2026-10-05**, with the code of the review branch (`27ef3ad7`), `kicad-cli` 10.0.6 (macOS) and 9.0.9 (pinned image), on the review's generated four-layer designs of 100 and 600 parts and on `examples/board_40parts`. The machine ran other jobs (load average 16 to 30), so wall times are upper bounds. Scripts, command lines and outputs are kept with the review's probes. Not repeated on `dev`; measurements 1 to 7 and 11 describe dispatcher and router code that did not change, and each becomes a hermetic test of this change. Measurements 8 to 10 belong to c0141 now and are copied into its design; they stay below so that the numbering of the others holds.

1. *A blocked write.* `fenolite _echo --write blocker/x.txt --confirm --json`, where `blocker` is a file: exit 1, empty stdout, a Python traceback on stderr ending in `FileExistsError` with an absolute path, and no error object.
2. *A build that fails in the middle.* `fenolite build design.py --out proj --confirm` (100 parts) with `proj/lib/` made read-only first: the plan holds 20 files, 2 428 106 bytes, in path order, `.fenolite/` first. The first 8 were written (the seven files of `.fenolite/` and `fp-lib-table`); the ninth, `proj/lib/Capacitor_SMD.pretty/C_0603_1608Metric.kicad_mod`, raised `PermissionError`: exit 1, empty stdout, a traceback, no receipt, no temporary file left. `fenolite check proj` then exits 2 with `FEN-2001` ("holds no .kicad_pro or .kicad_pcb file", an absolute path in the message), and `build --dry-run` plans the 20 files again, 8 of them as overwrites.
3. *A write beside an error.* `_echo --issue error --write x.txt --confirm`: exit 5, `x.txt` written, a receipt.
4. *Export, reviewed then confirmed.* `export <100-part board> --out fab --all --manifest --dry-run`, then `--confirm`, with a logging stand-in in front of `kicad-cli`: each run called `kicad-cli` 5 times (`version` and 4 `pcb export`). 15 of the 17 written files have another SHA-256 than the plan row of the same path: each Gerber holds `%TF.CreationDate,…%` and a `G04 … date …` line, the drill files a date, and the manifest the hashes of both. `--timestamp` does not reach `kicad-cli`.
5. *Fill, reviewed then confirmed.* `fill --dry-run`, then `--confirm`, on the unfilled 100-part board: one refill (`pcb drc`) in each run, 0.9 s and 1.5 s of 5.9 s; here the written bytes equal the plan.
6. *Route, reviewed then confirmed.* The 40-part example, built and placed with `place --strategy grid`, then `route --router freerouting --timeout 600 --dry-run` (29.2 s) and `--confirm` (37.4 s): 39 nets, 342 tracks and 49 vias each time, the written board equal to the plan (`H-G-DSN-REPEAT`); stderr held 0 bytes during both runs.
7. *A stopped route.* The same `route --confirm`, stopped after 12 s by SIGTERM to its process group: return code −15, no stdout, no stderr, the project unchanged; the next call routed from the start (19.3 s). Stopped after 10 s by SIGTERM to the `fenolite` process alone: the Freerouting `java` process kept running, with parent 1.
8. *Check at 600 parts* (c0141; taken before `check` had the stages `erc.kicad` and `parity`, so the time and the process count are those of `27ef3ad7`, not of `dev`). `fenolite check` on the filled 600-part board: 30.3 s, 6 `kicad-cli` processes (`version`, 4 `pcb drc`, 1 `pcb export`) for 7.0 s in all; 897 issues, 168.3 KB; the `drc.kicad` summary gives `unconnected` 499 and `by_type` `silk_over_copper` 199 and `silk_overlap` 199, canary `fired`, and nothing says a count was cut. The board holds 644 open connections (c0108, measurement 4). With `--stages drc.kicad --format concise` (c0066) the reply is 2.2 KB, with the same three counts.
9. *Report limits on 10.0.6* (c0141). Authored benches: a 400 mm square board of format 20241229 with a `{}` project and a rules file, 700 copies of one violation per bench, run with `kicad-cli pcb drc --format json --severity-all`. `clearance` 499; `unconnected_items` 499; `track_dangling`, `via_dangling`, `copper_edge_clearance`, `track_width` (rule 0.2 mm on 0.1 mm tracks), `hole_to_hole` (rule 1 mm), `hole_clearance` (rule 1 mm), `annular_width` (rule 0.15 mm), `silk_overlap`, `courtyards_overlap`, `lib_footprint_issues` and `shorting_items` (two pads of two nets in one footprint) 199 each. With 150 copies, `track_dangling`, `silk_overlap` and `unconnected_items` give 150. `--all-track-errors` leaves `track_dangling` at 199. The line "Found N violations" counts the entries written. The report has no key that marks a type as cut: its keys are `$schema`, `coordinate_units`, `date`, `ignored_checks`, `included_severities`, `kicad_version`, `schematic_parity`, `source`, `unconnected_items` and `violations`.
10. *Report limits on 9.0.9* (c0141). One board holding nine benches of 700 copies, run in the pinned image (34.8 s, emulated) and locally on 10.0.6 (2.1 s): 9.0.9 gives `clearance` 500, `unconnected_items` 499 and 199 for each of `copper_edge_clearance`, `courtyards_overlap`, `hole_to_hole`, `lib_footprint_issues`, `silk_overlap`, `track_dangling`, `track_width` and `via_dangling`; 10.0.6 gives 499, 499 and 199. With c0051's record (9.0.9 reports 499 to 508 `clearance` violations), the limits are per type, independent of each other, and equal on both majors, except that 9.0.9 can pass 499 `clearance` by a few.
11. *Plan sizes.* A dry run of the 600-part build plans 20 files, 12 627 996 bytes (`.fenolite/board.json` 10.0 MB, the board 1.8 MB, `circuit.json` 0.7 MB) in 9.0 s; an export of 600 parts writes 2.6 MB (review's scale record).

## Goals / Non-Goals

**Goals**
- The bytes that `--confirm` writes are the bytes a review saw, and no costly step runs twice for them.
- A command writes all its files or none, and every failure ends in one error object.
- A long step tells its caller that it is alive and how far it is, and a stopped route does not start over.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- New exit codes: the vocabulary 0 to 7 stays closed.

## Decisions

1. **A plan has an id, and its bytes are staged.** Whenever a mutating command plans writes and does not write them (with `--dry-run`, and in the refusal of exit 4), the dispatcher gives the plan an id, `result.plan_id`, and stages the planned bytes in the state folder (Decision 3) under that id. `--confirm --plan ID` writes the staged bytes and does not call the command: measured 4 to 6, the second run costs a whole tool run and, for `export`, gives other bytes. The reply repeats the reviewed `result`, `issues`, `evidence` and `input`, with the receipt; `receipt.plan` holds ID.
   - The refusal of exit 4 (`FEN-4001`) names `--confirm --plan <id>` in its hint, so the id reaches an agent through stderr even when `--fields` dropped `result.plan_id`.
   - Rejected: `--confirm --expect DIGEST`, which runs the command again and writes only when the new plan matches: two runs, and for `export` a refusal every time.
   - Rejected: a plan file in the working folder: a dry run would write into the user's tree, which c0011 ("the only new files are the `.bak` copies") and c0066 Decision 8 rule out.
   - Rejected: the bytes in the envelope: 12.6 MB at 600 parts (measured 11).

2. **What the id binds, and what `--plan` checks.** The id is the first 16 hex digits of the SHA-256 of the canonical JSON of: the command name; its arguments without the run flags; the working folder; the SHA-256 of every file the command declares in `Result.depends`; and, per planned write, its path, kind, size, SHA-256 and the SHA-256 of the file it replaces (`null` when there is none). No clock takes part, so the same dry run on the same files gives the same id.
   - The run flags change how a run happens, not what it plans: `--dry-run`, `--confirm`, `--plan`, `--json`, `--text`, `--fields`, `--limit`, `--cursor`, `--format`, `--progress`, `--seed`, `--timestamp`, `--no-backup`, `--timeout` and `--kicad-cli`.
   - `Result.depends` names the inputs that are not targets, for each of the fifteen mutating commands of `dev`: the design script of `build`, and its copper source when it reads one; the board and the files of its copy set that it read, for `place`, `route`, `fill`, `export`, `render`, `pnp` and `sync`; the board or the root schematic that `bom` read; every design file and artefact manifest that `manifest` hashed; the documents that `kit` packs; the input of `fmt` and `template`; for `restore`, the receipt file, the written files and the `.bak` files it reads; nothing for `_echo`. A target is checked through its own digest. The first design named eight commands; the review of 2026-10-07 found the other seven, and a consistency test now fails for a mutating command whose dry run declares a path that does not exist.
   - `restore` and a replayed plan. The receipt of `--confirm --plan ID` is an ordinary receipt with one more field, `plan`, which takes no part in `receipt.id`; `restore` reads it like any other. The roll back of Decision 6 leaves every earlier `.bak` as it was, so a receipt of an earlier write still restores after a failed one. `restore` is itself mutating: its plan gets an id, and `--plan` then checks the files it would replace.
   - An Altium build that refuses an edited PCB document (`FEN-7001`, exit 7) plans nothing, so there is no id. A document edited in Altium between the review and `--confirm --plan` is a target with another digest: `FEN-4002`, exit 4, and the next dry run gives the refusal of exit 7 with its own hint. The edited-output rule is not weakened: under `--plan` the digest check is at least as strict.
   - `--confirm --plan ID` refuses with `FEN-4002` (exit 4, not retryable), naming the first reason, when: no plan has that id; the folder, the command or its arguments differ; a file of `depends` or a target has another digest than at review; a staged file does not have its planned digest. Nothing is written, and the staged plan stays, except a damaged one. Exit 4 keeps its meaning: nothing was written, confirm again after a review.
   - Rejected: an age limit as the test of staleness: an hour-old plan of an untouched board is still right, and a minute-old plan of an edited one is not.
   - Rejected: binding every file a build reads (imported modules, libraries): unknowable without tracing the script; the targets and the script cover what a review can see.

3. **The state folder.** `fenolite.core.state.state_dir()`: `FENOLITE_STATE_DIR` when it is an absolute path; nothing when it is `off`; else `~/.cache/fenolite/state`, beside the library cache (`backends/kicad/libcache.py:215-221`). It holds `plans/<id>/` and `jobs/<key>/` (Decision 10).
   - A plan is staged in a temporary folder renamed into place. The store keeps at most 16 plans and 512 MiB, dropping the oldest first, and drops plans older than 7 days; a written plan is removed. 16 build plans of 600 parts take about 200 MB.
   - A plan that cannot be staged gives `plan.not-staged` (warning) with the reason, from the new table `cli/codes.py`, and the run goes on: the id is still given.
   - Rejected: the project or output folder (c0066 Decision 8: new files in every output folder). Rejected: the system's temporary folder, which some systems empty between two calls. Rejected: staging only on request (`--stage`): one more habit for every agent, for a cache the user can move or turn off.

4. **A plan that is not staged is planned again and compared.** When ID names no staged plan (staging `off`, a plan pruned, a stage that failed), or names one that holds a deferred write of c0078, which has no bytes before `--confirm`, `--confirm --plan ID` runs the command, and writes only when the new plan has the id ID; else `FEN-4002`. Deferred writes are then resolved as c0078 says, and their declared digests are part of the id. So the id always binds, and the store only saves the second run.
   - Rejected: refusing every plan that is not staged: `fetch` (c0078) and a machine without a writable cache could never use `--plan`.

5. **`--confirm` without `--plan` keeps its meaning**: one run that plans and writes. It is not the defect: the defect is a review followed by a second run. Rejected: making `--plan` mandatory, which breaks every script and the guide's loop. Rejected: reusing a staged plan whose id matches the present call without `--plan`: computing the id needs the run it would save.

6. **Writes are all or nothing.** The dispatcher writes the plan of one command with `core.io.atomic_write_all`:
   - *Prepare:* create the missing parent folders, recording them; write and `fsync` every new content to a temporary file beside its target; keep every existing target and every existing `.bak` by a hard link beside it, or a copy where a link fails.
   - *Commit:* replace the targets with `os.replace` in plan order; then, with backups on, rename each kept target to `<path>.bak`, else remove it.
   - *Roll back* on any exception (`BaseException`, so SIGINT and Decision 8 are covered): put back every replaced target and every `.bak` from its kept link, remove the targets that did not exist, the temporary and kept files and the folders created; then raise `WriteError(path, reason)`, a `FenoliteError` with `cli_code = "FEN-1002"`.
   - The dispatcher prints the envelope (`ok` false, the command's `result` with `plan` and `plan_id`, `receipt` null) and one `FEN-1002` object: exit 1, `retryable` true, the message naming the path relative to the working folder and the system's reason ("permission denied"), no absolute path, the hint "nothing was written; fix the cause and run the same command again". With `--plan`, the stage stays for that retry.
   - *Exit 1.* Exit 1 is "internal failure"; a failed write is one, and `retryable` tells it from a bug. Rejected: exit 3 (it says the input is at fault; a full disk or a held file is not), exit 2 (the command line can be right), a new exit code (the vocabulary is closed).
   - Rejected: a journal that repairs a write cut by SIGKILL on the next run. The replacements take microseconds per file; the temporary files beside the targets show such a cut.
   - `atomic_write` stays for single files.

7. **An error finding plans no write.** The dispatcher plans, stages and writes nothing when the command's issues hold one of severity `error`, unless the command sets `Result.write_on_error`; `place --force` sets it, and nothing else. c0096's constrained strategy refuses `--force` and reports `place.incomplete` as a warning, so it writes under the rule and needs no exception. `result.plan` and `result.plan_id` are then absent and the exit code is 5. Measured 3, the rule is a convention of each command today. c0108 relies on it ("c0120 makes that an invariant"). Rejected: leaving it to the commands, which `_echo` already breaks.

8. **Signals stop the tools.** On POSIX, `main()` turns SIGTERM and SIGINT into `Interrupted`, an exception raised in the main thread. `subprocess.run` kills its child on any exception, and c0109's `Budget.run` does the same, so a stopped `route` stops its router (measured 7: it does not today). The writer rolls back (Decision 6), the job record keeps what finished (Decision 10), and the dispatcher prints the envelope and `FEN-1003` (exit 1, `retryable` true, "stopped by a signal; nothing was written").
   - Rejected: starting tools in their own process group and relying on the caller to stop the group: measured 7, a caller may stop only the parent.
   - Windows: a forced stop (`TerminateProcess`) cannot be handled; a Ctrl+C is.

9. **Progress records on stderr, on request.** The global flag `--progress` turns on a reporter that writes one record per line on stderr. In JSON mode a record is `{"progress": {"command", "event", "step", "index", "total", "detail", "elapsed_ms"}}`, with `event` `step` (a unit starts), `done` (it ends) or `alive`; in text mode a line `progress: <command>: …`. At least one record is written every 10 s while the command runs, from a daemon thread. The error object stays the last line, so "Typed errors on stderr" is modified to say so.
   - Units: one per stage of `check` (`run_checks(…, progress=…)`), one per router process of `route` (Decision 10), the refill of `fill`, one per kind of `export`, one per view of `render`. Other commands give `alive` records only.
   - `fenolite.core.progress.Progress` is a protocol with `step(name, *, index=None, total=None)` and `done(name, *, detail="")`, with `NULL_PROGRESS`; `core` may be imported by `checks`, `routing` and the backends, so the units are reported where they happen. `Context.progress` holds the reporter.
   - Rejected: progress by default: stderr would no longer be one error object for the suites and the recipes that read it so. Rejected: a progress file: a write outside the protocol, and `check` must create nothing. Rejected: relaying the tools' own log lines (measured 6: Freerouting's passes), which no tool keeps stable.

10. **The route job record.** `RoutingJob` gains `on_run: Callable[[FinishedRun], None] | None` and `progress: Progress`. A plugin calls `on_run` once for each process that ended with copper, with that copper, before it starts the next process, and reports each process as a unit. `route` keeps a job record in `<state>/jobs/<key>/`, one file per `FinishedRun`, written with `atomic_write`.
    - *Key:* the first 16 hex digits of the SHA-256 of the canonical JSON of the Fenolite version, the router's name and version, the SHA-256 of the board and of its project file, and the route arguments without the run flags and without `--out`.
    - *Reuse:* when the record exists, `route` reads the board, rips (`--rip`), merges the recorded copper, then selects nets, so the recorded nets are not routed again, with today's selection and with c0108's. `route.resumed` (info) and `result.resumed` (`runs`, `nets`) say what was reused. A record that cannot be read is removed.
    - *End:* the record is removed after a confirmed write (the board then holds its copper, and its digest changes), and after a dry run that attempted every selected net. It stays after a stop, a failed write, and a run that ended its budget (c0109): then the same call, made again, goes on.
    - At most 8 records, none older than 7 days. Only finished processes with copper are recorded: a failed or cut process is routed again.
    - Rejected: resuming inside the plugins: each would need its own store. Rejected: a record for `check`: its longest unit is one tool run or the copper check, which cannot be split (measured 8: 7 s of tools in 30 s).

11. **Report limits per type: moved to c0141.** On 2026-10-07 the maintainer split this decision off (decision 6 of that day). c0141-drc-report-limits holds `DrcLimits`, `LimitedOracle`, `REPORT_LIMITS`, `summary.limits`, `check.report-limit`, the hypothesis `H-K-DRC-LIMITS`, the bench and the modification of "Check output is deterministic". Nothing of it is specified, budgeted or tasked here, and this change does not wait for it. The number 11 is kept so that the other decisions keep the numbers other proposals cite.

12. **Other changes that hold the same requirements** (checked 2026-10-07 on `origin/dev` at `9aba2dff`, and against the review of the 26 proposals of v0.4).
    - "Mutation protocol" and "Typed errors on stderr" (`cli-contract`): the living text is unchanged since this proposal was written, and no open change on `dev` holds a delta of either (c0084, c0091 and c0092 hold other `cli-contract` deltas). Each delta here is the living text of `9aba2dff` with only this change's clauses and scenarios added. No other proposal of v0.4 modifies them; c0078 adds "Deferred writes" beside them.
    - `core-primitives` and `routing`: this change adds one requirement to each ("Atomic writes of several files", "Router runs reported for progress and resumption") and modifies none; "Atomic I/O" and "Router protocol" stay. c0078, c0109 and c0110 modify "Freerouting plugin" (order c0078, c0109, c0110), which this change does not touch: the plugin's calls of `on_run` and of the reporter are stated by this change's own requirement.
    - c0066 (archived): "Receipt identity" and "Restore command" are living; `receipt.plan` is added beside their fields, with a default, through "Staged plans".
    - c0078 adds "Deferred writes" (`PlannedWrite.source`, `FEN-3006`). Order: c0078 first, as the smaller change; task 3.4 then plans deferred writes again under `--plan` (Decision 4). If this change lands first, c0078 regenerates its dispatcher part on "Staged plans" and "All-or-nothing writes": its sources are called before the prepare phase, and a mismatch writes nothing, as both texts say.
    - c0108 relies on Decision 7. c0109: when it lands first, a unit of progress and a `FinishedRun` are a `RouterRun` with outcome `done`, and `Budget.run` reports them; when this change lands first, a unit is one KiCadRoutingTools process per net and one Freerouting run, and c0109 regenerates on "Router runs reported for progress and resumption". `FinishedRun.tier` defaults to 0 until c0109's tiers exist.
    - c0096 edits `cmd_place.py` (the constrained strategy); it sets no `write_on_error` (Decision 7). c0116: `--plan` writes the hashes its dry runs show. c0119: its runner ignores progress lines and reads no plan id.
    - c0079: `describe` lists `--plan` and `--progress` from the parsers, with no change of its own. c0080: every registry code must be on its recovery page, so `FEN-1002`, `FEN-1003` and `FEN-4002` need lines there (task 7.2). `tests/unit/cli/test_explain_cmd.py` on `dev` already fails for a code without a table in `cli/data/explain.toml`: tasks 1.2, 2.2, 3.1, 3.2 and 5.2 add the five tables.

13. **The second backend.** `dev` writes Altium documents (c0084 to c0088). Nothing here is specific to a backend: the dispatcher stages and writes `PlannedWrite`s whatever their kind, so an Altium build gets a plan id, `--plan`, all-or-nothing writes and `FEN-1002` like a KiCad build, and its compound documents, which `build` writes whole, are replaced or kept whole. `build --target altium` declares the same inputs as `build` (the script and the copper source). The edited-document refusal of the Altium build is covered in Decision 2. `route`, `fill` and `check` progress units exist for KiCad boards only, because those commands take KiCad boards. No rule kind, selector or model field is added.

14. **Determinism.** Plan ids, job keys and `receipt.plan` are digests of the inputs. Progress records carry times and go to stderr, which no determinism rule covers. `--seed` and `--timestamp` take no part in the id: under `--plan` the bytes are fixed.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/core/io.py` | `atomic_write_all(writes, *, backup=True) -> tuple[WriteReceipt, ...]`; `WriteError(path, reason)` (`cli_code = "FEN-1002"`) |
| `src/fenolite/core/state.py` (new) | `STATE_ENV = "FENOLITE_STATE_DIR"`; `state_dir() -> Path \| None` |
| `src/fenolite/core/progress.py` (new) | `Progress` (protocol: `step`, `done`); `NULL_PROGRESS` |
| `src/fenolite/cli/plans.py` (new) | `plan_id(...)`, `StagedPlan`, `stage(...)`, `load(id)`, `remove(id)`, `prune()`; `PLAN_KEEP = 16`, `PLAN_BYTES = 512 MiB`, `PLAN_DAYS = 7`; `RUN_FLAGS` |
| `src/fenolite/cli/jobs.py` (new) | `route_job_key(...)`, `JobRecord` (`runs()`, `add(run)`, `remove()`); `JOB_KEEP = 8` |
| `src/fenolite/cli/progress.py` (new) | `StderrProgress(mode, stream, command, interval=10.0)` |
| `src/fenolite/cli/codes.py` (new) | `ISSUE_CODES`: `plan.not-staged` (warning); named in `cli/explain.py::TABLES` |
| `src/fenolite/cli/data/explain.toml` | tables for `FEN-1002`, `FEN-1003`, `FEN-4002`, `plan.not-staged` and `route.resumed` |
| `src/fenolite/cli/api.py` | `Context.progress`, `Context.state`; `Result.depends`, `Result.write_on_error` |
| `src/fenolite/cli/main.py` | `--plan`, `--progress`; ids and staging; `--plan` replay and re-plan; the write through `atomic_write_all`; Decision 7; `Interrupted` and the signal handlers |
| `src/fenolite/cli/output.py`, `schemas/fenolite.envelope.v0.json` | `Receipt.plan: str \| None = None` |
| `src/fenolite/cli/errors.py` | `FEN-1002`, `FEN-1003`, `FEN-4002` |
| `src/fenolite/cli/cmd__echo.py` | `--write` repeatable; `--steps N`, `--sleep S` |
| `src/fenolite/cli/cmd_route.py` | the job record, `result.resumed`, `depends` |
| `src/fenolite/cli/cmd_place.py` | `write_on_error` with `--force`; `depends` |
| `src/fenolite/cli/cmd_build.py`, `cmd_fill.py`, `cmd_export.py`, `cmd_render.py`, `cmd_fmt.py`, `cmd_template.py`, `cmd_bom.py`, `cmd_pnp.py`, `cmd_manifest.py`, `cmd_sync.py`, `cmd_kit.py`, `cmd_restore.py`, `cmd_check.py` | `depends` (every mutating command); progress units (`check`, `fill`, `export`, `render`) |
| `src/fenolite/checks/stages.py` | `run_checks(…, progress=NULL_PROGRESS)` |
| `src/fenolite/routing/protocol.py`, `routing/codes.py` | `FinishedRun`, `RoutingJob.on_run`, `RoutingJob.progress`; `route.resumed` (info) |
| `src/fenolite/routing/plugins/kicad/routingtools.py`, `plugins/specctra/freerouting.py` | progress per process, `on_run` per finished process |
| `tests/unit/core/test_io_all.py`, `tests/unit/cli/test_plans.py`, `test_write_failures.py`, `test_progress.py`, `test_interrupt.py`, `test_route_jobs.py`, `tests/unit/routing/test_finished_runs.py` (new); `tests/consistency/test_cli_consistency.py`; `tests/conftest.py` | hermetic; an autouse fixture sets `FENOLITE_STATE_DIR` to a folder of the test |
| `docs/cli-contract.md`, `AGENTS.md`, `agent/SKILL.md`, `docs/routing.md` | the protocol, the codes, the state folder, the records |

## Hypotheses registered by this change

None. `H-K-DRC-LIMITS` went to c0141 with the report limits. Ids used without changing their level: `H-G-DSN-REPEAT`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| staged plans, `--plan`, `FEN-4002`, the re-plan | mechanical | `test_plans.py`, the consistency suite; `export` with a fake `kicad-cli` that stamps its run |
| all-or-nothing writes, `FEN-1002` | mechanical | `test_io_all.py`, `test_write_failures.py` |
| no write beside an error | mechanical | the consistency suite |
| signals, `FEN-1003` | mechanical, POSIX | `test_interrupt.py` with a fake router |
| progress records | mechanical | `test_progress.py` |
| route job record | mechanical | `test_route_jobs.py` with the fake KiCadRoutingTools |
| `route` results | `UNVERIFIED`, as today | — |

## Risks / Trade-offs

- **Hidden writes in the user's cache.** Every dry run of a mutating command writes there. Mitigation: bounded (16 plans, 512 MiB, 7 days, a written plan removed), named by `FENOLITE_STATE_DIR`, turned off with `off`, and documented; it never holds anything the command did not plan.
- **A stale plan written.** Mitigation: Decision 2 checks every target and declared input. A build reads more than it declares (libraries, imported modules); `--plan` then writes what was reviewed, which is what the reviewer saw.
- **Exit 1 is no longer always a bug.** Agents that stop on exit 1 must read `code` and `retryable`. Mitigation: `AGENTS.md`, the contract page and c0080's recipes say so.
- **A resumed route differs from a fresh one.** Runs made in two calls need not equal one call's runs. Mitigation: `result.resumed` names them; KiCad judges the board as always.
- **Hard links.** Some file systems refuse them. Mitigation: a copy, at the cost of reading each replaced file once.
- **A thread in the CLI.** The heartbeat writes from a daemon thread. Mitigation: one lock around stderr; the thread stops before the envelope is printed.

## Migration Plan

- Additive for callers that ignore the new keys: `result.plan_id`, `receipt.plan`, `result.resumed`, `route.resumed`, `plan.not-staged`, two flags, three codes.
- Behaviour changes: a failed write gives an envelope, an error object and no change, instead of a traceback and part of the files; a command that reports an error writes nothing, `place --force` excepted; a stopped `route` stops its router.
- `CHANGELOG.md` says all of it, and that dry runs now write under `~/.cache/fenolite/state`.
- No file format and no model change, so model documents of every release are read and written as before. The envelope schema gains `receipt.plan` with a default: an envelope of 0.2.x or 0.3.0 still validates. Reverting a part removes its code; the store and the records can be deleted at any time.

## Budget (6.0 days)

| part | days |
|---|---|
| entry check; the test ground (state folder fixture, `_echo --steps`, `--sleep`, repeatable `--write`); the loop test on real tools | 0.5 |
| all-or-nothing writes: `atomic_write_all`, rollback, `FEN-1002`, the dispatcher | 0.75 |
| no write beside an error, `write_on_error` | 0.25 |
| signals and `FEN-1003` | 0.25 |
| staged plans: state folder, id, store, pruning, `--plan`, checks, `FEN-4002`, receipt, `depends` in the fifteen mutating commands | 1.5 |
| the re-plan of plans that are not staged, deferred writes | 0.25 |
| progress: protocol, flag, records, heartbeat, units in five commands, "Typed errors on stderr" | 0.75 |
| route job record: plugin calls, record, reuse, removal | 0.75 |
| documentation, the five `explain.toml` tables and closing | 1.0 |

Cut order: (1) the heartbeat (`alive` records); (2) the units of `fill`, `export` and `render`; (3) the re-plan of Decision 4 (a plan that is not staged then gives `FEN-4002`); (4) the route job record (a cut route then goes on through c0108's selection after a confirmed write; a stopped one starts over). Never cut: staged plans with `--plan`, all-or-nothing writes, no write beside an error, signals.

## Open Questions

- **Staging by default.** Default: on, in `~/.cache/fenolite/state`. The maintainer may prefer it off until asked, at the cost of one more flag in every loop.
- **One cache root.** c0078 puts fetched tools under the platform's cache folder (`~/Library/Caches` on macOS); the library cache and this state folder use `~/.cache/fenolite`. Default: follow the library cache; one rule for all three is a later decision.
- **Progress on a terminal.** Default: only with `--progress`. Text mode on a terminal could turn it on by itself.
- **The exit code of a failed write.** Default: 1 with `FEN-1002`, retryable. Exit 3 would match `FEN-3001`'s hint ("check the path and permissions").
- **Record runs that failed.** Default: no; they are routed again on the next call, which may fail again in the same way.
