# core-primitives Specification

## Purpose
Provide the stdlib-only primitives shared by all packages: exact units and conversions, identifiers, evidence labels, errors and findings, and atomic file I/O.
## Requirements
### Requirement: Length and angle parsing and formatting
`fenolite.core.units` SHALL parse strings with units `nm`, `um`, `mm`, `cm`, `m`, `mil`, `in` into integer nanometres, SHALL parse `deg`/`udeg` into integer microdegrees, SHALL reject values that are not exactly representable, and SHALL format nanometres back into any of those units with the minimal exact decimal representation.

#### Scenario: Millimetres
- **WHEN** `parse_length("0.25mm")` is called
- **THEN** it returns `250000`

#### Scenario: Mils
- **WHEN** `parse_length("10mil")` is called
- **THEN** it returns `254000`

#### Scenario: Inexact value rejected
- **WHEN** `parse_length("0.0000001mm")` is called
- **THEN** a `ValueError` is raised stating the value is not representable in nanometres

#### Scenario: Round trip formatting
- **GIVEN** `nm = 250000`
- **WHEN** `format_length(nm, "mm")` is called
- **THEN** it returns `"0.25mm"` and `parse_length` of that string returns `250000`

### Requirement: Exact conversion to and from the 1/10000 mil unit
`fenolite.core.units` SHALL provide `u_to_nm(u: int) -> int` and `nm_to_u(nm: int) -> int` computed with integer arithmetic only, rounding half to even at the midpoint, symmetrically for negative values, and the boundary cases MUST be tabulated in `docs/formats/units.md`.

#### Scenario: Whole multiples are exact
- **WHEN** `u_to_nm(50)` and `nm_to_u(127)` are called
- **THEN** they return `127` and `50` respectively

#### Scenario: No floats involved
- **GIVEN** `u = 10**18`
- **WHEN** `u_to_nm(u)` is called
- **THEN** the result equals `u * 127 // 50` exactly (no rounding is needed and no float is involved)

#### Scenario: Negative symmetry
- **WHEN** `u_to_nm(-u)` is compared with `-u_to_nm(u)` for the hypothesis range
- **THEN** they are equal

### Requirement: Identifier helpers
`fenolite.core.ids` SHALL expose `new_id(prefix, rng)`, `derived_id(prefix, backend, native_id)` and `content_id(prefix, backend, doc_native_id, section, content_hash)` implementing the derivation rules of the design model, and SHALL validate prefixes against the closed prefix table.

#### Scenario: Unknown prefix rejected
- **WHEN** `new_id("foo", rng)` is called
- **THEN** a `ValueError` is raised

### Requirement: Evidence labels
`fenolite.core.evidence` SHALL define the `Level` enumeration with the total order `ALTIUM_VERIFIED_KIT > KICAD_VERIFIED > ORACLE_VERIFIED > CORPUS_VERIFIED > ALTIUM_VERIFIED_AUTHOR_REPORT > INFERRED > UNKNOWN > UNVERIFIED`, `min_level(*levels)`, an `Evidence(level, oracle, hypotheses)` record, and the string forms used in CLI output.

#### Scenario: Lowest level wins
- **WHEN** `min_level(Level.KICAD_VERIFIED, Level.INFERRED)` is called
- **THEN** it returns `Level.INFERRED`

#### Scenario: String form with oracle
- **WHEN** `Evidence(Level.ORACLE_VERIFIED, "kicad-import", []).label()` is called
- **THEN** it returns `"ORACLE-VERIFIED(kicad-import)"`

### Requirement: Errors and issues
`fenolite.core.errors` SHALL define `FormatError(file, locator, offset, message)`, `ConsistencyError` and `Issue(code, severity, message, where, hint, retryable)` with `severity` restricted to `error | warning | info` and `code` restricted to dotted lowercase identifiers.

#### Scenario: Invalid issue code
- **WHEN** `Issue(code="Bad Code", …)` is constructed
- **THEN** a `ValueError` is raised

### Requirement: Atomic I/O
`fenolite.core.io.atomic_write(path, data, backup=True)` SHALL write to a temporary file in the same directory, rename it over the target, keep the previous content in `<path>.bak` when `backup` is true and the target existed, and return a receipt with `path`, `sha256` and `backup_path`.

#### Scenario: Interrupted write leaves the original intact
- **GIVEN** an existing file and a write that fails before the rename
- **WHEN** the failure occurs
- **THEN** the original file is unchanged and no partial file remains

#### Scenario: Receipt hash matches
- **WHEN** `atomic_write` completes
- **THEN** `receipt.sha256` equals `sha256_of(path)`

