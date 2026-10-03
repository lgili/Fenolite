## MODIFIED Requirements

### Requirement: Inspect command
`fenolite inspect FILE [--summary | --streams]` SHALL be registered by `src/fenolite/cli/cmd_inspect.py` with `mutates=False`, and SHALL describe one file without running any external tool. `--summary` is the default view and summarises one KiCad file. `--streams` lists the storages and streams of a compound file ("Inspect stream tree"). Giving both views MUST exit 2 with `FEN-2001`.
- **Kinds.** Boards, footprint files and symbol libraries (file or `.kicad_symdir` folder) MUST be read through `registry.for_path(FILE).read`. `.kicad_sch` and `.kicad_wks` files MUST be read header-only through `versions.inspect`, with root-child counts by head. With the `--summary` view, `.kicad_pro`, `.kicad_dru` and files that are not S-expressions MUST exit 2 with `FEN-2001`; when such a file starts with the compound file signature, the hint MUST name `--streams`.
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

#### Scenario: Compound file without the stream view
- **WHEN** `uv run fenolite inspect tests/data/altium/blink/blink.PcbDoc --json` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and its hint names `--streams`

#### Scenario: Two views
- **WHEN** `uv run fenolite inspect tests/data/altium/blink/blink.PcbDoc --summary --streams` runs
- **THEN** the exit code is 2 with `FEN-2001`

## ADDED Requirements

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
