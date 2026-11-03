## Why

Fenolite's first user is an AI agent, and nothing measures whether an agent can use it. The one recorded session (`docs/release/v0.1.md`, "Manual checks") was run once by hand: a new session, given the guide, took a finished example through five commands. It started from a script that already existed, it is labelled `UNVERIFIED`, and no command repeats it.

So every decision about the guide, the hints and the commands is a guess. A check made by hand on 2026-10-05 found, in a few minutes, that a board made from the built-in catalog could never pass `check` (c0077) and that no router was usable on a new machine (c0078). Both had passed every test, and both are still so on `dev` at `9aba2dff`.

The v0.1 acceptance had one such item (`docs/roadmap.md`, Phase 2, item 7): "An agent completes the loop on the small example in 10 turns or fewer, every output labelled". Nothing measures it. This change turns it into a tool.

## What Changes

- **Tasks.** Five authored tasks under `tools/agent_eval/tasks/`, each a requirement in plain words with what a correct result holds: the nets as groups of `REF-PIN` (a part's reference and a pin number of its symbol), a board size, the files to produce.
- **A judge.** `tools/agent_eval/judge.py` decides a run with Fenolite itself: `fenolite check` exits 0, the nets of the built project form the expected groups, the board fits, the files exist. Without `kicad-cli` the verdict is `unjudged`, never `passed`.
- **A call log.** A shim named `fenolite`, first on `PATH`, records every call the agent makes: arguments, exit code, error code, time.
- **A runner.** `tools/agent_eval/run.py --task NAME --runner NAME` installs the built wheel in a fresh environment, makes an empty work folder outside the repository, installs the skill as an outside user would, starts the agent with the task's prompt and a time budget, then judges and writes `result.json`.
- **Reference solutions.** Each task has a solution that a `replay` runner plays without any agent. The suites run them, so a task that Fenolite can no longer solve fails CI.
- **A record.** `docs/evidence/agent-eval.md` holds one row per run: date, commit, runner, model, task, verdict, calls, minutes and the first call that failed.
- **Cost control.** A real agent runs only when a person asks, one task by default, never in CI.

Milestone: v0.4 (the agent track). Size: 6.75 design-days.

## Capabilities

### New Capabilities
- `agent-eval`: tasks, judge, call log, runner, reference solutions and the evidence page.

### Modified Capabilities
None.

No requirement name of `agent-eval` exists in a living spec or in an open change on `dev` at `9aba2dff`.

## Non-goals

- No agent in CI and no API key in the repository.
- No ranking of models or agents.
- No judgement of a circuit's merit: the tasks prescribe the netlist.
- No sandboxing of the agent beyond an empty work folder and a clean environment; the record says so.
- No task that needs a KiCad library or a router download.
- No transcript in the repository.
- No Altium target in a task: the judge reads a KiCad project. A task for `build --target altium` waits for a way to judge one without the vendor's tool.

## Evidence level required

- Judge, call log, runner and tasks: mechanical, proved by hermetic tests. Each reference solution is judged through `fenolite check` on the `kicad-10` job (`KICAD-VERIFIED`).
- A run with a real agent is a dated measurement with its commit, runner version and model. It supports no release claim until a release change defines a gate.

## Prerequisites

- `0.3.0` is released from `dev` first, with c0123 in it: c0123 lets one pin hold several pads, and the judge's `nets` check and the task `custom-footprint` are written for the model as c0123 leaves it.
- c0077 and c0079 are archived: a catalog board that passes `check`, `fenolite init`, `fenolite skill install`.
- The harness and the first batch come before c0080; the second batch comes after it.
- c0097 (board authoring) changes what a `copper.short` finding carries. The task `fix-short` builds its starting project on the code under test, so it needs nothing of c0097 and follows it when it lands.
- c0078 only for a later sixth task; nothing of c0096 or c0099; no other proposal of v0.4.
- **The maintainer.** Tasks 4.2 and 4.3 are runs with a real agent, which cost money and which only the maintainer starts. The change cannot be archived before he has run the first one or decided not to.

## Impact

- New: `tools/agent_eval/` (`run.py`, `judge.py`, `shim.py`, `tasks.py`, `runners.toml`, `tasks/`), `docs/evidence/agent-eval.md`, `tests/unit/test_agent_eval.py`, `tests/kicad/acceptance/test_eval_solutions.py`, a `make agent-eval` target.
- No change to the package.
- One source id, S-0618, reserved for the public page that documents the non-interactive mode of the first real runner.
- No error code, no issue code, no command-line flag of `fenolite`, no model key. The files of the tasks live under `tools/`, not under `tests/data`, so `tests/data/MANIFEST.toml` does not change.
- Running cost: one agent session per task and run, bounded by the task's minutes. The harness prints the budget before it starts.
