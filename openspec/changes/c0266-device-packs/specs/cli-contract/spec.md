## ADDED Requirements

### Requirement: Library verbs
`fenolite library` SHALL treat a first positional `fetch`, `packs`, `seed`, `check`, `review`, `import` or `propose` as a verb, and any other first positional as the board path of `library PATH --out|--diff`. `capabilities` SHALL list each implemented verb as the command `library <verb>` with its arguments. A path named like a verb MUST be written with a leading `./`.

#### Scenario: Board path form unchanged
- **WHEN** `fenolite library examples/<board> --out lib.pretty --dry-run --json` runs
- **THEN** the result is the c0223 result as on 0.6.0

#### Scenario: Verbs are listed
- **WHEN** `fenolite capabilities --json` runs
- **THEN** its commands hold `library fetch`, `library packs` and `library seed` with their arguments

### Requirement: Library fetch command
`fenolite library fetch [VERSION] [--locked SCRIPT] [--pin SCRIPT] [--from FILE] [--sha256 HEX]` SHALL be mutating and SHALL plan one folder `<packs dir>/<name>/<version>/` (kind `device-pack`), and with `--pin` the lock write, all or nothing. Bytes MUST match a row of `cli/data/packs.toml`, the `--sha256` given, or the locked tree digest; else `FEN-3006` and nothing is written.

#### Scenario: Dry run makes no request
- **GIVEN** `urllib.request.urlopen` patched to raise and an empty `FENOLITE_PACKS_DIR`
- **WHEN** `fenolite library fetch --dry-run --json` runs
- **THEN** it exits 0, the plan lists the newest row's folder with its size and digest, and no connection was opened

#### Scenario: Install from a file and pin
- **GIVEN** the demo archive, a test row with its digest and tree, and a design using a demo record
- **WHEN** `fenolite library fetch 1.0.0 --from demo.tar.gz --pin design.py --confirm --json` runs
- **THEN** the cache holds the unpacked tree with its stamp, the lock pins 1.0.0 with that tree, and the receipt lists both

#### Scenario: Tampered archive
- **GIVEN** an archive whose bytes differ from the row's digest
- **WHEN** it is fetched with `--from` and `--confirm`
- **THEN** it exits 3 with `FEN-3006` holding both digests, and the cache is unchanged

### Requirement: Library fetch network rules
With `--confirm` and without `--from`, `library fetch` SHALL make one `https` request to the row's address (or the table's `url_template` for a locked version), with only a `User-Agent: fenolite/<version>` header, a 60 s timeout, `https`-only redirects, at most `bytes + 1` bytes and no retry; a failure MUST exit 6 with `FEN-6003`. Extraction MUST use the `data` filter and require one top-level folder.

#### Scenario: Unsafe member refused
- **GIVEN** an archive with the member `../outside.toml` and a matching test row
- **WHEN** it is fetched with `--from` and `--confirm`
- **THEN** it exits 3, no `outside.toml` exists, and the cache is unchanged

### Requirement: Library packs command
`fenolite library packs [--pack DIR] [--script FILE] [--verify]` SHALL be read-only and offline, and SHALL list every pack found with `name`, `version`, `source`, `tree`, record counts, `requires` and `compatible`; with `--script`, the lock's pin and whether a source satisfies it. With `--verify`, a cached tree whose digest differs from its stamp MUST exit 5 with `library.pack-tree-differs`.

#### Scenario: Verify finds an edit
- **GIVEN** a cached demo pack with one record edited after the fetch
- **WHEN** `fenolite library packs --verify --json` runs
- **THEN** it exits 5 and `issues` holds `library.pack-tree-differs` naming the folder

### Requirement: Library seed command
`fenolite library seed --from-librepcb DIR --commit SHA --library NAME --into DIR [--namespace NS]` SHALL be mutating, write one record file per converted element under `--into` all or nothing, and report `result.records` (id, kind, origin element) and `result.skipped`. When `DIR/.git` exists its `HEAD` commit MUST equal `--commit`, else exit 3 with `FEN-3004`.

#### Scenario: Commit mismatch
- **GIVEN** a fixture checkout whose `.git/HEAD` names another commit
- **WHEN** the seed runs with `--commit` of 40 zeros
- **THEN** it exits 3 with `FEN-3004` naming the commit, and plans nothing

### Requirement: Pack error code
The registry of `fenolite.cli.errors` SHALL hold `FEN-6004` (exit 6, `retryable: false`, "a device pack pinned by the design lock is not available"), whose hint names `fenolite library fetch`. `docs/cli-contract.md` and `explain.toml` MUST list it.

#### Scenario: Code registered and explained
- **WHEN** `uv run pytest tests/unit/cli/test_exitcodes.py tests/unit/cli/test_explain_cmd.py` runs
- **THEN** `FEN-6004` is registered with exit 6 and explained with a fix naming `library fetch`
