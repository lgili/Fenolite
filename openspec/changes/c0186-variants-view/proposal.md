## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P1-5 of that analysis.

Altium projects keep assembly variants in the project (`.PrjPcb` `[ProjectVariant<n>]` sections). A reviewer
checks which parts a variant does not fit and which parameters it changes. The viewer shows every part as
fitted.

## What Changes

- **Variant choice.** The page gets a Variant selector for an Altium project with variants ("[No Variations]"
  first). The choice applies to every document of the project.
- **Not fitted parts.** On sheets a not-fitted part is drawn with Altium's cross over it; on the board it is
  dimmed, and in 3D it is hidden. Varied parameters show their variant value in Properties.
- **Reply.** `fenolite view ... --variant NAME --json` counts fitted and not-fitted parts.

## Capabilities

### New Capabilities

- `variant-view`: the Variant selector and the drawing of not-fitted parts and varied parameters.

### Modified Capabilities

- `cli-contract`: ADDED "View command shows a variant".

## Non-goals

- Creating or editing variants.
- KiCad variants (no file form in KiCad 9).

## Evidence level required

- Variant records: task 0.1 records their keys in `docs/formats/altium/project.md` from the public projects
  that hold variants; their meaning is `INFERRED` until the maintainer's review (task 2.2).

## Impact

- **New:** `src/fenolite/backends/altium/read/variants.py`, `tests/unit/view/test_variants.py`.
- **Changed:** `view/project.py`, `view/page.html`, `cli/cmd_view.py`, `docs/viewer.md`, `docs/cli-contract.md`.
- **Size:** 3 design-days.
