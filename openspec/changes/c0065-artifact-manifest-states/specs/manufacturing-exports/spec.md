## ADDED Requirements

### Requirement: Artefact states
Every manifest entry SHALL carry one `state` of `manifest.STATES = ("generated", "checked", "roundtrip-ok", "oracle-verified", "native-verified")`, in rising order, and `fenolite.exports.states.assign(entries, *, stages, sheets_ok, current) -> tuple[ArtifactEntry, ...]` SHALL assign it: the highest rung a file reaches together with every lower rung that applies to its kind. `stages` maps a stage name to its status and evidence level, `sheets_ok` a sheet path to its RT1 verdict, and `current` a path to the file's present SHA-256.
- **Current.** An entry is current when `current[path]` equals its `sha256` and every hash of its `from` equals the present hash of that source. A derived entry that is not current MUST be `generated` with `stale` true.
- **`generated`.** Every entry reaches it.
- **`checked`.** `model.validate` and `copper.clearance` are in `stages` with status `ok`. A derived entry (kinds `gerbers`, `drill`, `pos`, `ipcd356`, `bom`, `pnp`, `render`) reaches it when it is current and the sources its `from` names are `checked`, and reaches no higher rung.
- **`roundtrip-ok`.** Applies to kinds `kicad_pcb` and `kicad_sch` only: the board needs `roundtrip` with status `ok`, and a sheet needs `sheets_ok[path]` true. Every other design kind skips the rung.
- **`oracle-verified`.** No rule assigns it; every kind skips the rung. The state is reserved for a tool that is neither the producer of a file nor its format's own application.
- **`native-verified`.** The board needs `drc.kicad` with status `ok` and level `KICAD-VERIFIED`. A sheet needs `erc.kicad` with status `ok` and level `KICAD-VERIFIED`. The kinds `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_sym`, `kicad_wks` and `lib-table` reach it exactly when the board does.
- A stage that is missing from `stages`, skipped, or below the level its rule names MUST NOT give its rung, and a rung that is not reached MUST stop the ladder for that file.
- `assign` MUST be pure, MUST import nothing from `checks`, and with an empty `stages` MUST leave every entry `generated`.

#### Scenario: Board up the ladder
- **GIVEN** a board entry that is current, and `stages` with `model.validate`, `copper.clearance` and `roundtrip` `ok` and `drc.kicad` `ok` at `KICAD-VERIFIED`
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k ladder` calls `assign`
- **THEN** the board's state is `native-verified`

#### Scenario: A failed rung stops the ladder
- **GIVEN** the same stages with `roundtrip` `errors`
- **WHEN** `assign` runs
- **THEN** the board's state is `checked`, although `drc.kicad` is `ok`

#### Scenario: DRC below KICAD-VERIFIED
- **GIVEN** the stages of the first scenario with `drc.kicad` `ok` at `UNVERIFIED`
- **WHEN** `assign` runs
- **THEN** the board's state is `roundtrip-ok`

#### Scenario: Derived file of a checked board
- **GIVEN** a Gerber entry whose `from` holds the board's present hash, and a board that reaches `native-verified`
- **WHEN** `assign` runs
- **THEN** the Gerber's state is `checked`

#### Scenario: Stale artefact
- **GIVEN** a Gerber entry whose `from` holds another hash than the board's present one
- **WHEN** `assign` runs
- **THEN** its state is `generated` and `stale` is true

#### Scenario: No check, no claim
- **WHEN** `assign` runs with `stages` empty
- **THEN** every entry is `generated`, and none is `oracle-verified` under any input of the test's generator

### Requirement: Manifest merging
`manifest.merge(existing, entries, *, board, tool, timestamp) -> Manifest` SHALL return the manifest of an output folder after a command wrote files into it: the entries of `existing` with those of `entries` replacing equal paths, sorted by path.
- `existing` MAY be `None`: the result then holds only `entries`.
- Entries that the command did not write MUST be kept unchanged, their `state`, `from` and `tool` included.
- New entries MUST have the state `generated`, `stale` false, `from` holding the SHA-256 of the board and, when the command read one, of the schematic, and `tool` naming what wrote the file (`kicad-cli <version>` or `fenolite <version>`).
- `board`, `tool` and `generated` of the manifest MUST be those of the merging run; `check` MUST become `null`, because the merging run checked nothing; `states` MUST be recounted.
- `export --manifest` MUST merge in this way instead of replacing the file, and a manifest in the folder that `manifest.load` refuses MUST give `manifest.unreadable` (error) and no planned write.

#### Scenario: Two runs, one manifest
- **GIVEN** a folder in which `export --gerbers --manifest --confirm` ran, and then `export --drill --manifest --confirm`
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k merge` reads `fenolite-artifacts.json`
- **THEN** it lists the Gerbers and the drill files, sorted by path, each `generated`

#### Scenario: Re-export replaces by path
- **GIVEN** the same folder after the board changed and `export --gerbers --manifest --confirm` ran again
- **WHEN** the manifest is read
- **THEN** each Gerber entry has the new board hash in `from`, the drill entries keep the old one, and `check` is `null`

#### Scenario: Unreadable manifest refused
- **GIVEN** a folder whose `fenolite-artifacts.json` holds `{`
- **WHEN** `fenolite export <board> --out <folder> --gerbers --manifest --confirm` runs
- **THEN** the exit code is 5, the issues hold `manifest.unreadable`, and no file is written

### Requirement: Project manifest
The manifest that `fenolite manifest` writes SHALL list the design files of a project and the artefacts of the folders it is given, with the states of "Artefact states".
- **Design files.** One entry per file of `projectset.project_set(<board>)`: `kind` from `manifest.design_kind(path)` (`kicad_pcb`, `kicad_sch`, `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_sym`, `kicad_wks`, `lib-table`), `layer` `null`, an empty `from`, `content_sha256` equal to `sha256`, and `tool` `fenolite <version>` when `.fenolite/build.json` records that hash for the file and `null` otherwise. A library folder MUST be listed file by file.
- **Artefacts.** For each artefact folder, the entries of its `fenolite-artifacts.json`, with paths relative to the project manifest's folder; without such a file the folder contributes nothing. A listed file that does not exist MUST be dropped with `manifest.missing` (warning). A file under the folder that no entry lists MUST give `manifest.unlisted` (info).
- **Hashes.** `bytes` and `sha256` of every entry MUST be computed from the file as it is when the command runs.
- **Check.** `check` MUST hold the stages that ran, each with its status, evidence level and oracle, and `tool_version`; with no check it MUST be `null`.
- **Codes.** `exports.codes.ISSUE_CODES` MUST gain `manifest.unreadable` (error), `manifest.missing` (warning by the command, error by `--verify`), `manifest.changed` (error), `manifest.stale` (warning) and `manifest.unlisted` (info).
- The manifest MUST NOT list itself, any file under `.fenolite/`, a `.bak` file or a `.kicad_prl`.
- `docs/exports.md` MUST state each state's rule in one line and what the state does not claim.

#### Scenario: Design files of a built project
- **GIVEN** the blink built with a schematic into `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_manifest_cmd.py -k design` runs `fenolite manifest <dir> --no-check --confirm`
- **THEN** the manifest lists the triad, the schematic, both tables and every file under `lib/`, each `generated` with `tool` naming `fenolite`, and lists neither `.fenolite/build.json` nor itself

#### Scenario: Edited file loses its writer
- **GIVEN** the same project with one byte of the board changed
- **WHEN** the command runs again
- **THEN** the board's entry has `tool` `null` and the new hash

#### Scenario: Artefact folder included
- **GIVEN** `fab/` inside the project, written by `export --all --manifest`, with one extra file `notes.txt`
- **WHEN** `fenolite manifest <dir> --artifacts <dir>/fab --no-check --confirm` runs
- **THEN** the manifest lists the fabrication files as `fab/…`, and the issues hold one `manifest.unlisted` info naming `fab/notes.txt`

## MODIFIED Requirements

### Requirement: Artefact manifest
`fenolite.exports.manifest.build(*, board, tool_version, artifacts, timestamp) -> dict` SHALL build the manifest written as `fenolite-artifacts.json`, and `schemas/fenolite.artifacts.v0.json` SHALL validate it.
- The manifest MUST hold:
  - `schema`: `fenolite.artifacts.v0`;
  - `fenolite`: the package version;
  - `generated`: `timestamp` in the envelope's format;
  - `board`: `path` (relative to the project root, with `/`), `sha256`, `format_version`;
  - `tool`: `name` (`kicad-cli`) and `version`;
  - `artifacts`: one object per artefact, sorted by `path`, with `path`, `kind`, `layer` (or `null`), `bytes`, `sha256`, `content_sha256`, `evidence`, `state`, `stale`, `from` and `tool` ("Artefact states");
  - `project`: `board` and `schematic`, each `{path, sha256, format_version}` or `null`;
  - `check`: `null`, or `{stages, tool_version}` with one `{name, status, level, oracle}` per stage that ran ("Project manifest");
  - `states`: the number of artefacts per state, with every state of `manifest.STATES` as a key.
- `content_sha256(data, kind)` MUST be the SHA-256 of `data` without the lines that start with any prefix in `exports.plan.VOLATILE_PREFIXES` for that kind. A line is compared after its leading blanks are removed. The prefixes MUST be the date-bearing lines recorded by `H-K-EXPORT-REPEAT`: `%TF.CreationDate`, `G04 Created by KiCad`, `; DRILL file`, `; #@! TF.CreationDate` and, for the Gerber job file, `"CreationDate":`.
- The manifest MUST NOT hold an absolute path, a temporary path, the home directory or a user name, and MUST NOT list itself.
- `dumps(manifest)` MUST be canonical JSON (sorted keys, two-space indent, a final newline).
- The artefact files MUST be written with the bytes `kicad-cli` produced; Fenolite MUST NOT edit them.
- `tools/gen_schemas.py --check` MUST cover the schema, whose id stays `fenolite.artifacts.v0`: the fields that this requirement adds to c0024's manifest have defaults, so a manifest written before them still validates.
- `manifest.load(text) -> Manifest` MUST read a manifest and give an entry without `state` the state `generated`, `stale` false, an empty `from` and `tool` `None`. A text that is not JSON, or whose `schema` is not `fenolite.artifacts.v0`, MUST raise `FormatError` (`FEN-3004`).

#### Scenario: Manifest validates
- **WHEN** `uv run pytest tests/unit/exports/test_manifest.py -k schema` builds a manifest for three artefacts
- **THEN** it validates against `schemas/fenolite.artifacts.v0.json`, and the artefacts are sorted by path

#### Scenario: Dates do not change the content hash
- **GIVEN** two Gerber texts that differ only in their `%TF.CreationDate` and `G04 Created by KiCad` lines
- **WHEN** `content_sha256` is computed for each
- **THEN** the two values are equal and the two `sha256` values differ

#### Scenario: A changed aperture changes the content hash
- **GIVEN** two Gerber texts that differ in one `%ADD` line
- **WHEN** `content_sha256` is computed for each
- **THEN** the values differ

#### Scenario: Reproducible with a timestamp
- **WHEN** `build` runs twice with the same arguments and `timestamp`
- **THEN** `dumps` gives equal text, and the text holds no absolute path

#### Scenario: Entries carry a state
- **WHEN** `uv run pytest tests/unit/exports/test_manifest.py -k state` builds a manifest for three artefacts
- **THEN** each entry has `state` `generated`, `stale` false, a `from` with the board's SHA-256 and a `tool`, and `states.generated` is 3

#### Scenario: Manifest of v0.1 still read
- **GIVEN** the authored `tests/data/exports/manifest_v01.json`, written in the shape of c0024 without the added fields
- **WHEN** `manifest.load` reads it and the text is validated against the schema
- **THEN** it validates, and every loaded entry has the state `generated`
