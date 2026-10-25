## ADDED Requirements

### Requirement: Stable snapshot
`fenolite snapshot PATH --out DIR` SHALL copy a board or a project with its companion files (project, rules, library tables, sheets, and the libraries the project names inside its folder), and SHALL accept the copy only when the SHA-256 of every source file is the same before and after the copy.
- A file whose hash changes during the copy MUST be copied again, at most three times, then reported with `safety.unstable` (exit 3), and nothing MUST be left in `DIR`.
- The reply MUST list every copied file with its hash; `DIR/snapshot.json` MUST hold the same list.

#### Scenario: A file saved during the copy
- **GIVEN** a project folder and a test hook that rewrites its board once while the snapshot copies it
- **WHEN** `uv run pytest tests/unit/safety/test_snapshot.py -k saved` takes the snapshot
- **THEN** the snapshot holds the second content of the board and its hash, and the reply notes one retry

### Requirement: Publish guarded by receipts
`fenolite publish SRC --to DST --receipt RECEIPT` SHALL be a writing command under the mutation protocol that replaces each file of `DST` with its counterpart in `SRC` only when the file's current SHA-256 equals the hash that `RECEIPT` recorded for it, the receipt of Fenolite's last write there.
- A file of `DST` whose hash differs from the receipt MUST be left as it is and reported with `safety.changed-since-receipt` (error, exit 5), and the files that were replaced MUST be named; a file that `RECEIPT` does not name and that exists in `DST` MUST be treated the same way.
- A file new to `DST` MUST be added. Every replaced file MUST be backed up as the mutation protocol does, and the new receipt MUST be written beside the old.

#### Scenario: The owner saved one file
- **GIVEN** a receipt of three files written into `DST`, and one of them changed in `DST` since
- **WHEN** `fenolite publish src --to dst --receipt dst/fenolite-receipt.json --confirm --json` runs
- **THEN** two files are replaced, the changed one is untouched, the exit code is 5 and the issues hold one `safety.changed-since-receipt` naming it

### Requirement: Open sessions and placeholders
Every writing command SHALL report `safety.open-session` (warning) when a file it would replace has a lock file of a CAD tool beside it, and SHALL report `safety.placeholder` (exit 3) before it reads a file that a sync client keeps only online.
- A lock-file pattern MUST be listed with its tool and a public source registered in `docs/evidence/sources.md`; a tool without such a source is not detected, and `docs/cli-contract.md` MUST say so.
- An online-only file MUST be recognised by the attributes that the operating system documents for it (an offline or recall-on-open attribute; a dataless flag), never by reading its content.
- `fenolite doctor --sessions PATH` MUST list the lock files and the online-only files under `PATH`, writing nothing.

#### Scenario: A board open in KiCad
- **GIVEN** a project folder with the lock file that KiCad writes beside an open board
- **WHEN** `fenolite fill <project> --dry-run --json` runs
- **THEN** the reply holds one `safety.open-session` naming the board and the lock file

### Requirement: Project references
`fenolite refs PROJECT [--repoint OLD=NEW]` SHALL list every path that the documents of a project hold (sheets, libraries, drawing documents, output jobs, as the readers give them), each with its document and whether it resolves, and with `--repoint` SHALL rewrite the paths that start with `OLD` under the mutation protocol.
- A document whose format Fenolite cannot write MUST be listed with `refs.not-writable` (warning) and left as it is.
- A path that resolves outside the project folder MUST be reported with `refs.outside` (warning).

#### Scenario: A copied project still points at the old folder
- **GIVEN** an authored KiCad project copied to a new folder whose library table holds an absolute path into the old folder
- **WHEN** `fenolite refs <copy> --json` runs
- **THEN** the reply lists that path with `refs.outside`, and `fenolite refs <copy> --repoint <old>=<copy> --confirm` rewrites it so that it resolves inside the copy

### Requirement: Gated and three-way differences
`fenolite diff A B --allow KINDS` SHALL exit 5 when the difference holds a change of a kind outside `KINDS`, naming each such change; and `fenolite diff BASE OURS --three-way THEIRS --out FILE` SHALL write `THEIRS` with the changes from `BASE` to `OURS` applied, under the mutation protocol, refusing with `diff.conflict` (exit 5, nothing written) when a changed item was also changed in `THEIRS`.
- For Altium documents, differences of bytes that decode to equal values within the format's units MUST be classified as `resave` and left out of the semantic difference.

#### Scenario: A change outside the allowed set
- **GIVEN** two boards that differ by a moved track and a changed rule
- **WHEN** `fenolite diff a.kicad_pcb b.kicad_pcb --allow track --json` runs
- **THEN** the exit code is 5 and the issues name the rule change
