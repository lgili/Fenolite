## ADDED Requirements

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
