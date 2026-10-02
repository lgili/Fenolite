# cli-contract Specification

## Purpose
Define the machine-readable contract every `fenolite` command follows (output modes, envelope, typed errors, exit codes, mutation protocol, determinism flags, capability discovery) so that AI agents and CI pipelines can drive the tool without parsing human text.
## Requirements
### Requirement: Output mode selection
Every `fenolite` command SHALL emit JSON on stdout when stdout is not a TTY and human-readable text when it is. The flags `--json` and `--text` SHALL override the detection. JSON output MUST be exactly one JSON document followed by a newline.

#### Scenario: Piped invocation yields JSON
- **GIVEN** a command run as `fenolite capabilities | cat`
- **WHEN** the command completes
- **THEN** stdout contains a single JSON object parseable by `json.loads`

#### Scenario: Terminal invocation yields text
- **GIVEN** a command run with stdout attached to a pseudo-terminal
- **WHEN** the command completes
- **THEN** stdout is not a JSON document and contains at least one line of text

#### Scenario: Explicit override
- **WHEN** `fenolite capabilities --json` runs on a pseudo-terminal
- **THEN** stdout is a JSON document

### Requirement: Envelope
Every JSON response MUST be an object with exactly the top-level keys `ok`, `command`, `schema`, `input`, `result`, `issues`, `evidence`, `receipt`, `elapsed_ms`, and MUST validate against `schemas/fenolite.envelope.v0.json`. `schema` MUST be `fenolite.<command>.v0`. `issues` MUST be a list of `{code, severity, message, where, hint, retryable}` objects with `severity` in `error | warning | info`. `evidence` MUST be `{level, oracle, hypotheses}`.

#### Scenario: Envelope validates
- **WHEN** any registered command runs with `--json`
- **THEN** the output validates against the envelope schema and `schema` equals `fenolite.<command>.v0`

#### Scenario: Evidence defaults to UNVERIFIED
- **GIVEN** a command that does not set an evidence level
- **WHEN** it runs with `--json`
- **THEN** `evidence.level` equals `UNVERIFIED`

### Requirement: Field projection
The global flag `--fields a,b.c` SHALL restrict `result` to the listed dotted paths and SHALL always keep `ok`, `command`, `schema`, `issues`, `evidence` and `receipt` in the envelope.

#### Scenario: Projection keeps mandatory keys
- **WHEN** `fenolite capabilities --json --fields commands` runs
- **THEN** `result` contains only `commands` and the envelope still contains `issues` and `evidence`

#### Scenario: Unknown field is a usage error
- **WHEN** `fenolite capabilities --json --fields nope` runs
- **THEN** the exit code is 2 and stderr carries error code `FEN-2xxx`

### Requirement: Typed errors on stderr
Whenever a command exits with a non-zero code, stderr MUST carry exactly one error object `{code, message, hint, retryable, where}` (JSON in JSON mode, one line `error <code>: <message> (<hint>)` in text mode). `code` MUST match `FEN-[1-7][0-9]{3}` and its first digit MUST equal the exit code.

#### Scenario: Internal exception
- **GIVEN** the hidden `_echo` command is invoked with `--raise`
- **WHEN** it runs
- **THEN** the exit code is 1 and stderr carries `FEN-1xxx` with a non-empty `message`

#### Scenario: Usage error
- **WHEN** `fenolite capabilities --no-such-flag` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2xxx`

### Requirement: Exit-code vocabulary
Commands MUST use only these exit codes: `0` success; `1` internal failure; `2` usage error; `3` input unreadable or from a future format version; `4` confirmation required; `5` verification produced findings of severity `error`; `6` external tool missing or incompatible; `7` requested operation not representable without loss.

#### Scenario: Findings map to 5
- **GIVEN** `_echo --issue error` produces an issue of severity `error`
- **WHEN** it runs
- **THEN** the exit code is 5 and `ok` is `false`

#### Scenario: Warnings do not fail
- **GIVEN** `_echo --issue warning` produces only warnings
- **WHEN** it runs
- **THEN** the exit code is 0 and `ok` is `true`

### Requirement: Mutation protocol
A command declared as mutating MUST accept `--dry-run` and `--confirm`. With `--dry-run` it MUST return the plan of intended writes in `result.plan` with exit 0 and write nothing. Without `--confirm` it MUST return the plan with exit 4 and error `FEN-4001` and write nothing. With `--confirm` it MUST write atomically (temporary file then rename), keep a `.bak` of any overwritten file unless `--no-backup` is given, and fill `receipt.written` with `{path, sha256}` for every file written.

#### Scenario: Dry run writes nothing
- **GIVEN** `_echo --write out.txt --dry-run`
- **WHEN** it runs in an empty directory
- **THEN** exit code is 0, `result.plan` lists `out.txt`, and the directory is still empty

#### Scenario: Missing confirmation
- **GIVEN** `_echo --write out.txt`
- **WHEN** it runs
- **THEN** exit code is 4, stderr carries `FEN-4001`, and nothing is written

#### Scenario: Confirmed write with receipt and backup
- **GIVEN** `out.txt` already exists
- **WHEN** `_echo --write out.txt --confirm` runs
- **THEN** `out.txt` has the new content, `out.txt.bak` holds the previous content, and `receipt.written[0].sha256` equals the SHA-256 of the new file

#### Scenario: Conflicting flags
- **WHEN** `_echo --write out.txt --dry-run --confirm` runs
- **THEN** the exit code is 2

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

### Requirement: Capabilities command
`fenolite capabilities` SHALL list every registered command with `name`, `mutates` and `schema`; the backends registered; the optional extras detected; the external tools detected (`kicad-cli`, `java`, `docker`) with version strings when present; and the boolean `sends_data_offsite`.

#### Scenario: Capabilities lists commands
- **WHEN** `fenolite capabilities --json` runs
- **THEN** `result.commands` contains an entry named `capabilities` with `mutates` equal to `false`

#### Scenario: Tool detection is non-fatal
- **GIVEN** `kicad-cli` is not installed
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the exit code is 0 and `result.tools.kicad-cli` is `null`

### Requirement: Consistency test covers every command
`tests/consistency/test_cli_consistency.py` SHALL enumerate all registered commands and verify `--help`, JSON envelope validity, text mode, `--fields`, error mapping and, for mutating commands, the mutation protocol.

#### Scenario: New command without envelope fails the suite
- **GIVEN** a contributor registers `cmd_foo.py` whose `run` returns a plain dict
- **WHEN** the consistency test runs
- **THEN** it fails naming `foo`

### Requirement: Library errors map to registered codes
The command dispatcher SHALL convert an exception raised inside a command as follows:
- a `fenolite.core.errors.FenoliteError` whose class attribute `cli_code` is a registered `FEN-NNNN` code becomes that code's error;
- a `FormatError` without `cli_code` becomes `FEN-3004` ("malformed input file");
- any other exception stays `FEN-1001`.

The error's `message` SHALL be `exc.message` for a `FormatError` and `str(exc)` otherwise, so the location is never repeated inside the message. For a `FormatError`, `where` SHALL be built from its `file`, `locator` and offset, joined by `:` with the offset written `@N`. When the exception has a non-empty `hint` attribute, it SHALL replace the registry hint. The exit code SHALL be the first digit of the resulting code.

The registry SHALL contain `FEN-3003` ("input format version older than the oldest supported"), `FEN-3004` ("malformed input file"; hint "the message and where locate the problem") and `FEN-7002` ("target format version older than the input; downgrade is not supported"), in addition to the existing `FEN-3002`. `docs/cli-contract.md` SHALL list all four.

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

### Requirement: Backends in capabilities
`fenolite capabilities` SHALL fill `result.backends` with `CapabilityReport.to_json()` of every backend in `fenolite.backends.registry.all_backends()`, sorted by name. Each entry MUST have the keys `name`, `read_kinds`, `write_kinds`, `targets`, `default_target`, `downgrade`, `operations` and `evidence`.
- Listing backends MUST NOT run any external tool, so the entry is the same with `--no-tools`.
- The `kicad-cli` entry of `result.tools` MUST take its path from `fenolite.backends.kicad.cli.find_kicad_cli()`. Its version detection MUST stay as before, so the same machine reports the same path and version.
- `docs/cli-contract.md` MUST describe the backend entry under "Discovery".

#### Scenario: KiCad backend listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result.backends[0].name` is `kicad`, its `read_kinds` contain `kicad_pcb`, `kicad_mod` and `kicad_sym`, its `operations` contain `detect` and `read`, and contain `write` only when its `write_kinds` is not empty, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Backend field projection
- **WHEN** `uv run fenolite capabilities --json --no-tools --fields backends` runs
- **THEN** `result` contains only `backends`, and the exit code is 0

#### Scenario: Same kicad-cli as before
- **GIVEN** `FENOLITE_KICAD_CLI` naming a fake `kicad-cli` script whose `version` prints `10.0.6`
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_backends.py -k tool_path` runs `capabilities`
- **THEN** `result.tools.kicad-cli.path` is that script and `result.tools.kicad-cli.version` is `10.0.6`

### Requirement: KiCad target and lossy flags
Every `fenolite` command SHALL accept the global flags `--kicad-version {9,10}` (default 10) and `--allow-lossy`, before or after the command name, like `--seed`. The dispatcher MUST pass them to the command as `Context.kicad_target: int` and `Context.allow_lossy: bool`.
- Any other `--kicad-version` value MUST be a usage error: exit 2 with `FEN-2001`.
- A command that writes KiCad files MUST use `Context.kicad_target` as its target and `Context.allow_lossy` as its lossy switch.
- `docs/cli-contract.md` MUST describe both flags.
- The `FEN-7001` hint, "re-run with --allow-lossy to accept the loss", refers to this flag.

#### Scenario: Flags reach the context
- **GIVEN** a test command that returns `ctx.kicad_target` and `ctx.allow_lossy` in its result
- **WHEN** `fenolite --kicad-version 9 --allow-lossy <test command> --json` runs
- **THEN** the result holds `9` and `true`

#### Scenario: Defaults
- **GIVEN** the same test command
- **WHEN** it runs without either flag
- **THEN** the result holds `10` and `false`

#### Scenario: Unsupported target is a usage error
- **WHEN** `fenolite --kicad-version 8 capabilities --json` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Consistency test covers the flags
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** it passes, and every command's `--help` lists `--kicad-version` and `--allow-lossy`

### Requirement: Legacy board edits are refused
The registry in `src/fenolite/cli/errors.py` SHALL contain `FEN-7003` with exit code 7, message "input from KiCad 8.0 is read-only; writing needs a KiCad 9.0 or newer source" and a hint naming `kicad-cli pcb upgrade`. `fenolite.backends.kicad.versions.LegacyEditRefusedError` MUST carry `cli_code = "FEN-7003"`, and `LossyWriteError` MUST carry `cli_code = "FEN-7001"`, so the dispatcher maps both through "Library errors map to registered codes". `docs/cli-contract.md` MUST list `FEN-7001` (`LossyWriteError`) and `FEN-7003` (`LegacyEditRefusedError`) in its codes table.

#### Scenario: Legacy edit maps to exit 7
- **GIVEN** the test command of the `run_raising` fixture in `tests/unit/cli/test_library_errors.py`, raising `LegacyEditRefusedError` for a board at `20240108`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 7, stderr carries `FEN-7003`, and its `hint` contains `kicad-cli pcb upgrade`

#### Scenario: Lossy write maps to exit 7
- **GIVEN** the same fixture's command raising `LossyWriteError` with `droppable == True`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and its `hint` contains `--allow-lossy`

#### Scenario: Non-droppable loss keeps its own hint
- **GIVEN** the same fixture's command raising `LossyWriteError` with `droppable == False` and an issue `kicad.board.opaque-net-ref`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and its `hint` does not contain `--allow-lossy`

#### Scenario: Codes documented
- **WHEN** `docs/cli-contract.md` is read
- **THEN** its codes table has rows for `FEN-7001` and `FEN-7003`

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

