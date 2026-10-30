## Why

Stage 0 of the enclosure line (`docs/research/enclosures.md`, sections 7 and 8). A user who has chosen a
box usually holds its STEP model, downloaded under the maker's own terms. Today there is no Fenolite way
to see the board inside that box: KiCad has no enclosure object, and the usual practice is to hang the
box's STEP on a dummy footprint by hand (S-0958, INFERRED). Fenolite already exports a STEP with
`kicad-cli pcb export step --subst-models` and renders with `pcb render`, so the missing piece is small:
put the user's STEP on a footprint without pads at a known pose, and say how to do the same in Altium.

## What Changes

- **New command `fenolite enclosure place PATH --step FILE --at X,Y [--z Z] [--rot DEG] [--ref REF]
  [--in-place]`.** It adds one footprint without pads to a KiCad board, through the reviewed-plan protocol
  (`--dry-run`, then `--confirm --plan ID`). The footprint carries the user's STEP as its 3D model at the
  given pose, and has the attributes `board_only`, `exclude_from_pos_files` and `exclude_from_bom`, no
  courtyard and no pad, so it reaches no BOM, no position file and no DRC courtyard test. Its reference
  is `ENC1` unless `--ref` names another; it is written without `fenolite.path`, so a rebuild keeps it as a
  board-only footprint (`docs/lens.md`).
- **The STEP stays the user's.** By default the file is copied into the project as `enclosure/<name>.step`
  and named `${KIPRJMOD}/enclosure/<name>.step`; `--in-place` keeps the user's path. Either way Fenolite
  never commits, publishes or uploads it, and the reply never holds an absolute path. An info
  `enclosure.step-local` reminds the user that the file keeps its maker's terms.
- **Combined outputs with no new export kind.** `fenolite export --step` locates the copy as a `project`
  model and writes one assembly STEP with the board, its parts and the box; `fenolite render --png`
  shows it. `result.place` reports the pose in nm and µdeg and the `--component-filter` that leaves the
  box out.
- **Altium checklist.** `docs/enclosures.md` gains a written checklist to place the same STEP as a 3D Body
  at the reported pose and to compare it (S-0950 to S-0953), settled by the maintainer's author report.
- **Codes.** `FEN-3010` (exit 3): the file is not an ISO 10303-21 file (S-0954). Issue codes
  `enclosure.step-local` (info), `enclosure.replaced` (info) and `enclosure.ref-taken` (error).

## Capabilities

### New Capabilities

- `enclosure-step`: the enclosure footprint, its pose, the STEP's place in the project, the combined
  export and render, and the Altium checklist.

### Modified Capabilities

- `cli-contract`: ADDED "Enclosure place command".

## Non-goals

- No box model, no `design.fit`, no fit check: c0307, c0308 and c0309.
- No 3D kernel, no gmsh, no interference volume, no STEP writer (stage 3).
- No vendor STEP in Fenolite, its tests or `lgili/fenolite-library` (Decided). Tests use a box STEP
  that `kicad-cli` exports from a board authored for Fenolite.
- No Altium write of 3D bodies: the Altium side is a checklist.

## Evidence level required

- The combined STEP holds the box at the pose: `KICAD-VERIFIED` (9.0.x, 10.0.x) through `H-K-ENCL-STEP`;
  KiCad 9.0.9 placed no model in a VRML export (`H-K-MODEL-PLACE`), so 9.0 is measured, not assumed.
- The render shows the box: `KICAD-VERIFIED` through `H-K-ENCL-RENDER`; no DRC finding added:
  `H-K-ENCL-DRC`.
- Altium: `INFERRED` until the checklist's author report (`H-A-ENCL-IMPORT`).

## Impact

- New: `src/fenolite/cli/cmd_enclosure.py`, `src/fenolite/cli/_enclosure_place.py`, tests under
  `tests/unit/cli/` and `tests/kicad/enclosure/`, `docs/enclosures.md`, `docs/formats/step/header.md`.
- Changed: `cli/errors.py` (`FEN-3010`), `explain.toml`, `docs/cli-contract.md`, the agent guide,
  registers, `openspec/README.md`, `CHANGELOG.md`.
- Sources: S-0950 to S-0954 and S-0958 registered here; S-0037 and S-0001 reused.
- Size: about 5 design-days. First change of the line; c0307 to c0310 build on it.
