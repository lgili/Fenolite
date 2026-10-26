## 0. Entry check

- [x] 0.1 Find the public projects with variants and record the keys in `project.md`. Proof: `openspec validate c0186-variants-view --strict --no-interactive`.
  - 2026-10-25: four of the six public project files carry a `[ProjectVariant<n>]` section.

    | project | variant | variations |
    |---|---|---|
    | prjpcb-01 | `Production` | 56 (Kind 1: 47, Kind 0: 9) |
    | prjpcb-03 | `48V` | 45 (Kind 2) |
    | prjpcb-04 | `Default` | 6 |
    | prjpcb-06 | `No Crystal` | 1 |

    prjpcb-02 and prjpcb-05 have none.
  - The keys (`Description`, `UniqueID`, `Variation<k>` with `Designator`, `UniqueId`, `Kind` and `AlternatePart`, `ParamVariation<k>`, `ParamDesignator<k>`) are recorded in `docs/formats/altium/project.md`, "Variants", under `H-A-PRJ-VARIANT` (INFERRED).
  - A variation keeps the designator the part had when it was made; `No Crystal` names its crystal `X?`. Matching is therefore by unique id (design, decision 2).
  - Branch `c0186-variants-view`, from `c0185-project-nets`. Proof passed.

## 1. Read and draw

- [x] 1.1 Add `read/variants.py`. Proof: `uv run pytest tests/unit/backends/altium -k variant -q`.
  - 2026-10-25: proof passed (17). `test_variants_read.py` covers the three kinds, an unknown kind, an alternate part and a parameter variation.
- [x] 1.2 Draw not-fitted parts and varied parameters (scenario "An authored variant"). Proof: `uv run pytest tests/unit/view/test_variants.py -q`.
  - 2026-10-25: proof passed (2).
  - The page has a variant selector. A part that is not fitted is crossed on the sheet, and dimmed and crossed on the board. 3D leaves its body out. The component panel shows the state and the varied parameters.
  - Browser check, Chromium of the container, on the public project S-0175 (`altium-set:05`) with `No Crystal`: X201 is crossed on its sheet and on the board.
- [x] 1.3 Add `--variant` (scenario "Unknown variant"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -q`.
  - 2026-10-25: proof passed (16).
  - `result.variant` gives `{name, fitted, not_fitted}`. On S-0175 it reads 26 fitted and 1 not fitted.
  - An unknown name is exit 2, `FEN-2001`.

## 2. Closing

- [x] 2.1 Docs, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 921 passed, 34 skipped).
  - Changed: `docs/viewer.md` ("Assembly variants"), the `view` section of `docs/cli-contract.md`, a line in `references/files.md`, the hypothesis row, the evidence matrix and the LEGAL-ANNEX row.
  - `test_altium_build.py::test_evidence` leaves `H-A-PRJ-VARIANT` out of the build's rows, because only `fenolite view` reads variants.
- [ ] 2.2 The maintainer compares a variant of their own with Altium. Proof: the record under this task.
