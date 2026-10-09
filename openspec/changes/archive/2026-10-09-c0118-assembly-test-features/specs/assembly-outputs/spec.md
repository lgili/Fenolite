## ADDED Requirements

### Requirement: Fiducial rows in the placement table
`exports.placement.PlacementRow` and `PlacedRow` SHALL gain `fiducial: bool = False`, true when a pad of the footprint has `fab_property` `fiducial_global` or `fiducial_local`. The `[placement]` table of an assembly template SHALL take the key `fiducials`, a boolean, `true` by default, and `fiducial` SHALL join the placement column fields, its cell `yes` for a fiducial row and empty otherwise.
- `apply` MUST leave out the fiducial rows when `fiducials` is false, together with the DNP and `smd_only` filters.
- The default template MUST keep the rows of KiCad's own position file (`H-K-POS-ROWS`): a fiducial whose footprint lacks `exclude_from_pos_files` stays a row.
- `docs/assembly.md` MUST describe the key and the field.

#### Scenario: Fiducials kept by default
- **GIVEN** a built board with the fiducial `FID1` of `design.fiducial()` and the resistor `R1`
- **WHEN** `fenolite pnp` runs with the default template
- **THEN** the rows are `FID1` and `R1`, and only the row of `FID1` has `fiducial` true

#### Scenario: A template drops them
- **GIVEN** the same board and a template whose `[placement]` table holds `fiducials = false`
- **WHEN** `fenolite pnp --template` runs with it
- **THEN** the only row is `R1`; with `fiducials = true` and a column `{ name = "Fid", field = "fiducial" }`, the cell of `FID1` is `yes` and that of `R1` is empty
