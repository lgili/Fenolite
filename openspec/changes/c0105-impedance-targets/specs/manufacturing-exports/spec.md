## ADDED Requirements

### Requirement: Impedance table for the fabricator
`fenolite.exports.impedance.impedance_table(design) -> tuple[ImpedanceRow, ...]` SHALL give the impedance table of a design: one row per impedance target and layer ("Impedance targets in the rules model"), sorted by target name, then in stack order. It reads the model only, runs no tool and writes nothing.
- `ImpedanceRow` MUST hold `target`, `kind`, `structure` (`microstrip` for one reference on an outer layer, `stripline` for two references on an inner layer, else `""`), `layer`, `references`, `ohms`, `tolerance_percent`, `width`, `gap` (`None` for a single target), `heights` (one height per reference in nanometres, from `Board.stackup`, or `None` without a stack-up), `epsilon_r` (the permittivity between the layer and its references, as decimal text, `""` when unknown or when the references see different values), `classes` (names) and `nets` (the names of the classes' nets, sorted).
- `COLUMNS` MUST be the CSV header: `target`, `kind`, `structure`, `layer`, `references`, `ohms`, `tolerance_percent`, `width_mm`, `gap_mm`, `heights_mm`, `epsilon_r`, `classes`, `nets`. `render_csv(rows, estimates=None) -> bytes` MUST write them through `assembly.render_csv`, lengths as exact millimetre text, lists joined by one space, and, when `estimates` is given, the columns `estimate_ohms` and `suggested_width_mm` after them.
- `fenolite.exports.impedance.ISSUE_CODES` MUST be the closed table of the codes of the table and of `fenolite impedance` ("Impedance command"):

| code | severity | when |
|---|---|---|
| `impedance.none` | info | the design holds no impedance target |
| `impedance.no-stackup` | warning | an estimate needs a stack-up that the board lacks, or a row's layers are not in it; the rows left out are counted |
| `impedance.estimate-unsupported` | info | rows whose structure has no form: differential, one reference on an inner layer, two references on an outer layer |
| `impedance.mixed-dielectric` | info | a row's height crosses dielectrics of different permittivity, combined in series |
| `impedance.out-of-range` | warning | a row lies outside the stated range of its form |
| `impedance.off-target` | warning | a row's estimate lies outside the target's tolerance; never given without a tolerance |

- The table and the CSV MUST hold no date, no absolute path and no number produced from a `float`. `exports.impedance.EVIDENCE` MUST be the level of the design's source, as the command reports it.

#### Scenario: Table of the bench
- **GIVEN** the design of "Two targets synthesised for target 10" with the four-layer stack-up of the bench (0.2 mm prepreg of permittivity 4.3 between `F.Cu` and `In1.Cu`)
- **WHEN** `impedance_table(design)` is called
- **THEN** it returns three rows: `SE50` on `F.Cu` and `B.Cu`, `microstrip`, `heights == (200_000,)` on `F.Cu`, `epsilon_r == "4.3"`, then `USB90` on `F.Cu` with `gap == 150_000` and its two nets

#### Scenario: CSV header and lengths
- **WHEN** `render_csv` writes those rows
- **THEN** the first line is the header of `COLUMNS`, and the `USB90` line holds `0.2` and `0.15` in `width_mm` and `gap_mm`
