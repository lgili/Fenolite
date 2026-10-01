## ADDED Requirements

### Requirement: Geometry errors map to a registered code
`fenolite.geometry.errors.GeometryError` SHALL carry `cli_code = "FEN-3005"`, and the registry in `src/fenolite/cli/errors.py` SHALL contain `FEN-3005` with exit code 3, message "geometry in the input cannot be represented" and the hint "the message names the geometry code and the points".
- The dispatcher MUST map `GeometryError` through "Library errors map to registered codes", so a geometry failure raised while a command reads or builds user input exits 3 instead of 1.
- `docs/cli-contract.md` MUST list `FEN-3005` (`GeometryError`) in its codes table.
- `FEN-3005` is the only new code of this change. `DesignScriptError`, a `FormatError` that wraps every `DslError` and every exception of a design script, MUST map to `FEN-3004`; `LibraryError` and its subclasses MUST keep `FEN-3001`; and `LossyWriteError`, `RulesLossError` and `LayoutExistsError` MUST map to `FEN-7001`.

#### Scenario: Geometry error maps to exit 3
- **GIVEN** the test command of the `run_raising` fixture in `tests/unit/cli/test_library_errors.py`, raising a `GeometryError` with code `geometry.degenerate`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 3, stderr carries `FEN-3005`, and its `message` names `geometry.degenerate`

#### Scenario: Registry row and codes table
- **WHEN** the registry of `fenolite.cli.errors` is looked up for `FEN-3005`
- **THEN** the entry has exit code 3, and the codes table of `docs/cli-contract.md` has a row for `FEN-3005` naming `GeometryError`

#### Scenario: Script errors keep the malformed-input code
- **GIVEN** a `design.py` that raises `ValueError` at line 12
- **WHEN** `fenolite build design.py --out out --dry-run --json` runs
- **THEN** the exit code is 3 and stderr carries `FEN-3004` with `where` ending in `:line:12`

### Requirement: Refusals carry their issues
When a command raises a `FenoliteError` whose `issues` attribute is a non-empty sequence of `Issue`, the dispatcher SHALL put those issues, in order, in the envelope's `issues` list, in addition to the error object on stderr.
- The rule MUST apply whatever the exit code, so a refusal with exit 3 (`UnresolvedLibrariesError`) or exit 7 (`LossyWriteError`, `RulesLossError`, `LayoutExistsError`) names every refused file, net or lib id.
- The envelope's `ok` MUST stay `false`, and its `result` MUST stay as the dispatcher builds it for an exception today.
- An exception without an `issues` attribute, or with an empty one, MUST give an empty `issues` list, as before.
- The JSON document on stdout MUST still be exactly one document and MUST validate against the envelope schema.

#### Scenario: Lossy refusal lists its issues
- **GIVEN** the `_raise` test command of `tests/unit/cli/test_library_errors.py` raising `LossyWriteError` with two issues `kicad.project.pattern-unsafe`, run through a fixture that returns stdout as well as stderr
- **WHEN** it runs with `--json`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and the envelope's `issues` holds the two issues in order

#### Scenario: Unresolved libraries list every lib id
- **GIVEN** a `design.py` whose parts name the unknown lib ids `Nope:A` and `Nope:B`
- **WHEN** `fenolite build design.py --out out --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and the envelope's `issues` holds one `kicad.lib.*` issue for each of the two lib ids

#### Scenario: Exceptions without issues are unchanged
- **GIVEN** the hidden `_echo` command invoked with `--raise`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 1 and the envelope's `issues` is an empty list

## MODIFIED Requirements

### Requirement: Determinism flags
The global flags `--seed INT` and `--timestamp ISO8601` SHALL be accepted by every command, and commands that generate identifiers or dates MUST take them from these flags.
- Ids derived from keys (`design-model` "Identifier derivation", third and fourth cases) are not generated: they MUST NOT depend on `--seed`.
- A command that writes no date, such as `build`, MUST accept `--timestamp` and ignore it.

#### Scenario: Identical outputs
- **WHEN** `_echo --gen-id --seed 7 --timestamp 2026-01-01T00:00:00Z --json` runs twice
- **THEN** both stdout documents are byte-identical except `elapsed_ms`

#### Scenario: Keyed ids ignore the seed
- **GIVEN** two empty folders `B1` and `B2`
- **WHEN** `fenolite build examples/blink_2layer/design.py --confirm --json` runs with `--out B1 --seed 1 --timestamp 2026-01-01T00:00:00Z`, and with `--out B2 --seed 2 --timestamp 2027-06-01T00:00:00Z`
- **THEN** every file under `B1` has the same bytes as the file with the same relative path under `B2`
