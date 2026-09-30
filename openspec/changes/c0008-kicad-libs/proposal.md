## Why

Designs name parts by library identifiers such as `Device:R` (S-0001). To build a board or check a footprint assignment, Fenolite must find the file behind each identifier and read its pads, graphics, pins and units. KiCad resolves identifiers through project and global library tables, path variables and, since 10.0, nested tables and folder-based symbol libraries (S-0045, S-0046). The official libraries are CC-BY-SA 4.0 as a collection (S-0048): they are read from an install, never committed.

## What Changes

- `fenolite.model.library` (new): immutable definitions `FootprintDef`, `SymbolDef`, `SymbolPin`, `SymbolUnit`, `PinAlternate` and the container `Library`. Footprints reuse the board `Pad`, `Padstack` and `Graphic`. New id prefixes `fpd` and `sym`, and the generated schema `library.json`.
- `backends/kicad/mod.py`: `read_footprint` reads a `.kicad_mod` file, text or node. Unmodelled children stay as slots.
- `backends/kicad/sym.py`: `read_symbol_library` reads a `.kicad_sym` file or a `.kicad_symdir` folder. It covers units, body styles, pins with alternates, both power forms, the pre-10 empty-text marker `~`, and derived symbols.
- `backends/kicad/libs.py` and `liberrors.py`: library tables in both syntaxes with nested `Table` rows, path variables (`KIPRJMOD`, environment, `KICAD9_*`/`KICAD10_*`, versioned fallback), project-over-global precedence with a template fallback, and a `LibraryResolver`. Failures are typed issues.
- An authored CC0 mini library under `tests/data/libs/` with 9.0 and 10.0 variants. `kicad-cli` 9.0.9 and 10.0.6 must load it.
- `needs_libs` census over the local install or `KICAD*` folders; `docs/formats/kicad/libraries.md`; sources S-0040 … S-0049; hypotheses `H-K-LIB-*`.

The planned half-week budget cannot hold the full scope. This change is estimated at 7.25 days (design, "Budget"). The fetched per-tag cache (fetch tool, pins, tree hash), the 9.0.9 census, `kicad_common.json` variables, demo-library corpus rows and the DRC-harness probes move to a follow-up change with its own budget line.

## Capabilities

### New Capabilities
- `kicad-library-read`: footprint and symbol-library reading into definitions, with slots, version policy, derived symbols and located errors.
- `kicad-library-resolution`: library identifiers, tables, path variables, discovery and precedence, library sources, and the resolver with its closed issue set.

### Modified Capabilities
- `design-model`: library-definition entities, their id prefixes and their schema.
- `corpus-policy`: the `needs_libs` skip rule names its sources and message (MODIFIED `Skip markers`).

## Non-goals

- Writing footprints, symbols or tables, and placing footprints into boards (board backend change).
- Modelling symbol body drawings, `fp_text`, text boxes, dimensions, zones, groups, points, custom-pad primitives and oval drills. These stay opaque slots.
- Library types other than `KiCad` and `Table`, design-block tables, and files older than KiCad 8.0.
- The fetched library cache and everything listed above as moved to the follow-up.
- 3D model fetching, footprint generation, linting, a `fenolite libs` command, and a CI job for library tests.

## Evidence level required

- Footprint and symbol reading: `INFERRED` (`H-K-LIB-READ`). The install census is recorded as supporting data. `CORPUS-VERIFIED` needs a round trip over manifest files from two origins, which only a writer change can run.
- Mini library loads, and re-reading it after `fp upgrade`/`sym upgrade` gives equal definitions: `KICAD-VERIFIED` on 10.0.6 (local and `kicad-10` job) and on 9.0.9 for the 9.0 variants (`kicad-9` job). The `~` rule: `KICAD-VERIFIED` (10.0.6).
- Table parsing, precedence, path variables, fallback, nested tables and relative URIs: `INFERRED` from S-0045/S-0046, with `H-K-LIB-*` rows.

## Impact

- New modules under `backends/kicad/` and `model/`, two id prefixes, one schema file, updates to `tests/_resources.py` and `tests/conftest.py`.
- Rows in `PROVENANCE.md` and `LEGAL-ANNEX.md`. No runtime dependency and no CLI change. `LibraryError` maps to `FEN-3001`.
- Depends on c0006 (`sexpr`, `slots`, required-resource mode, `kicad-10` job) and c0007 (`versions`, token inventory, `kicad-9` job).
