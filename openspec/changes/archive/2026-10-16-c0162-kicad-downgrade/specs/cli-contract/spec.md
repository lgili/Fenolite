## MODIFIED Requirements

### Requirement: Library errors map to registered codes
The command dispatcher SHALL convert an exception raised inside a command as follows:
- a `fenolite.core.errors.FenoliteError` whose class attribute `cli_code` is a registered `FEN-NNNN` code becomes that code's error;
- a `FormatError` without `cli_code` becomes `FEN-3004` ("malformed input file");
- any other exception stays `FEN-1001`.

The error's `message` SHALL be `exc.message` for a `FormatError` and `str(exc)` otherwise, so the location is never repeated inside the message. For a `FormatError`, `where` SHALL be built from its `file`, `locator` and offset, joined by `:` with the offset written `@N`. When the exception has a non-empty `hint` attribute, it SHALL replace the registry hint. The exit code SHALL be the first digit of the resulting code.

The registry SHALL contain `FEN-3003` ("input format version older than the oldest supported"), `FEN-3004` ("malformed input file"; hint "the message and where locate the problem") and `FEN-7002` ("target format version older than the input; no downgrade was asked"; hint "convert the project with 'fenolite convert <project> --to kicad --kicad-version <target>'"), in addition to the existing `FEN-3002`. `docs/cli-contract.md` SHALL list all four.

Tests SHALL inject these exceptions through a command registered only for the test, by a fixture in `tests/unit/cli/test_library_errors.py` that adds it to the discovered command set; the shipped `_echo` command is not changed.

#### Scenario: Future format maps to exit 3
- **GIVEN** a test command whose `run` raises `FutureFormatError("board 20990101 is newer than 20260206", file="a.kicad_pcb")`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 3, stderr carries `FEN-3002` with `where` equal to `a.kicad_pcb`, and the message does not start with `a.kicad_pcb`

#### Scenario: Too-old input carries the upgrade hint
- **GIVEN** a test command whose `run` raises `UnsupportedFormatError` for a board at `20221018`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 3, stderr carries `FEN-3003`, and its `hint` contains `kicad-cli pcb upgrade`

#### Scenario: Downgrade maps to exit 7
- **GIVEN** a test command whose `run` raises `DowngradeRefusedError` from major 10 to target 9
- **WHEN** it runs
- **THEN** the exit code is 7 and stderr carries `FEN-7002`

#### Scenario: Plain format error maps to exit 3
- **GIVEN** a test command whose `run` raises `FormatError("unbalanced parenthesis", file="b.kicad_pcb", offset=12)`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 3, stderr carries `FEN-3004` with `message` equal to `unbalanced parenthesis` and `where` equal to `b.kicad_pcb:@12`

#### Scenario: Unregistered code falls back to internal error
- **GIVEN** a `FenoliteError` subclass with `cli_code = "FEN-3999"`, which is not registered
- **WHEN** a command raises it
- **THEN** the exit code is 1 and stderr carries `FEN-1001`

