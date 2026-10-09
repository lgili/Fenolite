## Why

Milestone v0.4 (this proposal was written as "v0.2c" before the renaming of 2026-10-07); every statement about the code below was checked against `origin/dev` at `9aba2dff`.

The complex-board review of 2026-10-05 found that `fenolite export` writes four kinds (and, since c0084, an Altium rule file), while a manufacturer and an enclosure designer also ask for IPC-2581 or ODB++, a STEP model, board PDF and DXF files and a schematic PDF, which c0024 left out with no destination. The 3D library is never fetched, models are never vendored, and the runner's clean environment hides the user's model folder from `kicad-cli`.

Measured on `kicad-cli` 10.0.6 and 9.0.9 (design, Context):

- Both majors have the six commands; at 600 parts each run takes 2 to 18 s on 10.0.6.
- A model that `kicad-cli` cannot find is left out of the STEP, with exit 0. The 9.0.9 image holds no model.
- A missing sub-sheet becomes an empty page of the schematic PDF, with exit 0 and no message.
- STEP and ODB++ differ between two runs beyond their dates, IPC-2581 too on 10.0.6.

## What Changes

- **Six kinds**: `--ipc2581`, `--odb`, `--step`, `--pdf`, `--dxf`, `--sch-pdf`, one argument list each, valid on both majors. `--all` keeps c0024's four; `--preset` (c0074) and `--altium-rul` (c0084) are untouched, and a preset changes no document kind.
- **Models in the STEP**: Fenolite locates every model a footprint names, copies it into the run with its variable, and reports its source and SHA-256; a missing one is a warning naming its parts.
- **Schematic PDF**: every sheet goes into the run; a sheet that cannot be given refuses the kind.
- **Repeatability per kind** (`bytes`, `content`, `none`).
- **`fenolite models PATH [--vendor]`**: where each model was found; `--vendor` copies them into the project's `3dmodels/`, which exports read first.
- **Fetch**: `tools/kicad_libs_fetch.py --models` fetches single model files, checked by GitLab's SHA-256.
- **Manifest**: the six kinds are derived kinds of "Artefact states"; vendored models are design files of the project manifest, kind `3d-model`.
- A board PDF whose outline leaves its paper gives a warning.

Size: 6.25 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `manufacturing-exports`: MODIFIED "Export kinds and their arguments", "Artefact manifest", "Artefact states", "Project manifest", "Export evidence"; ADDED "STEP export with 3D models", "Schematic PDF export sheets", "Board PDF export page check", "Document kinds in the manifest".
- `cli-contract`: MODIFIED "Export command" (written on the text of c0084's open delta), "Manifest option of producing commands"; ADDED "Models command".
- `kicad-library-resolution`: MODIFIED "Missing 3D models are warnings"; ADDED "3D model location", "3D model pins", "3D model fetch".
- `kicad-oracle`: MODIFIED "Subcommand matrix from help text"; ADDED "Document exports are probed on both majors".

## Non-goals

- Options of the new kinds (IPC-2581 version, STEP origin, own layer lists): nowhere in v0.4, because one fixed list per kind is what the probes prove; preset tables for them can follow, each key with its option probe as "Export presets" asks.
- Drawings: c0117. The impedance table file: c0105.
- `stpz`, `glb`, `vrml`, `stl`, `brep`, `xao`, `ply`, `u3d`, `3dpdf`, `gencad`: nowhere, because the review's package needs none.
- Checking file content: nowhere, because it is KiCad's (c0024).
- Variants: roadmap v0.5b.
- Models of authored and catalog footprints: nowhere in v0.4, because `FootprintDef.models` holds paths without placement. `FootprintDef.bodies` (the extruded volumes of c0121) are not model files and reach no STEP through this change; `docs/exports.md` keeps the two words apart.
- Documents from an Altium board: nowhere. `export` resolves its board with `projectset.resolve_board`, which refuses a `.PcbDoc` or an Altium project (exit 2, `FEN-2001`), as it does today for the four kinds; the documents of an Altium project come from the output job that an Altium build writes (c0087, c0138).
- A model download by `fenolite` itself: c0078 (`fetch`).

Limits: `step`, `odb` and `ipc2581` hashes identify a file, not the board's content, and a `--dry-run` plan shows other hashes than `--confirm` writes until c0120; KiCad reads `3dmodels/` only if the user names it; a board past its paper is cut in the board PDF (warning only).

## Evidence level required

- `H-K-EXPORT-DOCS`, `-DOCS-REPEAT`, `-MODELS`, `-SHEETS`: `KICAD-VERIFIED (9.0.x, 10.0.x)`; `H-K-EXPORT-PDF-PAGE`: `KICAD-VERIFIED (10.0.x)` at least.
- `H-G-MODELS-FETCH`: `INFERRED` until the first real fetch, which needs the maintainer's consent.
- The rest: mechanical.

## Impact

- New: `backends/kicad/models.py`, `exports/documents.py`, `cli/cmd_models.py`, `tests/data/models/`, `tests/kicad/export/test_document_probes.py`.
- Changed: `exports/`, `cli/cmd_export.py`, `backends/kicad/{libs,libcache,helpmatrix}.py`, `libraries.toml`, `tools/kicad_libs_fetch.py`, docs.

## Prerequisites

- `0.3.0` is released from `dev`, with c0084 archived: "Export command" then holds `--altium-rul`, and this change's delta of it is that text plus the six flags. If c0084 is still open when this change is implemented, c0084 lands first and task 0.1 regenerates the delta.
- Already on `dev` (archived): c0024, c0060, c0061, c0062, c0064, c0065, c0066, c0074. Nothing of this change waits for them any more.
- No proposal of v0.4 must land before this one. Waiting for this one: c0117 (`run_kind(layers=)`, the PDF prefix, and its regenerated "Artefact states"), c0118 (its regenerated "Artefact states" and "Manifest option of producing commands"), c0105 (its manifest kind) and c0119 stage 5.
- c0096, c0097 and c0099: nothing here touches them.
