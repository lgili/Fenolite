# file-safety Specification

## Purpose
How Fenolite works on files that someone else owns (change c0201): a copy of a project that no save interrupted, the return of an edited copy guarded by the hashes of a receipt, the warning for a file open in a CAD tool, the refusal to read a file a sync client keeps only online, and the paths a project's documents hold. The user guide is `docs/file-safety.md`.
## Requirements
### Requirement: Stable snapshot
`fenolite snapshot PATH --out DIR` SHALL copy a design file with its companions, or every project file of a folder, and SHALL accept the candidate copy only when a validation pass observes that the SHA-256 of every requested file equals the hash of the bytes held for that file.
- Every validation pass MUST cover the complete requested file set, including files that did not change in an earlier pass. The first pass follows the initial reads, and each later pass follows the reads of all files changed in the preceding pass.
- A file whose observed hash changed MUST be read again within at most three retry rounds after the initial round. `retries` MUST count the additional file-content reads, not hash checks. If a validation pass at the end of that budget still finds mismatches, every such path MUST be reported with `safety.unstable` (error), and nothing MUST be written, even when a path first changed during that final round.
- `DIR/snapshot.json` (schema `fenolite.snapshot.v0`) MUST list every copied file with the SHA-256 of its copied bytes.
- This observation MUST NOT be presented as an atomic filesystem snapshot or a source lock. The guarantee covers the requested paths and the hashes observed in validation; it cannot detect arbitrary saves after a file's last hash check, bytes changed and restored between checks, or new files outside the requested set.
- Public help, the generated agent guide, CLI contract, issue explanation and supporting hypothesis MUST describe this observed-hash guarantee consistently. They MUST NOT claim that acceptance proves one project-wide instant or no intervening save, or that every unstable file was read four times.

#### Scenario: A file saved during the copy
- **GIVEN** an authored project and a hook that saves its board once after its first read
- **WHEN** `uv run pytest tests/unit/safety/test_snapshot.py -k saved` reads the companions of the board
- **THEN** the copy holds the saved content of the board, and one retry is counted

#### Scenario: A previously settled file changes during another file's retry
- **GIVEN** two authored files A and B, B changes during the initial round, and A changes while B is read again
- **WHEN** the complete-set validation runs after that retry
- **THEN** it detects A's new hash, rereads A within the remaining budget, and accepts only the bytes validated by a pass over both files

#### Scenario: A new mismatch exhausts the shared retry budget
- **GIVEN** successive saves keep B changing until the final allowed read round, which changes only A after A passed earlier validation
- **WHEN** the final complete-set pass runs
- **THEN** it names A as unstable, counts only the additional reads actually performed, and the snapshot command writes no files or manifest

#### Scenario: The source has no concurrent save
- **GIVEN** an empty requested set or authored files whose bytes do not change
- **WHEN** the initial read and complete-set validation finish
- **THEN** the result reports no unstable path and zero retries; each copied file and manifest row hold matching hashes

#### Scenario: An engineer interprets a snapshot result
- **WHEN** the engineer reads the command help, CLI contract, supporting hypothesis or explanation of safety.unstable
- **THEN** these describe checks of observed hashes and a shared retry budget without promising an atomic project save or four reads of each unstable file

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
