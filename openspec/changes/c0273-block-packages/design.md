## Context

- **Source.** `docs/research/circuit-blocks.md` (2026-10-29), section 2 gap 6 ("Distribution"), section 3.7
  and row c0273 of section 4, with the maintainer questions 1 (starter blocks in the core, recommended) and
  4 (upgrades never silent). Concepts only, from atopile (versioned packages with a manifest) and Altium
  (Where-Used, push-or-stay updates).
- **Maintainer decision of 2026-10-29.** All library material outside the core lives in one repository,
  `fenolite-library` (github.com/lgili/fenolite-library, c0279), pulled by `fenolite get`. Blocks are its
  kind `blocks`. The first version of this change proposed a separate Python distribution
  `fenolite-blocks`, entry points in the group `fenolite.blocks`, a static package index, a lock section
  `[block-packages]` and `FEN-6006` for a missing package. Those are dropped. What stays: the three tiers,
  discovery without import, a static record per block, pinned versions, and `blocks upgrade`.
- **What c0268 defines.**
  - `@block(id=, version=, ...)`, `describe(block) -> BlockRecord` and `record_json` (`fenolite.block.v0`)
    with record, definition and interface digests.
  - Catalog sources `builtin` (`fenolite.blocks`) and `file` (`--from`), the error `blocks.duplicate-id`,
    and `blocks list`, `show`, `doc` and `where`.
  - The lock section `[blocks]` (instance path → `id@version`), `lock.block-version` (error) on a version
    difference, and the reserved namespace `Fenolite`.
- **What c0279 defines.** Items with `item.json`, `PROVENANCE.json`, `LICENSE` and `NOTICE`; licence
  families; releases; `fenolite get KIND ID` copying into `fenolite_library/<kind folder>/<id path>/` beside
  the script; the lock section `[library.items]`; `FEN-6004` for a missing vendored folder; `executes` for
  items whose payload is code.
- **What exists on `dev` (0.6.0).** No plugin mechanism. `pyproject.toml` has `dependencies = []` and
  closed extras. The runner executes the design script with its folder first on `sys.path`.

## Goals / Non-Goals

**Goals**

- Blocks can live outside the core, released on their own, under the same record and version rules.
- Listing and reading vendored blocks never runs their code.
- A project builds with the block versions it locked, on any machine, and an upgrade is a planned,
  reviewed lock change.

**Non-Goals**

- See the proposal.

## Decisions

### 1. Three tiers

| tier | where | namespace | licence | versioned with | found by |
|---|---|---|---|---|---|
| starter | `fenolite.blocks` (core) | `Fenolite` | Apache-2.0 | Fenolite; each block its own version (c0268) | `builtin` source |
| library | `fenolite_library/blocks/<Namespace>/<name>/` beside the script, vendored by `fenolite get block` | `FenoliteBlocks` for authored items; a source namespace for converted ones | the item's (c0279 families) | the item; pinned by `[library.items]` | `library` source (decision 3) |
| project | modules beside the script | any but `Fenolite` | the project's | the project's git history | the script's own imports; `--from` for the catalog |

- **The starter library** is small and stays small. It holds the blocks of c0272 and later the generic
  ones that the research lists (decoupling set, reverse-polarity protection, crystal, reset, connector with
  ESD). It imports only `fenolite.dsl`, `fenolite.model` and `core`, uses no third-party module, and its
  modules have no import side effects (c0268's test). A block that needs a device outside the shipped
  catalog belongs in the library, not in the core.
- **Library blocks** are items of `fenolite-library`, one block per item. Authored items use the namespace
  `FenoliteBlocks`, Apache-2.0, family `apache`. A block derived from a third-party design keeps that
  licence and records its provenance (c0279).
- **A project** gets a block with `fenolite get block FenoliteBlocks:buck_6v --dry-run`, confirms it, and
  imports it: `from fenolite_library.blocks.FenoliteBlocks.buck_6v import buck_6v`.
- **Alternative considered:** a Python distribution per library (`fenolite-blocks`) found through entry
  points (the first version of this change). Rejected by the maintainer's decision: one repository, one
  command, a licence and provenance per item, and every third-party file visible in the project.

### 2. The block item

```
fenolite-library/blocks/apache/FenoliteBlocks/buck_6v/
  item.json  PROVENANCE.json  LICENSE  NOTICE
  __init__.py          # exports the BlockDef buck_6v in __all__
  block.json           # fenolite.block-item.v0 (decision 4)
  usage/  tests/  golden/  layouts/   # c0270 and c0271 files
```

- The item folder is a regular Python package (`__init__.py`). Its modules may import `fenolite.dsl`,
  `fenolite.model`, the standard library and other block items named in `depends` (by their vendored module
  path), nothing else. The library's CI checks this with an import-graph test.
- `item.json` has `"kind": "block"`, the block id, the block's version (equal to the record's) and
  `"executes": true`.
- **Vendored layout.** `get` copies the folder to `fenolite_library/blocks/<Namespace>/<name>/`. The
  folders `fenolite_library/`, `fenolite_library/blocks/` and `fenolite_library/blocks/<Namespace>/` stay
  without `__init__.py`, so they are namespace packages (PEP 420) found from the script's folder on
  `sys.path`. The top-level name `fenolite_library` avoids clashing with installed modules.

### 3. Discovery without import

`fenolite.cli.blockvendored.find_vendored(script_dir) -> tuple[VendoredBlock, ...]`:

1. List `fenolite_library/blocks/*/*/block.json` beside the script, in POSIX path order.
2. Read each with `json.loads` and check its schema. A folder without a readable `block.json` gives
   `blocks.item-broken` (warning) naming the folder.
3. `VendoredBlock(id, version, namespace, module, root, record, digest)`, where `module` is
   `fenolite_library.blocks.<Namespace>.<name>` and `digest` is the record digest.

No module is imported. A test asserts that after `find_vendored()` and `blocks list`, `sys.modules` holds
no `fenolite_library` module. The catalog source `library` turns each record into a c0268 catalog entry, so
`list`, `show` and `doc` work on vendored blocks. These commands gain `--script FILE` (default
`design.py` in the working directory when it exists) to locate the vendored folder.

### 4. The record file

```json
{"fenolite": ">=0.8.0", "id": "FenoliteBlocks:buck_6v", "namespace": "FenoliteBlocks",
 "record": <fenolite.block.v0 record>, "schema": "fenolite.block-item.v0", "version": "1.1.0"}
```

- `fenolite blocks index ITEM_DIR --out FILE [--check]`:
  - it imports the item package by path under a private module name (the author's own code, run on
    purpose);
  - it describes the one `BlockDef` in the package's `__all__`; zero or several is `FEN-3004`;
  - it writes canonical JSON (`canonical.dumps`) and plans one file (kind `block-index`) through the
    mutation protocol.
- `--check` compares with the committed file and exits 5 with `blocks.index-stale` on a difference. It
  writes nothing.
- The record's namespace MUST equal the file's `namespace`, and its id and version MUST equal the item's,
  else `FEN-3004`.
- **At build time**, for each used instance of a vendored block, the build compares the record digest it
  computes with `describe` against `block.json`. A difference gives `blocks.index-stale` (warning) naming
  the folder and the id: a local edit of vendored code. The build still uses the code.

### 5. Versions in the lock

```toml
[blocks]
"pwr/buck" = "FenoliteBlocks:buck_6v@1.1.0"
"sense_a" = "Fenolite:voltage_divider@1.0.0"

[library.items."block/FenoliteBlocks:buck_6v"]
index = "sha256:5d0e…"
path = "fenolite_library/blocks/FenoliteBlocks/buck_6v"
release = "1.4.0"
spdx = "Apache-2.0"
tree = "fenolite-tree-1:3f9c…"
version = "1.1.0"
```

- `[blocks]` is c0268's: per instance, the block version that served it. A changed version stops the build
  with `lock.block-version`.
- `[library.items]` is c0279's, written only by `fenolite get`. It replaces the first version's
  `[block-packages]`.
- **Missing vendored folder.** c0279's build check reports `library.item-missing` and exits 6 with
  `FEN-6004` before the script runs.
- **Unpinned missing module.** When the script raises `ModuleNotFoundError` for a module under
  `fenolite_library.blocks.` that no lock entry pins, the script error keeps today's behaviour, and its hint
  adds `fenolite get block <Namespace>:<name> --dry-run`, derived from the module path.

### 6. `fenolite blocks upgrade`

```
fenolite get block FenoliteBlocks:buck_6v --version 1.2.0 --dry-run --json   # new code, new item pin
fenolite blocks upgrade design.py --dry-run --json                           # review the instance steps
fenolite blocks upgrade design.py --confirm --plan <plan_id>
```

- It runs the script as `build` does, with the lock read, but without the `lock.block-version` stop and
  without planning outputs. It then plans one write: the lock (kind `lock`), with every `[blocks]` entry
  whose locked version differs from the used one, or only those of `--block ID` (repeatable).
- **`result.upgrades`**, one row per changed instance, sorted by path:
  - `path`, `id`, `before`, `after`;
  - `step`: `patch`, `minor`, or `downgrade` when `after` is lower;
  - `record`: the used record (from `block.json` or `describe`);
  - `deprecated`, when set;
  - `issues`: the build issues under the new versions that name the instance or a path under it;
  - with `--out DIR`, `circuit`: per part path under the instance, added, removed, or changed value,
    device or lib id, against `DIR/.fenolite/circuit.json`.
- A MAJOR step cannot happen under one id (c0268: interface changes need a new id). If an item breaks that
  rule, the row has `step: "major"`, and the command refuses it with `blocks.upgrade-major` (error, exit
  5) unless `--allow-major` is given.
- A build error under the new versions is reported, and the command plans nothing, exiting 5 or 3 as
  `build` would.
- It writes nothing without `--confirm`, never edits the script or vendored files, and its receipt lists
  the lock with its SHA-256. `--frozen` is not accepted (exit 2).
- c0268's hint of `lock.block-version` becomes `fenolite blocks upgrade <script>`.

### 7. Namespaces

- A vendored item in the namespace `Fenolite` gives `blocks.namespace-reserved` (error); it is not listed,
  and a build that imports it fails with the same issue.
- One id from a vendored item and from a project block (`--from`) gives c0268's `blocks.duplicate-id`.

### 8. The library's CI for blocks

Added to c0279's `check.yml` for changed block items, with the pinned `fenolite`:

- `fenolite blocks index <item> --check`;
- c0268's version rules against the previous release (through `fenolite library audit --base`);
- c0270's usage builds and `fenolite blocks test`;
- the import-graph rule of decision 2 and c0268's no-side-effect import test;
- `sources` ids of every record registered in the library's `sources.toml`.

### 9. Codes

| code | severity / exit | when |
|---|---|---|
| `blocks.index-stale` | warning (exit 5 under `blocks index --check`) | a record file does not match the block's code |
| `blocks.item-broken` | warning | a vendored block folder without a readable `block.json` |
| `blocks.namespace-reserved` | error | a vendored item claims `Fenolite` |
| `blocks.upgrade-major` | error | `blocks upgrade` meets a MAJOR step without `--allow-major` |
| `library.item-missing` / `FEN-6004` | error, exit 6 | c0279: a pinned vendored folder is missing |
| `FEN-7004` | exit 7 | existing (c0249): the `[blocks]` section would change under `--frozen` |

## Risks / Trade-offs

- **Code from the library runs in the build.** It runs only when the script imports it, as any Python.
  `get` marks it `executes`, the library's CI tests it, and listing never imports it.
- **Namespace packages.** A stray `fenolite_library/__init__.py` would turn the root into a regular package.
  `get` never writes one, and `blocks.item-broken` names a vendored root that cannot be imported.
- **The record file can lie.** A hand-edited `block.json` lists another block. The build compares digests
  for every used block (`blocks.index-stale`), and the library's CI runs `--check`.
- **Version discipline for behaviour.** A library release could change a block's formula without raising
  its version. c0268's version rules and c0270's golden files, both enforced by the library's CI, are the
  defence; the item tree digest in the lock makes any byte change visible.

## Open Questions

1. **Namespace of authored library blocks.** Recommended: `FenoliteBlocks`, Apache-2.0.
2. **Should the starter library ever move out of the core?** Recommended: no. It stays small, and
   everything else goes to the library (research question 1).
3. **Company-private block libraries.** Recommended: later, through c0279's open question 7 (private
   libraries in the same format), not through entry points.
4. **Should `fenolite get block --version` also plan the `[blocks]` rewrite?** Recommended: no. Keep the
   two reviews separate: the files and licence in `get`, the circuit effect in `blocks upgrade`.

## Relation to the other changes of this batch

- **c0268:** adds the catalog source `library` and replaces the hint of `lock.block-version` with
  `fenolite blocks upgrade <script>`.
- **c0269:** none. Library blocks get hierarchical pins like any block.
- **c0270:** the library runs c0270's usage builds and tests in its CI. `blocks test` covers vendored blocks
  through the same catalog.
- **c0271:** a library block's layout files ship inside its item folder, beside its code.
- **c0272:** fills the starter library.
- **c0279:** the repository, the blocks kind's folder, `get`, `[library.items]` and `FEN-6004`.
- **c0266:** the same project-side pattern for device records (data, read as TOML); blocks are code,
  read through `block.json` until a script imports them.
