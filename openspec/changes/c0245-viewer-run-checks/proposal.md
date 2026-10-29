## Why

The viewer's Project review lists Read document, Netlist connectivity, ERC, DRC, Copper clearance, Placement
rules, Zone fill, Model validation, Conversion and Fabrication export. On a document opened without
`--check` every card but the first says "Not run", and the panel tells the user to run `fenolite check` in a
terminal and reopen the page with `--check FILE`. The checks exist and are read-only; the page simply cannot
ask for them. A reviewer who finds a problem on the board cannot confirm it with DRC from where he looks.

## What Changes

- **Run from the page.** In `fenolite view --serve`, each review card gets a Run control, and a Run checks
  entry (palette and review panel) runs `check` with the stages the user picks. The tools menu also runs
  `analyze --kinds ...` (its clearance, creepage and connectivity paths become finding groups), `ready` for
  a KiCad project and `equivalent` of the open document against another document of the tree.
- **Progress and cancel.** A run shows its stage progress, elapsed time and a Cancel control; one run at a
  time per server. A cancelled or timed-out run changes nothing and says so.
- **Results where they belong.** A `check` reply fills the review cards (stage by stage, merged with
  earlier runs of other stages) and the Messages markers; `analyze` fills Findings; `ready` and `equivalent`
  show their findings with Locate. Results stay bound to the input hash: a later save makes them Limited, as
  "Project review status and finding workflow" requires.
- **Server.** `POST /run`, `GET /run/<job>` and `POST /run/<job>/cancel`, behind the same loopback, Host,
  Origin, header and size guard as `POST /marks`. The server accepts a command name from an allow-list, a
  document id of the tree and typed options, never a command line or a path. Each run is the command line
  `python -m fenolite <command> --json --progress` in a child process in the project folder, through the
  runner that `fenolite mcp` uses (timeout, cancel by process group, progress records).
- **CLI.** `fenolite view --serve` gains `--run-timeout SECONDS` (default 600) and `--no-run`. Exported pages
  show recorded results only; their Run controls are absent.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-viewer`: run requests, the allow-list, the run guard, progress and cancel, results in the review and
  findings, runs only from a live server, runs only on request.
- `cli-contract`: `fenolite view --run-timeout` and `--no-run`.

## Non-goals

- No writing command, not even `check --exclude`: writes are c0246, behind `--allow-actions`.
- No run when a page opens or a file is saved: every run is a user's request (the review requirement's
  "without running checks on opening" stands).
- No `--kicad-cli`, `--requirements` or other path argument from the page; the server's environment decides
  which `kicad-cli` runs, as for the command line.
- No remote access: the server still binds `127.0.0.1` only.

## Evidence level required

A run adds no fact: each reply keeps its own `evidence.level` per stage (`KICAD-VERIFIED(kicad-cli …)` for
the KiCad stages, Fenolite's own labels for the rest) and the page shows it unchanged. The server routes are
proven by unit tests with a fake runner and by one integration test that runs `check --stages
model.validate,copper.clearance` (no `kicad-cli` needed) through the real child-process runner; the page by
Chromium tests in `tests/visual` with stubbed routes, in the `viewer` CI job.
