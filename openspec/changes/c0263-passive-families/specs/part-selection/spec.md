## ADDED Requirements

### Requirement: Grammar family rows
A `fenolite.family.v1` record SHALL be a row source of c0254, read from the same places as v0 families and from installed packs. Its candidates MUST be the encode candidates of the query, each an in-memory c0248 device with `id = "<family id>@<MPN>"`, `manufacturer`, `mpn`, symbol, footprint, the pins `1` and `2`, `kind`, `value` and ratings in c0248's integer units.

#### Scenario: A pick of an exact MPN
- **GIVEN** `examples/families/` holding `example_mlcc.toml` beside a script that asks `capacitor(farad("100n"), rating=volt(25), case="0603", dielectric="X7R")` with an empty lock
- **WHEN** it is built with `--dry-run --json`
- **THEN** the pick is `Example:EX_MLCC@EX03R104KAT`, `issues` hold `pick.new`, and the planned BOM row names `Example Passive` and `EX03R104KAT`

### Requirement: Picks of grammar candidates
The lock entry of a grammar candidate SHALL have `device` the candidate id, `row` the family id and `sha256` the SHA-256 of the candidate's canonical text (family id, version, MPN and sorted attributes). An edit of the family that leaves the candidate unchanged MUST keep the locked hash and plan no lock write.

#### Scenario: An unrelated grammar edit keeps the pick
- **GIVEN** a confirmed build whose lock holds `C_in` as `Example:EX_MLCC@EX03R104KAT`, after which a `[[valid]]` row for size `05` is widened
- **WHEN** the build runs with `--dry-run`
- **THEN** the device is the locked one, no `pick.row-changed` is given, and no lock write is planned
