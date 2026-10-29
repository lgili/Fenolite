## Why

c0268 gives blocks records, versions and a catalog, but the catalog only knows the blocks shipped inside
Fenolite and Python files named on the command line. A block library must grow beyond the core without
making the core heavier. It must not tie a block fix to a Fenolite release, and it must not let a project
build differently on another machine. The research of 2026-10-29 (`docs/research/circuit-blocks.md`, section
2 gap 6, section 3.7 and row c0273 of section 4) proposes three tiers:

- a small starter library `fenolite.blocks` in the core;
- further blocks in a separate Python package `fenolite-blocks`, which a project declares as its own
  dependency;
- a project's own blocks beside its script.

Blocks are code, so the data-only packs of c0266 cannot carry them. Discovery must find installed packages
without running their code, the lock must pin the versions that served a build, and an upgrade must be
planned and reviewed.

atopile ships blocks as versioned packages with a manifest and a registry, and Altium offers push-or-stay
updates with Where-Used. Only these concepts are taken. Fenolite uses standard Python packaging (entry
points, S-0218) and its own lock, and copies no manifest schema, registry protocol or package content.

## What Changes

- **Three tiers, one catalog.**
  - **Starter library.** `fenolite.blocks` in the core: Apache-2.0, stdlib only, namespace `Fenolite`,
    versioned with Fenolite. c0272 fills it.
  - **Block packages.** A Python distribution declares an entry point in the group `fenolite.blocks`, whose
    name is the namespace and whose value is a top-level package. It ships a generated, static index
    `fenolite-blocks-index.json` beside its code. The official package is `fenolite-blocks` (namespace
    `FenoliteBlocks`, Apache-2.0, separate repository). Other authors use the same mechanism with their own
    namespaces.
  - **Project blocks.** Plain Python modules beside the script, as in c0251 and c0268.
- **Discovery without import side effects.** `blocks list`, `show`, `doc` and `capabilities` read
  installed packages through `importlib.metadata` entry points and `importlib.util.find_spec` of a
  top-level package, and read the index file. No module of a package is imported. Only a design script that
  imports a block runs package code, as it runs any Python.
- **The index.** `fenolite blocks index PACKAGE_DIR --out FILE` describes every block of a package
  (c0268's `describe`) and writes `fenolite.block-index.v0` through plan and confirm. `--check` fails on a
  stale index, for the package's own CI.
- **Pinned in the lock.**
  - c0249's lock gains `[block-packages."<distribution>"]` with `version`, `namespace` and `index` (the
    SHA-256 of the index file). It is written only for packages that served a block instance of the build.
  - Instance versions stay in c0268's `[blocks]`, and a changed block version still stops the build
    (`lock.block-version`).
  - A changed package version whose used blocks kept their versions moves the pin with
    `lock.block-package-moved` (info). `--frozen` refuses that, as any lock change.
  - A pinned package that is not installed exits 6 with a new code, `FEN-6006`, whose hint names the
    install command.
- **`fenolite blocks upgrade SCRIPT`** runs the script as a build does, without writing outputs. It plans
  the lock rewrite that takes the installed versions, for all instances or for `--block ID` and
  `--package NAME`.
  - The plan lists each instance's version step (patch or minor), the installed record, its deprecation,
    and the build issues under the new versions.
  - With `--out DIR`, it also lists the circuit differences of each instance against the last build in
    `DIR`.
  - It writes only the lock, through plan and confirm, with a receipt. It never edits the script.
- **Namespaces.** `Fenolite` stays reserved for the core. Two distributions that claim one namespace give
  `blocks.namespace-conflict` (error). A record whose namespace differs from its entry point's name is
  refused.

## Capabilities

### New Capabilities

None. `block-library` is created by c0268.

### Modified Capabilities

- `block-library`: ADDED "Starter library in the core", "Block package entry points", "Block package
  index", "Discovery without import", "Block package namespaces", "Index matches the installed blocks".
- `design-dsl`: ADDED "Block packages in the design lock", "Missing pinned block package".
- `cli-contract`: ADDED "Blocks index command", "Blocks upgrade command", "Upgrade review content", "Block
  package error code", "Block packages in capabilities and doctor".

## Dependencies

- **c0268 block-records** (required): records, `describe`, `record_json`, digests, the catalog sources,
  the `[blocks]` section and `lock.block-version`.
- **c0249 design-lock** (required): `LockSection`, plan and confirm of the lock, `--frozen`.
- **c0266 device-packs**: the model this change follows for "pin only what is used" and for discovery
  through `importlib.metadata` without import. Packs carry data; block packages carry code.
- Independent of c0269 to c0272. c0272's blocks are the first content of the starter library.

## Non-goals

- No registry service, no download command and no package installation by Fenolite. Installing a package
  is the project's tool's job (`uv add fenolite-blocks`, `pip install`).
- No content of `fenolite-blocks` is specified here. Its first release is decided in its repository, under
  the rules of c0268 and c0272.
- No two versions of one package in one environment. Python imports one.
- No change of `pyproject.toml` `dependencies` or extras of Fenolite. The core never depends on a block
  package.

## Evidence level required

- Discovery, index, namespaces, lock pins and upgrade plans: `INFERRED`, unit-tested with a test
  distribution installed into a temporary environment, and no network (`H-G-BLOCK-PACKAGES`).

## Impact

- New:
  - `src/fenolite/cli/blockpkg.py` (entry points, `find_spec`, index reading);
  - `src/fenolite/dsl/blockindex.py` (index schema, canonical text);
  - the verbs `blocks index` and `blocks upgrade` in `cli/cmd_blocks.py`;
  - `tests/data/blocks/pkg/` (an authored test distribution, CC0) and tests under `tests/unit/cli` and
    `tests/unit/blocks`;
  - `docs/blocks.md` sections "Packages" and "Upgrading".
  - Outside this repository: the `fenolite-blocks` repository with its CI (index check, version rules,
    usage builds of c0270).
- Changed:
  - `cli/blocksrc.py` (the source `package`);
  - `dsl/lock.py` (section `block-packages`);
  - `cli/cmd_build.py` and `cli/_script.py` (package pins, `FEN-6006` mapping);
  - `cli/errors.py` and `cli/data/explain.toml`;
  - `cli/cmd_capabilities.py` and `cli/cmd_doctor.py`;
  - `docs/cli-contract.md`;
  - the guide page `commands.md`;
  - `CHANGELOG.md`.
- Size: about 4 design-days (S).
