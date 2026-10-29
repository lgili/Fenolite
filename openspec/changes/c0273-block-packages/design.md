## Context

- **Source.** `docs/research/circuit-blocks.md` (2026-10-29), section 2 gap 6 ("Distribution"), section 3.7
  and row c0273 of section 4, with the maintainer questions 1 (starter blocks in the core, recommended) and
  4 (upgrades never silent). Concepts only, from atopile (versioned packages with a manifest and a
  registry) and Altium (Where-Used, push-or-stay updates). Fenolite uses standard Python packaging: entry
  points and distribution metadata (`importlib.metadata`, S-0218).
- **What c0268 defines.**
  - `@block(id=, version=, ...)`, `describe(block) -> BlockRecord` and `record_json` (`fenolite.block.v0`)
    with record, definition and interface digests.
  - Catalog sources `builtin` (`fenolite.blocks`) and `file` (`--from`), the error `blocks.duplicate-id`,
    and `blocks list`, `show`, `doc` and `where`.
  - The lock section `[blocks]` (instance path → `id@version`), `lock.block-version` (error) on a version
    difference, and the reserved namespace `Fenolite`.
  - The empty package `fenolite.blocks`, which may import only `dsl`, `model` and `core`.
- **What c0266 defines** (the model followed here). Packs are found through `importlib.metadata` without
  importing code. The lock section `library` pins only packs that served a lookup. A missing pinned pack
  exits 6 with `FEN-6004`.
- **What exists on `dev` (0.6.0).** No plugin or entry-point mechanism. `pyproject.toml` has
  `dependencies = []` and closed extras. `fenolite capabilities` and `doctor` list extras and tools.

## Goals / Non-Goals

**Goals**

- Blocks can live outside the core, released on their own, under the same record and version rules.
- Listing and reading installed blocks never runs their code.
- A project builds with the block versions it locked, on any machine. A machine without the package says
  so clearly, and an upgrade is a planned, reviewed lock change.

**Non-Goals**

- See the proposal.

## Decisions

### 1. Three tiers

| tier | where | namespace | licence | versioned with | found by |
|---|---|---|---|---|---|
| starter | `fenolite.blocks` (core) | `Fenolite` | Apache-2.0 | Fenolite; each block its own version (c0268) | `builtin` source |
| package | an installed distribution | one per entry point (`FenoliteBlocks` for the official one) | the package's | the package; each block its own version | `package` source (decision 3) |
| project | modules beside the script | any but `Fenolite` | the project's | the project's git history | the script's own imports; `--from` for the catalog |

- **The starter library** is small and stays small. It holds the blocks of c0272 and later the generic
  ones that the research lists (decoupling set, reverse-polarity protection, crystal, reset, connector with
  ESD). It imports only `fenolite.dsl`, `fenolite.model` and `core`, uses no third-party module, and its
  modules have no import side effects (c0268's test). A block that needs a vendor device belongs in a
  package, not in the core.
- **The official package `fenolite-blocks`** is a separate repository under the same owner, Apache-2.0, with
  DCO sign-off as the main repository. It depends on `fenolite>=<the first release with this change>`. The
  core never depends on it. Its CI runs, on every pull request:
  - `fenolite blocks index fenolite_blocks --check`;
  - the c0268 version rules against the previous release (its own `VERSIONS.toml`);
  - c0270's usage builds and tests;
  - a source check: every record's `sources` names an id of the package's `sources.toml` (`D-` ids, as
    c0266's packs).
- **A project** declares the package in its own dependencies (`uv add fenolite-blocks`) and imports blocks
  in its script (`from fenolite_blocks.power import buck_6v`). The lock pins what was used (decision 5).

### 2. Entry points

A package declares, in its `pyproject.toml`:

```toml
[project.entry-points."fenolite.blocks"]
FenoliteBlocks = "fenolite_blocks"
```

- The entry point **name** is the namespace (c0259's name pattern) of every block of the package. The
  **value** is a top-level package name: no dot and no `:attr`.
- One distribution may declare several namespaces, one entry point each, each with its own package
  folder.
- **Alternative considered:** a manifest file found by scanning `site-packages`. Rejected: entry points are
  the standard, cheap and documented way to advertise plugins (S-0218).

### 3. Discovery without import

`fenolite.cli.blockpkg.find_packages() -> tuple[BlockPackage, ...]`:

1. `importlib.metadata.entry_points(group="fenolite.blocks")`. No `EntryPoint.load()`.
2. For each entry point, `importlib.util.find_spec(value)`. For a top-level name this locates the package
   without executing it, and works for regular and editable installs. A missing spec gives
   `blocks.package-broken` (warning) naming the distribution.
3. Read `<package folder>/fenolite-blocks-index.json` with `json.loads` and check its schema.
4. `BlockPackage(distribution, version, namespace, module, root, index, digest)`, where `version` is
   `ep.dist.version` and `digest` is `sha256:` of the index file's bytes.

A test asserts that after `find_packages()` no module of a test distribution is in `sys.modules` (the
c0266 pattern). The catalog source `package` turns each index record into a c0268 catalog entry, so `list`,
`show` and `doc` work on packages without importing them.

### 4. The index

```json
{"blocks": [<fenolite.block.v0 record>, ...], "distribution": "fenolite-blocks",
 "fenolite": ">=0.7.0", "namespace": "FenoliteBlocks", "schema": "fenolite.block-index.v0",
 "version": "1.2.0"}
```

The JSON above shows the shape.

- `fenolite blocks index PACKAGE_DIR --out FILE [--check]`:
  - it imports the package named by the folder (the author's own code, run on purpose);
  - it describes every `BlockDef` listed in the `__all__` of the package's modules;
  - it writes the records sorted by id, with `canonical.dumps`;
  - it plans one file (kind `block-index`) through the mutation protocol.
- `--check` compares with the committed file and exits 5 with `blocks.index-stale` on a difference. It
  writes nothing.
- Each record's namespace MUST equal the index's `namespace`, else `FEN-3004`. The index records which
  Fenolite version range made it (`fenolite`), copied from the distribution's requirement on `fenolite`.
- **At build time**, the build checks each used instance of a package block. Its id and version must appear
  in the package index, and the record digest that the build computes with `describe` must equal the
  indexed one. Otherwise the build gives `blocks.index-stale` (warning) naming the package and the id. The
  build still uses the code, since the index is only the catalog's view.

### 5. Package pins in the lock

```toml
[blocks]
"pwr/buck" = "FenoliteBlocks:buck_6v@1.1.0"
"sense_a" = "Fenolite:voltage_divider@1.0.0"

[block-packages."fenolite-blocks"]
index = "sha256:3f9c…"
namespace = "FenoliteBlocks"
version = "1.2.0"
```

- Registered through `LockSection("block-packages", resolve)`, written after `[blocks]`, keys sorted.
- **Which packages are pinned.** A distribution gets an entry when at least one instance of the build uses
  a block whose namespace is one of the distribution's entry points. The starter library and project blocks
  get none: the starter library is pinned by the Fenolite version, and project blocks by git.
- **Resolution**, per distribution:

  | lock entry | installed | result |
  |---|---|---|
  | none | `v`, digest `d` | entry planned; reason `package-locked` |
  | `v`, `d` | `v`, `d` | nothing |
  | `v`, `d` | `w` or another digest, and every used block keeps its `[blocks]` version | entry moved; `lock.block-package-moved` (info) |
  | `v`, `d` | a used block's version differs | c0268's `lock.block-version` (error) for that instance; the entry is left as it is |
  | `v`, `d` | not installed, and the script failed to import its package | exit 6, `FEN-6006` (decision 6) |
  | an entry | no instance uses the package | entry dropped; `lock.block-package-released` (info) |

- **Why a moved package version is not an error.** The block versions, which decide the circuit, are
  already pinned per instance. A package release that leaves the used blocks alone changes nothing that
  the design sees. Its pin moves visibly, `--frozen` refuses the move, and the change shows in the lock
  diff. Stopping every build on any package release would teach users to delete the lock.

### 6. A missing package

- When the script raises `ModuleNotFoundError` for a module that a `[block-packages]` entry's namespace
  maps to, the build exits 6 with the new **`FEN-6006`**:
  - message: "a block package pinned by the design lock is not installed";
  - hint: `uv add "fenolite-blocks==1.2.0"` or `pip install "fenolite-blocks==1.2.0"`, with the
    distribution and version from the lock;
  - `retryable` false.
- The lock records the namespace, not the module. The mapping namespace → module comes from the entry
  points of the installed environment. When the package is not installed at all, the build matches the
  missing module name against the lock's distribution names normalised by the packaging rules (`-` and
  `_` equal), which holds for the official package and is documented for others.
- Any other `ModuleNotFoundError` keeps today's script-error behaviour.
- **Code number.** c0266 takes `FEN-6004` for a missing device pack, and c0267 also proposes `FEN-6004`
  (supplier credentials). This change takes the next free number at implementation, `FEN-6006` at the time
  of writing. Task 0.1 records the number actually free.

### 7. `fenolite blocks upgrade`

```
fenolite blocks upgrade design.py --dry-run --json
fenolite blocks upgrade design.py --block FenoliteBlocks:buck_6v --out build/ --dry-run --json
fenolite blocks upgrade design.py --confirm --plan <plan_id>
```

- It runs the script as `build` does, with the lock read, but without the `lock.block-version` stop and
  without planning outputs. It then plans one write: the lock (kind `lock`), with:
  - every `[blocks]` entry whose locked version differs from the used one, or only those of `--block ID`
    or `--package NAME` (repeatable);
  - the `[block-packages]` entries of the selected packages set to the installed version and digest.
- **`result.upgrades`**, one row per changed instance, sorted by path:
  - `path`, `id`, `before`, `after`;
  - `step`: `patch`, `minor`, or `downgrade` when `after` is lower;
  - `record`: the installed record (from the index or `describe`);
  - `deprecated`, when set;
  - `issues`: the build issues under the new versions that name the instance or a path under it;
  - with `--out DIR`, `circuit`: per part path under the instance, added, removed, or changed value,
    device or lib id, against `DIR/.fenolite/circuit.json`.
- A MAJOR step cannot happen under one id (c0268: interface changes need a new id). If a package breaks
  that rule (`after` has another MAJOR), the row has `step: "major"`, and the command refuses it with
  `blocks.upgrade-major` (error, exit 5) unless `--allow-major` is given. Nothing is planned for a refused
  row.
- A build error under the new versions (a missing port, a `DslError` of the script) is reported, and the
  command plans nothing, exiting 5 or 3 as `build` would.
- It writes nothing without `--confirm`, never edits the script, and its receipt lists the lock with its
  SHA-256. `--frozen` is not accepted (exit 2).
- Replacing a deprecated block by its successor needs a script change. `upgrade` lists the replacement in
  `deprecated`, and the user changes the import.

### 8. Namespaces

- `Fenolite` is refused as an entry point name: `blocks.namespace-reserved` (error, the package is
  ignored).
- Two distributions with one namespace give `blocks.namespace-conflict` (error) naming both. The catalog
  lists neither, and a build that uses a block of that namespace fails with the same issue.
- A record whose namespace differs from its entry point's name makes the index invalid (`FEN-3004` from
  `blocks index`, and `blocks.package-broken` from discovery).

### 9. Capabilities and doctor

`capabilities --json` gains `block_packages`: per package `distribution`, `version`, `namespace`, `blocks`
(count) and `index` (digest), sorted by distribution. `doctor` shows the same in short and warns on
`blocks.package-broken`, `blocks.namespace-conflict` and `blocks.namespace-reserved`. Neither imports a
package.

### 10. Codes

| code | severity / exit | when |
|---|---|---|
| `lock.block-package-moved` | info | a pinned package's version or index changed while its used blocks kept their versions |
| `lock.block-package-released` | info | a pinned package serves no instance any more |
| `blocks.index-stale` | warning (exit 5 under `blocks index --check`) | the index does not match the package's blocks |
| `blocks.package-broken` | warning | an entry point whose package or index cannot be read |
| `blocks.namespace-conflict` | error | two distributions claim one namespace |
| `blocks.namespace-reserved` | error | a package claims `Fenolite` |
| `blocks.upgrade-major` | error | `blocks upgrade` meets a MAJOR step without `--allow-major` |
| `FEN-6006` | exit 6 | a block package pinned by the lock is not installed |
| `FEN-7004` | exit 7 | existing (c0249): the `[block-packages]` section would change under `--frozen` |

## Risks / Trade-offs

- **Code from a package runs in the build.** This is true of any Python import a script makes. Fenolite
  does not import packages to list them, and the lock makes the version visible. Package authors are
  responsible for side-effect-free modules, and the official package's CI tests it.
- **`find_spec` and namespace packages.** A top-level namespace package (no `__init__.py`) has several
  locations. The index is looked up in each, and the first found is used. More than one index is refused
  as `blocks.package-broken`.
- **The index can lie.** A hand-edited index lists blocks that the code does not have. The build compares
  digests for every used block (`blocks.index-stale`), and the package's CI runs `--check`.
- **Version moves without stopping** (decision 5) let a package release change a block's formula without
  raising its version. c0268's version discipline and c0270's golden files are the defence. The official
  package's CI enforces both.

## Open Questions

1. **Repository name and owner of the official package.** Recommended: `fenolite-blocks` next to the main
   repository, Apache-2.0, DCO, namespace `FenoliteBlocks`.
2. **Should the starter library ever move out of the core?** Recommended: no. It stays small, and
   everything else goes to packages (research question 1).
3. **Should a moved package version stop the build** (stricter than decision 5)? Recommended: no, because
   instance versions already stop it. `--frozen` covers releases.
4. **Code number `FEN-6006`.** Recommended: take the next free number after c0266 and c0267 settle
   `FEN-6004`.
5. **A registry or `blocks search` across PyPI?** Recommended: no. Discovery stays local and offline, and
   finding packages is the package index's job.

## Relation to the other changes of this batch

- **c0268:** adds the catalog source `package` and the lock section `block-packages`, and replaces the hint
  of `lock.block-version` with `fenolite blocks upgrade <script>`.
- **c0269:** none. Package blocks get hierarchical pins like any block.
- **c0270:** the official package runs c0270's usage builds and tests in its CI. `blocks test` covers
  package blocks through the same catalog.
- **c0271:** a package block's layout file ships inside the package, beside its code. The index records its
  path as c0271 defines.
- **c0272:** fills the starter library.
- **c0266:** the same discovery pattern and the same "pin only what is used" rule. Packs and block packages
  stay separate mechanisms, because one carries data and the other code.
