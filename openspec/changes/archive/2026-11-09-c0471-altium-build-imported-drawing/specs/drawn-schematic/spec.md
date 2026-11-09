## MODIFIED Requirements

### Requirement: Altium drawing written back

A drawing extracted from Altium sheets and written again by `backends/altium/drawn.py` SHALL read back
to an equal drawing: level S of `design-equivalence` finds no difference, the typed opaque items included.
`lower_drawn` and the native readback guard SHALL accept opaque subtrees (`OWNERINDEX=@<line>`), harness
records (`215`, `216`, `217`, `218`, and harness ports `18`), and opaque `Note` (`209`) and `CompileMask`
(`225`) records in both `convert` (`carry=True`) and `build --target altium` (`carry=False`).

#### Scenario: Write and extract again

- **GIVEN** the drawing extracted from each authored Altium fixture
- **WHEN** it is written as Altium sheets, read, and extracted again
- **THEN** the second drawing equals the first at level S

#### Scenario: Direct Altium build with subtrees, harnesses and compile masks

- **GIVEN** a project imported from Altium whose `schematic.toml` holds parameter-set subtrees (`RECORD=43`
  with child `RECORD=41`), harness connectors (`RECORD=215` with child `216` and `217`), signal harnesses
  (`RECORD=218`) and compile masks (`RECORD=225`)
- **WHEN** `fenolite build <design.py> --target altium` runs
- **THEN** the build succeeds (`exit_code == 0`) and the written `.SchDoc` files keep those records and pass
  the native readback guard
