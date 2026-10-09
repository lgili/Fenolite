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

### Requirement: Atomic writes of several files
`fenolite.core.io.atomic_write_all(writes, *, backup=True) -> tuple[WriteReceipt, ...]` SHALL write several files so that either every one is written or none is changed, and SHALL raise `WriteError` after putting everything back when any step fails. `atomic_write` stays as it is for a single file.
- `writes` is a sequence of `(path, data)`; the receipts MUST come in the same order and MUST equal those that `atomic_write` gives for each file.
- **Prepare.** The function MUST create the missing parent folders, remembering which it created; write and flush to disk every new content in a temporary file beside its target; and keep every existing target and every existing `<path>.bak` by a hard link beside it, or by a copy where the file system refuses a link.
- **Commit.** It MUST replace the targets with `os.replace` in the given order; then, with `backup` true, rename each kept target to `<path>.bak`, and otherwise remove it.
- **Roll back.** On any exception, `KeyboardInterrupt` and other `BaseException`s included, it MUST put back every replaced target and every `.bak` from what it kept, remove the targets that did not exist before, the temporary and kept files and the folders it created, and raise `WriteError(path, reason)`: `path` the file at which the step failed, `reason` the system's message without a path. `WriteError` MUST be a `FenoliteError` with `cli_code = "FEN-1002"`; an exception that is not an `OSError` MUST be raised again after the roll back instead.
- An exception that arrives after the last target and the last backup are in place MUST NOT undo the write: what was kept is removed and the receipts are returned.
- Two entries with one path MUST raise `ValueError` before anything is touched.
- The function MUST use the standard library only and MUST NOT follow a symbolic link out of the folder of a target.

#### Scenario: A failure in the middle changes nothing
- **GIVEN** three targets of which the first exists with a `.bak`, and a patch that makes the replacement of the third raise `PermissionError`
- **WHEN** `uv run pytest tests/unit/core/test_io_all.py -k rollback` calls `atomic_write_all`
- **THEN** `WriteError` names the third path, the first target and its `.bak` hold their previous bytes, the second and third targets do not exist, and the folder holds no temporary file

#### Scenario: Folders made for the write are removed
- **GIVEN** a target `a/b/c.txt` under a folder `a` that does not exist, and a second target that fails
- **WHEN** the function runs
- **THEN** `a` does not exist afterwards

#### Scenario: Receipts equal single writes
- **WHEN** two files are written with `atomic_write_all` in one folder and with `atomic_write` one by one in another
- **THEN** the receipts are equal apart from the folder, and both folders hold the same files, `.bak` files included

#### Scenario: Without links
- **GIVEN** `os.link` patched to raise `OSError`
- **WHEN** the rollback scenario runs
- **THEN** its outcome is the same

#### Scenario: An interrupt rolls back and passes on
- **GIVEN** a patch that raises `KeyboardInterrupt` after the first replacement
- **WHEN** the function runs over two existing files
- **THEN** both hold their previous bytes and `KeyboardInterrupt` is raised
