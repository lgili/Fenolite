## ADDED Requirements

### Requirement: Starter library in the core
`fenolite.blocks` SHALL be the starter library: blocks of the namespace `Fenolite`, licensed Apache-2.0, released with Fenolite, importing only `fenolite.dsl`, `fenolite.model` and `core`, and no third-party module. A block that needs a device outside the shipped catalog MUST NOT be added to it.

#### Scenario: Starter block uses a library device
- **GIVEN** a block under `src/fenolite/blocks/` whose part names a device of the `FenoliteDevices` namespace
- **WHEN** `uv run pytest tests/unit/blocks/test_records.py -k shipped_devices` runs
- **THEN** it fails naming the block and the device

### Requirement: Library block items
A `block` item of `fenolite-library` SHALL be one Python package folder holding one `BlockDef` in `__all__`, its record file `block.json` and `"executes": true` in `item.json`. `fenolite get block ID` SHALL vendor it into `fenolite_library/blocks/<Namespace>/<name>/` beside the script and write no `__init__.py` above it, so the script imports `fenolite_library.blocks.<Namespace>.<name>`.

#### Scenario: Vendored block imported by the script
- **GIVEN** the release fixture with the block item `Demo:led` and a project script importing `fenolite_library.blocks.Demo.led`
- **WHEN** `fenolite get block Demo:led --from <release> --confirm` runs and then `fenolite build design.py --dry-run --json`
- **THEN** the build succeeds with one instance of `Demo:led` and no `__init__.py` exists in `fenolite_library/` or `fenolite_library/blocks/`

### Requirement: Block record file
A block item SHALL hold `block.json` of schema `fenolite.block-item.v0` with `id`, `version`, `namespace`, `fenolite` and the c0268 record of its block, as canonical JSON. The record's namespace, id and version MUST equal the file's and the item's, else `FEN-3004`.

#### Scenario: Record file of a test item
- **WHEN** `fenolite blocks index tests/data/library/demo/blocks/apache/Demo/led --out O/block.json --confirm --json` runs
- **THEN** the file holds the id `Demo:led`, the namespace `Demo` and its record, and a second run plans nothing

### Requirement: Discovery without import
`find_vendored(script_dir)` SHALL find vendored blocks by listing `fenolite_library/blocks/*/*/block.json` and reading each with `json`, and return id, version, namespace, module, root, record and digest. It MUST NOT import any module. A folder without a readable `block.json` MUST give `blocks.item-broken` (warning). `blocks list`, `show` and `doc` SHALL accept `--script FILE`.

#### Scenario: Listed without import
- **GIVEN** a project with the vendored block `Demo:led`
- **WHEN** `fenolite blocks list --script design.py --json` runs
- **THEN** `result.blocks` holds `Demo:led` with source `library` and its item version, and `sys.modules` of that process holds no `fenolite_library` module

### Requirement: Library block namespaces
A vendored block item in the namespace `Fenolite` SHALL give `blocks.namespace-reserved` (error); the catalog MUST NOT list it, and a build that imports it MUST fail with that issue. One id from a vendored item and a project block SHALL give c0268's `blocks.duplicate-id`.

#### Scenario: Reserved namespace in a vendored folder
- **GIVEN** a vendored folder `fenolite_library/blocks/Fenolite/x/` with a valid `block.json` for `Fenolite:x`
- **WHEN** `fenolite blocks list --script design.py --json` runs
- **THEN** it exits 5 with `blocks.namespace-reserved` naming the folder, and `Fenolite:x` is not listed from it

### Requirement: Record file matches the vendored block
A build that uses a vendored block SHALL compare the record digest computed by `describe` with its `block.json`, and SHALL give `blocks.index-stale` (warning) naming the folder and the id when they differ. `fenolite blocks index ... --check` SHALL exit 5 with `blocks.index-stale` on any difference from the committed file and write nothing.

#### Scenario: Locally edited vendored block
- **GIVEN** the vendored `Demo:led` whose code gained a parameter after the copy while its `block.json` did not
- **WHEN** a design using `Demo:led` is built
- **THEN** the build succeeds and `issues` hold `blocks.index-stale` naming the folder and `Demo:led`
