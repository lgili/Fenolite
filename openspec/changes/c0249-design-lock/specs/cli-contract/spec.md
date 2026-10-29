## ADDED Requirements

### Requirement: Frozen builds
`fenolite build ... --frozen` SHALL compute the design lock and compare its entries in every section with the lock read, a missing file counting as empty. Any change of entries MUST refuse the build with exit 7 and `FEN-7004`, one `lock.changed` (error) issue per change in the envelope ("Refusals carry their issues") and no write planned, also under `--dry-run`. A difference of formatting only is not a change, and a frozen build never writes the lock.

#### Scenario: Frozen build with a new part
- **GIVEN** `examples/lock/design.py` with its committed `design.lock`, and a copy of the script that adds one unnamed part
- **WHEN** `fenolite build <copy> --out B --frozen --dry-run --json` runs
- **THEN** the exit code is 7, stderr carries `FEN-7004`, the envelope's `issues` hold one `lock.changed` naming the new part's path and the reason `assigned`, and nothing is written

#### Scenario: Frozen build unchanged
- **WHEN** `fenolite build examples/lock/design.py --out B --frozen --confirm --json` runs with its committed lock
- **THEN** the exit code is 0, `result.lock.frozen` is `true`, and the receipt does not list the lock

#### Scenario: Missing lock under --frozen
- **GIVEN** a copy of `examples/lock/design.py` without `design.lock`
- **WHEN** it is built with `--frozen --dry-run`
- **THEN** the exit code is 7 and stderr carries `FEN-7004`

### Requirement: Frozen error code
The registry in `src/fenolite/cli/errors.py` SHALL contain `FEN-7004`, with exit code 7, the message "the design lock would change under --frozen; nothing was written", the hint "build without --frozen, review result.lock.changes, commit the lock, then build frozen", and `retryable` false. `explain.toml` and the codes table of `docs/cli-contract.md` MUST list it.

#### Scenario: Code explained
- **WHEN** `fenolite explain FEN-7004 --json` runs
- **THEN** the exit code is 0, and `result` holds exit code 7 and the hint naming `--frozen`

### Requirement: Lock option of the build command
`fenolite build` SHALL accept `--lock FILE`, which names the design lock in place of `<script stem>.lock` beside the script. A relative `FILE` is resolved against the working directory, and `result.lock.file` MUST show it relative to the script folder when it is inside that folder, and otherwise by its file name only. These options are added under `design-dsl`, "Build command".

#### Scenario: Lock elsewhere
- **WHEN** `fenolite build examples/lock/design.py --out B --lock B/release.lock --confirm --json` runs
- **THEN** `receipt.written` lists `B/release.lock`, and no `design.lock` is created beside the script
