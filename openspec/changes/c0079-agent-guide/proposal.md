## Why

Fenolite is written to be driven by AI agents, and an agent that installs it gets nothing that says how. `agent/SKILL.md` is in the repository root: the wheel holds `src/fenolite` only, and the source distribution's allowlist does not name `agent/`. The guide's ten commands run on `examples/blink_2layer/design.py`, which exists only in a checkout and takes its parts from `tests/data/libs`, and its fifth line needs Freerouting. So `pip install fenolite` gives an agent `--help` and no first project.

Discovery does not answer an agent's first questions either. Measured on `dev` at `9aba2dff` on 2026-10-07: `fenolite capabilities --json --no-tools` prints 20.7 kB, of which the evidence matrix is 12.1 kB, the experimental writers 3.4 kB and the commands 3.1 kB. It names 30 public commands, none with a summary or an argument, and says nothing of router availability. On 2026-10-05 the same reply was 5.4 kB with 13 commands: the first reply grows with every change.

The project plan put the guide inside the package and decided "skills and the command line first". This change does that. The command descriptions it adds are also what a later MCP server can be generated from; that server stays in v0.5b and is no part of this change.

## What Changes

- **The guide ships.** `src/fenolite/agent/` holds `skill/SKILL.md`, `skill/references/` and `starters/`; `fenolite.agent.guide` reads them. The root `agent/` folder goes away.
- **`fenolite guide [TOPIC]`** prints the list of pages or one page of the installed version.
- **`fenolite skill show|install`** copies the packaged skill to the folder an agent reads (`--agent claude-code`, or `--dir DIR`), through the mutation protocol, and can add a pointer section to a project's `AGENTS.md`.
- **`fenolite init DIR`** writes a starter `design.py` that names only catalog parts and that the built-in router closes.
- **`capabilities --brief`**: commands with a one-line summary, the build targets, tools, router availability, guide pages and starters, in a reply whose size a test bounds (at most 11.9 kB for 33 commands, against 20.7 kB of the default view today). **`capabilities --command NAME`**: that command's arguments as data, from `fenolite.cli.describe`.
- **`Result.text`** lets a command print its own text in text mode.
- **The loop block of the guide** becomes ten commands that run anywhere KiCad is installed: `capabilities --brief`, `init`, `build`, `place`, `route --router direct`, `fill`, `check`, `export`, `render`. Tests run it on both KiCad majors. `inspect`, the tenth line of today's block, moves to the page's section on small questions, with the other reading commands that c0066 added.
- **One name for it.** This is the agent guide. The word "kit" belongs to the Altium verification kit (`fenolite kit`, c0091), which is unrelated; the start page says so in one sentence.

Milestone: v0.4 (the agent track). Size: 8.25 design-days.

## Capabilities

### New Capabilities
- `agent-guide`: the packaged skill, pages and starters, their loader, and the proof that the starter passes `check`. c0080 adds the written pages to the same capability.

### Modified Capabilities
- `cli-contract`: ADDED "Command text", "Command description", "Brief capabilities", "Command view of capabilities", "Guide command", "Skill command", "Init command".
- `release-gate`: MODIFIED "Agent guide is executable" (the file's place, the block, where it runs).

The MODIFIED delta is the living text of `release-gate` at `9aba2dff` with only this change applied. No open change on `dev` holds a delta of that requirement (c0136 modifies "Version 0.2.0" only), and no other proposal of v0.4 modifies it. The seven ADDED names are free in the living `cli-contract` and in every open change on `dev`.

## Non-goals

- No MCP server: it stays in v0.5b.
- No guide content beyond the start page: c0080 writes the pages.
- No change of the default `capabilities` result: `backends`, `experimental`, `matrix` and the other keys stay.
- No per-command result schemas.
- No agent in the table without a registered public source for its folder, and no install into a home folder by agent name: `--dir` takes any folder.
- No change to `examples/`, to the acceptance loop on them, or to `fenolite kit`.
- No change to a build: nothing here touches the KiCad or the Altium writers, the rules or the model.

## Evidence level required

- Loader, commands, descriptions and the brief view: mechanical, proved by unit tests and the consistency suite.
- The starter: hermetic build and copper check at the board read's level (`INFERRED`); the whole loop `KICAD-VERIFIED` on 9.0.9 and 10.0.6 (`H-K-GUIDE-STARTER`).
- The wheel's contents: the `wheel` CI job.
- Whether agents succeed with the guide is measured by c0081.

## Prerequisites

- `0.3.0` is released from `dev` first. c0092 (open on `dev`) edits `agent/SKILL.md` and decides which Altium write kinds leave `experimental`; the start page of this change is written from the status that c0092 leaves, and moves the file that c0092 edited.
- c0077 is archived: the starter names only catalog ids and must pass `check`.
- c0078 is optional: the start page names `fenolite fetch freerouting` only when c0078 is archived.
- c0096, c0097 and c0099 are not needed. Whichever of them is on `dev` when this change is implemented shows up in the command descriptions by itself (`place --strategy constrained|manual` of c0096), because they are read from the parsers.
- Waiting for this change: c0080, c0081, and the guide tasks of c0108, c0111 and c0120, which name `agent/SKILL.md` and must follow the move.

## Impact

- New: `src/fenolite/agent/` (package and data), `src/fenolite/cli/describe.py`, `cli/cmd_guide.py`, `cli/cmd_skill.py`, `cli/cmd_init.py`, tests under `tests/unit/agent/` and `tests/kicad/acceptance/`.
- Moved: `agent/SKILL.md` to `src/fenolite/agent/skill/SKILL.md`; `README.md`, `AGENTS.md`, `tests/unit/test_agent_skill.py` and `tests/routing/test_acceptance_loop.py` follow.
- Changed: `cli/api.py`, `cli/main.py`, `cli/output.py`, `cli/cmd_capabilities.py`, `cli/cmd__echo.py`, `docs/cli-contract.md`.
- One source id, S-0610, reserved for the public page that documents the first row of the agent folders table.
- No error code and no issue code is new, so `explain.toml` gains no table. No model key is new: projects and model documents of 0.2.x are untouched.
