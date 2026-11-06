## MODIFIED Requirements

### Requirement: Library made from a board
`fenolite library BOARD --out LIB [--diff LIBRARY]` SHALL write each footprint of a KiCad board, brought back to its origin, rotation 0 and the top side, into the footprint library `LIB` (a `.pretty` folder), under the mutation protocol.
- Instances of one name that differ MUST be written as `<name>_2` and so on, with `library.instances-differ` (warning).
  A variant MUST NOT take the name of another footprint of the board, nor of another variant: when `<name>_<n>`
  is taken, the next free number is used (change c0426), so no two footprints share one file.
- `--diff` MUST report per footprint the kinds that differ and write nothing.

#### Scenario: Silkscreen edited on the board
- **GIVEN** an authored board whose instances of `R_0603` have their silkscreen clipped, and a library with the unclipped footprint
- **WHEN** `fenolite library <board> --diff old.pretty --json` runs
- **THEN** the reply names `R_0603` with the kind `silkscreen`, the exit code is 5, and nothing is written

#### Scenario: Two instances that differ
- **GIVEN** an authored board with two `R_0603` instances, one with a pad moved
- **WHEN** `fenolite library <board> --out lib.pretty --dry-run --json` runs
- **THEN** the plan writes `R_0603.kicad_mod` and `R_0603_2.kicad_mod`, and the issues hold one `library.instances-differ`

#### Scenario: A variant name that the board already holds
- **GIVEN** an authored board with two `R_0603` instances that differ, and a third footprint of its own named `R_0603_2`
- **WHEN** a library is made from it
- **THEN** the variant of `R_0603` is `R_0603_3`, `R_0603_2` keeps its own pads, and each of the four footprints has its own file
