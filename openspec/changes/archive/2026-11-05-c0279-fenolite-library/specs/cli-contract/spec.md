## ADDED Requirements

### Requirement: Get command
`fenolite get KIND ID [--version V] [--release R] [--script FILE] [--into DIR]` SHALL be mutating. It SHALL plan the item and its `depends` closure, copied with `item.json`, `LICENSE`, `NOTICE` and `PROVENANCE.json` into `fenolite_library/<kind folder>/<id path>/` beside the script (a board into `--into`), plus `fenolite_library/ATTRIBUTION.md` and the lock. All of it is written or none. KIND MUST be `symbol`, `footprint`, `device`, `block` or `board`.

#### Scenario: Plan a device with its closure
- **GIVEN** a local release built from `tests/data/library_repo/demo/`, given with `--from`, and a project with `design.py`
- **WHEN** `fenolite get device Demo:EXB --from <release> --dry-run --json` runs
- **THEN** the plan lists the device, symbol and footprint folders, `fenolite_library/ATTRIBUTION.md` and `design.lock`, and nothing is written

#### Scenario: Confirmed copy keeps the licence files
- **WHEN** the same command is confirmed with its plan id
- **THEN** each copied folder holds its `LICENSE`, `NOTICE` and `PROVENANCE.json` byte for byte, and the receipt lists every file with its SHA-256

### Requirement: Licence shown and accepted
Every `get` result SHALL list, per item, `spdx`, `family`, `reciprocal`, `obligations`, `authors`, `upstream` and `executes`, and `result.licences` SHALL list each distinct id with `accept_required`. A confirm of a plan holding any id other than `CC0-1.0` MUST name each such id in `--accept-licence`, else exit 4 with `FEN-4003` listing the missing ids, writing nothing.

#### Scenario: Share-alike item needs acceptance
- **GIVEN** the release fixture with a `CC-BY-SA-4.0` footprint
- **WHEN** `fenolite get footprint Demo:SA_PAD --from <release> --confirm --json` runs
- **THEN** it exits 4 with `FEN-4003` naming `CC-BY-SA-4.0`, and nothing is written

#### Scenario: Accepted by name
- **WHEN** the same command runs with `--accept-licence CC-BY-SA-4.0`
- **THEN** it writes the item and the receipt echoes `CC-BY-SA-4.0` as accepted

### Requirement: Client licence check
`get` SHALL refuse with exit 3 and `FEN-3021` an item whose SPDX id is not in the shipped `library-licences.toml`, whose index row and `PROVENANCE.json` disagree on the id, or that lacks `LICENSE` or `NOTICE`. Nothing MUST be written.

#### Scenario: Release with a denied item
- **GIVEN** a test release whose index row says `CC-BY-NC-4.0` for `Demo:NC`
- **WHEN** `fenolite get device Demo:NC --from <release> --dry-run --json` runs
- **THEN** it exits 3 with `FEN-3021` naming the item and the id

### Requirement: Get updates and removals
A `get` of a vendored item at another version SHALL replace its folder and report `before` and `after`. `--remove KIND ID` SHALL plan the folder's deletion, the lock entry's removal and the attribution file. A folder whose tree differs from its pin MUST be refused with `FEN-7001` (`library.item-modified`) unless `--allow-lossy`; removing an item another depends on MUST exit 2.

#### Scenario: Local edit protected
- **GIVEN** the vendored `Demo:EXB` with one record edited after the copy
- **WHEN** `fenolite get device Demo:EXB --version 1.1.0 --from <release> --confirm --json` runs
- **THEN** it exits 7 with `FEN-7001`, `issues` holds `library.item-modified`, and nothing is written

### Requirement: Get closure conflicts
When the closure of a requested item needs a version of an item that the project already vendors at another version, `get` SHALL report `library.depends-conflict` (error) naming both versions, exit 5, and plan nothing.

#### Scenario: Conflicting dependency
- **GIVEN** a project vendoring `footprint/Demo:SOT` 1.0.0 and a device whose `depends` names 1.1.0
- **WHEN** the device is planned
- **THEN** it exits 5 with `library.depends-conflict` naming 1.0.0 and 1.1.0

### Requirement: Get restore and status
`fenolite get --locked SCRIPT` SHALL plan every lock entry whose folder is missing, from its pinned release, index digest and tree, and nothing else. `fenolite get --status [--script FILE]` SHALL be read-only and report per entry `present`, `modified` and `newer`, exiting 5 with `library.item-missing` when a folder is missing.

#### Scenario: Restore after a fresh clone
- **GIVEN** a project whose lock pins `device/Demo:EXB` and whose `fenolite_library/` folder was deleted, with the release cached
- **WHEN** `fenolite get --locked design.py --offline --confirm --json` runs
- **THEN** the folder is restored with the pinned tree and the lock is unchanged

### Requirement: Get list and search
`fenolite get --list [--kind K] [--release R]` and `fenolite get --search TEXT [--kind K] [--licence ID|FAMILY] [--limit N]` SHALL be read-only, open no connection and read only a cached index. Rows SHALL hold kind, id, version, title, SPDX, family, authors and gallery page, sorted by kind and id; without a cached index they MUST exit 6 with `FEN-6006`, hinting `fenolite get --refresh --dry-run`.

#### Scenario: Search the cached index
- **GIVEN** the release fixture's index cached under `FENOLITE_LIBRARY_DIR` and `urllib.request.urlopen` patched to raise
- **WHEN** `fenolite get --search exb --licence cc0 --json` runs
- **THEN** it exits 0 and lists `device` `Demo:EXB` with `CC0-1.0`, and no connection was opened

#### Scenario: Nothing cached
- **GIVEN** an empty `FENOLITE_LIBRARY_DIR`
- **WHEN** `fenolite get --list --json` runs
- **THEN** it exits 6 with `FEN-6006` whose hint names `fenolite get --refresh --dry-run`

### Requirement: Get network and cache rules
`get` SHALL download only under `--confirm`, one `https` request per missing asset, with only a `User-Agent` header, a 60 s timeout, `https`-only redirects, at most the expected bytes plus one and no retry (`FEN-6003` on failure). It checks the index against `cli/data/library.toml`, `--index-sha256` or the lock, then archives and trees (`FEN-3006`). `--offline` MUST open no connection (`FEN-6006` when missing).

#### Scenario: Dry run makes no request
- **GIVEN** `urllib.request.urlopen` patched to raise and an empty cache
- **WHEN** `fenolite get device Demo:EXB --release 1.0.0 --index-sha256 <hex> --dry-run --json` runs
- **THEN** it exits 0, the plan lists the cache writes with their sizes and digests, and no connection was opened

#### Scenario: Tampered archive
- **GIVEN** a release folder whose devices shard differs from the index's digest
- **WHEN** `get` is confirmed with `--from` that folder
- **THEN** it exits 3 with `FEN-3006` holding both digests, and neither the cache nor the project changes

### Requirement: Library tooling verbs
`fenolite library` SHALL accept the verbs `audit ROOT` (read-only), `replay ITEM` (read-only for the tree), `release ROOT --version V --out DIR` and `gallery ROOT --release DIR --out DIR` (both mutating, under plan and confirm). `capabilities` SHALL list each as `library <verb>` with its arguments. A board path named like a verb MUST be written with `./`.

#### Scenario: Verbs listed
- **WHEN** `fenolite capabilities --json` runs
- **THEN** its commands hold `get`, `library audit`, `library replay`, `library release` and `library gallery` with their arguments

### Requirement: Library error codes
The registry of `fenolite.cli.errors` SHALL hold `FEN-6004` (exit 6, not retryable, a pinned library item is missing, hint naming `fenolite get --locked`), `FEN-6006` (exit 6, not retryable, not in the offline cache), `FEN-4003` (exit 4, licences must be accepted by name) and `FEN-3021` (exit 3, licence not allowed or licence files missing). `docs/cli-contract.md` and `explain.toml` MUST list them.

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/cli/test_exitcodes.py tests/unit/cli/test_explain_cmd.py` runs
- **THEN** the four codes are registered with their exits and explained, and `FEN-6004`'s fix names `fenolite get --locked`
