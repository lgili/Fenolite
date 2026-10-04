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

### Requirement: Inspect command
`fenolite inspect FILE [--summary]` SHALL be registered by `src/fenolite/cli/cmd_inspect.py` with `mutates=False`, and SHALL summarise one KiCad file without running any external tool. `--summary` is the only view in this change and the default.
- **Kinds.** Boards, footprint files and symbol libraries (file or `.kicad_symdir` folder) MUST be read through `registry.for_path(FILE).read`. `.kicad_sch` and `.kicad_wks` files MUST be read header-only through `versions.inspect`, with root-child counts by head. `.kicad_pro`, `.kicad_dru` and files that are not S-expressions MUST exit 2 with `FEN-2001`.
- **Result.** `result` MUST hold `kind`, `format_version`, `major`, `status`, `generator`, `generator_version`, `counts`, `opaque_count` and `model_findings`. Board `counts` MUST hold `footprints`, `pads`, `nets`, `tracks`, `arcs`, `vias`, `zones`, `fills`, `keepouts`, `graphics` and `texts`. `opaque_count` MUST be `pcb.opaque_count` of the design for a board and `null` otherwise. `model_findings` MUST count the `model.*` findings by severity. `input.path` MUST be the file name without its folder, so the output does not depend on the working directory.
- **Issues.** Reader issues MUST be reported as issues. `model.*` findings MUST only be counted, so a board that KiCad saves with duplicate references exits 0.
- **Errors.** A read error MUST exit 3 with its code (`FEN-3002`, `FEN-3003` or `FEN-3004`), and a missing file with `FEN-3001`.
- **Evidence.** The envelope evidence MUST be the reader module's `EVIDENCE`, and `INFERRED` (`H-K-TOK-CONSTANTS`) for header-only kinds.
- `example_args` MUST be `(EXAMPLE_BOARD, "--summary")`, with `fenolite.cli._examples.EXAMPLE_BOARD` as in "Check command input" (`verification-loop`), and MUST run no subprocess from any working directory.

#### Scenario: Authored board summary
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.kind` is `kicad_pcb`, `format_version` is `20241229`, `major` is 9, `counts` is footprints 2, pads 4, nets 3, tracks 3, arcs 1, vias 1, zones 1, fills 2, keepouts 1, graphics 6 and texts 1, and `opaque_count` equals `pcb.opaque_count` of the read design

#### Scenario: Model findings are counted
- **GIVEN** a copy of the authored board whose second footprint has the reference of the first
- **WHEN** `uv run pytest tests/unit/cli/test_inspect_cmd.py -k findings` runs `inspect` on it
- **THEN** the exit code is 0 and `result.model_findings.error` is at least 1

#### Scenario: Unreadable and deferred files
- **WHEN** `fenolite inspect` runs on `tests/data/kicad/sexpr/mirror/unbalanced.kicad_pcb` and on a `.kicad_pro` file
- **THEN** the first exits 3 with `FEN-3004`, and the second exits 2 with `FEN-2001`

#### Scenario: Inspect is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `inspect` with its `example_args`
- **THEN** the exit code is 0

### Requirement: Doctor command
`fenolite doctor` SHALL be registered by `src/fenolite/cli/cmd_doctor.py` with `mutates=False`, and SHALL report the external tools Fenolite can use. A missing or unsupported tool MUST give an issue and exit 0.
- **Candidates.** `fenolite.backends.kicad.cli.kicad_cli_candidates(explicit=()) -> tuple[CliCandidate, ...]` MUST list, in order, each `--kicad-cli PATH` (repeatable; source `explicit`), `FENOLITE_KICAD_CLI` (`env`), `kicad-cli` in each `PATH` entry (`path`) and the macOS application bundle (`macos-app`). It MUST keep existing files only, deduplicated by resolved path, and the first source of each.
- **kicad-cli entries.** `result.kicad_cli` MUST hold one entry per candidate with `path`, `source`, `version`, `major`, `supported` (major in `TARGET_MAJORS`), `selected` (true for the candidate at the resolved path that `find_kicad_cli(<first --kicad-cli, or None>)` returns) `matrix` (the rows of `command_matrix`, `"unknown"` for the rows of pages that did not parse) and `evidence` (see **Evidence**). `result.by_major` MUST map each major to the paths of its candidates.
- **Other tools.** `result.java` MUST hold `path`, the first line of `java -version` and the major per JEP 223 (S-0081), so `1.8.0_402` gives 8 and `17.0.2` gives 17. `result.docker` MUST hold `path`, the version from `docker --version`, and `daemon`, the output of `docker version --format '{{.Server.Version}}'` (S-0080) or `null` when the daemon does not answer. A missing tool MUST be `null`.
- **Runner.** Every `kicad-cli` call, `--help` included, MUST go through c0009's `KicadCli`.
- **Issues.** `doctor.tool-missing` (warning) for each absent tool and for an explicit path or `FENOLITE_KICAD_CLI` that names a missing file (then `find_kicad_cli` returns `None`), `doctor.tool-unsupported` (warning) for a candidate whose major is not in `TARGET_MAJORS`, and `doctor.help-unparsed` (warning) naming each page that did not parse.
- **No run.** `--no-run` MUST list the candidates and run no tool; versions and matrices are then `null`.
- **Evidence.** Each `result.kicad_cli[]` entry that ran MUST carry its own `evidence`: `helpmatrix.EVIDENCE` with oracle `kicad-cli <version>` when every page of that candidate parsed, `UNVERIFIED` otherwise. The envelope evidence MUST be `helpmatrix.EVIDENCE` with one oracle, `kicad-cli <version>` of the selected candidate (of the first candidate that ran when none is selected), when every page of every candidate that ran parsed, and `UNVERIFIED` otherwise, with `--no-run`, or when no candidate ran. It MUST never be above `helpmatrix.EVIDENCE`.
- `capabilities` MUST stay unchanged. `example_args` MUST be `("--no-run",)`.

#### Scenario: Synthetic help pages
- **GIVEN** a fake `kicad-cli` whose `version` prints `10.0.6` and whose `--help` pages are authored synthetic pages, no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/cli/test_doctor_cmd.py -k matrix` runs `fenolite doctor --kicad-cli <fake> --json`
- **THEN** the candidate has `source` `explicit`, `major` 10, `supported` true, and the matrix rows that the pages list

#### Scenario: Missing java and docker
- **GIVEN** `PATH` holding neither `java` nor `docker` nor `kicad-cli`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `fenolite doctor --json` runs
- **THEN** `result.java` and `result.docker` are `null`, two `doctor.tool-missing` warnings name them, and the exit code is 0

#### Scenario: No run
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `doctor --no-run`
- **THEN** the exit code is 0, the candidates are listed, and `evidence.level` is `UNVERIFIED`

#### Scenario: One entry per binary
- **GIVEN** `FENOLITE_KICAD_CLI` and a `PATH` entry naming the same fake `kicad-cli` through a symbolic link, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `fenolite doctor --json` runs
- **THEN** `result.kicad_cli` holds one entry, with source `env`

#### Scenario: Override names a missing file
- **GIVEN** `FENOLITE_KICAD_CLI` naming a file that does not exist, a fake `kicad-cli` on `PATH`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `fenolite doctor --no-run --json` runs
- **THEN** the `PATH` candidate is listed with `selected: false`, one `doctor.tool-missing` warning names `FENOLITE_KICAD_CLI`, and the exit code is 0

#### Scenario: Local installation
- **GIVEN** kicad-cli 10.0.6 installed locally
- **WHEN** `uv run fenolite doctor --json` runs
- **THEN** it lists a 10.0.6 candidate with `selected: true`, and an entry or a `doctor.tool-missing` warning for each of `java` and `docker`

### Requirement: Export command
`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--all] [--manifest] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_export.py` with `mutates=True`, and SHALL write the fabrication files that `kicad-cli` produces from a copy of the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Kinds.** `--all` MUST select the four kinds. A call that selects none MUST exit 2 with `FEN-2001`.
- **Tool.** The command MUST exit 6 with `FEN-6001` when no `kicad-cli` is found and with `FEN-6002` for an unsupported major or a board newer than the tool reads. `--timeout` MUST default to 300 and apply to each run.
- **Source.** The board, its project files and its folder MUST NOT change; every run happens on the copy set of `projectset.project_set`.
- **Writes.** The command MUST return one `PlannedWrite` per artefact at `DIR/<artefact path>`, and with `--manifest` one for `DIR/fenolite-artifacts.json`; `DIR` is relative to the working directory. When any selected kind fails, the command MUST return no `PlannedWrite`, MUST report the kind's issue and MUST exit 5. The mutation protocol (`--dry-run`, `--confirm`, backup, receipt) applies unchanged.
- **Result.** `result` MUST hold `board`, `out`, `kinds`, `artifacts` (`path`, `kind`, `layer`, `bytes`, `sha256`, `content_sha256`; sorted by path), `tool_version` and `tool_writes`. No value MUST hold a temporary path, the home directory or a date.
- **Exit codes.** 0 when the files are planned or written; 5 with `export.failed` or `export.kind-unavailable`; 3 for a board Fenolite cannot read.
- `example_args` MUST be `(EXAMPLE_BOARD, "--out", "fab", "--all", "--manifest", "--dry-run")`, `mutation_example_args` the same without `--dry-run`, and `example_tools` MUST be `("kicad-cli",)`.

#### Scenario: Plan, then write
- **GIVEN** a fake `kicad-cli` 10.0.6 that writes two Gerbers, two drill files, a position file and a netlist
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k plan` runs `fenolite export <board> --out fab --all --manifest --dry-run` and then `--confirm`
- **THEN** the first exits 0 with a seven-file plan and writes nothing, and the second writes the seven files and its receipt lists each with its SHA-256

#### Scenario: Manifest matches the files
- **GIVEN** the folder the previous scenario wrote
- **WHEN** `fab/fenolite-artifacts.json` is read
- **THEN** each entry's `sha256` and `bytes` equal the file's, and `board.sha256` equals the source board's

#### Scenario: One failing kind writes nothing
- **GIVEN** a fake `kicad-cli` that exits 1 for `pcb export drill`
- **WHEN** `fenolite export <board> --out fab --all --confirm` runs
- **THEN** the exit code is 5, the issues hold one `export.failed` with `where` `drill`, and `fab` does not exist

#### Scenario: No kind selected
- **WHEN** `fenolite export <board> --out fab --confirm` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Source is untouched
- **WHEN** `uv run pytest tests/unit/cli/test_check_readonly.py -k export` hashes the project folder before and after `fenolite export … --out <elsewhere> --confirm`
- **THEN** the folder holds the same files with the same bytes

#### Scenario: No tool
- **GIVEN** no `kicad-cli` on `PATH` and no `FENOLITE_KICAD_CLI`
- **WHEN** `fenolite export <board> --out fab --all --dry-run` runs
- **THEN** the exit code is 6 and stderr carries `FEN-6001`

### Requirement: Render command
`fenolite render PATH --out DIR [--svg] [--png] [--width PX] [--height PX] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_render.py` with `mutates=True`, and SHALL write the review views of the board that `PATH` names.
- A call with neither `--svg` nor `--png` MUST exit 2 with `FEN-2001`. `--width` MUST default to 1600 and `--height` to 1200; both MUST be between 64 and 8192.
- The tool errors, the copy set and the mutation protocol MUST be `export`'s.
- The command MUST return one `PlannedWrite` per view produced, at `DIR/<view name>`.
- `result` MUST hold `board`, `out`, `views` (`path`, `kind`, `bytes`, `sha256`; sorted by path) and `tool_version`.
- A view that fails MUST give `render.failed` (warning) and the exit code MUST stay 0.
- `example_args` MUST be `(EXAMPLE_BOARD, "--out", "views", "--svg", "--png", "--dry-run")`, `mutation_example_args` the same without `--dry-run`, and `example_tools` MUST be `("kicad-cli",)`.

#### Scenario: Plan, then write
- **GIVEN** a fake `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/unit/cli/test_render_cmd.py -k plan` runs `fenolite render <board> --out views --svg --dry-run` and then `--confirm`
- **THEN** the first plans `views/front.svg` and `views/back.svg` and writes nothing, and the second writes both

#### Scenario: Size out of range
- **WHEN** `fenolite render <board> --out views --png --width 10 --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

### Requirement: Tool-backed command examples
`fenolite.cli.api.Command` SHALL have the field `example_tools: tuple[str, ...]`, default `()`, naming the external tools the command's examples need, and the suites SHALL provide a fake for each.
- The only name accepted in v0.1 MUST be `kicad-cli`; `tests/consistency/test_cli_consistency.py` MUST fail for any other.
- For a command with `kicad-cli` in `example_tools`, `tests/consistency/test_cli_consistency.py` and `tests/unit/cli/test_hermetic_examples.py` MUST run its examples with `FENOLITE_KICAD_CLI` set to a fake built by `tests/_fakecli.py`, and the examples MUST then meet every rule of the consistency suite: exit 0, a valid envelope, and for `mutation_example_args` the planned files written in an empty folder.
- A command with `example_tools == ()` MUST still run its examples with `subprocess.run` and `subprocess.Popen` patched to raise.
- `capabilities` MUST list `example_tools` for each command that has any.

#### Scenario: Export example runs against the fake
- **WHEN** `uv run pytest tests/consistency -k export` runs
- **THEN** `export`'s `example_args` exit 0, and its `mutation_example_args` write `fab/fenolite-artifacts.json` and at least one Gerber in an empty folder

#### Scenario: Tool-free commands stay hermetic
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs
- **THEN** every command with `example_tools == ()` passes with subprocess creation patched to raise

#### Scenario: Unknown tool name
- **GIVEN** a test command with `example_tools=("ngspice",)`
- **WHEN** the consistency suite's name check runs on it
- **THEN** it fails and names the command

### Requirement: Experimental features in capabilities
`fenolite capabilities` SHALL fill `result.experimental` with one entry per experimental feature, sorted by `name`. Each entry MUST have exactly the keys `name`, `command`, `option`, `write_kinds` and `evidence`, the last written as `{level, oracle, hypotheses}` like the `evidence` of `CapabilityReport.to_json()`.
- An experimental feature MAY change its output, its options or its issue codes in any release. Its envelopes MUST NOT carry a level that `fenolite.verify.release_verified` accepts (`verification-evidence`, "Release-verified levels").
- Listing the entries MUST NOT run an external tool, so `result.experimental` is the same with `--no-tools`. The module that defines an entry MUST be imported inside `cmd_capabilities._run`, not when `fenolite.cli.cmd_capabilities` is imported.
- An experimental feature MUST NOT appear in `result.backends` unless it is a registered `Backend` (`backend-protocol`, "Backend registry").
- `docs/cli-contract.md` MUST describe `result.experimental` under "Discovery".
- Two entries are listed, in this order:
  - `name` `altium-pcb-writer`, `command` `build`, `option` `--target altium`, `write_kinds` `["altium_pcbdoc", "altium_pcblib"]` (`fenolite.lens.altium.PCB_WRITE_KINDS`), and the evidence of `fenolite.lens.altium.PCB_BUILD_EVIDENCE` (`altium-build`, "PCB evidence and capabilities");
  - `name` `altium-schematic-writer`, `command` `build`, `option` `--target altium`, `write_kinds` equal to `fenolite.backends.altium.project.WRITE_KINDS` (`["altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib"]`, c0033 and c0034), and the evidence of `fenolite.lens.altium.ALTIUM_BUILD_EVIDENCE` (`altium-build`, "Altium build evidence").
- The two entries MUST NOT share a write kind, so each can be cut or promoted on its own.

#### Scenario: Altium writers listed as experimental
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the exit code is 0, `result.experimental` holds two entries named `altium-pcb-writer` and `altium-schematic-writer`, in that order, each with `command` `build`, `option` `--target altium` and `evidence.level` `INFERRED`, the first with `write_kinds` `["altium_pcbdoc", "altium_pcblib"]`, no entry of `result.backends` is named `altium`, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Same entry without tool detection
- **WHEN** `uv run fenolite capabilities --json` and `uv run fenolite capabilities --json --no-tools` run
- **THEN** both `result.experimental` values are equal

#### Scenario: Field projection
- **WHEN** `uv run fenolite capabilities --json --no-tools --fields experimental` runs
- **THEN** `result` contains only `experimental`, and the exit code is 0

#### Scenario: Experimental evidence is never release-verified
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_experimental.py` parses the `evidence.level` of every entry with `fenolite.verify.parse_level`
- **THEN** `release_verified` of each level is `False`

### Requirement: Place command
`fenolite place PATH [--strategy grid|manual] [--move REF=X,Y[,ROT[,SIDE]]]... [--only REF,…] [--pitch L] [--gap L] [--margin L] [--force] [-o OUT]` SHALL be registered by `src/fenolite/cli/cmd_place.py` with `mutates=True`, and SHALL move footprints of the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`.
- **Grid.** With `--strategy grid` (the default without `--move`), the command MUST place every footprint that is off the board (`layout-lens`, "Placement precedence"), or those of `--only`, with `placement.grid.place`, in component-path order (reference order for footprints without `fenolite.path`). It only translates.
- **Manual.** Each `--move` MUST name a reference and a position in the frame of the DSL's `place()` (relative to the top-left corner of the bounding box of the board ring, Y down; relative to the file origin when the board has no outline), with lengths in the DSL's syntax, an optional rotation in degrees and an optional side. An unknown reference MUST give `place.unknown-ref`. A rotation or side change MUST resolve definitions from the project's `fp-lib-table`.
- **Legality.** After the moves, `placement.legality.check` MUST run on the whole layout. With any `place.*` error and without `--force`, the command MUST return no `PlannedWrite` and exit 5. With `--force` it MUST write and still report the issues.
- **Write.** One `PlannedWrite` for the board, at `--out` when given and at the board's path otherwise; none when nothing moved. The mutation protocol applies unchanged.
- **Result.** `result` MUST hold `board`, `strategy`, `moved` (`ref`, `path`, `from`, `to`, each placement as `x`, `y` in nm, `rotation` in µdeg and `side`; sorted by reference), `unplaced` and `legality` (counts by code).
- **Built projects.** When `.fenolite/` holds a locked placement for a moved part, the command MUST report `place.script-locked` (warning), because the next build restores the script's placement.
- No subprocess MUST run. Two runs on equal boards MUST write equal bytes.
- `example_args` MUST be `(EXAMPLE_BOARD, "--move", "R1=12mm,8mm", "--out", "fenolite-placed.kicad_pcb", "--dry-run")`, and `mutation_example_args` the same without `--dry-run`.

#### Scenario: Grid places staged parts
- **GIVEN** a confirmed build of a blink variant with `R1` and `D1` staged
- **WHEN** `uv run pytest tests/unit/cli/test_place_cmd.py -k grid` runs `fenolite place <dir> --confirm`
- **THEN** both footprints lie inside the outline, `result.moved` lists them, `result.unplaced` is empty, and the exit code is 0

#### Scenario: Illegal move refused
- **GIVEN** the built blink
- **WHEN** `fenolite place <dir> --move R1=<the position of D1> --confirm` runs
- **THEN** the exit code is 5, `issues` holds `place.courtyard-overlap`, and no file changes; with `--force` the board is written

#### Scenario: Unknown reference
- **WHEN** `fenolite place <dir> --move R99=1mm,1mm --dry-run` runs
- **THEN** the exit code is 5 and `issues` holds `place.unknown-ref` naming `R99`

#### Scenario: Nothing to place
- **GIVEN** a built blink with every part placed
- **WHEN** `fenolite place <dir> --confirm` runs
- **THEN** the exit code is 0, `result.moved` is empty, and no file changes

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `place` with its `example_args`
- **THEN** the exit code is 0 and the plan names `fenolite-placed.kicad_pcb`

### Requirement: Route command
`fenolite route PATH --router NAME [--nets GLOB]... [--rip] [--include-zone-nets] [--router-path DIR] [--router-python PATH] [--router-option KEY=VALUE]... [--allow-offsite] [--timeout SECONDS] [-o OUT]` SHALL be registered by `src/fenolite/cli/cmd_route.py` with `mutates=True`, and SHALL add routed copper to the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`.
- **Router.** `NAME` MUST be a key of `routing.registry.routers()`; otherwise the command MUST exit 2 with `FEN-2001` and a hint listing the registered names. A router whose `available()` is false MUST exit 6 with `FEN-6001` and its reason. A router with `sends_data_offsite` MUST be refused with exit 2 unless `--allow-offsite` is given.
- **Job.** The command MUST select nets with `routing.select.unrouted` (after `select.rip` when `--rip` is given), build `JobPad`s from the backend's `BoardFrame.board_pads`, and take each net's width, clearance and via sizes from its net class, else from the project's default class.
- **Write.** The command MUST merge the result with `routing.merge.apply` and return one `PlannedWrite` for the board, written by `write_board` for the board's own major, at `--out` when given and at the board's path otherwise. It MUST return none when no net was selected or the result holds no copper. The mutation protocol applies unchanged.
- **Result.** `result` MUST hold `board`, `router`, `tool_version`, `selected`, `routed`, `unrouted`, `tracks`, `vias`, `ripped`, `fills_stale` and `log` (at most 20 lines, sanitised: no temporary path, no home directory).
- **Issues and exit codes.** Each selected net left unrouted MUST give `route.unrouted` (warning). The exit code MUST be 5 for `route.bad-item` or `route.tool-failed`, and 0 otherwise.
- **Evidence.** The envelope evidence MUST be `UNVERIFIED`, with the router's name and version as the oracle text.
- `example_args` MUST be `(EXAMPLE_UNROUTED, "--router", "direct", "--out", "fenolite-routed.kicad_pcb", "--dry-run")`, and `mutation_example_args` the same without `--dry-run`; both MUST run no subprocess.

#### Scenario: Direct route of the example
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k example` runs the mutation example with `--confirm` in an empty folder
- **THEN** the exit code is 0, `fenolite-routed.kicad_pcb` holds one more segment than the example board, `result.routed` names its net, and `evidence.level` is `UNVERIFIED`

#### Scenario: Unknown router
- **WHEN** `fenolite route <board> --router nope --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `direct` and `kicadroutingtools`

#### Scenario: Tool not installed
- **GIVEN** no `FENOLITE_KRT`
- **WHEN** `fenolite route <board> --router kicadroutingtools --dry-run` runs
- **THEN** the exit code is 6, stderr carries `FEN-6001`, and the hint names the repository and the pinned tag

#### Scenario: Nothing to route
- **GIVEN** a board whose every net has copper
- **WHEN** `fenolite route <board> --router direct --confirm` runs
- **THEN** the exit code is 0, `result.selected` is empty, and no file changes

#### Scenario: Routes survive a rebuild
- **GIVEN** a confirmed blink build routed with the fake tool and `--confirm`
- **WHEN** the build runs again twice
- **THEN** the routed segments are kept with their uuids, and the second rebuild writes the bytes of the first

### Requirement: Routers in capabilities and doctor
`fenolite capabilities` SHALL list the registered routers in `result.routers`, sorted by name, each with `name`, `description`, `sends_data_offsite` and `builtin`, without importing a plugin's tool or running a subprocess. `result.sends_data_offsite` MUST stay `false` while no enabled feature sends data without an explicit flag.

`fenolite doctor` SHALL add `result.routers`, each entry with `name`, `available`, `path`, `version` and `reason` from `Router.available()`; a registered router that is not available MUST give `doctor.tool-missing` (warning) naming it, and a plugin listed by `routing.registry.unavailable()` MUST give `doctor.tool-unsupported` (warning) with its error. With `--no-run`, `doctor` MUST list the names only and call no `available()`.

#### Scenario: Routers listed
- **WHEN** `fenolite capabilities --json --no-tools` runs
- **THEN** `result.routers` holds `direct` with `builtin: true` and `kicadroutingtools` with `sends_data_offsite: false`

#### Scenario: Doctor reports a missing tool
- **GIVEN** no `FENOLITE_KRT`
- **WHEN** `fenolite doctor --json` runs
- **THEN** the `kicadroutingtools` entry has `available: false`, one `doctor.tool-missing` warning names it, and the exit code is 0

### Requirement: Contract page names every command
`docs/cli-contract.md` SHALL describe every registered command that is not hidden: the page MUST hold the text `fenolite <name>`, or a level-2 heading that is the command's name with or without backticks. `tests/consistency/test_cli_consistency.py` SHALL check this over the command registry with `undescribed_commands(names, page)`, so a command added later fails the suite until the page describes it.
- The page MUST hold a section `## template` that states the command line `fenolite template build SPEC --target kicad -o OUT`, that the command is mutating and runs no tool, the keys of `result` (`sheet`, `target`, `kicad_version`, `drawn`, `output`), the exit codes 0, 2, 3 (`FEN-3001`, `FEN-3004`), 4 and 7, and the evidence (`INFERRED`, `H-K-WKS-CORNER`).
- The page MUST name every code of `fenolite.templates.ISSUE_CODES` in backticks.
- The section MUST describe the command as it behaves: each statement is checked against a run of the command before the section is merged.

#### Scenario: Every command is described
- **WHEN** `uv run pytest tests/consistency/test_cli_consistency.py -k contract_names` reads the registry and the page
- **THEN** it passes, and `undescribed_commands(["template"], page)` returns `["template"]` for a copy of the page without the `template` section

#### Scenario: Template codes are listed
- **WHEN** `uv run pytest tests/consistency/test_cli_consistency.py -k template_codes` runs
- **THEN** every code of `fenolite.templates.ISSUE_CODES` is found in backticks on the page

#### Scenario: Section matches a run
- **WHEN** `uv run fenolite template build src/fenolite/templates/examples/iso5457_generic.sheet.toml --target kicad -o out.kicad_wks --json --dry-run` runs
- **THEN** the exit code is 0, `result` holds exactly the keys `sheet`, `target`, `kicad_version`, `drawn`, `output` and `plan`, the evidence is `INFERRED` with `H-K-WKS-CORNER`, and nothing is written

