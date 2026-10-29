## ADDED Requirements

### Requirement: Pack manifest
A device pack SHALL be a folder with `pack.toml` of schema `fenolite.pack.v0` holding `name`, `version` (semantic), `summary`, `licence`, `namespaces` and `requires` (`fenolite` version range, `schemas`), plus `sources.toml` and a c0259 record tree. `fenolite.catalog.packs.read_pack(root)` SHALL refuse with `FEN-3004` a missing or unknown key, the namespace `Fenolite`, a record outside `namespaces`, or a licence other than `CC0-1.0`.

#### Scenario: A pack is read
- **GIVEN** the authored pack `tests/data/packs/demo/` with one package, one pins and one device record
- **WHEN** `uv run pytest tests/unit/catalog/test_packs.py -k read` runs
- **THEN** `read_pack` returns its name, version, namespaces and three records

#### Scenario: Reserved namespace
- **WHEN** a pack whose `namespaces` holds `Fenolite` is read
- **THEN** `FEN-3004` is raised naming `namespaces`

### Requirement: Pack sources registry
Each record of a pack SHALL name in `sources` only ids of the pack's `sources.toml`, whose rows hold `id` (`D-` and four digits), `title`, `url`, `licence`, `retrieved` and `used`. An unregistered id MUST raise `FEN-3004` naming the record and the id.

#### Scenario: Unregistered pack source
- **WHEN** a pack record names `D-0099` and `sources.toml` lacks it
- **THEN** `FEN-3004` is raised naming the record and `D-0099`

### Requirement: Pack discovery
`find_packs(*, paths=())` SHALL find packs offline in this order: `--pack DIR` and `FENOLITE_PACKS_PATH`; the installed distribution `fenolite-devices` through `importlib.metadata`, importing none of its modules; the cache `<packs dir>/<name>/<version>/` with a valid stamp. Each pack SHALL report `name`, `version`, `source`, `root` and `tree` (`fenolite-tree-1`).

#### Scenario: Cached pack without stamp is ignored
- **GIVEN** `FENOLITE_PACKS_DIR` holding `fenolite-devices/1.4.0/` without `.fenolite-pack.toml`
- **WHEN** `find_packs()` runs
- **THEN** that folder is not returned

#### Scenario: Extra found without import
- **GIVEN** a test distribution `fenolite-devices` installed in a temporary environment
- **WHEN** `find_packs()` runs
- **THEN** the pack is returned with source `extra` and `sys.modules` holds no module of that distribution

### Requirement: Pack precedence
For each id, project records SHALL win over pack records, and pack records over the shipped catalog. One id in two packs without a project record of that id MUST give `library.pack-conflict` (error) naming both packs. A project record that overrides a pack record SHALL give `library.overrides-pack` (info).

#### Scenario: Project wins over the pack
- **GIVEN** the demo pack holding `FenoliteDevices:EXB` and a project device with the same id
- **WHEN** a design using it is built
- **THEN** the project device is used and `issues` holds `library.overrides-pack`

#### Scenario: Two packs, one id
- **GIVEN** two packs on `--pack` both holding `Shop:X`, and a design using `Shop:X`
- **WHEN** it is built
- **THEN** the build reports `library.pack-conflict` naming both packs and writes nothing

### Requirement: Packs are read lazily
A pack's records SHALL be read only when an id is looked up that neither the project nor the shipped catalog holds. A design that uses no pack record MUST build byte for byte as without packs, and MUST get no `library` lock section.

#### Scenario: Unused pack changes nothing
- **GIVEN** a design using only shipped devices, built once without packs and once with the demo pack on `--pack`
- **WHEN** both outputs and both lock files are compared
- **THEN** they are byte-identical and neither lock holds `[library]`

### Requirement: Pack pinned in the design lock
A build in which a pack served an id SHALL hold `[library."<pack>"]` with `version` and `tree` in the design lock of c0249. Without an entry, the highest available version SHALL be used and pinned (`library.pack-locked`, info). With an entry, only a pack of that version and tree MUST be used. An entry whose pack serves no id SHALL be dropped (`library.pack-released`, info).

#### Scenario: First use pins the pack
- **GIVEN** the demo pack 1.0.0 cached and a design using `FenoliteDevices:EXB` without a lock
- **WHEN** `fenolite build design.py --dry-run --json` runs
- **THEN** the plan holds the lock with `[library."fenolite-devices"]` version `1.0.0` and its tree, and `issues` holds `library.pack-locked`

#### Scenario: Newer pack does not move a lock
- **GIVEN** a lock pinning 1.0.0 and both 1.0.0 and 1.1.0 cached
- **WHEN** the design is built
- **THEN** version 1.0.0 is used and the lock is unchanged

### Requirement: Missing pinned pack
When the lock pins a pack version that no source holds with the pinned tree, the build SHALL report `library.pack-missing` (error) and exit 6 with `FEN-6004`, naming the pack and version, with a hint naming `fenolite library fetch <version> --pin <script>`. A source of that version with another tree SHALL be ignored with `library.pack-tree-differs` (warning). Nothing MUST be written.

#### Scenario: Locked pack not installed
- **GIVEN** a lock pinning `fenolite-devices` 1.0.0 and an empty packs folder
- **WHEN** `fenolite build design.py --json` runs
- **THEN** it exits 6, stderr holds `FEN-6004` whose hint names `fenolite library fetch 1.0.0 --pin design.py`, and no file is written

### Requirement: Frozen builds and packs
Under `--frozen`, any change of the `library` section (a new pin, a released pin, a version or tree change) SHALL be refused as a lock change with `FEN-7004` (c0249), listing each change.

#### Scenario: Frozen build refuses a first pin
- **GIVEN** a design that starts using a pack record and a lock without `[library]`
- **WHEN** `fenolite build design.py --frozen --json` runs
- **THEN** it exits 7 with `FEN-7004` and `issues` holds a `lock.changed` for section `library`

### Requirement: Pack compatibility
A pack whose `requires.fenolite` excludes the running version, or whose `requires.schemas` names a schema the core cannot read, SHALL give `library.pack-incompatible` (error) naming the requirement when a design uses it, and `library packs` SHALL show it as incompatible.

#### Scenario: Pack needs a newer core
- **GIVEN** a pack with `requires = { fenolite = ">=9.0.0", schemas = [] }` that serves a used id
- **WHEN** the design is built
- **THEN** the build reports `library.pack-incompatible` naming `>=9.0.0` and writes nothing

### Requirement: Builds stay offline
No build, check, capabilities, doctor or `library packs` run SHALL open a network connection or read a pack from anywhere but the sources of "Pack discovery".

#### Scenario: Build with packs and no network
- **GIVEN** `socket.socket.connect` patched to raise and the demo pack cached
- **WHEN** a design using a pack record is built
- **THEN** it succeeds and no connection was attempted

### Requirement: Data repository releases
The `fenolite-devices` repository SHALL hold only data under CC0-1.0, and each tag `v<version>` SHALL publish a byte-reproducible archive (sorted members, mtime 0, owner 0, gzip mtime 0), `SHA256SUMS`, `index.json` and a data-only wheel with no Python module. Its CI SHALL run records, regenerate, versions, origin, renders with visual diff, and a double pack build compared byte for byte.

#### Scenario: Archive is reproducible
- **GIVEN** the authored demo pack tree
- **WHEN** `uv run pytest tests/unit/catalog/test_pack_archive.py` builds its archive twice with the documented recipe
- **THEN** both archives have one SHA-256, and their unpacked tree digest equals the tree's

### Requirement: Seeded records from LibrePCB
`fenolite library seed --from-librepcb DIR --commit SHA` SHALL convert LibrePCB packages, components with symbols, devices and parts into c0259 records, each with `origin` (library, commit, element UUID), `licence = "CC0-1.0"`, `evidence = "UNVERIFIED"` and version `1.0.0`. The checkout's licence file MUST be the CC0 1.0 legal code, else `FEN-3004`. No build or check SHALL call the converter.

#### Scenario: Seed records carry their origin
- **GIVEN** the authored fixture `tests/data/librepcb/demo/` (CC0 legal code, one package, one component with a symbol, one device with two parts), written for Fenolite from the public format page
- **WHEN** `fenolite library seed --from-librepcb tests/data/librepcb/demo --commit <40 hex> --library Demo --into out --dry-run --json` runs
- **THEN** the plan lists one package, one pins and one device record, each with `origin.element` equal to its element UUID and evidence `UNVERIFIED`

#### Scenario: Not a CC0 library
- **GIVEN** the same fixture with another licence file
- **WHEN** the command runs
- **THEN** it exits 3 with `FEN-3004` naming the licence file and plans nothing

### Requirement: Seed determinism and safety
Two seed runs on the same checkout and commit SHALL give the same ids and bytes. Ids SHALL be `<namespace>:<name>` with other characters replaced by `_`; a collision SHALL append `_` and the first 8 hex digits of the element UUID (`library.seed-renamed`). An element that cannot be converted SHALL be skipped with `library.seed-skipped`. A reviewed record MUST NOT be overwritten (`FEN-7001`).

#### Scenario: Same bytes twice
- **WHEN** the seed of the fixture is confirmed into two empty folders
- **THEN** both folders have one tree digest

#### Scenario: Custom pad outline skipped
- **GIVEN** a fixture package with a custom pad outline
- **WHEN** it is seeded
- **THEN** `issues` holds `library.seed-skipped` naming the package UUID and the reason, and the device using it is skipped too

#### Scenario: Reviewed record kept
- **GIVEN** a seeded record in `--into` with a `reviewed_by` entry
- **WHEN** the seed runs again over it with `--confirm`
- **THEN** it exits 7 with `FEN-7001` naming the record and writes nothing
