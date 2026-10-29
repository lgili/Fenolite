## Why

The maintainer asked on 2026-10-28 for a stable Python API before the v1.0 freeze (`docs/roadmap.md`,
phase 5: "freeze: CLI, envelope and schemas `v1`"). `fenolite.api` holds only `equivalent` and `convert`
today. Analyses, checks, placement, routing and exports are reachable only through the command line, so a
Python caller (a notebook, a test bench, the MCP server of c0195) starts `python -m fenolite ... --json` as a
child process and parses stdout: a process per call, the process's working folder, and stdout that any
print would corrupt.

## What Changes

- `fenolite.api.run(command, *args, cwd=None, seed=None, timestamp=None) -> Reply`: any command in the
  process, through the dispatcher of `fenolite`. `Reply` holds the exit code, the envelope and the error
  object exactly as `--json` prints them. Nothing is printed, no signal handler is installed, the process's
  working folder is not changed, and the mutation protocol is the command line's.
- The dispatcher of `fenolite.cli.main` builds a reply value and `main` prints it; `invoke` returns it as
  JSON values. Every CLI test stays green.
- Typed calls that return records, not dictionaries: `read_design` (`ReadSide`), `read_board` (`Board`),
  `connectivity` (`ConnectivityReport`), `analyze_current` and `analyze_distances` (`AnalysisReport`).
- `docs/api.md` lists every public name of `fenolite.api`, frozen for 1.0, and a test keeps it complete.
- Package layering: `api` may import `cli` inside a function body only (`run`), a new `LAZY` table of the
  layering test.

## Capabilities

### New Capabilities

- `python-api`: "In-process command runner", "Mutation protocol in process", "In-process limits", "Typed
  design and board reads", "Typed board analyses" and "API reference page".

### Modified Capabilities

- `package-layering`: one ADDED requirement, "Public API runs the commands lazily". "Allowed import edges"
  is left as it is: the new requirement is the one exception to its `api` row.

## Non-goals

- Typed functions for every command: `run` covers them all; the typed list stays short so that it can be
  frozen.
- A progress callback for `run`: `--progress` records are dropped in process.
- Moving the MCP server (c0195, another branch) onto `run`: its own change decides.
- Schemas `v1`: the freeze change.

## Evidence level required

None new: `run` returns the replies of the commands with their own evidence, and the typed calls return the
reports of `fenolite.analysis` unchanged. No `INFERRED` value is added.

## Impact

- `src/fenolite/api/commands.py`, `src/fenolite/api/board.py`, `src/fenolite/api/__init__.py`.
- `src/fenolite/cli/main.py` (the reply value, `invoke`, the in-process parser), `src/fenolite/cli/api.py`
  (`Context.in_process`), `cmd_restore.py` and `cmd_view.py` (the two refusals).
- `tests/consistency/test_api_run.py`, `tests/unit/api/test_run_api.py`, `tests/unit/api/test_board_api.py`,
  `tests/unit/test_import_graph.py`.
- `docs/api.md`, `docs/cli-contract.md` (one line under "Output"), `CHANGELOG.md`.
