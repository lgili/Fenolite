## Context

`docs/research/enclosures.md` (2026-10-30) recommends five stages for the product's case and puts the fit
check with a STEP the user already has first (stage 0, section 8). What exists:

- `fenolite export --step` runs `kicad-cli pcb export step -o 3d/<stem>.step --subst-models` on a copy set
  and locates every `(model …)` path itself: `${KIPRJMOD}/<rel>` is read from the board's folder
  (`project`), any other path is left to `kicad-cli` where it is (`in-place`) (`manufacturing-exports`,
  "STEP export with 3D models"; `docs/exports.md`, "3D models").
- `fenolite render --png` runs `pcb render` (`docs/cli-contract.md`, "render").
- The footprint `model` token is `(model "PATH" (offset (xyz X Y Z)) (scale …) (rotate (xyz RX RY RZ)))`.
  The frame was measured with `kicad-cli pcb export vrml` 10.0.7: offset in mm in the footprint frame with Y
  up, rotate Z clockwise seen from above; 9.0.9 placed no model in the same VRML export
  (`docs/formats/kicad/libraries.md`, `H-K-MODEL-PLACE`).
- The footprint `attr` flags `board_only`, `exclude_from_pos_files` and `exclude_from_bom`
  (`docs/formats/kicad/board.md`, S-0001).
- A footprint without `fenolite.path` that matches no part is kept by a rebuild as board-only, with the
  info `layout.board-only` (`docs/lens.md`, "Board-only footprints").
- `testpoints --place` adds footprints without `fenolite.path` through the mutation protocol, with an
  optional DRC before and after (`docs/cli-contract.md`, "testpoints --place").

KiCad users show a box by attaching its STEP to a dummy footprint (S-0958, forum practice, INFERRED).
Altium imports a STEP as a 3D Body, embedded or linked (S-0950, S-0951), can define the board shape from
a 3D body (S-0952), and its Component Clearance rule uses 3D bodies (S-0953).

## Goals / Non-Goals

**Goals**

- One command puts the user's box STEP on the board at a stated pose, reversibly, through plan and confirm.
- `export --step` and `render --png` then show board and box together, with no new export kind.
- A written Altium checklist reproduces the same pose.
- The vendor's file never enters Fenolite's repositories, tests, fixtures or replies.

**Non-Goals**

- A box model, outline generation or a fit check (c0307 to c0309).
- Interference volumes, a STEP writer or gmsh (stage 3, Decided).
- Altium 3D-body records in a written `.PcbDoc`.

## Decided (maintainer, from `docs/research/enclosures.md`, section 10)

1. Vendor STEP files are linked only, never stored in Fenolite or `lgili/fenolite-library`.
2. Box models are authored one at a time from public datasheets with provenance, never scraped (c0307).
3. Fenolite's own box models are CC0 (c0307).
4. gmsh as a subprocess is stage 3; none of c0306 to c0310 needs a 3D kernel.
5. A check against a STEP the user downloaded runs on the user's machine and stores only results.
6. Stages 0 and 1 come before any 3D generation.

## Decisions

### 1. A command, not a DSL call

`fenolite enclosure place` works on any KiCad board: native, imported or built. A rebuild keeps the
footprint because it carries no `fenolite.path` (board-only). A DSL call would only serve scripts and would
put a user's file path into a script; c0308 may add one later on top of the same footprint writer.

Alternative considered: a new export option `export --step --enclosure FILE` that injects the model only
into the copy set. Rejected: the render, KiCad's own 3D viewer and the Altium checklist all need the box
on the board, and the user wants to look at it in KiCad.

`enclosure` is a command with actions; `place` is the first. c0307 adds `show`, c0310 `templates`.

### 2. The footprint

- Library link `Fenolite_Enclosure:ENC_<stem>` where `<stem>` is the STEP's file stem reduced to
  `[A-Za-z0-9_-]`; reference `ENC1` (or `--ref`); value the stem; layer `F.Cu`; locked.
- `attr board_only exclude_from_pos_files exclude_from_bom`; no pad, no courtyard, no silkscreen; one text on
  `F.Fab` with the reference. Without a courtyard KiCad's courtyard tests have nothing to judge; the
  footprint gets `allow_missing_courtyard` (S-0001, `board.md`) so DRC does not report it missing
  (`H-K-ENCL-DRC`).
- One `(model "${KIPRJMOD}/enclosure/<file>" (offset (xyz 0 0 Z)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 R)))`:
  the footprint sits at `--at` and the model offset carries only Z, so X and Y are the footprint's
  position and the rotation is the footprint's angle; `R` is 0. This keeps the pose in board coordinates
  that every tool shows.
- The footprint is also written as `lib/Fenolite_Enclosure.pretty/ENC_<stem>.kicad_mod`, with a row in the
  project's `fp-lib-table`, as builds do for `Fenolite_Holes`, so KiCad's "update from library" finds it.

### 3. The pose

`--at X,Y` (each length with its unit, board frame), `--z Z` (default 0: the model's origin on the board's
top face), `--rot DEG` (multiples of 0.001°, stored as µdeg). The box model's own origin is the maker's;
Fenolite does not know where the cavity is in it. The reply states the pose and the model's frame
convention so the user can correct it. c0307's mount options let c0308 compute the pose from a box model.

`result.place` = `{ref, footprint, model, at: {x, y}, z, rotation, filter}`; `filter` is the
`--component-filter` value that leaves the box out of a STEP export (S-0037, INFERRED until measured).

### 4. Where the STEP lives

- Default: plan a copy of `FILE` to `<board folder>/enclosure/<file>` (kind `3d-model`), and name it with
  `${KIPRJMOD}`. `export --step` then finds it as a `project` model on any machine with the project.
- `--in-place`: keep `FILE` where it is; the board then names the path as given, which is the user's
  choice. The reply shows it as `<in-place>/<file name>`, never the full path.
- `FILE` must start with the statement `ISO-10303-21;` after optional white space (S-0954), else exit 3
  with `FEN-3010` and nothing planned. `.stp` and `.step` are both accepted; case is ignored.
- `enclosure.step-local` (info) on every plan: "the STEP keeps its maker's terms; Fenolite does not
  publish it". `docs/enclosures.md` adds: do not commit a vendor STEP to a public repository unless its
  terms allow it.

### 5. Replacing and removing

A second `place` with the same `--ref` replaces that footprint and its model (`enclosure.replaced`, info).
A `--ref` already held by a footprint that is not a Fenolite enclosure footprint gives
`enclosure.ref-taken` (error): nothing is planned, exit 5. Removal is `fenolite restore` of the `.bak`, or
deleting the footprint in KiCad.

### 6. Checks before writing

Like `testpoints --place --drc`, `--drc` runs `kicad-cli pcb drc` on copies before and after and reports
new types; `lib_footprint_issues` and `lib_footprint_mismatch` are set aside. Without `--drc` no tool runs.

### 7. Altium checklist (`docs/enclosures.md`, "Altium")

Steps: open the converted project (`fenolite convert … --to altium`); Place » 3D Body, choose the same STEP,
linked (S-0950, S-0951); set X, Y, rotation and the Z offset to `result.place`; view in 3D; optionally use
"Define board shape from 3D body" (S-0952) and the Component Clearance rule (S-0953) to compare. The
report records whether the body sits where KiCad's render shows it.

## FEN- and issue codes

| code | kind | when |
|---|---|---|
| `FEN-3010` | exit 3 | the file given to `--step` does not start with `ISO-10303-21;` |
| `enclosure.step-local` | info | every plan: the STEP keeps its maker's terms and stays local |
| `enclosure.replaced` | info | an enclosure footprint of that reference is replaced |
| `enclosure.ref-taken` | error | `--ref` names a footprint that is not an enclosure footprint |

`FEN-3009` is taken by c0307. Checked on 2026-10-30 against `cli/errors.py` and every branch: `FEN-3001` to
`FEN-3008` are used or proposed.

## Hypotheses registered by this change

- `H-K-ENCL-STEP`: the combined STEP of `export --step` holds the box's solids at the pose, on 9.0.x and
  10.0.x.
- `H-K-ENCL-RENDER`: `render --png` with the footprint differs from the render without it.
- `H-K-ENCL-DRC`: the footprint adds no DRC violation type.
- `H-A-ENCL-IMPORT`: following the checklist puts the box where KiCad shows it (author report).

## Evidence per behaviour

| behaviour | level before merge |
|---|---|
| footprint text and pose | `INFERRED` (unit tests on the written board) |
| combined STEP | `KICAD-VERIFIED` (9.0.x, 10.0.x) or the measured 9.0 limit documented |
| render | `KICAD-VERIFIED` |
| Altium | `INFERRED` until the author report |

## Test fixture

A box made of public facts only: a board authored for Fenolite whose outline is a 120 × 80 mm rectangle
with a 116 × 76 mm cut-out and whose stack-up is 30 mm thick, exported by `kicad-cli pcb export step
--board-only` in the KiCad job. The STEP is generated at test time and never committed. The test reads the
combined STEP as text: it counts `MANIFOLD_SOLID_BREP` entities and finds the box's product name, without
any 3D kernel. If KiCad refuses a 30 mm board, the fixture uses the thickest board it accepts and the test
records the limit.

## Risks / Trade-offs

- **9.0 may not place the model** in a STEP export, as it did not in VRML (`H-K-MODEL-PLACE`). Then the
  command still writes, `docs/enclosures.md` says the combined STEP needs 10.0, and the reply gives
  `enclosure.step-local` with that note.
- **A huge vendor STEP** slows exports. Nothing to fix here; the reply gives the file size.
- **The lid hides the board** in a top render. `docs/enclosures.md` shows `render --png` from the bottom
  and a second `place` of a base-only STEP when the maker supplies one.

## Open Questions

1. Should `place` also accept `--box BOX.json --mount NAME` to compute the pose? Recommended: yes, but in
   c0308, once c0307's mount frame exists.
2. Should the copy into `enclosure/` add a `.gitignore` entry? Recommended: no; say it in the docs and the
   info. Changing a user's ignore file is outside the command's job.
3. Embedded models (KiCad 9 can embed a file in a footprint)? Recommended: no, never for a vendor file;
   revisit only for Fenolite's own generated models (stage 3).

## Relation to the other changes

c0307 defines the box model and its mount frame; c0308 uses it to compute the pose and can call this
change's footprint writer; c0309 judges the fit in 2D and 2.5D; c0310 writes face templates. Only this
change touches a STEP, and only the user's.

## Size

About 5 design-days: command and footprint 1.5, copy and sniffing 0.5, KiCad probes on two majors 1.5,
Altium checklist and docs 1, guide and closing 0.5.
