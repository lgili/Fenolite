# block-library Specification

## Purpose
TBD - created by archiving change c0268-block-records. Update Purpose after archive.
## Requirements
### Requirement: Block record fields
A block decorated with `id` SHALL have a record: `id` (`<namespace>:<name>`, each part `[A-Za-z0-9_.+-]+`), `version` (`MAJOR.MINOR.PATCH`), `summary` (one line, at most 120 characters), `category`, `licence` (SPDX), `evidence` (a label of the evidence vocabulary), `sources`, and optionally `replaces` and `deprecated` (`by`, `since`, `reason`). A bad value MUST raise `DslError` at decoration naming the block and the keyword.

#### Scenario: Version form
- **WHEN** `@block(id="Acme:div", version="1.0", summary="d", licence="MIT")` decorates a block
- **THEN** `DslError` is raised naming `version` and the form `MAJOR.MINOR.PATCH`

#### Scenario: Id without version
- **WHEN** `@block(id="Acme:div")` decorates a block
- **THEN** `DslError` is raised saying that `id` and `version` go together

### Requirement: Block categories
`category` SHALL be one of `analog`, `power`, `protection`, `interface`, `indicator`, `timing`, `connector` and `other`, and SHALL default to `other`. Any other text MUST raise `DslError` at decoration, listing the set.

#### Scenario: Unknown category
- **WHEN** a block is decorated with `category="sensors"`
- **THEN** `DslError` is raised listing the eight categories

### Requirement: Reserved block namespace
The namespace `Fenolite` SHALL be reserved for blocks defined in modules under `fenolite.blocks`. Decorating a block with a `Fenolite:` id in any other module MUST raise `DslError`. A `Fenolite:` block MUST have `licence` `Apache-2.0` and at least one source, and each of its sources MUST be an `S-` id of `docs/evidence/sources.md`, which a test checks.

#### Scenario: Reserved namespace in a project
- **WHEN** a project module decorates a block with `id="Fenolite:mine"`
- **THEN** `DslError` is raised naming the namespace `Fenolite`

#### Scenario: Unregistered source of a shipped block
- **GIVEN** a shipped block whose `sources` hold an `S-` id that `docs/evidence/sources.md` lacks
- **WHEN** `uv run pytest tests/unit/blocks/test_records.py -k sources` runs
- **THEN** it fails naming the block and the id

### Requirement: Describing a block
`fenolite.dsl.describe(block_def) -> BlockRecord` SHALL return the header and parameters from the decorator. It SHALL also return the ports, local parts, local nets, nested blocks and `requires` (device ids, lib ids, c0254 query texts), read by using the block once with its defaults in a detached design. It MUST read no file, library or lock, MUST run no tool and MUST NOT convert the design to a model.

#### Scenario: Ports from defaults
- **GIVEN** the authored block `tests/data/blocks/divider.py` with the ports `HI`, `OUT` and `LO` and two local parts
- **WHEN** `describe` runs on it
- **THEN** the record lists the three ports with their kinds, directions and docs, and the parts `bot` and `top`

#### Scenario: Hermetic describe
- **GIVEN** `open`, `subprocess.run` and the catalog loader patched to raise
- **WHEN** `describe` runs on the authored divider
- **THEN** it returns the record

### Requirement: Blocks that cannot be elaborated
When a block has a required parameter, its record SHALL list the parameters and give `null` for `ports`, `parts`, `nets`, `blocks` and `requires`, with `elaboration` naming the parameter. When the block function raises, `describe` SHALL return the record with `elaboration.error` holding the exception class and message instead of raising.

#### Scenario: Required parameter
- **GIVEN** a block whose parameter `vout` has no default
- **WHEN** `describe` runs
- **THEN** `ports` is `null` and `elaboration` names `vout`

### Requirement: Canonical block record
`record_json(record)` SHALL write the record as canonical JSON of schema `fenolite.block.v0`, with keys sorted, lists sorted by name, values as c0251's canonical texts and no float, so that equal records give equal bytes. The record SHALL carry `digests`: `interface` (ports and parameter names, types, units), `definition` (also defaults, limits, parts, nets, blocks and requires) and `record` (all but `digests`).

#### Scenario: Doc change keeps the definition
- **GIVEN** the authored divider and a copy whose port `HI` has another `doc`
- **WHEN** both are described
- **THEN** their `record` digests differ and their `definition` and `interface` digests are equal

#### Scenario: Stable bytes
- **WHEN** `record_json(describe(divider))` is computed in two processes with different `PYTHONHASHSEED`
- **THEN** the texts are byte-identical

### Requirement: Shipped block versions
`src/fenolite/blocks/VERSIONS.toml` SHALL hold, per shipped id, `version` and the three digests, and `removed = true` for a removed id. The version test SHALL require PATCH or more for a changed record digest and MINOR or more for a changed definition digest. It SHALL refuse a changed interface digest under an id, and the reuse of a removed id.

#### Scenario: Port renamed under an id
- **GIVEN** a shipped block whose port `OUT` is renamed `VOUT` while its id stays
- **WHEN** `uv run pytest tests/unit/blocks/test_versions.py` runs
- **THEN** it fails naming the id and saying that an interface change needs a new id with `replaces`

#### Scenario: Default changed without a minor step
- **GIVEN** a shipped block whose parameter default changed and whose version rose only in PATCH
- **WHEN** the version test runs
- **THEN** it fails naming the id and asking for a MINOR version

### Requirement: Replacements of blocks
A record with `replaces = X` SHALL be accepted by the catalog only when block `X`, if it is in the same catalog, holds `deprecated.by` naming that record's id. Otherwise `blocks show` and the version test MUST report the mismatch, naming both ids.

#### Scenario: Replacement without deprecation
- **GIVEN** authored blocks `Acme:div2` with `replaces = "Acme:div"` and `Acme:div` without `deprecated`
- **WHEN** `fenolite blocks show Acme:div2 --from tests/data/blocks/replace.py --json` runs
- **THEN** it exits 3 with `FEN-3004` naming `Acme:div` and `Acme:div2`

### Requirement: Generated block pages
`fenolite.dsl.record.page(record) -> str` SHALL give a Markdown page with LF line ends and no date. The page SHALL hold the id and version as title, the summary, a table of category, licence and evidence, and tables of parameters (name, type, unit, default, allowed, doc) and ports (name, kind, direction, optional, doc). It SHALL also hold the requirements and the sources. Equal records MUST give equal pages.

#### Scenario: Page of the authored divider
- **WHEN** `page(describe(divider))` is computed
- **THEN** it starts with `# Acme:divider 1.0.0`, holds a parameter row for `current` with the allowed text `1uA to 10mA`, and a port row for `HI`

### Requirement: Shipped block pages are current
`tools/gen_block_docs.py` SHALL write `docs/blocks/<name>.md` for each shipped block and `docs/blocks/index.md`, adding each source's title from `docs/evidence/sources.md`. With `--check` it SHALL fail on any difference from the committed pages, and the consistency tests SHALL run it.

#### Scenario: Stale page
- **GIVEN** a shipped block whose summary changed and whose page was not regenerated
- **WHEN** `uv run pytest tests/consistency -k block_docs` runs
- **THEN** it fails naming `docs/blocks/<name>.md`

### Requirement: Catalog sources of blocks
`find_blocks(*, files=())` SHALL return one entry per block with its record, its source (`builtin` for `fenolite.blocks` and its modules' `__all__`, `file` for each `--from` file imported by path) and its module name. Two entries with one id SHALL give `blocks.duplicate-id` (error) naming both sources.

#### Scenario: Shipped and file blocks
- **WHEN** `find_blocks(files=["tests/data/blocks/divider.py"])` runs
- **THEN** it returns every shipped block with source `builtin` and `Acme:divider` with source `file`

#### Scenario: Import of the shipped blocks is clean
- **WHEN** `uv run pytest tests/unit/blocks/test_import_side_effects.py` imports `fenolite.blocks` and its modules in a fresh process
- **THEN** no design is created, no file is opened and no third-party module is imported

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
- **WHEN** `fenolite blocks index tests/data/library_repo/block_items/blocks/cc0/Demo/led --out O/block.json --confirm --json` runs
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

