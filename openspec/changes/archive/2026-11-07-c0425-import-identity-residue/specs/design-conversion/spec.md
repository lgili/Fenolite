## MODIFIED Requirements

### Requirement: Library made from a board
`fenolite library BOARD --out LIB [--diff LIBRARY]` SHALL write each footprint of a KiCad board, brought back to its origin, rotation 0 and the top side, into the footprint library `LIB` (a `.pretty` folder), under the mutation protocol.
- Instances of one name that differ MUST be written as `<name>_2` and so on, with `library.instances-differ` (warning). A variant MUST take the next suffix that no footprint of the board and no earlier variant holds, so no two written footprints share a name (change c0425).
- `--diff` MUST report per footprint the kinds that differ and write nothing.

#### Scenario: Silkscreen edited on the board
- **GIVEN** an authored board whose instances of `R_0603` have their silkscreen clipped, and a library with the unclipped footprint
- **WHEN** `fenolite library <board> --diff old.pretty --json` runs
- **THEN** the reply names `R_0603` with the kind `silkscreen`, the exit code is 5, and nothing is written

#### Scenario: Two instances that differ
- **GIVEN** an authored board with two `R_0603` instances, one with a pad moved
- **WHEN** `fenolite library <board> --out lib.pretty --dry-run --json` runs
- **THEN** the plan writes `R_0603.kicad_mod` and `R_0603_2.kicad_mod`, and the issues hold one `library.instances-differ`

#### Scenario: A variant name the board already holds
- **GIVEN** the authored two-layer board with a second `R_0603` instance whose pad is moved, and its LED footprint renamed `R_0603_2`
- **WHEN** `uv run pytest tests/unit/library/test_derive.py -k already` derives the library
- **THEN** the footprints are `R_0603`, `R_0603_2` (the board's own) and `R_0603_3` (the variant of `R_0603`)

## ADDED Requirements

### Requirement: Designators used twice explained by a lost schematic
When a conversion to KiCad loses the schematic because the imported circuit has duplicate designators, the `schematic` row SHALL explain, besides the components that only a schematic holds, the level 1 `ref-ambiguous` difference at each designator that the source circuit holds more than once (`Explains("schematic", ("component-missing", "ref-ambiguous"), "ref")`).

#### Scenario: Designator used twice
- **GIVEN** the public Altium blink's design with a second `R1`, made in memory, and a report whose `schematic` row is lost for duplicate designators
- **WHEN** `uv run pytest tests/unit/convert/test_report.py -k twice` asks its `Explainer`
- **THEN** the `ref-ambiguous` difference at `R1` (2 in the source, 1 or 0 written) is explained by `schematic`, one at `D1` (held once) is not, and without the lost row nothing is explained

