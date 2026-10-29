## Why

The catalog draws its 100 footprints with private helpers (`_chip_footprint`, `_row_pads`, `_quad_pads`,
`_paste_grid`, `_thermal_paste`, `_pin1_index`, `_make_footprint`) fed by Python tuples of manufacturer
land numbers. Nobody outside `fenolite.catalog` can reuse them, a new package needs new code, no
footprint has a 3D body, and there is no way to get a land from package dimensions when the datasheet
gives none.

The research `docs/research/component-library.md`, section 4.2 and change c0260 of its section 5, found
that the large libraries are generated, not drawn: at least 78 % of KiCad's footprints come from
per-family generators with parameter files, and the commercial tools compute land patterns from package
dimensions with a calculator and keep the manufacturer's pattern when one is given. The calculator they
use (IPC-7351B) is paywalled and its tables may not be copied. Fenolite needs its own calculator, with
its own constants, documented and labelled `INFERRED`.

## What Changes

- **Public per-family generators** in `fenolite.catalog.footprints`: `chip`, `molded`, `gullwing`
  (SOIC, SSOP, TSSOP, MSOP, QFP, SOT), `nolead` (QFN, DFN, SON, with thermal pad and paste grid), `grid`
  (grid arrays), `to`, `dip`, `header` and `connector` (a series expanded per position count). Each
  takes a `fenolite.package.v0` record (c0259) whose dimensions are exact length ranges in the c0246
  interval semantics, and returns the footprint, its bodies, its STEP solids and its findings.
- **A land calculator** with worst-case arithmetic on the ranges and **Fenolite-authored, versioned
  constants** (`lands/1`): toe, heel and side goals per land class, pad gap, courtyard clearance, hole
  clearance and annular ring. The constants and their derivation are published in
  `docs/formats/library/lands.md` as `INFERRED`. Goals are back-solved from cited manufacturer patterns
  by `tools/calibrate_lands.py`; no IPC table is used.
- **Manufacturer land override.** A `[land]` table with a cited source wins over the calculator. The
  footprint records which one was used, and the result reports the difference from the calculated land.
- **Drawing conventions authored by Fenolite**, versioned (`drawing/0` reproduces the 0.6 catalog byte
  for byte; `drawing/1` adds silkscreen with copper clearance, a chamfered fabrication outline, pin-1
  marks, polarity bars and rounded pads).
- **Extruded 3D bodies from the same numbers**: `ComponentBody` entries with signed bounds in
  `FootprintDef.bodies`, and a **STEP writer of our own** (`fenolite.backends.step`, stdlib only, AP214
  planar and cylindrical B-rep). A `drawing/1` footprint names its STEP model under
  `${KIPRJMOD}/lib/Fenolite.3dshapes/`, which the build writes.
- **The catalog's private helpers are replaced** by the generators; the 100 shipped footprints keep
  their bytes.
- **A naming convention** for packages authored by Fenolite: `<FAMILY><pins>_B<L>x<W>_P<pitch>[...]`.
- **`fenolite library generate PACKAGE...`** writes `.kicad_mod` and `.step` files through plan and
  confirm; `Footprint.from_package(text)` gives a script a generated footprint.

## Capabilities

### New Capabilities

- `footprint-generators`: families, length ranges, land calculator, constants, override, thermal pad and
  paste, grid arrays, through-hole lands, courtyard, conventions, numbering, bodies, STEP writer, naming,
  stamp, command and result.

### Modified Capabilities

- `fenolite-component-catalog`: ADDED "Catalog footprints come from the generators".
- `dsl-footprint-authoring`: ADDED "Generated footprints in a script".
- `component-body-volumes`: ADDED "Generated bodies are known volumes".

## Non-goals

- No IPC-7351 table, formula transcription or naming pattern; no three-level density table (only
  `nominal` is shipped, open question 1).
- No symbol (c0261), no library lint, render sheet or review record (c0262), no import of downloaded
  footprints (c0264), no datasheet extraction (c0265), no data repository (c0266).
- No thermal vias in exposed pads, no stencil step or process tuning beyond the paste grid, no
  photorealistic 3D (no fillets, no lead bends, no texture), no STEP reader.
- Irregular catalog footprints (switches, LED modules, mounting holes, test points) stay explicit pad
  lists of c0259.

## Evidence level required

- Calculator, conventions, naming, numbering: `INFERRED` (Fenolite-authored; hypothesis `H-G-LAND-CALC`),
  unit- and property-tested.
- A land from a `[land]` table: the package record's own label for its cited numbers.
- STEP files: `KICAD-VERIFIED` that `kicad-cli pcb export step` of a board using generated footprints
  adds one body per footprint and reports no missing model (`H-K-STEP-MODELS`), on 9.0 and 10.0.
- Catalog migration: byte-identical `.kicad_mod` files for all 100 entries (golden SHA-256 list).

## Impact

- New: `src/fenolite/catalog/footprints/` (`__init__.py`, `ranges.py`, `lands.py`, `drawing.py`,
  `bodies.py`, one module per family, `codes.py`), `src/fenolite/backends/step.py`,
  `tools/calibrate_lands.py`, `docs/formats/library/lands.md`, `docs/formats/library/naming.md`,
  `docs/formats/step/part21.md`, `docs/footprint-generators.md`, `examples/generated/`, tests.
- Changed: `src/fenolite/catalog/__init__.py` (helpers removed), `src/fenolite/dsl/footprint.py`
  (`Footprint.from_package`), `src/fenolite/lens/build.py` (writes generated STEP models),
  `src/fenolite/cli/cmd_library.py` (verbs), `explain.toml`, `docs/cli-contract.md`, `docs/dsl.md`,
  `docs/catalog/sources.md`, guide page `footprints.md`, `CHANGELOG.md`.
- Dependencies: c0259 (package record envelope, stable ids, catalog data files) and c0246 (interval
  semantics). c0262, c0264 and c0265 build on it. No runtime dependency; no `package-layering` change
  (`catalog` → `model`; the writer is a top-level `backends` module, which `lens` and `cli` may import).
- Size: about 15 design-days (L).
