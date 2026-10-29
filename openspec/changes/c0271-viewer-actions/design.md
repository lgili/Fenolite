## Context

- **Depends on c0270:** the run routes, the guard function, the jobs of `Live`, the child-process runner
  of `cli/_viewrun.py` (timeout, cancel, progress) and the run strip of the page. Uses c0269's inspector
  for the part and finding actions and c0268's command registry and palette.
- **What exists** on `dev` at `5191911`:
  - The mutation protocol (`docs/cli-contract.md`, "Staged plans"): a writing command without `--confirm`
    plans and writes nothing (exit 4, or 0 with `--dry-run`) and returns `result.plan` with `plan_id`; the
    plan's bytes are staged in `plans/<id>/` of the state folder (`fenolite.cli.plans.stage`, `load`,
    `StagedPlan.data(row)`); `--confirm --plan ID` writes those bytes without running the command again and
    refuses with `FEN-4002` when a target or an input changed; every write keeps a backup unless
    `--no-backup` and returns a `receipt` (files, SHA-256, backups); `fenolite restore RECEIPT` puts the
    backups back when every written file is still as the write left it, and is itself a confirmed write.
  - `FenoliteBackend._plan_refusal`-like logic of the MCP server: a confirm is refused unless the staged
    plan is a plan of the same command whose every write lies under the root.
  - The MCP catalog leaves `check --exclude` and `--reason` out of its tool (`READ_TOOLS`), so actions build
    their words from their own templates (Decision 2) and use only the runner core.
  - `fenolite.view.compare.compare(new, old)` gives the board changes (added, removed, moved, changed parts,
    zones) that the page draws for `--compare` (`S.diff`, `drawDiff`, `buildDiffList`).
  - Commands: `fill PATH`, `tidy PATH [--prune] [--straighten] [--chamfer [--zones]] [--gate drc]`,
    `silk PATH [--designators [--keep]] [--clip]`, `testpoints PATH --place [--grid L] [--size L]`,
    `place PATH --move REF=X,Y[,ROT[,SIDE]]` (board frame: from the outline's top-left corner, Y down, the
    viewer's frame), `place PATH --shift REFS --by DX,DY`, `place PATH --turn REFS --about X,Y --angle A`,
    `check PATH --exclude CODE:ITEM_A:ITEM_B --reason TEXT` (KiCad only), `export PATH -o DIR [--gerbers]
    [--drill] [--pos] [--pdf]`, `bom PATH -o FILE`, `restore RECEIPT`.

## Goals / Non-goals

- **Goals:** the common fixes of a review done from the page, each one reviewed on the board before it is
  written, each undoable, none possible unless the user started the server for it.
- **Non-goals:** the proposal's.

## Decisions

### 1. Routes

- `GET /actions` → `{"enabled": bool, "reason"?: str, "token"?: str, "actions": {name: {"options": …,
  "available": bool, "why"?: str}}}`; the token is a 128-bit random value created when the server starts and
  is returned only to a request that passes the guard with `X-Fenolite-Action: 1`.
- `POST /action/plan` `{"action", "doc", "options", "target"?}` → `202 {"job"}`: the dry run.
- `POST /action/confirm` `{"job"}` → `202 {"job"}`: `--confirm --plan <plan_id of that job>`.
- `POST /action/undo` `{"receipt": "<receipt id>"}` → `202 {"job"}`: the dry run of `restore` on a receipt
  of this session; its confirm uses `/action/confirm` like any plan.
- Jobs share the c0270 job table and its one-at-a-time rule (a run and an action exclude each other);
  `GET /run/<job>` reports them. A finished plan job adds `plan` (writes, issues, `plan_id`) and `preview`.
- Guard: c0270's guard with the header `X-Fenolite-Action: 1` and the header `X-Fenolite-Token: <token>`.
  Without `--allow-actions` every action route answers 403 and `GET /actions` says why.

### 2. The action allow-list and templates

`fenolite.view.actions` (new, standard library only) holds `ACTIONS`: per action, the command, a template
of words and the typed options. The server never accepts words:

| action | words | options |
|---|---|---|
| `fill` | `fill PATH` | none |
| `tidy` | `tidy PATH [--prune] [--straighten] [--chamfer [--zones]] [--gate drc]` | booleans; `gate_drc` on by default |
| `silk` | `silk PATH [--designators [--keep]] [--clip]` | booleans |
| `testpoints` | `testpoints PATH --place [--grid L] [--size L]` | lengths |
| `waive` | `check PATH --exclude CODE:A:B --reason TEXT` | `finding`: index of a `drc.kicad` finding of the session reply (code and items taken from it); `reason`: 1 to 300 printable characters, no line break |
| `move` | `place PATH --move REF=X,Y,ROT[,SIDE]` | `ref` of the board's parts; lengths; angle; side |
| `shift`, `turn` | `place PATH --shift REFS --by DX,DY`, `place PATH --turn REFS --about X,Y --angle A` | refs of the board's parts; lengths; angle |
| `export` | `export PATH -o DIR [--gerbers] [--drill] [--pos] [--pdf]` | kinds; `out`: a relative folder |
| `bom` | `bom PATH -o FILE` | `out`: a relative file ending in `.csv` |

Lengths match `^-?\d+(\.\d+)?(mm|mil|um)$`, angles `^-?\d+(\.\d+)?$`, references the tree's scene parts.
An output path must be relative, without `..` or a drive, resolve under the project root (symlinks
resolved) and default to `fab/` and `fab/bom.csv`. `PATH` is the project file, else the board, of the
document id. Every action is `available: false` for a document that is not a KiCad board or project, with
the reason "Altium documents are not written from the viewer". `--no-backup`, `--kicad-cli`, `--out` of
the board and every global flag are never set.

### 3. The plan, the preview and the confirm

A plan job runs the words with `--dry-run --json` through the runner core. When it ends with a plan, the
server loads it (`plans.load(state_dir(), plan_id)`), checks that the plan is of the action's command and
that every write lies under the root (the MCP rule), and, when one write replaces the open board, builds the
scene of the staged bytes (written to a temporary file of the state folder with the board's suffix, read
by the injected scene builder) and `compare.compare(staged_scene, current_scene)`; that diff is the
`preview`. The page shows the plan in a review dialog: the action, the files (path, kind, size, new and
replaced SHA-256), the issues by severity, the evidence, and on the board the preview drawn as `S.diff`
over the current scene (added green, removed magenta, moved arrows), with the Changes list. Error findings
plan no write and disable Confirm, as the protocol says. Confirm sends the job id; the server confirms
only a `plan_id` it planned in this session for that action and document, runs `--confirm --plan ID
--json`, and on `FEN-4002` answers the error with the hint "the file changed since the review"; the page
offers Review again, which reruns the plan.

### 4. Receipt, reload and undo

A confirmed job returns the receipt; the server keeps it in the session (`Live.receipts`, at most 32) and
writes it as JSON to `view-receipts/<receipt id>.json` of the state folder, so `restore` can read it as a
file. The page shows the receipt (files and digests, backups kept), then asks for the document's scene
again at once instead of waiting for the watcher. Undo is offered for the receipts of the session, newest
first: its plan is `restore <receipt file>`, reviewed and confirmed like any action; `restore` refuses when
a written file changed since, and the page shows its message.

### 5. Page

- Writing controls appear only when `GET /actions` says `enabled`. An **Actions** group joins the toolbar
  (fill, tidy, silkscreen, test points, export, BOM) with forms built from the options; the inspector gets
  **Move or rotate** for a part (fields prefilled with its position and rotation in the page unit, and a
  "nudge" of the grid step with the arrow keys while the form is open), **Move with copper** for the
  filtered parts, and **Waive finding** for a DRC finding (reason field required). All are registry
  commands and palette entries.
- The review dialog is modal, keyboard-operable, and names what will be written and where. Confirm is the
  only control that writes; Cancel discards the plan.
- An exported page never shows actions.

### 6. CLI

`fenolite view` gains `--allow-actions` (`--serve` only; without it `FEN-2001`). Its help says that the page
can then write the project's files through reviewed plans. `result.serve` gains `writes`, the receipts of
the session (ids and files). The agent guide gains a tested line, and `tools/gen_agent_guide.py`
regenerates the command guide.

## Security

- **Opt-in:** off unless `--allow-actions`; the reply and the page's About popover say when it is on.
- **Origin:** loopback only; Host and Origin checks; the custom header blocks cross-site requests without a
  preflight; the session token, read only through a guarded request, adds a second secret that another
  site cannot learn.
- **What can run:** only the templates of `ACTIONS`, with typed options; no command line, environment,
  external tool path or global flag from the page.
- **Where it can write:** the project root only; plan writes are checked against the root before confirm,
  output paths before planning; a confirm needs a plan this session made for the same action and document.
- **Recovery:** backups always kept; undo through `restore`; `FEN-1004` (incomplete rollback) is shown with
  its recovery files and no claim that nothing changed.
- **Altium:** no Altium document is written.

## Tests

- `tests/unit/view/test_actions.py` (new): templates give the expected words; refused: unknown actions,
  `..` and absolute outputs, a symlink out of the root, an unknown reference, a malformed length, a reason
  with a line break, an Altium document.
- `tests/unit/view/test_server.py`: action routes refuse without `--allow-actions`, without the header or
  the token; a confirm of a plan id the session did not make is refused; one job at a time with runs.
- `tests/unit/cli/test_view_actions.py` (new, real runner, copies of `two_layer.kicad_pcb` in `tmp_path`):
  `silk --designators` planned, previewed (the diff names moved designators or none), confirmed (receipt,
  backup, file changed), the file changed between plan and confirm gives `FEN-4002`, undo restores the
  original bytes; `move` of `R1` by 1 mm gives a preview with one moved part; `export` writes under `fab/`
  only. `fill` and `tidy --gate drc` are marked to need `kicad-cli` and run in the KiCad jobs.
- `tests/unit/cli/test_view_cmd.py`: `--allow-actions` without `--serve` is `FEN-2001`.
- `tests/visual/test_actions.py` (new, stubbed routes): a plan shows the files, the issues and the overlay;
  Confirm shows the receipt and reloads; `FEN-4002` offers Review again; an error finding disables Confirm;
  no action control on an exported page or without `enabled`.

## Risks / Trade-offs

- **A writing endpoint on a local port.** Mitigated by opt-in, loopback, guards, token, allow-list and root
  confinement; documented in `docs/viewer.md` with the advice to stop the server when done.
- **Preview cost:** reading the staged board doubles the read time of a plan; acceptable for a reviewed write.
- **KiCad only:** Altium users get checks (c0270) but no actions until c0241's gates pass.

## Open Questions

- Which actions should ship first if the list is cut: is the order fill, silk, tidy, move, waive, export,
  test points right?
- Should `--allow-actions` also require `--marks` or another file to log every write, or is the receipt
  list in the reply enough?
- Should the move form snap to a placement grid (which pitch?), or take exact values only (as designed)?
