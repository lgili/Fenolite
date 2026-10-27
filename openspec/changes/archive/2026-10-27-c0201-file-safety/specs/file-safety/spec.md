## ADDED Requirements

### Requirement: Stable snapshot
`fenolite snapshot PATH --out DIR` SHALL copy a design file with its companions, or every project file of a folder, and SHALL accept the copy only when the SHA-256 of every file is the same before and after all were read.
- A file whose hash changed MUST be read again, at most three times, then reported with `safety.unstable` (error), and nothing MUST be written.
- `DIR/snapshot.json` (schema `fenolite.snapshot.v0`) MUST list every copied file with its hash.

#### Scenario: A file saved during the copy
- **GIVEN** an authored project and a hook that saves its board once after its first read
- **WHEN** `uv run pytest tests/unit/safety/test_snapshot.py -k saved` reads the companions of the board
- **THEN** the copy holds the saved content of the board, and one retry is counted

### Requirement: Publish guarded by receipts
`fenolite publish SRC --to DST --receipt RECEIPT` SHALL replace a file of `DST` only when its SHA-256 is the one `RECEIPT` recorded.
- `RECEIPT` is a `snapshot.json`, or the envelope or receipt of a confirmed write.
- Any other changed file MUST be `safety.changed-since-receipt` (error), and nothing MUST be written; `--skip-changed` makes it `safety.skipped` (warning) and writes the rest.
- New files MUST be added, and nothing deleted.

#### Scenario: The owner saved one file
- **GIVEN** a snapshot of an authored project, edited, and one file of the project saved by its owner since
- **WHEN** `uv run pytest tests/unit/safety/test_publish.py -k owner` runs `fenolite publish snap --to proj --receipt snap/snapshot.json --confirm`
- **THEN** the exit code is 5, one `safety.changed-since-receipt` names that file, and no file of the project changed

### Requirement: Open sessions
Every writing command SHALL report `safety.open-session` (warning) for each file of its plan that has a CAD tool's lock file beside it, and `fenolite doctor --sessions PATH` SHALL list the lock files under `PATH`, writing nothing.
- A lock-file pattern MUST come from a public source registered in `docs/evidence/sources.md`: KiCad's `~<file name>.lck`.

#### Scenario: A board open in KiCad
- **GIVEN** an authored project with KiCad's lock file beside its board
- **WHEN** `uv run pytest tests/unit/safety/test_sessions.py -k open` plans a write of that board
- **THEN** the reply holds one `safety.open-session` naming the board and the lock file

### Requirement: Online-only files
A file that a sync client keeps only online SHALL be recognised by the attributes its operating system documents, never by reading it, and `snapshot`, `publish` and `refs` SHALL stop before any read with `FEN-3007` (exit 3, retryable).

#### Scenario: A file kept only online
- **GIVEN** a `stat` result with `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS`, or with `SF_DATALESS`
- **WHEN** `uv run pytest tests/unit/safety/test_placeholders.py tests/unit/safety/test_snapshot.py -k online` runs
- **THEN** the file is online-only, and a snapshot of a project that holds it exits 3 with `FEN-3007`

### Requirement: Project references
`fenolite refs PATH [--repoint OLD=NEW]` SHALL list the paths that a project's documents hold, each with its document and whether it resolves inside the project, and with `--repoint` SHALL rewrite those that start with `OLD`, in KiCad documents, under the mutation protocol.
- A path outside the project MUST be `refs.outside` (warning); a path of an Altium project to repoint MUST be `refs.not-writable` (warning) and left as it is.

#### Scenario: A copied project still points at the old folder
- **GIVEN** an authored KiCad project copied to a new folder whose library table names a folder of the old place
- **WHEN** `uv run pytest tests/unit/safety/test_refs.py -k copied` runs `fenolite refs <copy>` and then `--repoint <old>=<copy> --confirm`
- **THEN** the first reply holds `refs.outside`, and after the rewrite the table names the copy and no issue remains
