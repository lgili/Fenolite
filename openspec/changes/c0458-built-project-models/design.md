# Design: c0458

## Context

- `lens.build._vendor` copies each placed footprint of a library row byte for byte to
  `lib/<nickname>.pretty/`. The footprint's `model` paths are kept as written.
- `fenolite import --to python` of an Altium project writes `<library>.3dshapes/<file>.step` beside the
  design script and names them `${KIPRJMOD}/<library>.3dshapes/<file>.step` (c0409 B9, c0423). In the script's
  folder the path resolves; in the built folder it does not.
- `LibraryResolver.locate_model` already resolves a model path as KiCad does, with `project_dir` the script's
  folder during a build.

## Decisions

### 1. The build copies project models, and only those

For each vendored footprint, each model path that starts with `${KIPRJMOD}/` (or `\`) and that
`locate_model` finds in the project folder (source `project`, a `rel` without `..`) is copied to `rel`. A file
the build already writes wins (a generated model of an authored footprint); `.fenolite/` is never a target.
`${KICAD<N>_3DMODEL_DIR}` paths are never copied, even when the project's `3dmodels` folder holds them:
those are official-library models (S-0048). Absolute paths are not copied: the built board still names the
same file on the same machine.

Authored footprints and `Part.model` references are out of scope: they name paths the user wrote.

### 2. The conversion reads paths as KiCad does

`model_path` follows absolute paths and `..`. The c0449 reason `OUTSIDE` is replaced by `NOT_FOUND` for an
absent file outside the folder; `MISSING` keeps its text, so the census rows of absent files inside a project
do not change. The result of an absolute path now depends on the machine, as KiCad's does; the census rows of
the two demo boards with absolute paths are the same on every machine without those files.

## Evidence

- S-2170: `kicad-cli` 10.0.6 export of the built c0423 fixture, 15 of 15 models not found before, 0 after.
  `ORACLE-VERIFIED(kicad-cli)`. The GUI 3D viewer is inferred from `KIPRJMOD`'s definition (S-0045).
