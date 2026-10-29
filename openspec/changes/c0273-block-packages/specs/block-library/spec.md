## ADDED Requirements

### Requirement: Starter library in the core
`fenolite.blocks` SHALL be the starter library: blocks of the namespace `Fenolite`, licensed Apache-2.0, released with Fenolite, importing only `fenolite.dsl`, `fenolite.model` and `core`, and no third-party module. A block that needs a device outside the shipped catalog MUST NOT be added to it.

#### Scenario: Starter block uses a pack device
- **GIVEN** a block under `src/fenolite/blocks/` whose part names a device of a c0266 pack namespace
- **WHEN** `uv run pytest tests/unit/blocks/test_records.py -k shipped_devices` runs
- **THEN** it fails naming the block and the device

### Requirement: Block package entry points
A block package SHALL declare one entry point per namespace in the group `fenolite.blocks`, named by the namespace and valued by a top-level package name with no dot and no attribute. A value with a dot or an attribute MUST give `blocks.package-broken` (warning) naming the distribution, and the entry point is ignored.

#### Scenario: Dotted value ignored
- **GIVEN** a test distribution whose entry point is `Acme = "acme.blocks"`
- **WHEN** `find_packages()` runs
- **THEN** it returns no package for `Acme` and gives `blocks.package-broken` naming the distribution

### Requirement: Block package index
A block package SHALL ship `fenolite-blocks-index.json` in its package folder, of schema `fenolite.block-index.v0`, holding `distribution`, `version`, `namespace`, `fenolite` and the c0268 records of its blocks sorted by id, as canonical JSON. Every record's namespace MUST equal the index's namespace, else `FEN-3004`.

#### Scenario: Index of the test distribution
- **WHEN** `fenolite blocks index tests/data/blocks/pkg/acme_blocks --out I/fenolite-blocks-index.json --confirm --json` runs
- **THEN** the file holds the namespace `Acme` and the records `Acme:led` and `Acme:pullup`, and a second run plans nothing

### Requirement: Discovery without import
`find_packages()` SHALL find block packages through `importlib.metadata.entry_points(group="fenolite.blocks")` and `importlib.util.find_spec` of each value, read each index with `json`, and return distribution, version, namespace, module, root, index and the index's SHA-256. It MUST NOT import any module of a package. A package without a readable index MUST give `blocks.package-broken`.

#### Scenario: Listed without import
- **GIVEN** the test distribution `acme-blocks` installed into a temporary environment
- **WHEN** `fenolite blocks list --json` runs there
- **THEN** `result.blocks` holds `Acme:led` and `Acme:pullup` with source `package`, and `sys.modules` of that process holds no module of `acme_blocks`

### Requirement: Block package namespaces
An entry point named `Fenolite` SHALL give `blocks.namespace-reserved` (error) and its package MUST be ignored. Two distributions with one namespace SHALL give `blocks.namespace-conflict` (error) naming both; the catalog MUST list neither, and a build that uses a block of that namespace MUST fail with that issue.

#### Scenario: Two distributions, one namespace
- **GIVEN** two test distributions that both declare the entry point `Acme`
- **WHEN** `fenolite blocks list --json` runs
- **THEN** it exits 5 with `blocks.namespace-conflict` naming both distributions, and no `Acme:` block is listed

### Requirement: Index matches the installed blocks
A build that uses a block of a package SHALL compare its id, version and record digest with the package index, and SHALL give `blocks.index-stale` (warning) naming the package and the id when they differ. `fenolite blocks index ... --check` SHALL exit 5 with `blocks.index-stale` on any difference from the committed file and write nothing.

#### Scenario: Stale index in a build
- **GIVEN** the test distribution whose `Acme:led` code gained a parameter while its index did not
- **WHEN** a design using `Acme:led` is built
- **THEN** the build succeeds and `issues` hold `blocks.index-stale` naming `acme-blocks` and `Acme:led`
