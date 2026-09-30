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

#### Scenario: Identical outputs
- **WHEN** `_echo --gen-id --seed 7 --timestamp 2026-01-01T00:00:00Z --json` runs twice
- **THEN** both stdout documents are byte-identical except `elapsed_ms`

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

