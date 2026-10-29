## ADDED Requirements

### Requirement: Library blocks in the design lock
A build that uses a vendored library block SHALL record its instances in c0268's `[blocks]` and SHALL rely on c0279's `[library.items."block/<id>"]`, written by `fenolite get`, for the item version, release and tree digest. A build MUST NOT write any other lock section for library blocks, and blocks of the starter library or of the project get no `[library.items]` entry.

#### Scenario: Vendored block pinned twice over
- **GIVEN** a design using `Demo:led` 1.0.0 vendored by `fenolite get`, and no `[blocks]` entry yet
- **WHEN** `fenolite build design.py --dry-run --json` runs
- **THEN** the planned lock holds `"led1" = "Demo:led@1.0.0"` in `[blocks]`, keeps `[library.items."block/Demo:led"]` unchanged, and holds no `[block-packages]` section

#### Scenario: Starter blocks are not pinned as items
- **WHEN** a design that uses only `Fenolite:` blocks is built
- **THEN** its lock holds `[blocks]` entries and no `[library.items]` entry

### Requirement: Missing library block module
When a design script raises `ModuleNotFoundError` for a module under `fenolite_library.blocks.` that no lock entry pins, the build SHALL keep the script-error behaviour and its hint SHALL name `fenolite get block <Namespace>:<name> --dry-run`, derived from the module path. A pinned but missing folder SHALL be reported by c0279's check with `FEN-6004` before the script runs.

#### Scenario: Block never vendored
- **GIVEN** a script importing `fenolite_library.blocks.Demo.led` in a project without that folder and without a lock entry
- **WHEN** `fenolite build design.py --json` runs
- **THEN** it fails as a script error whose hint names `fenolite get block Demo:led --dry-run`, and no file is written
