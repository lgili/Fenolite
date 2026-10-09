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
- Without `--progress`, the error object MUST be the only thing Fenolite writes on stderr. With `--progress`, stderr MAY hold progress records before it ("Progress on stderr"), each on a line of its own, and the error object MUST be the last line.
- No exit MUST leave stderr without an error object or with a traceback: an exception that no handler maps, a failed write and a signal each end in one registered code (`FEN-1001`, `FEN-1002`, `FEN-1003`).
- The registry MUST hold `FEN-1002` (exit 1, `retryable` true: a write failed and nothing was changed), `FEN-1003` (exit 1, `retryable` true: the command was stopped by a signal and nothing was written) and `FEN-4002` (exit 4, `retryable` false: the plan named by `--plan` cannot be written as reviewed). `src/fenolite/cli/data/explain.toml` MUST hold one table for each, and `docs/cli-contract.md` MUST say that exit 1 is a bug only when `retryable` is false.

#### Scenario: Internal exception
- **GIVEN** the hidden `_echo` command is invoked with `--raise`
- **WHEN** it runs
- **THEN** the exit code is 1 and stderr carries `FEN-1xxx` with a non-empty `message`

#### Scenario: Usage error
- **WHEN** `fenolite capabilities --no-such-flag` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2xxx`

#### Scenario: A blocked write ends in an error object
- **GIVEN** a folder in which `blocker` is a file
- **WHEN** `uv run pytest tests/unit/cli/test_write_failures.py -k blocked` runs `_echo --write blocker/x.txt --confirm --json`
- **THEN** the exit code is 1, stderr is one JSON object with `code` `FEN-1002` and `retryable` true, and it holds no traceback and no absolute path

#### Scenario: The error is the last line under progress
- **GIVEN** `_echo --steps 3 --raise --progress --json`
- **WHEN** it runs
- **THEN** every line of stderr but the last parses as `{"progress": …}`, and the last is the error object `FEN-1001`

#### Scenario: The three codes are registered and explained
- **WHEN** `uv run pytest tests/unit/cli/test_exitcodes.py tests/unit/cli/test_explain_cmd.py` runs
- **THEN** `FEN-1002`, `FEN-1003` and `FEN-4002` are in the registry with exit codes 1, 1 and 4, and each has a table in `explain.toml`

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
- Whenever a plan is returned and not written (`--dry-run`, and the refusal of exit 4), `result.plan_id` MUST name it ("Staged plans"), and the hint of `FEN-4001` MUST name `--confirm --plan <id>`.
- `--confirm` without `--plan` MUST keep its meaning: one run that plans and writes. `--confirm --plan ID` MUST write the plan that a review saw, under the checks of "Staged plans". `--plan` without `--confirm`, and `--plan` with `--dry-run`, MUST exit 2 with `FEN-2001`.
- The files of one command MUST be written all or none ("All-or-nothing writes"), and a command whose issues hold an error MUST write none ("Error findings plan no write").

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

#### Scenario: The refusal names the plan
- **WHEN** `uv run pytest tests/unit/cli/test_plans.py -k refusal` runs `_echo --write out.txt --json` in an empty folder
- **THEN** the exit code is 4, `result.plan_id` is 16 hex digits, and the hint of `FEN-4001` on stderr holds `--confirm --plan` followed by that id

#### Scenario: A plan needs a confirmation
- **WHEN** `_echo --write out.txt --plan 0123456789abcdef` runs without `--confirm`, and again with `--dry-run`
- **THEN** both exit 2 with `FEN-2001`, and nothing is written

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
- Two backends are listed: `altium` (change c0043), then `kicad`. A consumer MUST find a backend by its `name`, not by its position.

#### Scenario: KiCad backend listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the entry of `result.backends` named `kicad` has `read_kinds` that contain `kicad_pcb`, `kicad_mod` and `kicad_sym`, its `operations` contain `detect` and `read`, and contain `write` only when its `write_kinds` is not empty, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Altium backend listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result.backends` holds two entries named `altium` and `kicad`, in that order; the `altium` entry has `read_kinds` `["altium_pcbdoc", "altium_pcblib", "altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib"]`, `write_kinds` `[]`, `targets` `[]`, `default_target` `null`, `operations` `["detect", "read"]` and `evidence.level` `INFERRED`

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
`fenolite inspect FILE [--summary | --streams]` SHALL be registered by `src/fenolite/cli/cmd_inspect.py` with `mutates=False`, and SHALL describe one file without running any external tool. `--summary` is the default view and summarises one KiCad file, or one file of a backend that satisfies `DocumentValidator` (`altium-verification`, "Altium file summary"). `--streams` lists the storages and streams of a compound file ("Inspect stream tree"). Giving both views MUST exit 2 with `FEN-2001`.
- **Kinds.** Boards, footprint files and symbol libraries (file or `.kicad_symdir` folder) MUST be read through `registry.for_path(FILE).read`. `.kicad_sch` and `.kicad_wks` files MUST be read header-only through `versions.inspect`, with root-child counts by head. A file whose backend satisfies `DocumentValidator` MUST be summarised as "Altium file summary" says. With the `--summary` view, `.kicad_pro`, `.kicad_dru` and every other file that no backend reads MUST exit 2 with `FEN-2001`; when such a file starts with the compound file signature, the hint MUST name `--streams`.
- **Result.** `result` MUST hold `kind`, `format_version`, `major`, `status`, `generator`, `generator_version`, `counts`, `opaque_count` and `model_findings`. Board `counts` MUST hold `footprints`, `pads`, `nets`, `tracks`, `arcs`, `vias`, `zones`, `fills`, `keepouts`, `graphics` and `texts`. `opaque_count` MUST be `pcb.opaque_count` of the design for a KiCad board and `null` for every other KiCad kind. `model_findings` MUST count the `model.*` findings by severity. `input.path` MUST be the file name without its folder, so the output does not depend on the working directory.
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

#### Scenario: Compound file of a registered backend is summarised
- **WHEN** `uv run fenolite inspect tests/data/altium/blink/blink.PcbDoc --json` runs
- **THEN** the exit code is 0 and `result.kind` is `altium_pcbdoc`

#### Scenario: Compound file that no backend reads
- **GIVEN** a compound file in `tmp_path` named `x.bin` that holds one stream `Data`
- **WHEN** `uv run pytest tests/unit/cli/test_inspect_cmd.py -k unknown_compound` runs `fenolite inspect x.bin --json`
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and its hint names `--streams`

#### Scenario: Two views
- **WHEN** `uv run fenolite inspect tests/data/altium/blink/blink.PcbDoc --summary --streams` runs
- **THEN** the exit code is 2 with `FEN-2001`

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
`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--ipc2581] [--odb] [--step] [--pdf] [--dxf] [--sch-pdf] [--all] [--altium-rul] [--manifest] [--preset FILE] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_export.py` with `mutates=True`, and SHALL write the fabrication files and documents that `kicad-cli` produces from a copy of the board that `PATH` names and, for `--sch-pdf`, of its schematic, and, with `--altium-rul`, the project's rules as an Altium rule file (`manufacturing-exports`, "Altium rule file export").
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Kinds.** `--all` MUST select the four fabrication kinds (`FAB_KINDS`: `gerbers`, `drill`, `pos`, `ipcd356`) and MUST NOT select `altium-rul` or a document kind; each document kind (`DOCUMENT_KINDS`: `ipc2581`, `odb`, `step`, `pdf`, `dxf` and `sch-pdf`) MUST be selected by its own flag. A call that selects no kind and no `--altium-rul` MUST exit 2 with `FEN-2001`.
- **Schematic.** With `--sch-pdf`, a board without `<stem>.kicad_sch` beside it MUST exit 3 with `FEN-3001` before any run, with a hint that names the other kinds.
- **Preset.** `--preset FILE` MUST be read with `exports.preset.read_preset` before any run, and each selected kind MUST run with `arguments(kind, preset, …)` (`manufacturing-exports`, "Export presets"); a preset error MUST exit 3 with `FEN-3004`. `result.preset` MUST hold `file` (the name as given) and `sha256`, or be `null` without a preset. A document kind has no preset table: it MUST run with the fixed arguments of "Export kinds and their arguments" whatever the preset holds.
- **Tool.** When a fabrication kind or a document kind is selected, the command MUST exit 6 with `FEN-6001` when no `kicad-cli` is found and with `FEN-6002` for an unsupported major or a board newer than the tool reads. `--timeout` MUST default to 300 and apply to each run. With `--altium-rul` alone no tool is looked for or run.
- **Source.** The board, its project files and its folder MUST NOT change; every run happens on the copy set of `projectset.project_set`, with the model files of `manufacturing-exports`, "STEP export with 3D models", for the `step` kind.
- **Writes.** The command MUST return one `PlannedWrite` per artefact at `DIR/<artefact path>`, and with `--manifest` one for `DIR/fenolite-artifacts.json`; `DIR` is relative to the working directory. When any selected kind fails, the command MUST return no `PlannedWrite`, MUST report the kind's issue and MUST exit 5. Only an issue of severity `error` stops the writes: an issue of severity `info` MUST NOT (`manufacturing-exports`, "Stack-up note in exports", gives the first one), and neither does a warning, as "Exit codes" states. The mutation protocol (`--dry-run`, `--confirm`, backup, receipt) applies unchanged.
- **Result.** `result` MUST hold `board`, `out`, `kinds`, `artifacts` (`path`, `kind`, `layer`, `bytes`, `sha256`, `content_sha256`; sorted by path), `tool_version` (`null` when no tool ran), `tool_writes`, `repeat` (each selected fabrication or document kind mapped to its `Kind.repeat`) and `models` (the `ModelUse` objects of the `step` kind, `[]` without it), and with `--altium-rul` `rules` (`written`, `not_lowered`). No value MUST hold a temporary path, the home directory or a date.
- **Exit codes.** 0 when the files are planned or written, whatever the warnings (`kicad.lib.missing-3d-model`, `export.model-unread`, `export.page-too-small`); 5 with `export.failed`, `export.kind-unavailable` or `export.sheet-missing`; 3 for a board Fenolite cannot read or a missing schematic.
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

#### Scenario: Preset changes the drill units
- **GIVEN** a recording fake `kicad-cli` and a preset with `[drill]` `units = "in"`
- **WHEN** `fenolite export <board> --out fab --drill --preset fab.toml --dry-run` runs
- **THEN** the drill run saw `--excellon-units in`, and `result.preset.file` is `fab.toml`

#### Scenario: Invalid preset
- **WHEN** the same command runs with a preset whose schema is `other.v1`
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the fake saw no run

#### Scenario: The rule file needs no tool
- **GIVEN** an authored project with one clearance rule on a net, and no `kicad-cli` on the machine
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k altium_rule_file_needs_no_tool` runs `fenolite export <dir> --out fab --altium-rul --dry-run` and then `--manifest --confirm`
- **THEN** the first plans `fab/board.RUL` and writes nothing, the second writes it and the manifest, `result.kinds` is `["altium-rul"]`, `result.tool_version` is `null`, and the evidence is `INFERRED` with no oracle

#### Scenario: Document kinds
- **GIVEN** a fake `kicad-cli` 10.0.6 that writes one file for `ipc2581`, `odb` and `step`, two layer files for `pdf` and one for `dxf`
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k documents` runs `fenolite export <board> --out fab --ipc2581 --odb --step --pdf --dxf --dry-run`
- **THEN** the exit code is 0, the plan holds the six files, `result.repeat` maps `ipc2581`, `odb` and `step` to `none`, `pdf` to `content` and `dxf` to `bytes`, and `result.models` is a list

#### Scenario: All keeps the four kinds
- **GIVEN** a recording fake `kicad-cli`
- **WHEN** `fenolite export <board> --out fab --all --dry-run` runs
- **THEN** the fake saw exactly the runs of `gerbers`, `drill`, `pos` and `ipcd356`, and `result.kinds` holds neither a document kind nor `altium-rul`

#### Scenario: A preset leaves a document kind alone
- **GIVEN** a recording fake `kicad-cli` and a preset with `[drill]` `units = "in"`
- **WHEN** `fenolite export <board> --out fab --drill --dxf --preset fab.toml --dry-run` runs
- **THEN** the drill run saw `--excellon-units in`, and the `dxf` run saw exactly the arguments of "Export kinds and their arguments"

#### Scenario: Schematic PDF without a schematic
- **GIVEN** `two_layer.kicad_pcb`, which has no `two_layer.kicad_sch` beside it
- **WHEN** `fenolite export <board> --out fab --sch-pdf --dry-run` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001` naming `two_layer.kicad_sch`, and the fake saw no run

#### Scenario: A missing sheet writes nothing
- **GIVEN** a board with a schematic whose sub-sheet file is missing, and a fake `kicad-cli`
- **WHEN** `fenolite export <board> --out fab --pdf --sch-pdf --confirm` runs
- **THEN** the exit code is 5, the issues hold `export.sheet-missing`, and `fab` does not exist

#### Scenario: An info does not stop the writes
- **GIVEN** a fake `kicad-cli` 10.0.6 and a run of the drill kind that reports one issue of severity `info` that is not `export.stackup-default`
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k severity` runs `fenolite export <board> --out fab --drill --dry-run` and then `--confirm`
- **THEN** the first exits 0 with the plan of the drill files and the info among its issues, and the second writes those files

#### Scenario: An error stops the writes
- **GIVEN** the same run reporting one issue of severity `error`
- **WHEN** `fenolite export <board> --out fab --drill --confirm` runs
- **THEN** the exit code is 5, `result` holds no plan, the receipt is `null` and `fab` does not exist

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
- An experimental feature MUST NOT appear in `result.backends` unless it is a registered `Backend` (`backend-protocol`, "Backend registry"). Since change c0043 the registered backend `altium` reads Altium files; it lists no write kind, so the two writers below stay experimental features and are not part of its report.
- `docs/cli-contract.md` MUST describe `result.experimental` under "Discovery".
- Two entries are listed, in this order:
  - `name` `altium-pcb-writer`, `command` `build`, `option` `--target altium`, `write_kinds` `["altium_pcbdoc", "altium_pcblib"]` (`fenolite.lens.altium.PCB_WRITE_KINDS`), and the evidence of `fenolite.lens.altium.PCB_BUILD_EVIDENCE` (`altium-build`, "PCB evidence and capabilities");
  - `name` `altium-schematic-writer`, `command` `build`, `option` `--target altium`, `write_kinds` equal to `fenolite.backends.altium.project.WRITE_KINDS` (`["altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib"]`, c0033 and c0034), and the evidence of `fenolite.lens.altium.ALTIUM_BUILD_EVIDENCE` (`altium-build`, "Altium build evidence").
- The two entries MUST NOT share a write kind, so each can be cut or promoted on its own.

#### Scenario: Altium writers listed as experimental
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the exit code is 0, `result.experimental` holds two entries named `altium-pcb-writer` and `altium-schematic-writer`, in that order, each with `command` `build`, `option` `--target altium` and `evidence.level` `INFERRED`, the first with `write_kinds` `["altium_pcbdoc", "altium_pcblib"]`, the entry of `result.backends` named `altium` has an empty `write_kinds`, and the envelope validates against `schemas/fenolite.envelope.v0.json`

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
`fenolite place PATH [--strategy grid|manual|constrained] [--move REF=X,Y[,ROT[,SIDE]]]... [--only REF,…] [--pitch L] [--gap L] [--margin L] [--force] [-o OUT] [--constraints FILE] [--max-candidates N] [--preview-dir DIR]` SHALL be registered by `src/fenolite/cli/cmd_place.py` with `mutates=True`, and SHALL move footprints of the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`.
- **Rules of a built project.** The command MUST load the board folder's `.fenolite/` with `canonical.load_dir` at most once, and take from it the locked placements of "Built projects" and `checks.placement.rules_of(<that model>)`. Without a readable `.fenolite/` it judges no rule.
- **Grid.** With `--strategy grid` (the default without `--move`), the command MUST place every footprint that is off the board (`layout-lens`, "Placement precedence"), or those of `--only`, with `placement.grid.place`, in component-path order (reference order for footprints without `fenolite.path`). It only translates. The bounding box of every rule area of the board that forbids footprints (`Keepout.no_footprints`) MUST join the cut-outs that the grid avoids.
- **Manual.** Each `--move` MUST name a reference and a position in the frame of the DSL's `place()` (relative to the top-left corner of the bounding box of the board ring, Y down; relative to the file origin when the board has no outline), with lengths in the DSL's syntax, an optional rotation in degrees and an optional side. An unknown reference MUST give `place.unknown-ref`. A rotation or side change MUST resolve definitions from the project's `fp-lib-table`.
- **Legality.** For grid/manual, after the moves, `placement.legality.check` MUST run on the whole layout, with the board's keep-outs as `keepouts`. With any `place.*` error and without `--force`, the command MUST return no `PlannedWrite` and exit 5. With `--force` it MUST write and still report the issues.
- **Rules.** After the moves, `checks.placement.judge` MUST run on the layout with the rules of the built project. Each `placement.*` issue MUST be reported with a severity no higher than `warning` and MUST NOT refuse the write.
- **Measures.** `checks.placement.measure` MUST run on the layout after the moves, with the track width plus the clearance of the class `Default` of `KicadBackend().design_rules` on the board's copy set as `pitch` (`None` without that class).
- **Write.** For grid/manual, one `PlannedWrite` for the board, at `--out` when given and at the board's path otherwise; none when nothing moved. The mutation protocol applies unchanged.
- **Result.** `result` MUST hold `board`, `strategy`, `moved` (`ref`, `path`, `from`, `to`, each placement as `x`, `y` in nm, `rotation` in µdeg and `side`; sorted by reference), `unplaced`, `legality` (counts by code), `rules` (the counts of `judge` by rule family, all zero without rules) and `measures` (`Measures.to_json()` of the layout after the moves, with `change`: `hpwl` and `ratsnest` after minus before, in nm, both 0 when nothing moved).
- **Built projects.** When `.fenolite/` holds a locked placement for a moved part, the command MUST report `place.script-locked` (warning), because the next build restores the script's placement.
- **Evidence.** The envelope MUST carry `placement.EVIDENCE`, combined with `placement.legality.KEEPOUT_EVIDENCE` when the board holds a rule area that forbids footprints, and with `checks.placement.EVIDENCE` when a rule was judged.
- No subprocess MUST run. Two runs on equal boards MUST write equal bytes and return equal results.
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
- **THEN** the exit code is 0, `result.moved` is empty, `result.measures.change` is `{"hpwl": 0, "ratsnest": 0}`, and no file changes

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `place` with its `example_args`
- **THEN** the exit code is 0 and the plan names `fenolite-placed.kicad_pcb`

#### Scenario: Keep-out avoided by the grid and refused for a move
- **GIVEN** a confirmed build of a blink variant with `R1` staged and a rule area on `F.Cu` that forbids footprints over the 8 mm square at the top-left corner of the board, where the grid would otherwise put `R1`
- **WHEN** `uv run pytest tests/unit/cli/test_place_cmd.py -k keepout` runs `fenolite place <dir> --confirm`, and then `fenolite place <dir> --move R1=4mm,4mm --confirm`
- **THEN** the first run places `R1` outside the area's box with exit code 0; the second exits 5 with `place.keepout` naming `R1`, and writes nothing

#### Scenario: Rules and measures of a move
- **GIVEN** the blink built with `design.near("led", d1, r1.pad(2), within=mm(5))`
- **WHEN** `fenolite place <dir> --move R1=36mm,18mm --dry-run --json` runs, which brings `R1`'s pads within 5 mm of `D1`'s, and then the same command with `--move R1=2mm,2mm`
- **THEN** the first reply holds no `placement.too-far` and a negative `result.measures.change.hpwl`; the second holds one `placement.too-far` warning naming `D1` and exits 0, since a rule never refuses `place`

- **Constrained.** With `--strategy constrained`, the command SHALL use bounded neutral proposals from the integer `fenolite.placement-request.v0` request, preserve manual/grid defaults and refuse `--force`. `--constraints`, `--max-candidates` and `--preview-dir` SHALL apply to this strategy. `result.placement` SHALL contain positions, source/request hashes, unplaced reasons, objective metrics, intrinsic findings and placement assessment. `result.preview` SHALL identify the written/read-back geometry; dry-run previews MUST not write files. The constrained transaction MAY add planned preview writes alongside the board write and SHALL retain its hard-check findings instead of applying grid/manual force semantics.

#### Scenario: Constrained dry-run then confirmed placement
- **GIVEN** an authored request and preview directory
- **WHEN** dry-run is followed by --confirm
- **THEN** dry-run writes nothing and confirmed output has receipts and matching geometry hashes

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

### Requirement: Freerouting in doctor
`fenolite doctor` SHALL report, in the `freerouting` entry of `result.routers`, the jar path, the version, `java_major` and `java_ok` (`java_major >= 25`). A jar without a suitable Java MUST give `doctor.tool-unsupported` (warning) naming Java 25, and a missing jar `doctor.tool-missing`. `fenolite capabilities` MUST list `freerouting` with the plugin's `sends_data_offsite` value, and `result.sends_data_offsite` MUST stay `false`, because the router runs only when named and, while it sends data, only with `--allow-offsite`.

#### Scenario: Jar with an old Java
- **GIVEN** `FENOLITE_FREEROUTING_JAR` naming an existing file and a fake `java` that prints `17.0.2`
- **WHEN** `uv run pytest tests/unit/cli/test_doctor_cmd.py -k freerouting` runs `fenolite doctor --json`
- **THEN** the entry has `java_major: 17` and `java_ok: false`, one `doctor.tool-unsupported` warning names Java 25, and the exit code is 0

#### Scenario: Refused without the flag
- **GIVEN** the plugin with `sends_data_offsite` `True` and a fake jar
- **WHEN** `fenolite route <board> --router freerouting --dry-run` runs
- **THEN** the exit code is 2 and the hint names `--allow-offsite`

### Requirement: Inspect stream tree
`fenolite inspect FILE --streams` SHALL read `FILE` with `fenolite.backends.altium.read.cfb.read_compound` and list its storages and streams. The file is chosen by its content, not by its extension. The view reads the container only: it does not interpret any stream.
- `result` MUST hold exactly:
  - `kind`: `compound_file`;
  - `format_version`: the major version as a string, and `major` and `minor` as integers;
  - `sector_size`, `mini_sector_size`, `sectors`, `fat_sectors`, `difat_sectors` and `directory_entries`;
  - `root_clsid`: 32 lower-case hex digits, or `null` when it is zero;
  - `counts`: `storages`, `streams` and `bytes` (the sum of the stream sizes);
  - `entries`: one object per storage and stream in `CompoundFile.nodes()` order, without the root. A storage has `path`, `type` `storage` and `children` (a count). A stream has `path`, `type` `stream`, `size` and `sha256` of its bytes.
- `input` MUST hold the file name, the SHA-256 of the file, `kind` `compound_file` and the major version as `format_version`.
- `issues` MUST be `CompoundFile.notes`. A note never changes the exit code, which is 0.
- A `CompoundError` MUST exit 3 with `FEN-3004`; the error's `where` is `<file>:<locator>:@<offset>` and its message starts with the rule code (`altium-compound-reader`, "Located compound file errors"). A missing file exits 3 with `FEN-3001`.
- `--limit-bytes N` MUST set `Limits.max_file_bytes` for this run; without it the default applies. A value that is not a positive integer is a usage error.
- The envelope evidence MUST be `CompoundFile.evidence`.
- The output MUST depend only on the file's bytes and name, and the view MUST run no subprocess. `--fields` applies as for every command.
- `docs/cli-contract.md`, section "inspect", MUST describe the view, its result keys and its codes.

#### Scenario: Streams of the binary sample
- **WHEN** `uv run fenolite inspect tests/data/altium/sample/binary/altium_sample.SchDoc --streams --json` runs
- **THEN** the exit code is 0, `result.kind` is `compound_file`, `result.major` is 3, `result.counts.streams` is 2, `result.counts.storages` is 0, the entries are `Storage` and then `FileHeader`, each `sha256` is the digest of the bytes that `tests/_cfb_read.read_compound` returns for that path, and `issues` is empty

#### Scenario: Storages listed before their children
- **WHEN** the view runs on `tests/data/altium/blink/blink.PcbLib`
- **THEN** the entry `Library` has type `storage`, it comes before `Library/Data`, and its `children` equals the number of entries one level below it

#### Scenario: Broken file located
- **GIVEN** a copy of the binary sample in `tmp_path` whose FAT makes the chain of `FileHeader` a cycle
- **WHEN** the view runs on it with `--json`
- **THEN** the exit code is 3, stderr carries `FEN-3004`, its message starts with `cfb.chain`, and its `where` holds the file name, `stream:FileHeader` and an `@` offset

#### Scenario: Not a compound file
- **WHEN** the view runs on `tests/data/kicad/board/two_layer.kicad_pcb`
- **THEN** the exit code is 3 with `FEN-3004`, and the message starts with `cfb.signature`

#### Scenario: Size limit
- **WHEN** the view runs on the binary sample with `--limit-bytes 1000`
- **THEN** the exit code is 3 with `FEN-3004`, and the message starts with `cfb.limit` and names `max_file_bytes`

#### Scenario: Field projection
- **WHEN** the view runs on the binary sample with `--json --fields counts`
- **THEN** `result` holds only `counts`

### Requirement: Pads command
`fenolite pads PATH [REF [NUMBER]] [--origin X,Y]` SHALL be registered by `src/fenolite/cli/cmd_pads.py` with `mutates=False`, and SHALL list the pads of a board in the board frame from the board model, without running any tool. It is the query a script author needs to route by hand: where a pad is, on which layers and on which net.
- `PATH` MUST resolve with `projectset.resolve_board`; the board is read through `registry.for_path`, narrowed to `BoardFrame` for the pads (`backend-protocol`, "Board-frame protocol").
- `result.pads` MUST hold one object per `BoardPad`, in board order and pad order: `where` (`REF-NUMBER`), `ref`, `number`, `index`, `kind`, `position`, `rotation`, `side`, `layers`, `net`, `box` and `drill`.
  - `index` MUST be the position of the pad among the pads of its footprint that carry the same number, from 0: the value that `Part.pad(number, index=…)` takes (`design-dsl`, "Copper intents in the DSL").
  - `position` is `[x, y]`, `box` is `[x0, y0, x1, y1]`, the bounding box of the pad's copper over its copper layers, or `null` for a pad without copper. `net` is the net's name or `null`, `drill` the drill size or `null`.
  - Lengths MUST be integer nanometres and the rotation integer microdegrees.
- With `REF`, only the pads of that footprint MUST be listed, matched as `find_pads` matches: by component path first, else by reference. With `NUMBER`, only the pads that carry that number. `result.count` MUST be the number of listed pads.
- `--origin` MUST be two lengths with units, parsed with `core.units.parse_length`, default `0mm,0mm`. Every `position` and `box` MUST be reported relative to it, and `result.origin` MUST hold it. `docs/dsl.md` MUST tell a script author to pass the DSL's board origin, so that the numbers are the ones `Design.track` takes.
- An unknown reference MUST exit 2 with `FEN-2001` and the closest references in the hint; a number that the footprint does not have MUST exit 2 with the footprint's pad numbers in the hint; an origin without units MUST exit 2.
- The output MUST be deterministic and hold no absolute path.
- **Evidence.** `Evidence.combine` of the board read's evidence and `frame.EVIDENCE`.
- `example_args` MUST be `(EXAMPLE_BOARD, "R1")`.
- `docs/cli-contract.md` MUST describe the command and its result keys.

#### Scenario: Pads of one part
- **WHEN** `uv run fenolite pads tests/data/kicad/board/two_layer.kicad_pcb R1 --json` runs
- **THEN** the exit code is 0, `result.count` is 2, and `result.pads` holds `R1-1` on net `VCC` at `[20000000, 15800000]` and `R1-2` on net `LED_A` at `[20000000, 14200000]`, both with `kind` `smd`, `side` `top`, `index` 0, `drill` `null` and a `box` that contains their position

#### Scenario: One pad of a through-hole part
- **WHEN** `uv run fenolite pads tests/data/kicad/board/two_layer.kicad_pcb D1 1 --json` runs
- **THEN** `result.count` is 1, the pad is `D1-1` on net `GND` with `kind` `thru_hole`, `side` `bottom`, `layers` naming `F.Cu` and `B.Cu`, and `drill` 800000

#### Scenario: Positions relative to an origin
- **WHEN** the first command runs with `--origin 10mm,10mm`
- **THEN** `result.origin` is `[10000000, 10000000]`, and the position of `R1-1` is `[10000000, 5800000]`

#### Scenario: Whole board
- **WHEN** `uv run fenolite pads tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.count` is 4, in the order `R1-1`, `R1-2`, `D1-1`, `D1-2`

#### Scenario: Unknown reference and unknown number
- **WHEN** `fenolite pads <board> R9` and `fenolite pads <board> R1 7` run
- **THEN** both exit 2 with `FEN-2001`; the first hint names `R1`, and the second names the pad numbers `1` and `2`

#### Scenario: The command is hermetic and read-only
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py tests/unit/cli/test_check_readonly.py` run `pads` with its `example_args`
- **THEN** it exits 0, and the SHA-256 of every file of the board's folder is unchanged

### Requirement: Evidence matrix in capabilities
`fenolite capabilities` SHALL fill `result.matrix` with `MatrixRow.to_json()` of every row of `fenolite.backends.matrix.rows()`, in that order (`backend-protocol`, "Evidence matrix rows"). Each entry MUST have exactly the keys `backend`, `kind`, `detect`, `read`, `write`, `roundtrip_exact`, `roundtrip_modified`, `verified_by` and `experimental`.
- An operation is `null` when the backend package does not implement it for that kind, and the label of its evidence otherwise. The label states what holds for an arbitrary file of the kind. It is never stronger than the register row of an id in `verified_by` (`verification-evidence`, "Declared levels agree with the register").
- `verified_by` lists the hypothesis ids behind the row, sorted. Their statements, tests and results are rows of `docs/hypotheses.md`, and `docs/evidence/matrix.md` shows the level of each.
- An operation listed in `experimental` MAY change its output, its options or its issue codes in any release. An operation labelled `UNVERIFIED` MUST be listed there.
- Every write kind of every entry of `result.experimental` MUST have a row whose `write` is set and whose `experimental` contains `write`.
- Listing the matrix MUST NOT run an external tool, so `result.matrix` is the same with `--no-tools`. The `claims` modules MUST be imported inside `cmd_capabilities._run`, not when `fenolite.cli.cmd_capabilities` is imported.
- `result.backends` and `result.experimental` MUST stay as they are: the matrix adds a key and changes none.
- `docs/cli-contract.md` MUST describe `result.matrix` under "Discovery", with the meaning of the five operations and one example row.

#### Scenario: Matrix listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the exit code is 0, `result.matrix` is sorted by `backend` and then `kind`, its row for `kicad` and `kicad_pcb` has `read`, `write`, `roundtrip_exact` and `roundtrip_modified` set and `H-K-PCB-READ` and `H-K-PCB-WRITE` in `verified_by`, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Missing operation is null
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_matrix.py -k null` reads the row for `specctra` and `specctra_dsn`
- **THEN** its `write` is a label, and its `read`, `roundtrip_exact` and `roundtrip_modified` are `null`

#### Scenario: Board row and backend report agree
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_matrix.py -k agree` compares the `kicad_pcb` row with the `kicad` entry of `result.backends`
- **THEN** the row's `roundtrip_modified` starts with the entry's `evidence.level`, and every id of the entry's `evidence.hypotheses` is in the row's `verified_by`

#### Scenario: Experimental writers are marked
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_matrix.py -k experimental` reads `result.experimental` and `result.matrix`
- **THEN** every kind of every entry's `write_kinds` has a row with `write` set and `write` in `experimental`

#### Scenario: Same matrix without tool detection
- **WHEN** `uv run fenolite capabilities --json` and `uv run fenolite capabilities --json --no-tools` run
- **THEN** both `result.matrix` values are equal

#### Scenario: Field projection
- **WHEN** `uv run fenolite capabilities --json --no-tools --fields matrix` runs
- **THEN** `result` contains only `matrix`, and the exit code is 0

#### Scenario: Importing the command stays light
- **WHEN** `uv run python -c "import sys, fenolite.cli.cmd_capabilities; print(sorted(m for m in sys.modules if m.endswith('.claims')))"` runs
- **THEN** it prints `[]` and exits 0

### Requirement: Sync command
`fenolite sync DESIGN --out DIR --to-source [--check]` SHALL be registered by `src/fenolite/cli/cmd_sync.py` with `mutates=True`, and SHALL write the source-tree copies of a built project's layout beside the design script (`layout-lens`, "Sync of the source tree").
- **Direction.** `--to-source` MUST be given (exit 2, `FEN-2001` without it), so that a later direction cannot change what a bare `sync` does.
- **Script.** `DESIGN` MUST run as `build` runs it; a `DslError` of the script, `moves`, `module_moves` or `net_moves` MUST exit 3 with `FEN-3004`.
- **Board.** `DIR/<design name>.kicad_pcb` MUST exist; otherwise the command MUST exit 3 with `FEN-3001` and the hint "run fenolite build first". The refusals of `layout-lens` "Existing project files" apply unchanged.
- **Schematic.** When `DIR/<design name>.kicad_sch` exists and the schematic reader (c0060) is present, the command MUST read it and every child sheet it names, and plan `schematic-placements.toml` too; otherwise `result.symbols` is `null`.
- **Writes.** One `PlannedWrite` per file of `SyncPlan.files`, at `<script folder>/<file name>`; none when nothing changed. The mutation protocol applies unchanged, `.bak` files included.
- **Check.** With `--check`, the command MUST plan nothing and add one `sync.would-change` (error) per file of `SyncPlan.files`, so it exits 5 when a committed file is stale and 0 otherwise. `--check` with `--confirm` MUST be a usage error (exit 2).
- **Result.** `result` MUST hold `design`, `out`, `script_output` and the keys of `SyncPlan.result`; `issues` MUST hold its issues. No subprocess MUST run, and two runs on equal inputs MUST plan equal bytes.
- `example_args` MUST be `(str(MINIMAL), "--out", EXAMPLE_SYNC_OUT, "--to-source", "--dry-run")`, where `MINIMAL` is the packaged script of `build`'s example and `EXAMPLE_SYNC_OUT` is `tests/data/lens/sync_minimal/`, a committed target-10 build of it, without the ignored cache folder `.fenolite/`, that a test keeps byte-equal to a fresh build. `mutation_example_args` MUST be `None`: the command writes beside the design script, not under the working directory, so a mutation example would write into the package folder; `tests/unit/cli/test_sync_cmd.py` MUST run the mutation protocol on a copy of a design instead.

#### Scenario: Placements written beside the script
- **GIVEN** a copy of `examples/blink_2layer/` built with `--out B --confirm`, whose board was then edited by `edit_blink`
- **WHEN** `fenolite sync <copy>/design.py --out B --to-source --confirm --json` runs
- **THEN** the exit code is 0, `receipt.written` lists `<copy>/placements.toml`, and the file places `D1` 4 mm right of its `place()` position

#### Scenario: Stale file found by check
- **GIVEN** the same copy after that sync, whose board then gets `R1` moved 1 mm by token edit
- **WHEN** `fenolite sync <copy>/design.py --out B --to-source --check --json` runs
- **THEN** the exit code is 5, `issues` hold one `sync.would-change` naming `placements.toml` and the table of `R1`, and no file changes

#### Scenario: Current file passes check
- **GIVEN** the same copy right after the sync
- **WHEN** the command runs with `--check`
- **THEN** the exit code is 0 and `issues` hold no `sync.would-change`

#### Scenario: No board yet
- **WHEN** `fenolite sync examples/blink_2layer/design.py --out <empty folder> --to-source --dry-run` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and its hint says to run `fenolite build` first

#### Scenario: Direction required
- **WHEN** `fenolite sync examples/blink_2layer/design.py --out B --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `sync` with its `example_args`
- **THEN** the exit code is 0, the plan names `placements.toml` beside the packaged script, and nothing is written

### Requirement: Bom command
`fenolite bom PATH [--source kicad|model] [--template FILE] [--out FILE] [--against OTHER] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_bom.py` with `mutates=True`, and SHALL give the bill of materials of a project as a neutral table, written as a CSV file only with `--out`.
- **Project.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Source `kicad`** (the default). The parts MUST come from `KicadCli.export_bom` on a copy of the project's `<stem>.kicad_sch`, of its project file and of every other `.kicad_sch` under the project folder, read with `read_bom_csv` and `parts_from_kicad`. A project without that schematic MUST exit 3 with `FEN-3001` and a hint that names `--source model`. No tool MUST exit 6 with `FEN-6001`. A run that writes no bill, or a bill with another header, MUST exit 3 with `FEN-3004`. `counts.left_out` MUST be `null` for this source, because KiCad does not say what it leaves off a bill.
- **Source `model`.** The parts MUST come from `bom.parts_from_model` of the `.fenolite/` model on built input and of the board read on native input, with no subprocess.
- **Template.** `--template FILE` MUST be read with `assembly.read_template`; without it `assembly.DEFAULT` applies. A template error MUST exit 3 with `FEN-3004` and its issues in the envelope.
- **Result.** `result` MUST hold `source`, `template` (the file name without its folder, or `default`), `columns` (the column names), `lines` (one object per line, keyed by column name, as rendered text), `counts` (`parts`, `lines`, `dnp`, `left_out`) and, with `--against`, `changes` (each `{key, change, a_refs, b_refs}`). A column whose `property:<NAME>` no part has MUST give one `bom.property-missing` info.
- **`--against OTHER`.** `OTHER` MUST be read as `PATH` is, with the same source and template, and `changes` MUST be `bom.difference` of the two.
- **Writes.** With `--out FILE`, the command MUST return one `PlannedWrite` of kind `bom` whose bytes are `assembly.render_csv` of the table; without it, none. The mutation protocol applies; the project folder MUST NOT change otherwise.
- **Determinism.** Two runs on an unchanged project MUST give the same stdout apart from `elapsed_ms` and the same file bytes; no value MUST hold a date or an absolute path.
- **Evidence.** The envelope evidence MUST be `bom.EVIDENCE_KICAD` with the oracle `kicad-cli <version>`, or `bom.EVIDENCE_MODEL` under the rule of `assembly-outputs`, "Assembly issue codes and evidence".
- `example_args` MUST be `(EXAMPLE_BOARD, "--source", "model")`, `mutation_example_args` the same with `"--out", "bom.csv"`, and both MUST run no subprocess.

#### Scenario: Table as JSON
- **WHEN** `uv run fenolite bom tests/data/kicad/board/two_layer.kicad_pcb --source model --json` runs
- **THEN** the exit code is 0, `result.columns` is `["refs", "quantity", "value", "footprint"]`, `result.lines` holds one object per group, and no file is written

#### Scenario: File with a template
- **GIVEN** the blink built into `tmp_path`
- **WHEN** `fenolite bom <dir> --source model --template tests/data/assembly/columns.toml --out bom.csv --confirm` runs
- **THEN** `bom.csv` starts with the header `Parts,Count,Marking,Shape,Bin`, `receipt.written` lists it with its SHA-256, and a second run writes identical bytes

#### Scenario: Confirmation required
- **WHEN** the same command runs without `--confirm`
- **THEN** the exit code is 4, `result.plan` lists `bom.csv`, and no file is written

#### Scenario: From kicad-cli
- **GIVEN** a fake `kicad-cli` that writes the authored `bom_export.csv`
- **WHEN** `uv run pytest tests/unit/cli/test_bom_cmd.py -k kicad` runs `fenolite bom <project with a schematic> --json`
- **THEN** `result.source` is `kicad`, the fake saw `sch export bom` with `--fields` starting `Reference,Value,Footprint`, and `evidence.oracle` names the fake's version

#### Scenario: No schematic
- **WHEN** `fenolite bom tests/data/kicad/board/two_layer.kicad_pcb` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and the hint names `--source model`

#### Scenario: Difference of two projects
- **GIVEN** two builds of the blink, the second with the value of `R1` changed
- **WHEN** `fenolite bom <second> --source model --against <first> --json` runs
- **THEN** `result.changes` holds one `added` and one `removed` entry

### Requirement: Pnp command
`fenolite pnp PATH [--template FILE] [--side top|bottom|both] [--out FILE]` SHALL be registered by `src/fenolite/cli/cmd_pnp.py` with `mutates=True`, and SHALL give the placement table of a board from its model, written as a CSV file only with `--out`. It MUST run no subprocess.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`. The design MUST be read from the board file for built and native input alike, never from the `.fenolite/` model: `place`, `route` and `fill` write the board only, so the board is the one description of where the parts are.
- **Rows.** The rows MUST be `placement.apply(placement.rows_from_model(design), template, outline=<the board outline>)`, filtered by `--side` (default `both`).
- **Result.** `result` MUST hold `template`, `columns`, `rows` (one object per row, keyed by column name, as rendered text), `counts` (`rows`, `top`, `bottom`, `dnp`, `left_out`), `units`, `origin` and `y_axis`.
- **Writes.** With `--out FILE`, one `PlannedWrite` of kind `pnp`; without it, none.
- **Errors.** A template error MUST exit 3 with `FEN-3004`; `pnp.no-outline` MUST exit 5 and plan no file.
- **Evidence.** The envelope evidence MUST be `Evidence.combine(placement.EVIDENCE, <the board read's evidence>)`.
- `example_args` MUST be `(EXAMPLE_BOARD,)` and `mutation_example_args` `(EXAMPLE_BOARD, "--out", "pnp.csv")`.

#### Scenario: Rows of the authored board
- **WHEN** `uv run fenolite pnp tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.columns` is `["ref", "value", "footprint_name", "x", "y", "rotation", "side"]`, `result.units` is `mm`, and `result.rows` holds one row per footprint

#### Scenario: One side
- **GIVEN** the built blink, whose `D1` is on the bottom
- **WHEN** `fenolite pnp <dir> --side bottom --json` runs
- **THEN** `result.rows` holds only `D1`

#### Scenario: File with rotation rules
- **WHEN** `fenolite pnp <dir> --template tests/data/assembly/rotated.toml --out pnp.csv --confirm` runs
- **THEN** `pnp.csv` holds the columns of the template, the rotation of `U1` is its stored rotation plus the footprint offset of the template, and a second run writes identical bytes

#### Scenario: After a move
- **GIVEN** the built blink, and `fenolite place <dir> --move R1=12mm,8mm --confirm`
- **WHEN** `fenolite pnp <dir> --json` runs
- **THEN** the row of `R1` holds the position the board file has, and the other rows are unchanged

#### Scenario: Hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `pnp` and `bom` with their `example_args`
- **THEN** both exit 0

### Requirement: Diff of document inputs and the records view
`fenolite diff A B` ("Diff command", change c0066) SHALL also accept the inputs of a backend that satisfies `DocumentValidator` (`backend-protocol`, "Document sets and container round trips"), and SHALL offer `--view records` beside `model` and `tree`. Everything "Diff command" says of the result keys, the paged list `differences`, the exit code, determinism and `example_args` applies unchanged.
- **Inputs.** `A` and `B` MAY each be a file that `registry.for_path` gives such a backend for (an Altium document, library or project file), or a folder that holds exactly one project file of such a backend and no `.fenolite/meta.json`. A project file or folder is read with `backend.read` of the project file. `a.kind` and `b.kind` MUST then be the read kind that `backend.documents` gives the file (`altium_pcbdoc`, `altium_schdoc_ascii`, …). A folder that holds `.fenolite/meta.json` stays the built model, whatever else it holds.
- **Model view.** Designs and libraries of any two backends MUST be compared as "Diff command" says: `diff_designs` for two designs, `diff_libraries` for two libraries, exit 2 with `FEN-2001` for a design against a library. `--view tree` on such an input MUST exit 2 with `FEN-2001` and a hint that names `--view model`.
- **Records view.** `--view records` MUST compare two Altium files of one kind as `altium-verification`, "Records view of two Altium files", says, with `summary` per stream. For any other pair of inputs it MUST exit 2 with `FEN-2001` and a hint that names `--view model`. `--ext` with this view MUST exit 2 with `FEN-2001`.
- **Evidence.** The envelope evidence MUST be `Evidence.combine` of the two readings; in the records view it is the readers' evidence of the kind.
- `docs/cli-contract.md`, section "diff", MUST describe the three views and the Altium inputs.

#### Scenario: Two Altium documents in the model view
- **WHEN** `uv run pytest tests/unit/cli/test_diff_cmd.py -k altium_model` runs `fenolite diff tests/data/altium/blink/blink.PcbDoc tests/data/altium/blink/blink.PcbDoc --json`
- **THEN** the exit code is 0, `result.view` is `model`, `result.equal` is `true`, and `result.a.kind` is `altium_pcbdoc`

#### Scenario: A KiCad board against an Altium document
- **WHEN** `fenolite diff tests/data/kicad/board/two_layer.kicad_pcb tests/data/altium/blink/blink.PcbDoc --json` runs
- **THEN** the exit code is 0, `result.equal` is `false`, `result.a.kind` is `kicad_pcb` and `result.b.kind` is `altium_pcbdoc`

#### Scenario: Project folder as an input
- **WHEN** `fenolite diff tests/data/altium/blink tests/data/altium/blink/blink.PrjPcb --json` runs
- **THEN** the exit code is 0, `result.equal` is `true`, and both kinds are `altium_prjpcb`

#### Scenario: Records view refused for KiCad files
- **WHEN** `fenolite diff tests/data/kicad/board/two_layer.kicad_pcb tests/data/kicad/board/two_layer.kicad_pcb --view records` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `--view model`

#### Scenario: Tree view refused for Altium files
- **WHEN** `fenolite diff tests/data/altium/blink/blink.SchDoc tests/data/altium/blink/blink.SchDoc --view tree` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `--view model`

### Requirement: Netlist command
`fenolite netlist PATH [--source kicad|fenolite] [--min-pins N] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_netlist.py` with `mutates=False`, and SHALL print the components and nets of a KiCad project's schematic without writing any file.
- **Schematic.** `PATH` MUST be a `.kicad_sch` file, or a project folder, `.kicad_pro` or `.kicad_pcb` that `projectset.resolve_board` resolves, whose schematic is `<stem>.kicad_sch`. A missing path or schematic MUST exit 3 with `FEN-3001`; an ambiguous folder MUST exit 2 with `FEN-2001`.
- **Source `kicad`** (the default). The netlist MUST be `kicad-cli sch export netlist` on copies, read with `netlist.read_netlist` through `oracle.export_netlist_of`: the schematic, the sheet files it names inside its folder, and the copy set of the board beside it when there is one (else the project file of its stem). No tool MUST exit 6 with `FEN-6001` and a hint that names `--source fenolite`, an unsupported major with `FEN-6002`, and a run that times out with `FEN-6001` and `retryable: true`. A schematic the tool cannot load, and an export the reader refuses, MUST exit 3 with `FEN-3004` and the tool's sanitised line.
- **Source `fenolite`.** The netlist MUST be `sch_netlist.own_netlist` of the root sheet and of the child sheets it names, each read once with `read_schematic` and keyed by its path from the root file's folder, with no subprocess. A sheet file that is missing or outside that folder is not read, so its reference is a grammar issue. A sheet outside the grammar MUST exit 7 with `FEN-7001`, the grammar issues in `issues`, and a hint that names `--source kicad`.
- **Result.** `result` MUST hold `schematic` (the file name without its folder), `source`, `components` (each `ref`, `value`, `footprint`, `properties`), `nets` (each `name`, `class`, `unconnected`, `pins` as `{ref, pin, type}`) and `counts` (`components`, `nets`, `pins`, `unconnected`, `below_min_pins`). `unconnected` MUST be true for a net of one pin whose name starts with `unconnected-(`. Components MUST be sorted by natural order of the reference, nets by name, pins by reference and pin.
- **`--min-pins`.** Nets with fewer pins MUST be left out of `nets` and counted in `counts.below_min_pins`. The default MUST be 1; a value below 1 MUST exit 2 with `FEN-2001`.
- **Read-only and deterministic.** The project folder MUST be unchanged. The output MUST hold no date, no temporary path and no absolute path, and two runs MUST give the same stdout apart from `elapsed_ms`.
- **Evidence.** The envelope evidence MUST be that of the source: `Evidence.combine(netlist.EVIDENCE, oracle.EVIDENCE)` with oracle `kicad-cli <version>`, or `sch_netlist.EVIDENCE`.
- `example_args` MUST be `(EXAMPLE_SCHEMATIC,)`, with `fenolite.cli._examples.EXAMPLE_SCHEMATIC` the absolute path of `tests/data/kicad/schematic/flat.kicad_sch`, and `example_tools` MUST be `("kicad-cli",)`. `docs/cli-contract.md` MUST have a section "netlist". The fakes of the example suites MUST be given the authored `export_10.net` (`tests/_fakecli.py::EXAMPLE_NETLIST`), since a fake without a netlist refuses the schematic.

#### Scenario: Built blink through KiCad
- **GIVEN** a fake `kicad-cli` that writes the authored `export_10.net`
- **WHEN** `uv run pytest tests/unit/cli/test_netlist_cmd.py -k kicad` runs `fenolite netlist <project> --json`
- **THEN** the exit code is 0, `result.source` is `kicad`, `result.counts.components` is 3, the net `GND` lists `D1` pin `1` and `U1` pin `10`, and stdout holds no absolute path and no date

#### Scenario: Own reading without a tool
- **GIVEN** the blink built with a schematic into `tmp_path`, and `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `fenolite netlist <dir> --source fenolite --json` runs
- **THEN** the exit code is 0, `result.source` is `fenolite`, and `result.counts.unconnected` is 29

#### Scenario: Sheet outside the grammar
- **WHEN** `fenolite netlist tests/data/kicad/schematic/flat.kicad_sch --source fenolite --json` runs
- **THEN** the exit code is 7, stderr carries `FEN-7001`, the envelope's `issues` hold `kicad.sch.netlist-unsupported`, and the hint names `--source kicad`

#### Scenario: Small nets left out
- **WHEN** `fenolite netlist <dir> --source fenolite --min-pins 2 --json` runs on the built blink
- **THEN** `result.nets` holds `GND`, `LED_A` and `LED_DRV`, and `result.counts.below_min_pins` is 30

#### Scenario: Both sources agree
- **WHEN** `uv run pytest tests/kicad/check/test_netlist_oracle.py -k command` runs both sources on the built blink on 9.0.9 and on 10.0.6
- **THEN** the two `result.nets` are equal apart from `class`

#### Scenario: No schematic
- **WHEN** `fenolite netlist tests/data/kicad/board/two_layer.kicad_pcb` runs
- **THEN** the exit code is 3 and stderr carries `FEN-3001`

#### Scenario: Example runs against the fake
- **WHEN** `uv run pytest tests/consistency -k netlist` runs
- **THEN** `netlist`'s `example_args` exit 0 with a valid envelope

#### Scenario: Own reading of module sheets
- **GIVEN** the design of "Two modules, one nested" built into `tmp_path`
- **WHEN** `fenolite netlist <dir> --source fenolite --json` runs
- **THEN** the exit code is 0 and `result.components` lists `U1`, `R1`, `C1` and `R2`

### Requirement: Manifest command
`fenolite manifest PATH [--artifacts DIR]... [--stages a,b] [--no-check] [--verify] [--out FILE] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_manifest.py` with `mutates=True`, and SHALL write the project manifest of `manufacturing-exports`, "Project manifest", with a state on every entry.
- **Project.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s. `--out` MUST default to `fenolite-artifacts.json` in the board's folder (the project folder). An `--artifacts DIR` that is not inside the project folder MUST exit 2 with `FEN-2001`, and one that is not a folder MUST exit 3 with `FEN-3001`. Every path in the manifest is relative to the project folder, wherever `--out` puts the file.
- **Check.** Unless `--no-check` or `--verify` is given, the command MUST run the stages `--stages` names (default `DEFAULT_STAGES`) exactly as `check` does, with the same pre-flight and exit 6 without the tool, and MUST pass their statuses and evidence levels, with `sch.roundtrip_schematic` of every sheet (false for a sheet Fenolite cannot read), to `states.assign`. The issues of the check MUST be the command's issues, followed by the `manifest.*` issues. `--no-check` MUST run no stage and no tool, and every entry is then `generated`; `--no-check` with `--stages` MUST exit 2 with `FEN-2001`. The stage run MUST be the one `check` uses (`cmd_check.run_stages`), not a copy of it.
- **Writes.** The command MUST return one `PlannedWrite` for the manifest, whether or not the check found errors, and no other write. With an error issue the exit code is 5 after the write is planned or done; the mutation protocol applies.
- **`--verify`.** The command MUST read the existing manifest, hash every listed file, and report `manifest.missing` and `manifest.changed` (errors), `manifest.stale` (warning, a derived entry whose source has another hash now) and `manifest.unlisted` (info). It MUST plan no write and run no check and no tool; a missing manifest MUST exit 3 with `FEN-3001`, and one that `manifest.load` refuses MUST exit 3 with `FEN-3004`. A manifest that lists no design file is the manifest of an artefact folder: its paths MUST be resolved from its own folder, its sources compared with the board and schematic of `PATH`, and `manifest.unlisted` looked for in that folder. In a project manifest `manifest.unlisted` is looked for in the folders the derived entries came from: for each, the nearest folder above the file and below the project folder that holds a `fenolite-artifacts.json`, and the project folder for a file directly in it. `--verify` with `--no-check`, `--stages` or `--artifacts` MUST exit 2 with `FEN-2001`.
- **Result.** `result` MUST hold `manifest` (the path relative to the working directory), `project`, `states`, `artifacts` (`path`, `kind`, `state`, `stale`, `held`; sorted by path) and `check` (`stages` and `tool_version` as in the manifest, or `null`); with `--verify`, `verified` (true when no difference is an error) and `differences` (`path` and `code`, sorted by path) instead of `check`. No value MUST hold an absolute path, unless `PATH` or `--out` was given as one, or a date.
- **Paging.** The command MUST declare `paged="differences|artifacts"`: `differences` under `--verify`, else `artifacts`. The planned manifest is whole whatever the page.
- **Determinism.** With `--timestamp`, two runs on unchanged files MUST plan byte-identical manifests.
- **Evidence.** The envelope evidence MUST be that of the stages that ran, combined as `check` combines them, combined with `sch.EVIDENCE` when a sheet was judged, and `UNVERIFIED` with `--no-check` or `--verify`.
- `example_args` MUST be `(EXAMPLE_BOARD, "--no-check", "--out", "fenolite-artifacts.json", "--dry-run")`, `mutation_example_args` the same without `--dry-run`, and both MUST run no subprocess.

#### Scenario: Hashes only
- **WHEN** `uv run fenolite manifest tests/data/kicad/board/two_layer.kicad_pcb --no-check --out m.json --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `m.json`, every entry of `result.artifacts` has the state `generated`, and `result.check` is `null`

#### Scenario: States from a check
- **GIVEN** a fake `kicad-cli` whose DRC and ERC reports hold no violation, and a built project with an authored two-sheet schematic next to its board
- **WHEN** `uv run pytest tests/unit/cli/test_manifest_cmd.py -k states` runs `fenolite manifest <dir> --confirm --json`
- **THEN** the board and each sheet have the state `native-verified`, and `result.check` names `drc.kicad` and `erc.kicad` with status `ok`

#### Scenario: Errors still give a manifest
- **GIVEN** a fake whose DRC report holds one `clearance` violation of severity `error`
- **WHEN** the same command runs
- **THEN** the exit code is 5, the manifest is written, and the board's state is `roundtrip-ok`

#### Scenario: Verify an unchanged folder
- **GIVEN** a project whose manifest was just written
- **WHEN** `fenolite manifest <dir> --verify --json` runs
- **THEN** the exit code is 0, `result.verified` is `true`, and no file is written

#### Scenario: Verify after an edit
- **GIVEN** the same project with one byte of a Gerber changed and the board replaced
- **WHEN** `fenolite manifest <dir> --verify --json` runs
- **THEN** the exit code is 5, `result.verified` is `false`, and `result.differences` holds `manifest.changed` for the Gerber and for the board and `manifest.stale` for the other derived files

#### Scenario: Artefact folder outside the project
- **WHEN** `fenolite manifest <dir> --artifacts <a folder elsewhere> --no-check --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: No tool
- **GIVEN** no `kicad-cli` on `PATH` and no `FENOLITE_KICAD_CLI`
- **WHEN** `fenolite manifest <dir> --dry-run` runs
- **THEN** the exit code is 6, stderr carries `FEN-6001`, and the hint names `--no-check` and `--stages`

### Requirement: Manifest option of producing commands
`export`, `render`, `bom`, `pnp` and `testpoints` SHALL accept `--manifest`, and with it SHALL plan, beside their files, the manifest of their output folder merged with their entries (`manufacturing-exports`, "Manifest merging").
- The output folder is `--out DIR` for `export` and `render`, and the folder of `--out FILE` for `bom`, `pnp` and `testpoints`; `--manifest` without `--out` MUST exit 2 with `FEN-2001` for `bom`, `pnp` and `testpoints`.
- The entries MUST have the kinds of `KINDS` for `export`, `render` for each view, `bom`, `pnp` and `testpoints`; `layer` is `Artifact.layer`: set for a Gerber and for each layer file of `pdf` and `dxf`, `null` otherwise.
- `from` MUST hold the SHA-256 of the board for `export` (for its `sch-pdf` entry that of the root schematic instead), `render`, `pnp` and `testpoints`, and for `bom` that of the schematic (source `kicad`) or of the board (source `model`).
- `tool` MUST be `kicad-cli <version>` for files that tool wrote and `fenolite <version>` for the tables Fenolite rendered. `evidence` MUST be the level of the entry's own claim (`manufacturing-exports`, "Artefact manifest"): `exports.EVIDENCE`'s for a file of a fabrication kind or a view that `kicad-cli` wrote with the fixed options, `exports.DOCUMENTS_EVIDENCE`'s for a file of a document kind, the lower level of an export with a preset (c0074), and the level of the rows for a table.
- A folder whose manifest cannot be read (`manifest.unreadable`) MUST make the command plan no file at all, its own files included.
- `bom --source kicad` is not available yet (c0064 waits for the schematic writer); until it is, the `from` of a bill always holds the board's hash.
- A view that failed (`render.failed`) MUST have no entry.
- Without `--manifest`, each command MUST behave as before this requirement, and `export`'s result keys are unchanged.

#### Scenario: Views join the manifest
- **GIVEN** a folder `out` in which `export --all --manifest --confirm` ran, and a fake `kicad-cli`
- **WHEN** `uv run pytest tests/unit/cli/test_render_cmd.py -k manifest` runs `fenolite render <board> --out out --svg --manifest --confirm`
- **THEN** `out/fenolite-artifacts.json` lists the fabrication files and `front.svg` and `back.svg` with kind `render`

#### Scenario: Tables join the manifest
- **WHEN** `fenolite bom <dir> --source model --out out/bom.csv --manifest --confirm` and `fenolite pnp <dir> --out out/pnp.csv --manifest --confirm` run
- **THEN** the manifest of `out` lists `bom.csv` with kind `bom` and `pnp.csv` with kind `pnp`, each with `tool` naming `fenolite` and the board's hash in `from`

#### Scenario: Manifest needs a folder
- **WHEN** `fenolite pnp <dir> --manifest` runs without `--out`
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Layer and source of document entries
- **GIVEN** a fake `kicad-cli` and a board with a schematic beside it
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k document_manifest` runs `fenolite export <board> --out out --pdf --sch-pdf --manifest --confirm`
- **THEN** each `pdf` entry of `out/fenolite-artifacts.json` has its layer's canonical name in `layer` and the board's hash in `from`, and the `sch-pdf` entry has `layer` `null` and the root schematic's hash in `from`

#### Scenario: The test-point table joins the manifest
- **WHEN** `uv run pytest tests/unit/cli/test_testpoints_cmd.py -k manifest` runs `fenolite testpoints <dir> --out out/tp.csv --manifest --confirm` in a folder where `pnp --manifest` ran
- **THEN** the manifest of `out` lists `pnp.csv` and `tp.csv`, the second with kind `testpoints`, `tool` naming `fenolite` and the board's hash in `from`

### Requirement: Paged results
The dispatcher SHALL accept the global flags `--limit N` and `--cursor TOKEN` and SHALL cut the paged list of a command to one page, without keeping any state between calls.
- `fenolite.cli.api.Command` MUST have the fields `paged: str | None = None`, the dotted path of the command's main list in `result` or the literal `"issues"`, and `default_limit: int | None = None`. Several paths separated by `|` are alternatives: the first one that the result holds is paged, and `result.page.path` names it.
- With a limit (the flag, or else `default_limit`), the dispatcher MUST keep the items `offset` to `offset + limit - 1` of the paged list and MUST set `result.page` to `{path, limit, offset, total, next}`: `total` is the length of the whole list, and `next` the cursor of the following page or `null` on the last. Without a limit the list is whole and `result.page` is absent. When the object that holds the paged list also holds `total` or `truncated`, the dispatcher MUST set them to the length of the whole list and to whether the page is shorter than it.
- A cursor MUST be `<offset>.<digest>`, the digest being the first 8 hex digits of the SHA-256 of the canonical JSON of the whole list. `--cursor` MUST be refused with exit 2 (`FEN-2001`) when it is malformed, when its offset is past the end, when its digest is not that of the present list (the message says that the result changed since the cursor was issued), or when it is given without a limit in force.
- For `paged == "issues"` the envelope's `issues` list MUST be the page, and `result.page.path` MUST be `issues`.
- `ok`, the exit code, the error on stderr and every count in `result` MUST come from the whole result, never from the page.
- `--limit` MUST be at least 1; a value below 1, and `--limit` on a command whose `paged` is `None`, MUST exit 2 with `FEN-2001`.
- `--fields` MUST apply after paging and MUST be able to keep `page`.
- `capabilities` MUST list `paged` and `default_limit` for each command that has them. `check` and `analyze` MUST declare `paged = "issues"`.
- The hidden `_echo` command MUST take `--issues N`, which gives N numbered warnings of the code `echo.warning` before the issues of `--issue`, and MUST declare `paged = "issues"`.

#### Scenario: Two pages of issues
- **GIVEN** `_echo` producing five warnings
- **WHEN** `uv run pytest tests/unit/cli/test_paging.py -k two_pages` runs it with `--limit 2`, and again with `--limit 2 --cursor <the first run's next>`
- **THEN** the first envelope holds issues 1 and 2 with `result.page.total` 5 and a `next`, and the second holds issues 3 and 4 with `offset` 2

#### Scenario: Exit code from the whole result
- **GIVEN** `_echo` producing three warnings followed by one error
- **WHEN** it runs with `--limit 2`
- **THEN** the page holds two warnings, the exit code is 5 and `ok` is `false`

#### Scenario: Stale cursor
- **GIVEN** a cursor issued for a list of five issues
- **WHEN** the command runs again with that cursor and now produces six issues
- **THEN** the exit code is 2, and stderr carries `FEN-2001` saying that the result changed

#### Scenario: Command without a list
- **WHEN** `fenolite capabilities --limit 5` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Paging is deterministic
- **WHEN** the same paged call runs twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`, cursors included

### Requirement: Concise output
The dispatcher SHALL accept the global flag `--format concise|detailed`, default `detailed`. With `concise` it MUST keep, for each issue code, only the first issue in the envelope's order, and MUST add `result.issues_summary`: one object per code, sorted by code, with `code`, `count` and `by_severity`.
- Paging (`paged == "issues"`) MUST apply to the list that `concise` leaves.
- `ok` and the exit code MUST come from the whole result.
- `detailed` MUST leave the envelope as it is without this requirement.

#### Scenario: One issue per code
- **GIVEN** `_echo` producing three issues of one code and one of another
- **WHEN** `uv run pytest tests/unit/cli/test_paging.py -k concise` runs it with `--format concise`
- **THEN** `issues` holds two issues, and `result.issues_summary` gives the counts 3 and 1

#### Scenario: Detailed is the default
- **WHEN** the same command runs without `--format`
- **THEN** `issues` holds four issues, and `result` has no `issues_summary`

### Requirement: Diff command
`fenolite diff A B [--view model|tree] [--ext]` SHALL be registered by `src/fenolite/cli/cmd_diff.py` with `mutates=False`, `paged = "differences"` and `default_limit = 200`, and SHALL list the differences between two inputs without writing a file and without running any external tool.
- **Inputs.** `A` and `B` MUST each be a KiCad board, footprint file, symbol library or schematic (`.kicad_sch`, read with `sch.read_schematic`), or a folder that holds `.fenolite/meta.json` (the built model, loaded with `model.canonical.load_dir`). A missing path MUST exit 3 with `FEN-3001`, an input that nothing reads MUST exit 2 with `FEN-2001`, and a read error MUST exit 3 with its code.
- **Model view** (the default). Two designs MUST be compared with `checks.diff.diff_designs`, two libraries with `diff_libraries` and two sheets with `diff_sheets` (`verification-loop`, "Model difference report"). Inputs of two families MUST exit 2 with `FEN-2001`. `--ext` MUST pass `ext=True`.
- **Tree view.** `--view tree` MUST take two KiCad S-expression files of one kind and compare their parsed trees: `result.equal` is `tree_equal`, `result.first_difference` the locator of `sexpr.first_difference` or `null`, and `result.heads` the root child heads whose counts differ, each with its count in `a` and in `b`. Its `differences` list MUST be empty. A `.fenolite/` folder MUST exit 2 with `FEN-2001` and a hint that names `--view model`.
- **Result.** `result` MUST hold `view`, `equal`, `a` and `b` (each `{path, kind}`, `path` being the file or folder name without its parent), `summary` (per entity kind, the counts `added`, `removed` and `changed`), `differences` (objects `{path, change, a, b}`, in report order), `total` and `truncated` (true when the page is not the whole list).
- **Exit code.** A difference is a result, not a finding: the exit code MUST be 0 whether or not the inputs differ, and `issues` MUST hold only the readers' issues, those of `A` first.
- **Evidence.** The envelope evidence MUST be `Evidence.combine` of the two readings; a `.fenolite/` model counts as `INFERRED`. `input` MUST describe `A`.
- **Determinism.** Two runs on the same inputs MUST give the same stdout apart from `elapsed_ms`, and the output MUST hold no absolute path.
- `example_args` MUST be `(EXAMPLE_BOARD, EXAMPLE_BOARD)` and MUST run no subprocess from any working directory. `docs/cli-contract.md` MUST have a section "diff" with the views, the result keys and the matching keys.

#### Scenario: A file against itself
- **WHEN** `uv run fenolite diff tests/data/kicad/board/two_layer.kicad_pcb tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.view` is `model`, `result.equal` is `true`, `result.total` is 0 and `result.differences` is empty

#### Scenario: One footprint moved
- **GIVEN** a copy of `two_layer.kicad_pcb` in `tmp_path` whose first footprint is moved by 1 mm in X by a token edit
- **WHEN** `uv run pytest tests/unit/cli/test_diff_cmd.py -k moved` runs `fenolite diff <original> <copy> --json`
- **THEN** the exit code is 0, `result.equal` is `false`, and `result.differences` holds exactly one object, whose `change` is `changed` and whose `path` is `/footprint/<ref>/position`

#### Scenario: Built model against its board
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`
- **WHEN** `fenolite diff <project> <project>/<board>.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.a.kind` is `fenolite_model`, and `result.b.kind` is `kicad_pcb`

#### Scenario: Two schematics
- **GIVEN** a copy of `tests/data/kicad/schematic/flat.kicad_sch` whose `R1` is moved by 2.54 mm
- **WHEN** `fenolite diff <original> <copy> --json` runs
- **THEN** `result.differences` holds exactly one object, with the path `/symbol/R1#1/position`

#### Scenario: Tree view sees opaque content
- **GIVEN** a copy of `flat.kicad_sch` with one more `wire`
- **WHEN** `fenolite diff <original> <copy> --json` runs, and again with `--view tree`
- **THEN** the model view reports `equal` true, and the tree view reports `equal` false with `result.heads.wire` holding the two counts

#### Scenario: Page of differences
- **GIVEN** two authored designs with five differences
- **WHEN** `fenolite diff A B --limit 2 --json` runs
- **THEN** `result.differences` holds two objects, `result.total` is 5, `result.truncated` is `true`, and `result.page.next` is not `null`

#### Scenario: Diff is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise, and the working directory changed to an empty `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `diff` with its `example_args`
- **THEN** the exit code is 0

### Requirement: Roundtrip command
`fenolite roundtrip PATH [--level rt0|rt1|rt2] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_roundtrip.py` with `mutates=False`, and SHALL say up to which level Fenolite reads and writes a KiCad file back without loss. `--level` MUST default to `rt1`.
- **RT0.** For a `.kicad_pcb`, `.kicad_mod`, `.kicad_sch`, `.kicad_sym` or `.kicad_wks` file: `tree_equal(parse(dumps(parse(text))), parse(text))`. Any other file MUST exit 2 with `FEN-2001`.
- **RT1.** RT0, then `roundtrip.rt1` for a board and `sch.roundtrip_schematic` for a schematic. For another kind `result.rt1` MUST be `not-applicable` and the level reached `rt0`.
- **RT2.** RT1, then, for a `PATH` that `projectset.resolve_board` resolves, `KicadOracle.rt2` on the project's board and, when the project has a schematic, `KicadOracle.rt2_erc`. RT2 needs the tool: exit 6 with `FEN-6001` without it. A pair of reports that the oracle did not repeat MUST give `judged` false and MUST NOT fail the level. The schematic is judged by `checks.rt2.erc_rt2` on `ErcReport.kinds()`, the sheet, type, severity and exclusion of every violation, because KiCad's ERC can name another item of one violation in each run (`H-K-ERC-REPEAT-2`): it is not judged when the kinds of the two ERC runs on the project as it is differ, and it holds when the kinds of the re-dump's report equal those of the first run (`H-K-ERC-RT2-2`). The three runs MUST be made once; a difference of kinds fails the level, and a difference of items alone MUST NOT. The level reached is `rt2` only when the board's RT2 holds and, for a project with a schematic, the schematic's does. No ERC report at all MUST give `check.oracle-failed`.
- **Result.** `result` MUST hold `kind`, `level` (the highest level that holds, or `none`), and for each level asked `{passed, difference}`, with `opaque_count` for RT1 and `judged`, `normalised` and the report counts for RT2. For a project with a schematic, `result.rt2.schematic` MUST hold `passed`, `difference`, `judged`, `exact`, `violations`, `violations_redump`, `redumped` and `kept` (the sheet files re-dumped and left as they are). `exact` MUST be `true` when the three reports also have equal `entries()`, items included; it is information and changes neither `passed` nor the exit code.
- **Verdict.** A level that fails MUST give one `roundtrip.failed` issue of severity `error` whose `where` is the first difference, and the exit code is then 5. A read error MUST exit 3 with its code.
- **Read-only.** The file and its folder MUST be unchanged; RT2 runs on copies.
- **Evidence.** The reader's evidence for RT0 and RT1; combined with the oracle's for RT2.
- `example_args` MUST be `(EXAMPLE_BOARD,)` and MUST run no subprocess.

#### Scenario: Authored board
- **WHEN** `uv run fenolite roundtrip tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.level` is `rt1`, `result.rt1.passed` is `true`, and `result.rt1.opaque_count` equals `pcb.opaque_count` of the read design

#### Scenario: Schematic
- **WHEN** `fenolite roundtrip tests/data/kicad/schematic/flat.kicad_sch --json` runs
- **THEN** `result.kind` is `kicad_sch` and `result.level` is `rt1`

#### Scenario: Kind without a rebuild
- **WHEN** `fenolite roundtrip tests/data/libs/Mini.kicad_sym --json` runs
- **THEN** `result.level` is `rt0` and `result.rt1` is `not-applicable`

#### Scenario: Failure is an error
- **GIVEN** a `Validator` patched in the test so that RT1 fails with the difference `/kicad_pcb/footprint[0]/pad[1]`
- **WHEN** `uv run pytest tests/unit/cli/test_roundtrip_cmd.py -k failed` runs the command
- **THEN** the exit code is 5, and the issues hold one `roundtrip.failed` whose `where` is that locator

#### Scenario: RT2 through the tool
- **WHEN** `uv run pytest tests/kicad/check/test_roundtrip_cmd.py -rA` runs `fenolite roundtrip <built blink> --level rt2 --json` on 9.0.9 and on 10.0.6
- **THEN** `result.level` is `rt2` or RT2 is not judged, the exit code is 0, and the project snapshot is unchanged

#### Scenario: RT2 of the schematic
- **WHEN** `uv run pytest tests/kicad/check/test_roundtrip_cmd.py -k schematic -rA` runs the same command on the built blink, which has a schematic, on 9.0.9 and on 10.0.6
- **THEN** `result.rt2.schematic.passed` is `true` or its `judged` is `false`, no `roundtrip.failed` issue is reported, and the project snapshot is unchanged

#### Scenario: ERC names another item
- **GIVEN** a fake `kicad-cli` whose three ERC reports hold one violation of the same sheet, type and severity, with another item in one of them
- **WHEN** `uv run pytest tests/unit/cli/test_roundtrip_cmd.py -k rt2_schematic` runs the command
- **THEN** the exit code is 0, `result.level` is `rt2`, `result.rt2.schematic.passed` is `true` and its `exact` is `false`, after three ERC runs

#### Scenario: ERC difference of kinds
- **GIVEN** a fake `kicad-cli` whose ERC report of the re-dump holds one violation more than its two reports of the project
- **WHEN** the same test file runs the command
- **THEN** the exit code is 5 with one `roundtrip.failed` issue that names the type, after three ERC runs; when the two reports of the project differ in kinds instead, the exit code is 0, `judged` is `false` and the level is `rt1`

### Requirement: Fmt command
`fenolite fmt PATH [--check]` SHALL be registered by `src/fenolite/cli/cmd_fmt.py` with `mutates=True`, and SHALL give a KiCad S-expression file its canonical print (`kicad-sexpr`, "Canonical print check"), writing only through the mutation protocol.
- **Kinds.** `.kicad_pcb`, `.kicad_mod`, `.kicad_sch`, `.kicad_sym` and `.kicad_wks`. A `.kicad_pro`, a `.kicad_dru` and every other file MUST exit 2 with `FEN-2001`; the hint for `.kicad_pro` says that project files are kept byte for byte.
- **`--check`.** The command MUST plan no write. `result.formatted` MUST be true when the file equals its canonical print. When it does not, the command MUST report one `fmt.would-change` issue of severity `error` whose `where` is `<file name>:<the first differing line>`, and exit 5.
- **Without `--check`.** The command MUST return one `PlannedWrite` with the canonical text when it differs from the file, and none when it does not; `result.formatted` then says whether the file already was canonical.
- **Result.** `result` MUST hold `kind`, `formatted`, `lines` (of the file) and `first_difference` (a line number or `null`).
- A tree that `dumps` refuses (comments below the root) MUST exit 7 with `FEN-7001`; a file that does not parse MUST exit 3 with `FEN-3004`.
- `example_args` MUST be `(EXAMPLE_BOARD, "--check")`; `mutation_example_args` MUST be `(cmd_fmt.EXAMPLE_COPY,)`, a copy of the authored board that is not canonical, which `tests/_cliexamples.py::prepare_example` writes into the suite's folder before the command runs. Both MUST run no subprocess.
- For a command that `tests/_cliexamples.py::PREPARED` names, `tests/consistency/test_cli_consistency.py` and `tests/unit/cli/test_hermetic_examples.py` MUST prepare the working directory first, and the mutation-protocol test MUST prove that an unconfirmed run and a dry run leave every file of that folder as it was; for every other command the folder MUST stay empty, as before.

#### Scenario: Canonical file
- **GIVEN** the text `dumps(parse(text))` of `two_layer.kicad_pcb` written to `tmp_path`
- **WHEN** `fenolite fmt <file> --check --json` runs
- **THEN** the exit code is 0 and `result.formatted` is `true`

#### Scenario: File that would change
- **GIVEN** the same file with two blanks added after the first `(kicad_pcb`
- **WHEN** `fenolite fmt <file> --check --json` runs, and then `fenolite fmt <file> --confirm --json`
- **THEN** the first exits 5 with `fmt.would-change` naming line 1 and writes nothing, and the second writes the canonical text and keeps a `.bak`

#### Scenario: Formatting twice
- **WHEN** `fenolite fmt <file> --confirm` runs a second time
- **THEN** it plans no write, and `result.formatted` is `true`

#### Scenario: Project file refused
- **WHEN** `fenolite fmt tests/data/kicad/project/empty_10.kicad_pro --check` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

### Requirement: Explain command
`fenolite explain CODE` SHALL be registered by `src/fenolite/cli/cmd_explain.py` with `mutates=False`, and SHALL say what an error code or an issue code means and what to do about it, from data packaged with Fenolite.
- `src/fenolite/cli/data/explain.toml` MUST hold one table per code with `meaning` and `fix`, each a non-empty text of at most 400 characters, and `see`, a heading of `docs/cli-contract.md`.
- `fenolite.cli.explain.TABLES` MUST name every issue-code table of the package, and `all_codes()` MUST return every code of those tables and of the FEN registry of `cli/errors.py`.
- A code whose table key is a family (`<oracle>.drc.<type>`, `<oracle>.erc.<type>`) MUST be explained by the entry `<prefix>.*` of its family unless it has an entry of its own; `result.family` then names the family.
- `result` MUST hold `code`, `kind` (`error` or `issue`), `exit_code` (for a FEN code), `severities` (for an issue code), `meaning`, `fix`, `see` and `family`.
- An unknown code MUST exit 2 with `FEN-2001` and a hint that names the three closest codes (`difflib.get_close_matches`).
- A test MUST fail for a code of `all_codes()` without an entry, for an entry whose code is in no table and is not a family, and for a mapping in `src/fenolite` whose name ends in `ISSUE_CODES` and that `TABLES` does not name.
- `example_args` MUST be `("FEN-4001",)`.

#### Scenario: An error code
- **WHEN** `uv run fenolite explain FEN-4001 --json` runs
- **THEN** `result.kind` is `error`, `result.exit_code` is 4, and `result.fix` names `--confirm`

#### Scenario: An issue code of a family
- **WHEN** `fenolite explain kicad.drc.clearance --json` runs
- **THEN** the exit code is 0, `result.kind` is `issue`, and either the code has its own entry or `result.family` is `kicad.drc.*`

#### Scenario: Unknown code
- **WHEN** `fenolite explain check.read-refuse` runs
- **THEN** the exit code is 2, and the hint names `check.read-refused`

#### Scenario: Table is complete
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py -k complete` runs
- **THEN** every code of `all_codes()` has an entry, no entry is orphaned, and every `ISSUE_CODES` mapping of the package is in `TABLES`

### Requirement: Receipt identity
The receipt of a confirmed mutating command SHALL carry, beside `written` and `backup` ("Mutation protocol"), `id` and `undo`.
- `id` MUST be the first 16 hex digits of the SHA-256 of the canonical JSON of `{"written": …, "backup": …}`; it MUST NOT depend on a clock, a seed or the working directory.
- `undo` MUST be the string `fenolite restore - --confirm` when `backup` is not empty, and `null` otherwise.
- `schemas/fenolite.envelope.v0.json` MUST hold both fields, with defaults, so an envelope without them still validates.

#### Scenario: Identity of a write
- **WHEN** `_echo --write out.txt --confirm` runs twice in two empty folders with the same content
- **THEN** the two receipts have equal `id`s of 16 hex digits and `undo` `null`

#### Scenario: Undo offered after an overwrite
- **GIVEN** `out.txt` already exists
- **WHEN** `_echo --write out.txt --confirm` runs
- **THEN** `receipt.undo` is `fenolite restore - --confirm`

### Requirement: Restore command
`fenolite restore RECEIPT [--in DIR]` SHALL be registered by `src/fenolite/cli/cmd_restore.py` with `mutates=True`, and SHALL put back the backups of one confirmed write, described by the receipt that write returned. It MUST delete no file.
- **Receipt.** `RECEIPT` MUST be a file holding an envelope whose `receipt` is not `null`, or a bare receipt object; `-` MUST read it from stdin. Anything else MUST exit 3 with `FEN-3004`. The receipt's paths are relative to `--in DIR`, default the working directory.
- **Unchanged since.** Every file of `written` MUST exist with the recorded `sha256`; each one that does not MUST give `restore.changed-since` (error; `where` = the path), and the command MUST then plan nothing and exit 5.
- **Plan.** For every path of `backup`, the file `<path>.bak` MUST exist, else `restore.backup-missing` (error) and no plan. The plan MUST be one `PlannedWrite` per such path, at the written file's path, with the bytes of its `.bak` and the kind `restore`.
- **Kept files.** A written file without a backup MUST stay untouched and give one `restore.kept` info.
- **Nothing to restore.** A receipt whose `backup` is empty MUST give `restore.nothing` (error) and exit 5.
- **Undoable.** The mutation protocol applies: the content that the restore replaces becomes the new `.bak`, and the restore's own receipt restores it.
- **Result.** `result` MUST hold `id` (of the receipt read), `restored`, `kept` and, when refused, `changed`.
- The four codes MUST be documented in `docs/cli-contract.md`.
- `example_args` MUST pass a receipt that the suite prepares in its empty folder with `--dry-run`, and `mutation_example_args` the same without it; both MUST run no subprocess.

#### Scenario: Undo of an overwrite
- **GIVEN** `out.txt` holding `one`, then `_echo --write out.txt --confirm --json` writing `two`, its envelope saved as `r.json`
- **WHEN** `fenolite restore r.json --confirm` runs
- **THEN** `out.txt` holds `one`, `out.txt.bak` holds `two`, and the exit code is 0

#### Scenario: Changed since the write
- **GIVEN** the same receipt after `out.txt` was edited by hand
- **WHEN** `fenolite restore r.json --confirm` runs
- **THEN** the exit code is 5, the issues hold `restore.changed-since` naming `out.txt`, and no file changes

#### Scenario: Created files stay
- **GIVEN** the receipt of a build into an empty folder followed by a rebuild with a changed value, saved from the rebuild
- **WHEN** `fenolite restore <receipt> --in <cwd of the build> --confirm` runs
- **THEN** every file the rebuild overwrote has its previous bytes, no file is deleted, and the files that had no backup are reported with `restore.kept`

#### Scenario: Receipt from stdin
- **WHEN** the envelope of an overwrite is piped to `fenolite restore - --dry-run`
- **THEN** the exit code is 0 and `result.plan` lists the file

### Requirement: Net command
`fenolite net PATH [NAME]` SHALL be registered by `src/fenolite/cli/cmd_net.py` with `mutates=False` and `paged = "nets|net.pads"`, and SHALL describe the nets of a board, or one net, from the board model, without running any tool.
- `PATH` MUST resolve with `projectset.resolve_board`; the board is read through `registry.for_path`, narrowed to `BoardFrame` for the pads.
- **Without `NAME`.** `result.nets` MUST be `analysis.views.net_list(design)`: one row per net, sorted by name, with `name`, `class`, `pads`, `tracks`, `vias`, `zones` and `length` (the summed centre-line length of its tracks and arcs, in nm).
- **With `NAME`.** `result.net` MUST be `analysis.views.net_view(design, NAME, pads=…)`: `name`, `class`, `pads` (each `where` as `REF-PIN`, `layers`, `position`), `copper` (per layer: `tracks`, `arcs`, `length`), `vias`, `zones` (each `layers` and `filled`) and `box` (the bounding box of its pads and copper, or `null`). The paged list is then `net.pads`.
- An unknown name MUST exit 2 with `FEN-2001` and the three closest net names in the hint.
- Lengths MUST be integer nanometres. The output MUST be deterministic and hold no absolute path.
- **Evidence.** `Evidence.combine` of the board read's evidence and `frame.EVIDENCE`.
- `example_args` MUST be `(EXAMPLE_BOARD,)`.

#### Scenario: Net list of the authored board
- **WHEN** `uv run fenolite net tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.nets` names `GND`, `LED_A` and `VCC` in this order, each with its pad and track counts

#### Scenario: One net
- **WHEN** `fenolite net tests/data/kicad/board/two_layer.kicad_pcb GND --json` runs
- **THEN** `result.net.pads` lists the pads of `GND` as `REF-PIN`, and `result.net.copper` gives a length in nm per layer that has tracks

#### Scenario: Unknown net
- **WHEN** `fenolite net tests/data/kicad/board/two_layer.kicad_pcb GDN` runs
- **THEN** the exit code is 2 and the hint names `GND`

### Requirement: Region command
`fenolite region PATH --box X1,Y1,X2,Y2 [--layer NAME] [--kinds a,b]` SHALL be registered by `src/fenolite/cli/cmd_region.py` with `mutates=False` and `paged = "items"`, and SHALL list what a rectangle of the board holds.
- `--box` MUST be four lengths with units (`10mm,5mm,30mm,20mm`), parsed with `core.units.parse_length`, in the board file's frame; the rectangle is closed and its corners may come in any order. A length without a unit, or a rectangle of zero area, MUST exit 2 with `FEN-2001`.
- `result.items` MUST be `analysis.views.region_view(…)`: objects `{kind, where, net, layer, box}` sorted by kind and then `where`, for the kinds `footprint`, `pad`, `track`, `arc`, `via`, `zone` and `text`, filtered by `--kinds` and, with `--layer`, to items on that layer.
- `result` MUST also hold `box`, `layer` and `counts` per kind.
- `example_args` MUST be `(EXAMPLE_BOARD, "--box", "0mm,0mm,300mm,200mm")`.

#### Scenario: Whole board
- **WHEN** `uv run fenolite region tests/data/kicad/board/two_layer.kicad_pcb --box 0mm,0mm,300mm,200mm --json` runs
- **THEN** `result.counts.footprint` is 2, and every item has a `box` inside or across the rectangle

#### Scenario: One layer and one kind
- **WHEN** the same command runs with `--layer B.Cu --kinds track`
- **THEN** every item is a track on `B.Cu`

#### Scenario: Box without units
- **WHEN** `fenolite region <board> --box 0,0,10,10` runs
- **THEN** the exit code is 2, and the hint says that lengths need a unit

### Requirement: Neighbors command
`fenolite neighbors PATH REF [--radius L]` SHALL be registered by `src/fenolite/cli/cmd_neighbors.py` with `mutates=False` and `paged = "neighbors"`, and SHALL list the footprints near one part.
- `--radius` MUST be a length with a unit, default `5mm`.
- `result.radius` MUST be the radius in nm. `result.part` MUST hold `ref`, `position`, `rotation`, `side` and `box` (of its extent); `result.neighbors` MUST be the rows of `analysis.views.neighbors_view(…)`: `ref`, `distance` (nm; 0 when the extents touch or overlap), `overlap`, `side` and `shared_nets` (sorted names), sorted by distance and then reference.
- Only footprints on the part's side are neighbours; a through-hole part is on both sides.
- An unknown reference MUST exit 2 with `FEN-2001` and the closest references in the hint.
- `example_args` MUST be `(EXAMPLE_BOARD, "R1")`.

#### Scenario: Neighbours of a resistor
- **WHEN** `uv run fenolite neighbors tests/data/kicad/board/two_layer.kicad_pcb R1 --radius 50mm --json` runs
- **THEN** `result.part.ref` is `R1`, and `result.neighbors` lists the other footprint with its distance in nm and the nets it shares with `R1`

#### Scenario: Radius too small
- **WHEN** the same command runs with `--radius 0.01mm`
- **THEN** `result.neighbors` is empty and the exit code is 0

#### Scenario: Views are hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `net`, `region`, `neighbors`, `explain`, `roundtrip` and `fmt` with their `example_args`
- **THEN** each exits 0

### Requirement: Parity command
`fenolite parity PATH [--netlist auto|own|kicad]` SHALL be registered by `src/fenolite/cli/cmd_parity.py` with `mutates=False`, and SHALL compare the schematic and the board of a KiCad project (`verification-loop`, "Parity comparison").
- **Input.** `PATH` MUST resolve with `projectset.resolve_board`; the schematic is `<board stem>.kicad_sch` beside the board, read with every sheet it names. A missing schematic MUST exit 3 with `FEN-3001` naming it.
- **Netlist.** `auto` (default) MUST use the own netlist when the sheet tree is inside Fenolite's grammar and `kicad-cli`'s netlist export otherwise; `own` MUST refuse a tree outside the grammar as `netlist --source fenolite` does, with exit 7 (`FEN-7001`) naming the reasons; `kicad` MUST always run the export. A needed `kicad-cli` that is missing MUST exit 6.
- **Result.** `result` MUST hold `board`, `schematic` (the file names), `netlist` (`own` or `kicad`), `summary` and `findings` (the report's findings as objects `{code, severity, key, field, schematic, board}`); `issues` MUST hold one issue per finding, `where` its key.
- **Exit.** 5 when a finding has severity `error`, 0 otherwise.
- No file MUST be written, and the input folder MUST be unchanged.
- `example_args` MUST be `(EXAMPLE_PARITY,)`, a committed folder `tests/data/kicad/parity/agree/` holding the board and the schematic that `build` writes for the blink example at target 10, which agree, so the example runs without a tool; a test MUST keep the two files equal to a fresh build.

#### Scenario: Agreeing project
- **WHEN** `fenolite parity tests/data/kicad/parity/agree --json` runs
- **THEN** the exit code is 0, `result.netlist` is `own`, and `result.summary.refs_one_side` is 0

#### Scenario: Edited board
- **GIVEN** a copy of that folder whose board has one footprint's reference renamed
- **WHEN** `fenolite parity <copy> --json` runs
- **THEN** the exit code is 5, and `issues` hold `parity.missing-footprint` and `parity.extra-footprint`

#### Scenario: Third-party schematic without the tool
- **GIVEN** a project whose schematic holds wires, and no `kicad-cli`
- **WHEN** `fenolite parity <dir> --json` runs
- **THEN** the exit code is 6, and stderr names `kicad-cli`

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `parity` with its `example_args`
- **THEN** the exit code is 0

### Requirement: Deferred writes
`fenolite.cli.api.PlannedWrite` SHALL have the fields `source: Callable[[], bytes] | None = None`, `size: int | None = None` and `sha256: str | None = None`, so that a command can plan a file whose bytes are costly to obtain without obtaining them.
- A write with a `source` MUST have empty `data` and both `size` and `sha256` set; a `PlannedWrite` that breaks this MUST raise `ValueError` when it is created.
- The plan (`result.plan`, with `--dry-run` and with the refusal of exit 4) MUST list such a write with its declared `bytes` and `sha256`, as it lists any other.
- Without `--confirm` the dispatcher MUST NOT call `source`.
- With `--confirm` the dispatcher MUST call `source()` once per deferred write, before it writes any file of the command, and MUST compare the length and the SHA-256 of what it returns with the declared values. A difference MUST exit 3 with `FEN-3006` and write nothing, not even the command's other files.
- An exception of `source` that is a `CliError` MUST keep its code; nothing is written.
- A write without a `source` MUST behave as before this requirement.
- The hidden command `_echo` MUST accept `--defer PATH`, which plans a deferred write of fixed bytes, and `--defer-bad PATH`, whose source returns bytes of another digest, so that the suites can exercise the dispatcher without a network.

#### Scenario: Dry run does not call the source
- **GIVEN** `_echo --defer out.txt`, whose planned write has a source that the test counts
- **WHEN** `uv run pytest tests/unit/cli/test_fetch_cmd.py -k deferred_dry_run` runs it with `--dry-run`, and then without any protocol flag
- **THEN** the first exits 0 and the second exits 4, both plans list `out.txt` with its declared size and digest, the source was called zero times, and the folder is empty

#### Scenario: Confirmed deferred write
- **WHEN** the same command runs with `--confirm`
- **THEN** the source was called once, `out.txt` holds its bytes, and `receipt.written[0].sha256` equals the declared digest

#### Scenario: Wrong bytes write nothing
- **GIVEN** `_echo --defer-bad out.txt --write other.txt`, whose source returns bytes that do not have the declared digest
- **WHEN** it runs with `--confirm`
- **THEN** the exit code is 3, stderr carries `FEN-3006`, and neither `out.txt` nor `other.txt` exists

### Requirement: Fetch error codes
The registry of `fenolite.cli.errors` SHALL hold `FEN-6003` (exit 6, `retryable: true`, "download failed") and `FEN-3006` (exit 3, "fetched file does not match the pinned size or SHA-256"), and `docs/cli-contract.md` MUST list both with the other codes.
- The hint of `FEN-6003` MUST name `--from FILE`.
- The message of `FEN-3006` MUST hold the digest that was expected and the one that was found.
- `src/fenolite/cli/data/explain.toml` MUST hold a table for each of the two codes ("Explain command").

#### Scenario: Codes are registered and documented
- **WHEN** `uv run pytest tests/unit/cli/test_exitcodes.py tests/consistency` runs
- **THEN** both codes are in the registry with exit codes 6 and 3, and the contract page names both

#### Scenario: Codes are explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs, and then `uv run fenolite explain FEN-6003 --json`
- **THEN** the suite passes with a table for each of the two codes, and the command exits 0 with a `fix` that names `--from`

### Requirement: Fetch command
`fenolite fetch NAME [--from FILE] [--dir DIR]` SHALL be registered by `src/fenolite/cli/cmd_fetch.py` with `mutates=True`, and SHALL install one external tool of the table `src/fenolite/cli/data/fetch.toml` after checking its size and its SHA-256. It is the only code of Fenolite that downloads a tool.
- **Table.** Each row MUST hold `name`, `version`, `file`, `bytes`, `sha256`, `url`, `licence`, `source`, `env` and `needs`. A row whose name starts with `_` is hidden: no hint and no documentation names it. The table MUST hold the row `freerouting` with version `2.4.1`, file `freerouting-2.4.1.jar`, the address `https://github.com/freerouting/freerouting/releases/download/v2.4.1/freerouting-2.4.1.jar`, the size in bytes and the SHA-256 that `docs/evidence/routing.md` records for the gate's jar, licence `GPL-3.0`, source `S-0223` and env `FENOLITE_FREEROUTING_JAR`; and the hidden row `_selftest`, whose address is `package:` and whose file is `fetch-selftest.txt` of the same folder. A test MUST fail when a public row's `source` is not an id of `docs/evidence/sources.md` or its `url` is not `https`, and when the `bytes` or the `sha256` of the row `freerouting` differs from the value on that evidence page.
- **Destination.** `fenolite.core.tools.tool_path(name, file)` (`routing`, "Tools folder"), or `DIR/<file>` with `--dir`.
- **Plan.** The command MUST return one deferred write (`Deferred writes`) for the destination, with the row's `bytes` and `sha256`, or no write when the destination already holds bytes of that size and digest.
- **No request without confirmation.** With `--dry-run`, and without any protocol flag, the command MUST open no network connection and MUST read no file named by `--from`.
- **Network.** Without `--from`, the source MUST request the row's address with `urllib.request`, with the header `User-Agent: fenolite/<version>` and no other added header, a timeout of 60 s, and no query parameter; it MUST follow a redirect only to an `https` address, and MUST read at most `bytes + 1` bytes. Any failure MUST exit 6 with `FEN-6003`.
- **File.** With `--from FILE` the source MUST read that file; a missing file MUST exit 3 with `FEN-3001`.
- **Result.** `result` MUST hold `name`, `version`, `file`, `path`, `bytes`, `sha256`, `url`, `licence`, `origin` (`network`, `file` or `package`), `installed`, `needs` and `env`. `env` MUST map the row's variable to the destination when `--dir` is given, and MUST be empty otherwise.
- **Unknown name.** An unknown or missing `NAME` MUST exit 2 with `FEN-2001` and a hint that lists the public names.
- **Data.** The command sends no design data, so `result.sends_data_offsite` of `capabilities` MUST stay `false`.
- **Evidence.** The envelope evidence is `UNVERIFIED`: installing a tool proves nothing about a board.
- `example_args` MUST be `("_selftest", "--dir", "tools", "--dry-run")` and `mutation_example_args` `("_selftest", "--dir", "tools")`; both MUST run no subprocess and open no connection. `docs/cli-contract.md` MUST have a section `fetch` with the plan, the result keys, the two error codes and the sentence that no other command downloads.

#### Scenario: Dry run of the real row makes no request
- **GIVEN** `urllib.request.urlopen` patched to raise, and `FENOLITE_TOOLS_DIR` set to an empty folder of the test
- **WHEN** `uv run pytest tests/unit/cli/test_fetch_cmd.py -k dry_run` runs `fenolite fetch freerouting --dry-run --json`
- **THEN** the exit code is 0, `result.plan` lists `freerouting/freerouting-2.4.1.jar` under that folder with the row's size and digest, `result.licence` is `GPL-3.0`, `result.needs` names Java 25, and the folder is still empty

#### Scenario: Table agrees with the evidence page
- **WHEN** `uv run pytest tests/unit/cli/test_fetch_cmd.py -k table` reads `fetch.toml` and `docs/evidence/routing.md`
- **THEN** the row `freerouting` holds the size and the digest of the page's rows `size` and `SHA-256`, an `https` address and the registered source `S-0223`

#### Scenario: Confirmation required
- **WHEN** `fenolite fetch freerouting --json` runs with the same patches
- **THEN** the exit code is 4, stderr carries `FEN-4001`, and no connection was opened

#### Scenario: Install from a file
- **GIVEN** the row `freerouting` replaced in the test by one whose size and digest are those of a small file the test wrote
- **WHEN** `fenolite fetch freerouting --from <that file> --confirm --json` runs
- **THEN** the destination holds the file's bytes, `result.origin` is `file`, and a second run plans nothing and reports `installed: true`

#### Scenario: Wrong file refused
- **GIVEN** the same row and a file with other bytes
- **WHEN** `fenolite fetch freerouting --from <it> --confirm` runs
- **THEN** the exit code is 3, stderr carries `FEN-3006` with both digests, and the destination does not exist

#### Scenario: Network failure
- **GIVEN** `fetch.download` patched to raise `URLError`
- **WHEN** `fenolite fetch freerouting --confirm` runs
- **THEN** the exit code is 6, stderr carries `FEN-6003` with `retryable` true and a hint naming `--from`, and nothing is written

#### Scenario: Self-test row through the consistency suite
- **WHEN** `uv run pytest tests/consistency -k fetch tests/unit/cli/test_hermetic_examples.py` runs
- **THEN** `fetch` passes the mutation protocol in an empty folder, writing `tools/fetch-selftest.txt`, with subprocess creation patched to raise

#### Scenario: Unknown tool
- **WHEN** `fenolite fetch kicad` runs
- **THEN** the exit code is 2, and the hint names `freerouting` and not `_selftest`

### Requirement: Command text
`fenolite.cli.api.Result` SHALL have the field `text: str | None = None`, a text that a command wants printed as it is in text mode.
- In text mode, when `text` is set and the command succeeded, stdout MUST start with the status line that every command prints (`fenolite <name>: ok`), one empty line, the text, and one newline; the `input`, `result` and `evidence` lines of the generic rendering MUST NOT be printed.
- When the envelope holds issues or a receipt, their lines MUST follow the text after one empty line, in the form text mode gives them without `text`. An envelope with neither MUST end with the text's newline.
- `--format concise` ("Concise output") MUST fold the issues before they are printed, as it does without `text`, and MUST NOT change the text.
- In JSON mode `text` MUST have no effect: the envelope is unchanged and holds no key for it.
- A command without `text` MUST print as before this requirement.

#### Scenario: Text is printed after the status line
- **GIVEN** `_echo --text-body "line one"`, a hidden option that sets `Result.text`
- **WHEN** `uv run pytest tests/unit/cli/test_output.py -k command_text` runs it with `--text`, and with `--json`
- **THEN** the first stdout is `fenolite _echo: ok`, an empty line and `line one`, and the second is an envelope without that text

#### Scenario: Issues follow the text
- **WHEN** `_echo --text-body "line one" --issue warning --text` runs
- **THEN** stdout is the status line, an empty line, `line one`, an empty line and one line that starts with `warning:`

### Requirement: Command description
`fenolite.cli.describe` SHALL describe the arguments of every registered command as data taken from the command's own parser, so that documentation and other front ends never declare them a second time.
- `describe(command) -> CommandDescription` MUST return `name`, `summary` (the command's help line), `mutates`, `usage` (one line starting with `fenolite <name>`) and `arguments`, a tuple of `Argument(name, flags, kind, type, choices, default, required, repeatable, help)` in the parser's order.
- `kind` MUST be `positional`, `option` (takes a value) or `flag` (takes none). `type` MUST be `integer` or `number` for a parser type of `int` or `float`, `boolean` for a flag, and `string` otherwise. `flags` holds the option strings, empty for a positional. `choices` is a sorted list or `null`. `default` is a JSON value or `null`. `repeatable` is true for an argument that may be given more than once or takes several values.
- The global flags (`--json`, `--text`, `--fields`, `--limit`, `--cursor`, `--format`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version`, `--allow-lossy`, and those a later change adds) MUST NOT be in `arguments`; `global_arguments()` MUST return them once, read from the same parser. `--dry-run` and `--confirm` MUST be in the `arguments` of a mutating command and of no other.
- `describe` MUST build the description from the parser that `fenolite.cli.main.build_parser` gives the command, MUST run no command and MUST have no side effect.
- `CommandDescription.to_json()` and `Argument.to_json()` MUST return plain JSON values with exactly the fields above.
- A test MUST fail, for any registered command, when an option string that its `--help` prints is missing from its description or from `global_arguments()`, and when the description holds one that `--help` does not print.

#### Scenario: Build is described
- **WHEN** `uv run pytest tests/unit/cli/test_describe.py -k build` calls `describe` on the `build` command
- **THEN** `arguments` holds a `positional` for the design script, the `option` `--out` with `required` true, the `option` `--target` with the choices `altium` and `kicad`, and the flags `--dry-run` and `--confirm`; and it holds no `--json`

#### Scenario: Read-only command has no protocol flags
- **WHEN** `describe` is called on `check`
- **THEN** no argument has the flag `--confirm`, and `mutates` is `false`

#### Scenario: Global flags are listed once
- **WHEN** `uv run pytest tests/unit/cli/test_describe.py -k global_flags` calls `global_arguments()`
- **THEN** it holds `--limit` with the type `integer`, `--cursor`, and `--format` with the choices `concise` and `detailed`, and no command's `arguments` holds any of the three

#### Scenario: Descriptions agree with help
- **WHEN** `uv run pytest tests/unit/cli/test_describe.py -k agrees_with_help` runs over the command registry
- **THEN** for every command the option strings of its description and of `global_arguments()` equal the option strings found in its `--help` text, apart from `-h` and `--help`

### Requirement: Brief capabilities
`fenolite capabilities --brief` SHALL answer the first question of an agent in a reply whose size is bounded: what is installed here, what can it do, and where to read more. The default result of `capabilities` MUST stay as it is.
- With `--brief`, `result` MUST hold exactly the keys `fenolite_version`, `commands`, `targets`, `tools`, `routers`, `guide`, `starters` and `sends_data_offsite`.
- `commands` MUST list every command that is not hidden, sorted by name, each with exactly `name`, `summary` and `mutates`, `summary` being the command's help line.
- `targets` MUST hold exactly `build`, `kicad` and `default`: `build` is the sorted list of choices of `build --target` (`altium` and `kicad`), read from the command's description; `kicad` and `default` are the target majors and the default target of the `kicad` backend's entry in the default view. The brief view MUST NOT state an evidence level or the word `experimental` for a target: the status of each Altium write kind stays in the default view ("Backends in capabilities", "Experimental features in capabilities", "Evidence matrix in capabilities").
- `tools` and `sends_data_offsite` MUST equal the default view's.
- `routers` MUST list the registered routers sorted by name, each with exactly `name`, `available` and `reason`, from `Router.available()`; with `--no-tools`, `available()` MUST NOT be called and both values MUST be `null`.
- `guide` MUST list `guide.pages()` with exactly `topic`, `title` and `summary`, and `starters` MUST list `guide.starters()` with exactly `name` and `summary`.
- The JSON of the brief `result` with `--no-tools` MUST be under 300 bytes per listed command plus 2 000 bytes, and MUST hold none of the keys `backends`, `experimental`, `extras` and `matrix`; a test MUST check both.
- `--brief` and `--command` MUST exclude each other (exit 2, `FEN-2001`). `--fields` MUST work on the brief result. `--format concise` MUST be accepted with `--brief` and MUST NOT change `result`: it folds issues, and the view chooses the result.
- `docs/cli-contract.md` MUST describe the brief view under "Discovery".

#### Scenario: Brief view
- **WHEN** `uv run fenolite capabilities --brief --no-tools --json` runs
- **THEN** the exit code is 0, `result` has exactly the eight keys, `result.commands` names `build` with a non-empty `summary` and `mutates` true and holds no `_echo`, `result.targets.build` is `["altium", "kicad"]`, `result.routers` names `direct` with `available` `null`, `result.guide[0].topic` is `start`, and `result.starters` names `blink`

#### Scenario: Router availability
- **GIVEN** no Freerouting jar and no `FENOLITE_KRT`
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_brief.py -k routers` runs `capabilities --brief --json`
- **THEN** `direct` has `available` true and a `null` reason, and `freerouting` has `available` false and a reason

#### Scenario: Size bound
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_brief.py -k size` measures the brief result
- **THEN** it is under 300 bytes per listed command plus 2 000 bytes, and holds no `experimental` key

#### Scenario: Default view unchanged
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result` holds the keys it held before this requirement, with `backends`, `experimental` and `matrix` unchanged

### Requirement: Command view of capabilities
`fenolite capabilities --command NAME` SHALL return the description of one command.
- `result` MUST hold exactly `command` and `global_arguments`. `result.command` MUST be that command's entry of the default view's `commands`, extended with `summary`, `usage` and `arguments` from `fenolite.cli.describe.describe`; `result.global_arguments` MUST be `describe.global_arguments()` as JSON.
- A hidden command MUST be described when it is named exactly.
- An unknown name MUST exit 2 with `FEN-2001` and a hint that names the three closest command names.
- The view MUST run no tool, with or without `--no-tools`.
- `docs/cli-contract.md` MUST describe the view and the fields of an argument under "Discovery".

#### Scenario: One command
- **WHEN** `uv run fenolite capabilities --command route --json` runs
- **THEN** the exit code is 0, `result.command.name` is `route`, `result.command.mutates` is true, `result.command.arguments` holds the option `--router`, and `result.global_arguments` holds `--fields`

#### Scenario: Unknown command
- **WHEN** `fenolite capabilities --command rout` runs
- **THEN** the exit code is 2 and the hint names `route`

### Requirement: Guide command
`fenolite guide [TOPIC]` SHALL be registered by `src/fenolite/cli/cmd_guide.py` with `mutates=False`, and SHALL print the pages of the packaged agent guide (`agent-guide`, "Packaged agent guide") for the installed version, running no tool.
- **Without a topic.** `result` MUST hold exactly `version` and `topics`; `topics` lists `guide.pages()` in order, each with exactly `topic`, `title`, `summary` and `lines`. The command text MUST be one line per page, `<topic>: <summary>`.
- **With a topic.** `result` MUST hold exactly `topic`, `title`, `summary`, `text` and `version`. The command text ("Command text") MUST be the page's `text`, unchanged.
- An unknown topic MUST exit 2 with `FEN-2001` and a hint that names the closest topics, or all topics when none is close.
- The output MUST be deterministic and MUST hold no absolute path. The envelope evidence is `UNVERIFIED`.
- `example_args` MUST be `("start",)`. `docs/cli-contract.md` MUST have a section `guide`.

#### Scenario: List of pages
- **WHEN** `uv run fenolite guide --json` runs
- **THEN** the exit code is 0, `result.topics[0].topic` is `start`, and every entry has a one-line `summary`

#### Scenario: One page as text
- **WHEN** `uv run fenolite guide start --text` runs
- **THEN** stdout is the status line, an empty line and the body of `SKILL.md` without its front matter

#### Scenario: Unknown topic
- **WHEN** `fenolite guide strat` runs
- **THEN** the exit code is 2 and the hint names `start`

### Requirement: Skill command
`fenolite skill show` and `fenolite skill install [--agent NAME | --dir DIR] [--agents-md]` SHALL be registered by `src/fenolite/cli/cmd_skill.py` with `mutates=True`, and SHALL copy the packaged skill folder to where an agent reads it, only through the mutation protocol.
- **`show`.** It MUST plan no write, and `result` MUST hold exactly `name`, `description`, `version`, `files` (each `path`, `bytes` and `sha256`, of `guide.skill_files()`) and `agents` (each `agent` and `dir`, of `guide.AGENT_DIRS`).
- **`install`, the folder.** The target is `DIR`, or the folder of `guide.AGENT_DIRS[NAME]`; `--agent` and `--dir` MUST exclude each other, and an unknown agent MUST exit 2 with a hint that names the agents and `--dir`. The command MUST plan one write per file of `guide.skill_files()`, at `<target>/fenolite/<path>`.
- **`install`, the version line.** The planned `SKILL.md` MUST be the packaged file followed by the line `<!-- installed from fenolite <version> -->`; every other file MUST be planned byte for byte.
- **`install`, the pointer.** With `--agents-md` the command MUST also plan `AGENTS.md` in the working directory. Its content MUST be: for a missing file, `guide.AGENTS_SECTION` between the lines `<!-- fenolite:begin -->` and `<!-- fenolite:end -->`; for a file that holds both marker lines, the same file with everything between them replaced by the section; for a file without them, the file followed by an empty line and the marked section. A file that holds one marker without the other MUST exit 3 with `FEN-3004`.
- `guide.AGENTS_SECTION` MUST tell an agent to run `fenolite guide start --text` before a task about a circuit board, MUST name `fenolite capabilities --brief`, and MUST be at most 12 lines.
- `install` with none of `--agent`, `--dir` and `--agents-md` MUST exit 2 with `FEN-2001`.
- **Result.** `result` MUST hold `action`, `target` (or `null` with `--agents-md` alone), `files` (the paths planned) and `version`.
- The command MUST run no tool and open no connection.
- `example_args` MUST be `("show",)` and `mutation_example_args` `("install", "--dir", "skills")`. `docs/cli-contract.md` MUST have a section `skill`.

#### Scenario: Install into a named folder
- **WHEN** `uv run pytest tests/unit/cli/test_skill_cmd.py -k install_dir` runs `fenolite skill install --dir skills --confirm --json` in an empty folder
- **THEN** `skills/fenolite/SKILL.md` exists, its last line names the Fenolite version, its text before that line equals the packaged file, and the receipt lists every written file with its SHA-256

#### Scenario: Install for an agent
- **WHEN** `fenolite skill install --agent claude-code --dry-run --json` runs
- **THEN** the plan lists `.claude/skills/fenolite/SKILL.md` and nothing is written

#### Scenario: Pointer section is idempotent
- **GIVEN** an `AGENTS.md` with two lines of the user's own text
- **WHEN** `fenolite skill install --agents-md --confirm` runs twice
- **THEN** after the first run the file holds the user's two lines, an empty line and the marked section; the second run plans a file with the same bytes; and `AGENTS.md.bak` holds the user's original file after the first run

#### Scenario: Nothing asked
- **WHEN** `fenolite skill install --dry-run` runs
- **THEN** the exit code is 2 and the hint names `--agent`, `--dir` and `--agents-md`

### Requirement: Init command
`fenolite init DIR [--starter NAME] [--name NAME] [--force]` SHALL be registered by `src/fenolite/cli/cmd_init.py` with `mutates=True`, and SHALL write a starter project (`agent-guide`, "Starter projects") into `DIR`.
- `--starter` MUST default to `blink`; an unknown starter MUST exit 2 with `FEN-2001` and a hint that names the starters.
- The design name MUST be `--name`, else the last component of `DIR`; a name that does not match `^[A-Za-z0-9][A-Za-z0-9_.-]*$` MUST exit 2 with a hint that names `--name`.
- The command MUST plan one write per file of `guide.render_starter(starter, name)`, at `DIR/<file>`.
- When `DIR/design.py` exists, the command MUST exit 2 with `FEN-2001` and a hint that names `--force`, unless `--force` is given; with it the mutation protocol's backup applies.
- `result` MUST hold `starter`, `name`, `design` (the path of the script) and `next`: the two command lines `fenolite build <design> --out DIR/build --dry-run --json` and the same with `--confirm`. A test MUST parse both with the command line's own parser.
- The command MUST run no tool. `example_args` MUST be `("proj", "--dry-run")` and `mutation_example_args` `("proj",)`. `docs/cli-contract.md` MUST have a section `init`.

#### Scenario: New project
- **WHEN** `uv run pytest tests/unit/cli/test_init_cmd.py -k new_project` runs `fenolite init board --confirm --json` in an empty folder, and then the first command of `result.next`
- **THEN** `board/design.py` exists, starts with the `CC0-1.0` line and names the design `board`, and the build's dry run exits 0

#### Scenario: Existing script is kept
- **GIVEN** `board/design.py` written by the user
- **WHEN** `fenolite init board --confirm` runs, and then `fenolite init board --force --confirm`
- **THEN** the first exits 2 with a hint naming `--force` and leaves the file, and the second replaces it and keeps the user's text in `board/design.py.bak`

#### Scenario: Name that is not a design name
- **WHEN** `fenolite init "my board" --dry-run` runs
- **THEN** the exit code is 2 and the hint names `--name`

### Requirement: Ready command
`fenolite ready PATH [--no-kicad] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_ready.py` with `mutates=False` and `paged = "issues"`, and SHALL report whether the KiCad project that `PATH` names is electrically ready for fabrication, without writing a file.
- `PATH` MUST resolve with `projectset.resolve_board`.
- Document input (`cli._documents.find_documents`) MUST exit 2 with `FEN-2001` and a hint that names `fenolite check`.

#### Scenario: A ready project
- **GIVEN** the fixture `tests/data/kicad/ready/` and the fake `kicad-cli` of `tests/_fakecli.py`, whose ERC and DRC reports hold no violation
- **WHEN** `uv run pytest tests/unit/cli/test_ready_cmd.py -k ready_project` runs `fenolite ready <fixture> --kicad-cli <fake> --json`
- **THEN** the exit code is 0, `result.ready` and `result.complete` are true, every check is `ok`, and no file of the fixture changes

#### Scenario: Altium input
- **WHEN** `fenolite ready <an Altium .PcbDoc> --json` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`, whose hint names `fenolite check`

### Requirement: Ready checks and their sources
The command SHALL run the checks of `checks.readiness.READY_CHECKS` in order: `nets.open`, `erc.kicad`, `drc.kicad`, `pins.unconnected`, `power.nets`, `parts.fields`.
- `nets.open` MUST come from `analysis.connectivity` on the board that `cli._boardview.load_board` reads; the issues of both MUST be passed on.
- `erc.kicad` and `drc.kicad` MUST be the stages that `cli.cmd_check.run_stages` gives, unchanged.
- The last three MUST be judged on the intent ("Ready intent").

#### Scenario: Open nets make a project not ready
- **WHEN** `fenolite ready tests/data/kicad/board/two_layer.kicad_pcb --no-kicad --json` runs
- **THEN** the exit code is 5, `result.ready` is false, `result.checks` names the six checks in order, and the issues hold one `ready.net-open` with `where` `LED_A`

### Requirement: Ready intent
The intent SHALL be the `.fenolite/` model of a built project, else the board as read with the net classes and rules of the project files (`DesignRulesSource.design_rules`); zones always come from the board as read, matched by net name.
- A `.fenolite/` that cannot be loaded MUST give one `check.cache-unreadable` warning, and the board's reading MUST stand in.

#### Scenario: A built project is judged on its model
- **GIVEN** a confirmed build of the starter of `fenolite init`, not routed
- **WHEN** `uv run pytest tests/unit/cli/test_ready_cmd.py -k built` runs `fenolite ready <build> --no-kicad --json`
- **THEN** `result.project.built` is true, the issues hold one `ready.net-open` per net of the starter, and no `ready.pin-unconnected`

#### Scenario: An unreadable model
- **GIVEN** that build whose `.fenolite/board.json` holds `{`
- **WHEN** `fenolite ready <build> --no-kicad --json` runs
- **THEN** the issues hold one `check.cache-unreadable` warning and the checks still run

### Requirement: Ready without kicad-cli
Without `--no-kicad`, a missing or unsupported `kicad-cli` SHALL exit 6 with the `FEN-6001` or `FEN-6002` of the pre-flight of `run_stages`, whose hint names `--no-kicad`.
- With `--no-kicad`, no subprocess MUST run, and `erc.kicad` and `drc.kicad` MUST be `skipped` with reason `no-kicad`.
- Each skipped check, for that option or for the stage's own reason, MUST give one `ready.check-skipped` warning.

#### Scenario: No kicad-cli
- **GIVEN** no `kicad-cli` on `PATH` and no `FENOLITE_KICAD_CLI`
- **WHEN** `fenolite ready <fixture> --json` runs
- **THEN** the exit code is 6, stderr carries `FEN-6001`, and its hint names `--no-kicad`

#### Scenario: Skipped by option
- **WHEN** `fenolite ready <fixture> --no-kicad --json` runs with `subprocess.run` and `subprocess.Popen` patched to raise
- **THEN** the exit code is 0, `result.complete` is false, `erc.kicad` and `drc.kicad` are `skipped` with reason `no-kicad`, and the issues hold two `ready.check-skipped` warnings

### Requirement: Ready result and exit codes
`result` SHALL hold `project` (`board`, `built`), `ready`, `complete`, `checks` (one `StageResult.to_json()` per check, in order) and `counts` (issues per severity).
- `ready` MUST be true exactly when no issue has severity `error`, and `complete` exactly when no check is skipped.
- The exit code MUST be 0 when `ready` is true and 5 when it is false.
- The envelope evidence MUST be `Evidence.combine` of the evidence of the checks that ran.

#### Scenario: DRC findings are passed on
- **GIVEN** the fixture and a fake `kicad-cli` whose DRC report holds one `clearance` violation of severity `error`
- **WHEN** `fenolite ready <fixture> --kicad-cli <fake> --json` runs
- **THEN** the exit code is 5, `drc.kicad` has status `errors`, `result.counts.error` is 1, and the issues hold one `kicad.drc.clearance`

### Requirement: Ready example and documentation
`example_args` SHALL be `(EXAMPLE_READY, "--no-kicad")`, with `EXAMPLE_READY` the board of `tests/data/kicad/ready/`, and SHALL run no subprocess.
- `docs/cli-contract.md` MUST describe the command, its checks, its result and its exit codes.
- The page `checks` of the agent guide MUST hold a tested line of the command, and the start page MUST name it in "The loop".

#### Scenario: Hermetic example
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py tests/consistency -k ready` runs
- **THEN** every test passes

### Requirement: Staged plans
The dispatcher SHALL give every plan that is returned and not written an id, SHALL keep the planned bytes in a state folder outside the user's tree, and SHALL write them on `--confirm --plan ID` without running the command again, after checking that nothing a review relied on has changed.
- **Id.** `cli.plans.plan_id(…)` MUST be the first 16 hex digits of the SHA-256 of the canonical JSON of: the command name; its arguments without the run flags; the working folder; the SHA-256 of every file the command names in `Result.depends`; and, for each planned write, its path, kind, size, SHA-256 and the SHA-256 of the file it would replace (`null` when there is none). No clock, seed or state folder takes part, so the same dry run on the same files gives the same id.
- **Run flags.** `plans.RUN_FLAGS` MUST be `--dry-run`, `--confirm`, `--plan`, `--json`, `--text`, `--fields`, `--limit`, `--cursor`, `--format`, `--progress`, `--seed`, `--timestamp`, `--no-backup`, `--timeout` and `--kicad-cli`: they change how a run happens, not what it plans.
- **Declared inputs.** `fenolite.cli.api.Result` MUST gain `depends: tuple[str, ...] = ()`, the inputs of the command that are not its targets, each as `fenolite.cli.api.depends_on` spells it: relative to the working folder in POSIX form when the file lies inside it, absolute otherwise; sorted and without repeats. Every registered mutating command MUST set it: `build` the design script and, when it reads one, the copper source; `place`, `route`, `fill`, `export`, `render`, `pnp` and `sync` the board and the other files of its copy set that it read; `bom` the board or the root schematic it read; `manifest` every design file and every artefact manifest it hashed; `kit` the documents it packs; `fmt` and `template` their input file; `restore` the receipt file (none for `-`), every file of `written` and every `.bak` it reads; `models` (c0116) the board and every model file it copies; `fetch` (c0078) the file of `--from`, and nothing without it; `_echo` nothing. A target is not declared: it is checked through its own digest.
- **State folder.** `fenolite.core.state.state_dir()` MUST be `FENOLITE_STATE_DIR` when it is an absolute path, `None` when it is `off`, and `~/.cache/fenolite/state` otherwise. A plan MUST be staged under `plans/<id>/` in a temporary folder renamed into place, and MUST hold nothing the command did not plan. The store MUST keep at most `PLAN_KEEP` = 16 plans and `PLAN_BYTES` = 512 MiB, dropping the oldest first, MUST drop a plan older than `PLAN_DAYS` = 7 days, and MUST remove a plan once it is written. No file MUST be created in the working folder, the project or the output folder by a run that writes nothing.
- **Not staged.** A plan that cannot be staged (the store is `off`, full beyond one plan, or not writable) MUST give one `plan.not-staged` warning with the reason, from the table `fenolite.cli.codes.ISSUE_CODES`, and the run MUST go on with its id. A plan that holds a deferred write ("Deferred writes") has no bytes before `--confirm`: it MUST NOT be staged, MUST give no warning, and is planned again.
- **Replay.** `--confirm --plan ID` with a staged plan MUST NOT call the command. It MUST refuse with `FEN-4002` (exit 4), naming the first reason, when the working folder, the command or its arguments without the run flags differ from the plan's; when a file of `depends` or a target has another SHA-256 than at review (a target that did not exist must still not exist); or when a staged file does not have its planned SHA-256. Otherwise it MUST write the staged bytes through "All-or-nothing writes" and reply with the reviewed `result`, `issues`, `evidence` and `input`, the receipt, and `receipt.plan` set to ID; as after any confirmed write, `result` then holds neither `plan` nor `plan_id`, and the run flags of the call (`--fields`, `--limit`, `--format`) shape the reply. A refusal writes nothing and keeps the stage, except a damaged one, which it removes.
- **Planned again.** When ID names no staged plan, `--confirm --plan ID` MUST run the command once and write only when the id of the new plan equals ID; otherwise `FEN-4002`. So the id always binds what is written, and the store only saves the second run.
- **Receipt.** `Receipt` MUST gain `plan: str | None = None`, in `schemas/fenolite.envelope.v0.json` with a default; it takes no part in `receipt.id` ("Receipt identity"), so `fenolite restore` reads the receipt of a replayed plan as any other.
- A command that planned no write MUST get no `plan_id`.
- `docs/cli-contract.md` MUST describe the id, the checks, the state folder with its bounds and `FENOLITE_STATE_DIR`, and `AGENTS.md` MUST name `--confirm --plan` in its line about writing commands.

#### Scenario: The reviewed bytes are written without a second run
- **GIVEN** a fake `kicad-cli` that stamps each run with a counter, and `fenolite export <board> --out fab --all --manifest --dry-run --json`, whose `result.plan_id` is P
- **WHEN** `uv run pytest tests/unit/cli/test_plans.py -k replay` runs `fenolite export <board> --out fab --all --manifest --confirm --plan P`
- **THEN** the fake saw no further run, every written file has the SHA-256 of its plan row, `receipt.plan` is P, and `plans/P` is gone from the state folder

#### Scenario: A target changed after the review
- **GIVEN** `_echo --write out.txt --dry-run` over an existing `out.txt`, giving the id P, and `out.txt` then edited by hand
- **WHEN** `_echo --write out.txt --confirm --plan P` runs
- **THEN** the exit code is 4, stderr carries `FEN-4002` naming `out.txt`, the file keeps the hand edit, and the stage stays

#### Scenario: An input changed after the review
- **GIVEN** a dry-run `build` of an authored design, giving the id P, and the design script then edited
- **WHEN** `fenolite build design.py --out proj --confirm --plan P` runs
- **THEN** the exit code is 4 and stderr carries `FEN-4002` naming `design.py`

#### Scenario: Another command line
- **GIVEN** the id P of `_echo --write a.txt --dry-run`
- **WHEN** `_echo --write b.txt --confirm --plan P` runs
- **THEN** the exit code is 4 with `FEN-4002`, and neither file exists

#### Scenario: A plan that was not staged is planned again
- **GIVEN** `FENOLITE_STATE_DIR=off` and `_echo --write out.txt --dry-run`, whose reply holds the id P and one `plan.not-staged` warning
- **WHEN** `_echo --write out.txt --confirm --plan P` runs with the same setting, and then `_echo --write out.txt --confirm --plan 0000000000000000`
- **THEN** the first writes `out.txt` with `receipt.plan` P, and the second exits 4 with `FEN-4002`

#### Scenario: The id is a digest of the inputs
- **WHEN** the same dry run is made twice, with different `--seed`, `--timestamp` and `FENOLITE_STATE_DIR`
- **THEN** both replies hold the same `plan_id`

#### Scenario: The store is bounded
- **GIVEN** 17 staged plans in a state folder
- **WHEN** `uv run pytest tests/unit/cli/test_plans.py -k prune` stages the seventeenth
- **THEN** the store holds 16 plans and the oldest is gone

#### Scenario: Every mutating command declares its inputs
- **WHEN** `uv run pytest tests/consistency -k depends` runs the mutation example of every registered mutating command with `--dry-run`
- **THEN** each reply that holds a plan holds a `plan_id` of 16 hex digits, and each path of the command's `depends` names an existing file, inside the working folder when the path is relative

#### Scenario: A replayed plan can be undone
- **GIVEN** `out.txt` holding `one`, and `_echo --write out.txt` planned and then written with `--confirm --plan P`, the envelope saved as `r.json`
- **WHEN** `fenolite restore r.json --confirm` runs
- **THEN** `out.txt` holds `one` again and the exit code is 0

### Requirement: All-or-nothing writes
The dispatcher SHALL write the files of one command with `core.io.atomic_write_all` (`core-primitives`, "Atomic writes of several files"), so that a command writes every file of its plan or none, and a failed write SHALL end in an envelope and one error object.
- When the write raises `WriteError`, the dispatcher MUST print the envelope with `ok` false, the command's `result` (with `plan` and `plan_id`) and `receipt` `null`, and one `FEN-1002` object: exit 1, `retryable` true, a message that names the failing path relative to the working folder and the system's reason, and the hint "nothing was written; fix the cause and run the same command again". Neither MUST hold an absolute path or a traceback.
- After such a failure every target MUST hold the bytes it held before the command, every `.bak` that existed MUST be unchanged, and no target, temporary file or folder that the command created MUST remain. A receipt returned by an earlier command MUST therefore still restore.
- Under `--plan`, the stage MUST stay for the retry.
- `main()` MUST map every exception that is not a `CliError` to `FEN-1001` through "Library errors map to registered codes", printing no traceback.

#### Scenario: A build that fails in the middle changes nothing
- **GIVEN** an authored design and an output folder `proj` that already holds a built project, whose `proj/lib` is made read-only
- **WHEN** `uv run pytest tests/unit/cli/test_write_failures.py -k build` runs `fenolite build design.py --out proj --confirm --json` after a change of one value in the design
- **THEN** the exit code is 1, stderr carries `FEN-1002` naming a path under `proj/lib`, and every file of `proj` has the SHA-256 it had before, `.fenolite/` included

#### Scenario: A first build into a blocked folder leaves nothing
- **GIVEN** an empty folder in which `proj/lib` cannot be created because `proj` is read-only
- **WHEN** the same build runs
- **THEN** the exit code is 1 with `FEN-1002`, and `proj` holds no file and no folder that the command made

#### Scenario: The plan survives the failure
- **GIVEN** a plan P whose replay fails with `FEN-1002`
- **WHEN** the cause is removed and `--confirm --plan P` runs again
- **THEN** the files are written with the reviewed bytes

### Requirement: Error findings plan no write
The dispatcher SHALL plan, stage and write nothing for a command whose issues hold one of severity `error`, unless the command sets `Result.write_on_error`.
- `fenolite.cli.api.Result` MUST gain `write_on_error: bool = False`. Only three commands MAY set it: `place`, and only under `--force`, where writing beside an error is what the flag asks for; `manifest`, whose one write is the report of the findings ("Manifest command": the manifest is planned whether or not the check found errors); and `kit record`, whose record holds the failed steps of the run.
- With an error issue and without `write_on_error`, `result.plan` and `result.plan_id` MUST be absent, `receipt` MUST be `null`, no file MUST change, and the exit code MUST be 5 with `FEN-5001`, with `--dry-run`, with `--confirm` and with neither.
- The rule holds in the dispatcher, so a command need not empty its own writes; the commands that do so today MUST keep their replies.
- `docs/cli-contract.md` MUST state the rule under the mutation protocol, with its exceptions.

#### Scenario: No write beside an error
- **WHEN** `uv run pytest tests/unit/cli/test_write_failures.py -k error_finding` runs `_echo --issue error --write x.txt --confirm --json` in an empty folder
- **THEN** the exit code is 5, the folder is still empty, `receipt` is `null`, and `result` holds neither `plan` nor `plan_id`

#### Scenario: Forced placement still writes
- **GIVEN** an authored project in which `place --move` puts a part outside the outline
- **WHEN** `fenolite place <dir> --move R1=200mm,200mm --force --confirm` runs
- **THEN** the board is written, the exit code is 5, and the receipt lists the board

#### Scenario: The rule holds for every mutating command
- **WHEN** `uv run pytest tests/consistency -k error_no_write` reads the registry
- **THEN** it fails for a mutating command other than `place`, `manifest` and `kit` whose module sets `write_on_error`

### Requirement: Interrupted commands write nothing and stop their tools
On POSIX, `main()` SHALL turn SIGTERM and SIGINT into `fenolite.cli.main.Interrupted`, raised in the main thread, and a command stopped so SHALL stop the tool processes it started, write nothing, and end in one error object.
- `Interrupted` MUST be a `KeyboardInterrupt`, so that no handler of `Exception` catches it and code that lets Ctrl+C pass lets it pass. After the first signal both signals MUST be ignored until the command has ended, so that a second one cuts neither the roll back nor the error object; `main()` MUST put the caller's handlers back when it returns.
- Every tool process that Fenolite starts through `subprocess.run`, the KiCad runner or a routing plugin MUST be killed when the exception passes through its call, so that no `kicad-cli`, `java` or router process outlives the `fenolite` process that started it.
- A write in progress MUST roll back ("All-or-nothing writes"). The job record of a route MUST keep the runs that finished ("Resumable route jobs").
- The dispatcher MUST print the envelope with `ok` false and `receipt` `null`, and one `FEN-1003` object: exit 1, `retryable` true, the message "stopped by a signal; nothing was written".
- On Windows a Ctrl+C MUST be handled the same way; a forced stop of the process cannot be handled, and `docs/cli-contract.md` MUST say so. A stop by SIGKILL is outside this requirement on every system.

#### Scenario: A stopped route stops its router
- **GIVEN** a fake router process that sleeps and records its process id, started by `fenolite route <board> --router <fake> --confirm`
- **WHEN** `uv run pytest tests/unit/cli/test_interrupt.py -k router` sends SIGTERM to the `fenolite` process alone
- **THEN** `fenolite` exits 1 with `FEN-1003` as the last line of stderr, the fake's process no longer exists, and the board file is unchanged

#### Scenario: A signal during the write
- **GIVEN** `_echo --write a.txt --write b.txt --confirm` with a hook that raises `Interrupted` after the first replacement
- **WHEN** it runs over two existing files
- **THEN** both files hold their previous bytes, no `.bak` was added, and stderr carries `FEN-1003`

### Requirement: Progress on stderr
The global flag `--progress` SHALL make a command write progress records on stderr while it runs: one when a unit of work starts, one when it ends, and one at least every 10 seconds, so that a caller can tell a long step from a dead one.
- In JSON mode a record MUST be one line `{"progress": {"command", "event", "step", "index", "total", "detail", "elapsed_ms"}}` with `event` `step` (a unit starts), `done` (it ends) or `alive`; `index` and `total` are integers or `null`. In text mode it MUST be one line that starts with `progress: <command>: `. A record MUST hold no absolute path, home directory or temporary path.
- **Units.** `check`: one per stage that runs, named by the stage. `route`: one per router process ("Resumable route jobs"). `fill`: the refill. `export`: one per kind. `render`: one per view. Every other command gives `alive` records only.
- **Heartbeat.** While the command runs, at least one record MUST be written every `interval` seconds (10 by default), from a daemon thread that stops before the envelope is printed; writes to stderr MUST be serialised.
- `fenolite.core.progress` MUST define the protocol `Progress` with `step(name, *, index=None, total=None)` and `done(name, *, detail="")`, and `NULL_PROGRESS`, which does nothing. `fenolite.cli.api.Context` MUST gain `progress`. `run_checks` MUST take `progress=NULL_PROGRESS`. `checks`, `routing` and the backends MUST reach the reporter only through this protocol.
- Without `--progress`, a command MUST write nothing on stderr but its error object, as today, and stdout MUST be the same with and without the flag apart from `elapsed_ms`.
- `capabilities` MUST list `--progress` among the global flags (`result.global_flags`, the long flags every command accepts; `result.mutation_flags` holds `--dry-run`, `--confirm` and `--plan`), and `docs/cli-contract.md` MUST describe the records and say that they are not covered by the determinism rule.

#### Scenario: Units of a check
- **WHEN** `uv run pytest tests/unit/cli/test_progress.py -k check` runs `fenolite check <board> --stages model.validate,roundtrip --progress --json`
- **THEN** stderr holds, in order, a `step` and a `done` record for `model.validate` and for `roundtrip`, each a JSON line, and stdout equals the stdout of the same call without `--progress` apart from `elapsed_ms`

#### Scenario: A long step stays alive
- **GIVEN** `_echo --steps 1 --sleep 1.0 --progress` with the reporter's interval set to 0.1 s
- **WHEN** it runs
- **THEN** stderr holds at least three `alive` records between the `step` and the `done` record

#### Scenario: Silent by default
- **WHEN** `_echo --steps 3` runs without `--progress`
- **THEN** stderr is empty

#### Scenario: Records hold no path of the machine
- **WHEN** `fenolite export <board> --out fab --all --dry-run --progress --json` runs with a fake `kicad-cli`
- **THEN** there is one `step` and one `done` record per kind, and no record holds the temporary folder of a run or the home directory

### Requirement: Resumable route jobs
`fenolite route` SHALL keep the copper of each router process that finished in a job record in the state folder, and the same call made again SHALL reuse it instead of routing those nets again.
- **Key.** `cli.jobs.route_job_key(…)` MUST be the first 16 hex digits of the SHA-256 of the canonical JSON of the Fenolite version, the router's name and version, the SHA-256 of the board, of its project file and of its rules file (the rules file joins the key only when there is one: the router is given its rules), and the route arguments without the run flags and without `--out`. The record lives under `jobs/<key>/` of `state_dir()`, one file per finished run, each written with `atomic_write`; with the state folder `off` no record is kept and the command routes as today.
- **Recording.** `route` MUST pass `on_run` in the job (`routing`, "Router runs reported for progress and resumption") and MUST add each `FinishedRun` to the record before the next process starts.
- **Reuse.** When a record exists for the key, the command MUST read the board, apply `--rip`, merge the recorded copper, and only then select nets, so that the recorded nets are not routed again. It MUST then give one `route.resumed` info and `result.resumed` (`runs`, `nets`), and `result.tracks` and `result.vias` MUST count the reused copper with the new; without a record `result.resumed` MUST be `null`. A record that cannot be read MUST be removed and MUST NOT fail the command.
- **End.** `fenolite.cli.api.Result` MUST gain `written: Callable[[], None] | None = None`, which the dispatcher calls once after the writes of the result were all written; `route` removes its record through it. The record MUST be removed after a confirmed write of the routed board, and after a dry run that attempted every selected net. It MUST stay after a stop by a signal, after a failed write (`FEN-1002`) and after a run that wrote nothing and that a time limit cut, a dry run included (`result.budget.exhausted`): the same call made again then goes on with the nets that were not attempted. It MUST also stay after a dry run that reports an error finding, which plans no write. A confirmed run that a time limit cut writes the copper of its finished runs (`routing`, "Routing time budget"), and its record is removed as after any confirmed write. At most `JOB_KEEP` = 8 records are kept and none older than 7 days.
- `fenolite.routing.codes.ISSUE_CODES` MUST gain `route.resumed` (info), with its table in `explain.toml`. The envelope evidence stays `UNVERIFIED`.
- `docs/routing.md` MUST say what is kept, when it is reused and when it is removed, and that copper made in two calls need not equal the copper of one.

#### Scenario: A stopped route goes on
- **GIVEN** the fake per-net router of `tests/unit/cli/test_route_jobs.py`, set to end the process after its second net of five
- **WHEN** `fenolite route <board> --router <fake> --confirm` runs, is stopped, and runs again with the same arguments
- **THEN** the second call starts three router processes, its reply holds one `route.resumed` info and `result.resumed.nets` of 2, the written board holds the copper of all five nets, and the record is gone

#### Scenario: Another board, another record
- **GIVEN** the record of the first call
- **WHEN** one byte of the board changes and the same command runs
- **THEN** `result.resumed` is `null` and five router processes start

#### Scenario: A failed run is routed again
- **GIVEN** a fake router whose third process ends without copper
- **WHEN** the command runs twice
- **THEN** the record of the first call holds two runs, and the second call routes the third net again

### Requirement: Height limits in place
`fenolite place` SHALL also judge the height limits of a built project after its moves, in addition to the rules of "Place command".
- When the `.fenolite/` model that the command loads holds a height limit, `checks.placement.judge_heights` (`placement`, "Height limits judged") MUST run on the layout after the moves, with `heights_of(<the board>, <that model>)` and the extents the command already has. Each `placement.too-tall` and `placement.height-unknown` MUST be reported with a severity no higher than `warning` and MUST NOT refuse the write.
- `result.rules` MUST gain the family `height` with the counts of `judge_heights`; without a limit the family is absent and the reply is that of "Place command".
- The grid does not read heights: a part that the grid puts under an area too low for it is reported, not moved.
- The envelope's evidence MUST also combine `checks.placement.EVIDENCE` when a limit was judged. No subprocess MUST run, and two runs on equal boards MUST return equal results.

#### Scenario: A move under a low area
- **GIVEN** the blink built with `R1` created with `height=mm(9)`, a rule area `LID` on `F.Cu` over the 8 mm square at the top-left corner of the board (the courtyard of `U1` at (14, 15) mm reaches into a 10 mm square), and `design.height_limit("LID", max=mm(5))`, with `R1` placed outside the area
- **WHEN** `uv run pytest tests/unit/cli/test_place_cmd.py -k height` runs `fenolite place <dir> --move R1=4mm,4mm --dry-run --json`
- **THEN** the exit code is 0, `issues` hold one `placement.too-tall` warning naming `R1`, and `result.rules.height` is `{"judged": 1, "failed": 1, "unknown": 0}`

#### Scenario: No limit, same reply
- **GIVEN** the built blink without a height limit
- **WHEN** `fenolite place <dir> --move R1=12mm,8mm --dry-run --json` runs
- **THEN** `result.rules` holds no `height`

### Requirement: Models command
`fenolite models PATH [--vendor]` SHALL be registered by `src/fenolite/cli/cmd_models.py` with `mutates=True`, and SHALL list the 3D models that the footprints of a board name, with the source where Fenolite finds each; with `--vendor` it SHALL plan copies of them into the project's `3dmodels/` folder, which the `step` export kind reads first (`manufacturing-exports`, "STEP export with 3D models").
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`). A path that names no KiCad board (an Altium document or project) is refused there, as `export` refuses it.
- **Models.** The paths MUST be those of `models.board_models` on the board text, each located once as the `step` kind locates it. The command MUST run no tool and make no request.
- **Result.** `result.models` MUST hold one object per distinct path, sorted by path: `path`, `source` (`project`, `env`, `kicad-config`, `install`, `cache`, `in-place` or `missing`), `sha256` and `bytes` (`null` when missing or in place), and `refs` (sorted). `result.counts` MUST hold `paths`, `located` and `missing`.
- **Missing models.** Each path that is not located MUST give one `kicad.lib.missing-3d-model` (warning) naming the path and its references; the exit code stays 0.
- **`--vendor`.** The command MUST return one `PlannedWrite` of kind `3d-model` per located `${KICAD<N>_3DMODEL_DIR}/<rel>` path whose source is not `project`, at `<board folder>/3dmodels/<rel>` relative to the working directory, holding the bytes of the located file, and nothing else. Without `--vendor` it MUST return none. The mutation protocol applies. The board, its footprints and their model paths MUST NOT change.
- **Determinism.** No value MUST hold an absolute path or a date; two runs on unchanged inputs MUST give the same stdout apart from `elapsed_ms`.
- **Evidence.** The envelope evidence MUST be `models.EVIDENCE`, `INFERRED` (`H-K-EXPORT-MODELS`) until that hypothesis is `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- `example_args` MUST be `(EXAMPLE_BOARD,)` and `mutation_example_args` `(EXAMPLE_BOARD, "--vendor")`, and both MUST run no subprocess. The command MUST declare `paged = "models"` ("Paged results").
- `docs/cli-contract.md` MUST describe the command, its result keys and the order of the sources.

#### Scenario: Located and missing models
- **GIVEN** a copy of `two_layer.kicad_pcb` in `tmp_path` whose `R1` names `${KICAD10_3DMODEL_DIR}/Fenolite.3dshapes/Box_2x1.step` and whose `D1` names `${KICAD10_3DMODEL_DIR}/Fenolite.3dshapes/Absent.step`, with `KICAD10_3DMODEL_DIR` set to `tests/data/models` and no install
- **WHEN** `uv run pytest tests/unit/cli/test_models_cmd.py -k list` runs `fenolite models <board> --json`
- **THEN** the exit code is 0, `result.counts` is `{"paths": 2, "located": 1, "missing": 1}`, the `Box_2x1.step` entry has source `env` and the file's SHA-256, and the issues hold one `kicad.lib.missing-3d-model` naming `D1`

#### Scenario: Vendored, then read from the project
- **GIVEN** the same board
- **WHEN** `fenolite models <board> --vendor --confirm` runs, and then `fenolite models <board> --json`
- **THEN** the first writes `3dmodels/Fenolite.3dshapes/Box_2x1.step` beside the board, byte-equal to its source, and nothing else; the second reports that path with source `project`; the board file is unchanged

#### Scenario: The command is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py tests/consistency -k models` runs the examples
- **THEN** both exit 0 and the outputs hold no absolute path

### Requirement: Drawing options of the export command
`fenolite export` SHALL take `--fab-drawing`, `--assembly-drawing` and `--drawing-spec FILE`, and SHALL run the drawing kinds of `manufacturing-exports` beside the kinds of the requirement "Export command", under its board, tool, source, write and exit-code rules.
- Each flag MUST select its kind. A drawing kind MUST count as a selected kind for the rule that a call selecting no kind and no `--altium-rul` exits 2, and `--all` MUST NOT select one. A drawing kind runs `kicad-cli`: the "Tool" clause of "Export command" (`FEN-6001`, `FEN-6002`, `--timeout` per run) MUST apply when one is selected. `--preset` MUST NOT change the arguments of a drawing kind, and `result.repeat`, where "Export command" has it, MUST map both drawing kinds to `content`.
- The drawing kinds are KiCad's: `PATH` resolves with `projectset.resolve_board` as for every kind, so an Altium document or project is refused there (exit 2, `FEN-2001`) before the spec is read or a tool is looked for. `result.kinds` MUST list the drawing kinds after the other selected kinds, `fab-drawing` first.
- `--drawing-spec` MUST be read before any tool runs. Without a drawing flag it MUST exit 2 with `FEN-2001`; a missing file MUST exit 3 with `FEN-3001`; a `SpecError` MUST exit 3 with `FEN-3004` and list its problems in the message. Without the option, `drawing_spec.DEFAULT` MUST apply.
- `cmd_export` MUST compute each page's obstacles: through `templates.layout` for the spec's or the project's drawing sheet, through `drawing.default_sheet_obstacles` when the project names none. A sheet that cannot be read or built MUST give `drawing.sheet-unread` (error).
- A drawing issue of severity error MUST make the command plan no write and exit 5, as `export.failed` does; an info or a warning MUST NOT change the exit code.
- `result.drawings` MUST hold one object per page, in the order fabrication, assembly top, assembly bottom, with `kind`, `path`, `paper`, `portrait`, `sheet` (`spec`, `project` or `kicad-default`) and `blocks` (each with `name`, `at` and `size` in integer nanometres), and, for an assembly page, `side` and `designators_added`. No value MUST hold a temporary path, the home directory or a date.
- With a drawing kind selected, the envelope's evidence MUST be `Evidence.combine` of `exports.drawings.EVIDENCE` and the evidence of every other selected kind, with the oracle `kicad-cli <version>`.
- `docs/cli-contract.md` MUST describe the three options and `result.drawings`, and `docs/drawings.md` the spec file, the pages, the tables and the seven `drawing.*` codes.

#### Scenario: Plan, then write
- **GIVEN** a fake `kicad-cli` 10.0.6 that writes the files of both drawing kinds
- **WHEN** `uv run pytest tests/unit/cli/test_export_drawings.py -k plan` runs `fenolite export <board> --out fab --fab-drawing --assembly-drawing --dry-run` and then the same with `--confirm`
- **THEN** the first exits 0, plans the drawing files under `fab/drawings/` and writes nothing, and the second writes them with a receipt that lists each file with its SHA-256

#### Scenario: A spec without a drawing flag
- **WHEN** `fenolite export <board> --out fab --gerbers --drawing-spec d.toml --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: An invalid spec runs no tool
- **GIVEN** `d.toml` holding `[page] paper = "B9"` and `subprocess.run` patched to record its calls
- **WHEN** `fenolite export <board> --out fab --fab-drawing --drawing-spec d.toml --dry-run` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004` naming `page.paper`, and no `kicad-cli` run was made

#### Scenario: No room writes nothing
- **GIVEN** `d.toml` with `[page] paper = "A4"` and a board whose outline reaches y = 279 mm
- **WHEN** `fenolite export <board> --out fab --fab-drawing --drawing-spec d.toml --confirm` runs
- **THEN** the exit code is 5, the issues hold `drawing.no-room`, and `fab` does not exist

#### Scenario: The reply describes the pages
- **WHEN** the first command of "Plan, then write" runs with `--json`
- **THEN** `result.drawings` holds one object per page produced, each with its `paper`, `sheet` `kicad-default` and its blocks, and `result.kinds` ends with `fab-drawing`, `assembly-drawing`

#### Scenario: A drawing kind alone needs the tool
- **GIVEN** no `kicad-cli` on `PATH` and no `FENOLITE_KICAD_CLI`
- **WHEN** `fenolite export <board> --out fab --fab-drawing --dry-run` runs
- **THEN** the exit code is 6 and stderr carries `FEN-6001`, although no fabrication kind is selected

### Requirement: Testpoints command
`fenolite testpoints PATH [--side top|bottom|both] [--template FILE] [--min-coverage PERCENT] [--min-pitch LENGTH] [--min-fiducials N] [-o FILE] [--manifest]` SHALL be registered by `src/fenolite/cli/cmd_testpoints.py`, with `mutates=True` for `--out` only, and SHALL report the test points, fiducials, holes and net coverage of a board (`assembly-test-features`).
- `PATH` is a `.kicad_pcb`, a `.kicad_pro` or a project folder, read as `pnp` reads it: from the board file, with no tool run. An Altium document or project is refused as `pnp` refuses it: marks are read from KiCad's pad property, and no Altium record is known to hold one.
- The command MUST declare `paged = "test_points"` ("Paged results").
- `result` MUST hold `side`; `test_points`, `fiducials` and `holes`, rows of "Test-point report rows" with lengths in integer nanometres in the board frame; `coverage` with `eligible`, `covered` and `uncovered`; `counts` with `test_points`, `fiducials_top`, `fiducials_bottom`, `holes` and `tooling_holes`; and `template`, `units`, `origin` and `y_axis`. `issues` MUST hold the findings of "Assembly and test findings", and `evidence` MUST combine `exports.testpoints.EVIDENCE` with the read's.
- `--min-coverage` MUST be an integer from 0 to 100, `--min-pitch` a positive length with a unit, and `--min-fiducials` an integer of at least 1; another value MUST exit 2 (`FEN-2001`).
- `-o FILE` MUST plan one CSV file through the mutation protocol. Its header is `kind,ref,pad,net,x,y,side,access,width,height,drill`, with `kind` `test_point`, `fiducial`, `tooling_hole` or `hole`, one row per report row in that order; positions and sizes in the origin, Y axis, units and decimals of the template's `[placement]` table, sides by its side names, and its CSV options. No file MUST be planned when a finding is an error, or when the origin needs a board outline the board lacks (`pnp.no-outline`).
- `--manifest` follows "Manifest option of producing commands": with `-o FILE` it plans the manifest of the file's folder with one entry of kind `testpoints`; without `-o` it MUST exit 2 with `FEN-2001`.
- The exit code MUST be 0 without an error finding, 5 with one, and 3 for a file that cannot be read.
- The command MUST name `example_args` on the example board, and `mutation_example_args` that write `testpoints.csv`.
- `docs/cli-contract.md` MUST hold a section `testpoints` with its options, its result and its codes.

#### Scenario: A board without marks
- **WHEN** `fenolite testpoints tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** it exits 0, `result.test_points` is empty, `result.coverage.covered` is 0, and `issues` holds one `testpoint.none` info

#### Scenario: A coverage target missed
- **GIVEN** the build of "Features in a build" (`design-dsl`, "Assembly and test features in a build")
- **WHEN** `fenolite testpoints <board> --min-coverage 100 --out tp.csv --dry-run --json` runs
- **THEN** it exits 5, `issues` holds `testpoint.coverage-low`, `result.coverage.covered` is 1, and no write is planned

#### Scenario: The CSV of a build
- **GIVEN** the same build
- **WHEN** `fenolite testpoints <board> --out tp.csv --dry-run --json` runs
- **THEN** it exits 0 and plans `tp.csv`, whose first line is `kind,ref,pad,net,x,y,side,access,width,height,drill` and which holds a `test_point` row for `TP1` with the net `LED_A` and the access `top`, two `fiducial` rows and one `tooling_hole` row for `TH1`

#### Scenario: The CSV joins the manifest
- **GIVEN** the same build
- **WHEN** `uv run pytest tests/unit/cli/test_testpoints_cmd.py -k manifest` runs `fenolite testpoints <board> --out out/tp.csv --manifest --confirm`, and `fenolite testpoints <board> --manifest`
- **THEN** the first writes `out/tp.csv` and `out/fenolite-artifacts.json`, which lists `tp.csv` with kind `testpoints`, `tool` naming `fenolite` and the board's hash in `from`; the second exits 2 with `FEN-2001`

### Requirement: Stack-up in inspect
`fenolite inspect` SHALL report the stack-up of a board it reads, as an addition to the `result` of "Inspect command".
- For a board, `result.stackup` MUST be `null` when `Board.stackup` is `None`, and otherwise hold `thickness` (`Stackup.thickness()`, in nm), `finish`, `impedance_controlled` and `layers`: one object per entry, top to bottom, with `name`, `kind` and `thickness`, and with `dielectric_kind`, `material`, `epsilon_r`, `loss_tangent` and `color` when they are set. Footprint files and symbol libraries MUST NOT carry the key.
- The `kicad.board.stackup-*` issues of the reader MUST be reported as reader issues, as "Inspect command" requires of every reader issue.
- `docs/cli-contract.md` MUST describe the key under `inspect`.

#### Scenario: Board with a stack-up
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/stackup_four.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.stackup.thickness` is 2025000, `result.stackup.finish` is `ENIG`, and `result.stackup.layers` holds 14 objects, the first named `F.SilkS` with kind `silkscreen` and thickness 0

#### Scenario: Board without a stack-up
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.stackup` is `null`, and the other keys are those of "Authored board summary"
