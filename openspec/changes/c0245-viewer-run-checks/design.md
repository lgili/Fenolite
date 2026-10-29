## Context

- **What exists** on `dev` at `5191911`:
  - `fenolite.view.server` (`Live`, `serve`, `run`): stdlib `ThreadingHTTPServer` on `127.0.0.1`; `GET` of
    the page, `/project.json`, `/scene/<id>.json`, `/version/<id>`, `/marks`; one write, `POST /marks`,
    accepted only when the `Host` is this server's (`127.0.0.1:<port>` or `localhost:<port>`), the `Origin`
    (when sent) is the same, the header `X-Fenolite-Review: 1` is present, the type is JSON and the body is
    at most 64 KiB. A page of another site cannot send that header without a preflight, which the server
    never answers. `Live` receives its scene builder and refiner from `cmd_view` (callables), because
    `view` may import only `model`, `geometry` and `backends` (`tests/unit/test_import_graph.py`).
  - `cmd_view.check_reply(argument, …)` runs `check` in process for `--check run` on the project file, else
    the document; `_with_check` places a reply with `check_overlay.overlay`; `project_review.status(scene,
    check, reports)` composes the cards (`CATEGORIES` maps each card to its stages); `overlay_files` turns an
    `analyze` reply into finding groups.
  - `fenolite.mcp.backend.FenoliteBackend(commands, root=, timeout=, read_only=, only=)`: a catalog of typed
    tools built from the commands' parsers (`fenolite.mcp.tools.Catalog`), and `call(name, arguments,
    call)` that runs `python -m fenolite <command> --json [--progress] …` in `root`, in its own process
    group with stdin closed, stops it on `call.cancelled` or after the timeout (terminate, then kill; reply
    `FEN-1003`), reports `--progress` records through `call.progress`, and returns the envelope or the error
    object with the exit code in `_meta["fenolite/exit"]`.
  - `fenolite.api.run` runs a command in process; it cannot be stopped from another thread, so it is not
    used for runs the user may cancel (see Decision 3).
  - Page: `buildProjectReview()` draws the cards from `S.project_review` (or a fallback of not-run cards),
    `REVIEW.items` from `S.check.findings` and operation findings; Messages from `S.check`; Findings from
    `S.overlays` and their groups.
- **Constraint:** the review requirement keeps "no checks on opening"; nothing runs unless the user asks.

## Goals / Non-goals

- **Goals:** every card that can be computed by a read-only command can be run from the page; a run can be
  watched and stopped; its results land where the user already looks; nothing outside an allow-list runs.
- **Non-goals:** the proposal's.

## Decisions

### 1. Routes

- `GET /runs` → `{"enabled": bool, "reason"?: str, "commands": {name: {"options": {...}}}, "busy": job|null}`:
  what the page may offer for the server (`--no-run` gives `enabled: false` with the reason).
- `POST /run` with `{"command": "check", "doc": "<id>", "options": {"stages": ["drc.kicad"]}}` → `202
  {"job": "<id>"}`; `409` with the running job when one runs; `400` for a command, document or option the
  allow-list refuses; `403` for a failed guard; `413` above 16 KiB.
- `GET /run/<job>` → `{"state": "running" | "done" | "failed" | "cancelled" | "timeout", "command",
  "doc", "started", "elapsed", "progress": [last 50 records], "exit"?: int, "envelope"?: {...},
  "error"?: {...}, "review"?: {...}, "check"?: {...}, "overlays"?: [...]}`. Finished jobs are kept until
  the next run of the same document and command (at most 16 jobs).
- `POST /run/<job>/cancel` → `202`; the job ends `cancelled`.
- Guard of every `POST`: the `/marks` guard factored into one function `_guarded(handler, header)`, with
  the header `X-Fenolite-Run: 1` for runs. `GET /run/<job>` needs no guard (it only reads what this page
  started; ids are 128-bit random).

### 2. The allow-list

`fenolite.view.runs` (new, standard library only) holds `ALLOWED`, the commands and the options the page
may set, and `request(body, tree) -> RunRequest | RunRefused`, which validates a body into `(command, path,
arguments)`:

| command | target | options from the page |
|---|---|---|
| `check` | the project file, else the document (as `--check run`) | `stages`: names of the default stages, or of the document stages for Altium input; never `exclude`, `reason`, `kicad_cli` |
| `analyze` | the board document | `kinds`: names of `KINDS` and `OPT_IN_KINDS` |
| `ready` | the KiCad project file or board | `no_kicad`: bool |
| `equivalent` | the document as A | `b`: another document id of the tree; `level`: an integer level; `frame`: one of the command's frames |

The path is the tree's file of the document id: present, viewable or a project file, and under the tree's
root (the tree already lists paths that leave the project as not present). Option values are checked by type
and against the command's own choices, which the module reads from constants the view may import, or that
`cmd_view` passes in when they live in `cli` or `checks`. Unknown keys refuse the request. The JSON
arguments go to the MCP catalog's `command_line`, which builds the words from the parser, so no word of the
request reaches the command line unparsed.

### 3. The runner, injected

`Live` gains `runner: Runner | None` (a protocol of `view.runs`: `start(request, on_progress) -> Handle`
with `cancel()`, `wait()`), built in `cli/_viewrun.py` (new) around
`FenoliteBackend(discover(), root=tree.root, timeout=args.run_timeout, read_only=True, only=ALLOWED)`.
A job runs in a daemon thread that calls `backend.call(tool, arguments, call)` with a `Call` whose
`cancelled` event the cancel route sets and whose `progress` appends to the job's records. The child process
gives a true cancel and timeout (process group terminate then kill, `FEN-1003`), a crash cannot take the
server down, and the progress records are those of `--progress`. `view` imports nothing new: the runner is
passed in, as the scene builder is. With `--no-run`, or in a test that passes none, `/run` answers 403 and
`GET /runs` says why.

### 4. Results

When a job ends with exit 0 or 5 the server derives, under `Live.lock`:
- `check`: `check_overlay.overlay(reply, scene)` and `project_review.status(scene, merged, reports)`, where
  `merged = project_review.merge(previous, reply)` (new): stages of the new reply replace the stages of the
  same name, with their findings; other stages stay with their own input hash, so a stage run on an older
  revision shows Limited. The merged reply is kept per document in `Live` and replaces the `--check` reply
  for that document for the rest of the session.
- `analyze`: the finding groups of `overlay_files`' row logic, moved to `view.findings`-level helpers or
  passed in by `cmd_view`, tagged `run:analyze`.
- `ready`, `equivalent`: their issues, each with a location from `check_overlay`'s finders when it names a
  part, pad or net.
The page fetches the job, sets `S.check`, `S.project_review` and the run overlays, and redraws through the
existing builders (`buildProjectReview`, `buildMsgList`, the Findings section). Findings are never marked
fixed; the next run replaces them.

### 5. Page

- A **Run** control on each card whose stages the server offers (Netlist connectivity → `parity`,
  `netlist.assignment_compare`; ERC; DRC; Copper clearance; Placement rules; Zone fill; Model validation);
  **Run all checks** runs the default stages. Conversion and Fabrication export stay recorded-only (their
  commands write; c0246).
- A **Run** menu in the Tools group and palette commands: Run checks…, Analyze…, Readiness, Compare with….
  The forms list only the options of `GET /runs`.
- A run strip under the toolbar: command, current stage from the last progress record, elapsed time,
  Cancel; one run at a time, other Run controls disabled while it runs. Polling every 500 ms uses the
  navigation guard: results of a document that is no longer current are stored, not drawn.
- Failures show the error object's `message` and `hint`; exit 6 (`kicad-cli` missing) says which stages
  could not run; `cancelled` and `timeout` say that nothing changed.
- Exported pages and pages served with `--no-run`: no Run control; the card text keeps telling how to
  supply recorded results.

### 6. CLI

`fenolite view` gains `--run-timeout SECONDS` (default 600, above 0, `--serve` only) and `--no-run`
(`--serve` only). Each without `--serve` is `FEN-2001`. The reply's `result.serve` gains `runs`, the count of
runs by final state. The agent guide gains a tested line for both options and
`tools/gen_agent_guide.py` regenerates the command guide.

### 7. Tests

- `tests/unit/view/test_runs.py` (new): the allow-list accepts each table row and refuses unknown
  commands, unknown options, `exclude`, paths, document ids of missing or outside documents.
- `tests/unit/view/test_server.py`: guard refusals (Host, Origin, missing header, type, size), 409 while a
  fake runner blocks, cancel ends `cancelled`, a fake reply fills `review` and `check`, `--no-run` gives 403,
  a stale document's result does not replace another's; one integration test with the real runner on a copy
  of `two_layer.kicad_pcb` runs `check --stages model.validate,copper.clearance` and gets the review cards
  of those two stages.
- `tests/unit/view/test_project_review.py`: `merge` replaces stages by name and keeps the input hash of each.
- `tests/unit/cli/test_view_cmd.py`: `--run-timeout` and `--no-run` without `--serve` are `FEN-2001`.
- `tests/visual/test_run.py` (new, stubbed `fetch` as in `test_navigation.py`): Run on the DRC card shows
  the strip, progress and Cancel; a stubbed reply turns the card Failed and adds markers; a cancelled run
  leaves the cards as they were; an exported page shows no Run control.

## Security

- Loopback only, as today; no new listening socket.
- Every `POST` carries the custom header and passes the Host and Origin checks, which blocks other sites
  (no preflight answered) and DNS rebinding (Host check).
- Only allow-listed read-only commands run (the catalog is built `read_only=True` and `only=ALLOWED`), only
  on files of the tree, with options checked by type; no command line, path or environment comes from the
  page.
- One run at a time and a timeout bound the cost; a run is a child process, so a fault in a command cannot
  corrupt the server.

## Risks / Trade-offs

- **Child process start-up** costs about a second per run compared with an in-process call; the price of a
  real cancel and timeout, and the same path the MCP server already proves.
- **Reusing `fenolite.mcp`** from `cli/_viewrun.py` ties the viewer's runner to the MCP catalog; if that
  coupling is unwanted, the runner core (`_run`, `_wait`, `_stop`, `_stderr`) can move to a shared
  `fenolite.cli.childrun` module used by both, as the first task decides.

## Open Questions

- Should runs be on by default in `--serve` (as designed, with `--no-run`), or off by default behind
  `--allow-run`?
- Is 600 s the right default timeout for a page run (the MCP default), given that `drc.kicad` on a large
  board may need more?
- Should the merged session results be written anywhere (for example a `--check` file to reopen later), or
  stay in the server's memory (as designed)?
