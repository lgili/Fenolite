# c0458: a built project keeps its own 3D models

## Why

On the maintainer's board (private; codes and counts only) flow A, `fenolite build` of a design that
`fenolite import` made from an Altium project and then `convert --to altium`, lost 183 of 183 models as "not
found in the project folder"; flow B, from the PcbDoc, kept 182. The built footprints name
`${KIPRJMOD}/<library>.3dshapes/<file>.step`, the files lie beside the design script, and the build copies the
footprints but no model. KiCad reads `${KIPRJMOD}` as the built board's folder, so it finds none of them either:
`kicad-cli pcb export step` of the same flow on Fenolite's authored c0423 document gives `Could not add 3D model`
for 15 of 15 (S-2170). The c0449 conversion only reported what KiCad does.

The c0449 conversion also refused absolute paths and paths that leave the project folder, which KiCad reads.

## What Changes

- `fenolite build` copies each model file that a vendored footprint names as `${KIPRJMOD}/<rel>` and the
  design script's folder holds, byte for byte, to `<rel>` in the built project. Models under `${KICAD*}`
  variables (the official libraries) and absolute paths are still never copied: the restriction is about
  redistributing KiCad's official libraries (S-0048), and a project's own models already belong to the user.
  This amends design-dsl "Footprints of every row origin are vendored" ("no 3D model").
- `convert.models.model_path` reads a model path as KiCad does: absolute paths and paths that climb out of the
  project folder are followed. An absent file outside the folder gets the new reason "the model file is not
  found at its path"; the reason "leads outside the project folder" is gone.

## Impact

- `src/fenolite/lens/build.py` (`_vendor_models`), `src/fenolite/convert/models.py` (`model_path`,
  `NOT_FOUND`).
- Tests: `tests/unit/convert/test_built_models.py`.
- Docs: `docs/dsl.md`, `docs/conversion.md`, `docs/formats/kicad/libraries.md` (two rows),
  `docs/evidence/conversion.md` (the reason of 5 models of CM5_MINIMA_3 and 4 of One-Air-Max, whose absolute
  paths name files of their authors' machines), S-2170, CHANGELOG.
- A board built before this change keeps its missing models until it is built again.
