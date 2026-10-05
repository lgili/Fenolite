## Why

A board that passes `check` still cannot be ordered assembled: an assembly service asks for a bill of materials and a placement file, each with its own column names, order, units and rotation convention. The dogfood board of 2026-10-02 recorded the gap ("BOM and placement files in an assembly house's columns", roadmap, owner v0.2a). The plan gives v0.2a "`bom` via `kicad-cli sch export bom` with neutral columns mapped; PnP".

Fenolite must not ship anyone's format. The answer is a neutral table plus a column template that the user writes: names, order, units, rotation rules, side names, grouping.

Observed at proposal time: `sch export bom` exists on 9.0.9 and 10.0.6 with `--fields`, `--labels`, `--group-by` and the delimiters; on 10.0.6 it writes one quoted row per part, takes a user property as a field and gives an empty column for an unknown one. `pcb export pos` writes `Ref,Val,Package,PosX,PosY,Rot,Side` with Y negated, and c0009 already proved that model placements equal it.

## What Changes

- `exports/bom.py`: neutral BOM parts and lines; grouping by any fields; a difference of two BOMs.
- `exports/placement.py`: neutral placement rows from the board model; origin, axis, units and rotation rules applied with exact arithmetic.
- `exports/assembly.py`: the template (`*.toml`) for both tables, its validation, and CSV rendering. A neutral built-in template; no other template ships.
- `backends/kicad/bom.py` and `KicadCli.export_bom`: the parts of a project from `sch export bom`, read back from its CSV.
- `fenolite bom PATH` and `fenolite pnp PATH` (new): the table as JSON, or as a CSV file with `--out` through the mutation protocol; `--template FILE`; for `bom`, `--source kicad|model` and `--against OTHER`.
- Oracle tests on both majors: the BOM from the model equals the one from `kicad-cli` on the examples; placement rows equal `pcb export pos`.
- `docs/assembly.md`: the template reference with an invented example.

Size: 7 design-days; cut order in the design.

## Capabilities

### New Capabilities
- `assembly-outputs`: neutral BOM and placement tables, the template, CSV rendering, issue codes, evidence.

### Modified Capabilities
- `cli-contract`: ADDED "Bom command", "Pnp command".
- `kicad-oracle`: ADDED "BOM export through the package runner", "Assembly tables agree with kicad-cli".

## Non-goals

- No template of any assembly service, distributor or company, and no name of one in the repository. Examples use invented column names.
- No part search, pricing, stock or lifecycle data, and no network access.
- No variants (v0.5b), no alternates, no consolidation of equivalent parts.
- No change to `export`: KiCad's own position file stays its `pos` kind. The manifest entries of these tables are c0065's.
- No 3D or panel data, no feeder or machine file.

## Evidence level required

- Parts read from `kicad-cli`: `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-BOM-CSV`).
- Parts from the model: `KICAD-VERIFIED` when they equal `kicad-cli`'s on the built examples on both majors (`H-K-BOM-MODEL`); `INFERRED` until then, and always for a project without a schematic.
- Placement rows in KiCad's frame: `KICAD-VERIFIED` (`H-K-PCB-POS`, already verified, and `H-K-POS-ROWS` for the rows of this change).
- Grouping, column mapping, unit conversion and rotation rules: mechanical. Fenolite claims that the file holds the neutral table under the template; whether a template matches a service's expectations is the user's claim.

## Impact

- New: `src/fenolite/exports/{bom,placement,assembly}.py`, `backends/kicad/bom.py`, `cli/cmd_bom.py`, `cli/cmd_pnp.py`, `docs/assembly.md`, `tests/data/assembly/`.
- Changed: `backends/kicad/cli.py`, `exports/codes.py`, `docs/cli-contract.md`, `docs/exports.md`.
- No model change, no runtime dependency (`tomllib` and `csv` are stdlib).
- Implemented on 2026-10-05 without the `kicad` source, and completed with it on 2026-10-06 (design, "Implementation notes").
- Depends on c0061 for the `kicad` source (a schematic to export from); the `model` source and `pnp` need no pending change.
