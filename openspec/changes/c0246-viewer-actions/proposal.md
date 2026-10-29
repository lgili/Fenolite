## Why

With c0245 the viewer can check a board; it still cannot change one. A reviewer who sees unfilled zones,
designators over pads, a part one millimetre off or a DRC finding that is accepted by design must leave the
page, compose a command line, run its dry run, read the plan and confirm it. The commands exist (`fill`,
`tidy`, `silk`, `testpoints`, `place`, `check --exclude`, `export`, `bom`, `restore`) and all follow the
mutation protocol: a dry run returns a plan, `--confirm --plan ID` writes exactly the reviewed bytes, a
changed input gives `FEN-4002`, every write keeps a backup and returns a receipt. The page can drive that
protocol and show the plan where it matters: on the board.

## What Changes

- **Opt-in writing.** `fenolite view --serve --allow-actions` enables writing actions; without it the page
  offers none and the server refuses them, as `fenolite mcp` lists `fenolite_edit` only with
  `--allow-edit`.
- **Review before write.** Each action runs the command's dry run and shows its plan: the files it would
  write with their sizes and digests, the issues, and a before/after overlay of the board computed from the
  staged bytes with the existing revision compare (c0184). Nothing is written until Confirm, which runs
  `--confirm --plan <id>`. A file that changed since the review gives `FEN-4002` and a new review.
- **Receipt and undo.** After a write the page shows the receipt and reloads the document. Undo runs
  `restore` on that receipt, through the same review and confirm.
- **First actions, KiCad boards only:** fill zones; tidy (prune, straighten, chamfer) with `--gate drc`;
  silkscreen designators and clipping; test points `--place`; waive a DRC finding from the inspector with a
  reason (`check --exclude`); move or rotate the selected part (`place --move`) or the filtered parts with
  their copper (`place --shift`, `--turn`); exports (Gerber, drill, positions, PDF) and the BOM into a folder
  under the project.
- **Security.** Loopback only, the run guard of c0245 with its own header and a per-session token, a fixed
  allow-list of actions with typed options, output paths only under the project root, backups always kept,
  one write at a time, and no write of an Altium document.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-viewer`: writing actions behind the opt-in, plan review with the board overlay, confirm by plan,
  receipt and undo, the action allow-list, the action guard.
- `cli-contract`: `fenolite view --allow-actions`.

## Non-goals

- No free command line, no `edit` of design scripts, no `build` or `route` from the page in this change.
- No write of Altium documents: the actions are offered for KiCad boards and projects; an Altium document
  shows them as unavailable with the reason, until c0241's gated edit session exists.
- No `--no-backup` from the page, no multi-step undo history beyond the receipts of the session.
- No interactive drag-and-drop routing; moving a part is a reviewed `place` plan.

## Evidence level required

An action adds no fact: each reply keeps the evidence of its command (for example the DRC gate of `tidy`
reports `KICAD-VERIFIED(kicad-cli …)` when it ran, and the plan says when it did not). The protocol is
proven by unit tests of the routes with a fake runner and by integration tests on copies of
`tests/data/kicad/board/two_layer.kicad_pcb` that plan, confirm, refuse a changed file (`FEN-4002`) and
restore; the page by Chromium tests with stubbed routes in the `viewer` CI job. Tests that need `kicad-cli`
(fill, `--gate drc`) run in the KiCad CI jobs.
