## Why

c0268 gives blocks records, versions and a catalog, but the catalog only knows the blocks shipped inside
Fenolite and Python files named on the command line. A block library must grow beyond the core without
making the core heavier. It must not tie a block fix to a Fenolite release, and it must not let a project
build differently on another machine. The research of 2026-10-29 (`docs/research/circuit-blocks.md`, section
2 gap 6, section 3.7 and row c0273 of section 4) proposes three tiers: a small starter library in the core,
further blocks outside it, and a project's own blocks.

The maintainer decided on 2026-10-29 that blocks outside the core live in **`fenolite-library`**
(github.com/lgili/fenolite-library, c0279), the single repository for all third-party-derived and library
material, as its kind `blocks`, pulled into a project by `fenolite get block <id>`. The separate
distribution `fenolite-blocks` with entry points, first proposed here, is dropped. Discovery without import,
pinned versions and a reviewed upgrade stay.

Only concepts are taken from atopile (versioned packages) and Altium (push-or-stay updates).

## What Changes

- **Three tiers, one catalog.**
  - **Starter library.** `fenolite.blocks` in the core: Apache-2.0, stdlib only, namespace `Fenolite`,
    versioned with Fenolite. c0272 fills it.
  - **Library blocks.** The `blocks` kind of `fenolite-library`. One item is one block: a Python package
    folder with the block's code, its c0268 record file `block.json`, and c0270/c0271 files.
    Fenolite-authored items use the namespace `FenoliteBlocks` and Apache-2.0. `fenolite get block ID`
    vendors an item into `fenolite_library/blocks/<Namespace>/<name>/` beside the script, and the script
    imports it from there.
  - **Project blocks.** Plain Python modules beside the script, as in c0251 and c0268.
- **Discovery without import.** `blocks list`, `show` and `doc` read vendored blocks from their
  `block.json` files (the catalog source `library`), without importing any module. Only a design script
  that imports a block runs its code, as it runs any Python.
- **The record file.** `fenolite blocks index ITEM_DIR --out FILE` describes the item's block (c0268's
  `describe`) and writes `fenolite.block-item.v0` through plan and confirm. `--check` fails on a stale file,
  for the library's CI. A build compares each used vendored block with its record file.
- **Pinned in the lock.** c0268's `[blocks]` keeps instance versions. c0279's `[library.items."block/<id>"]`
  pins the item version, release and tree digest. A missing vendored folder exits 6 with c0279's
  `FEN-6004`.
- **`fenolite blocks upgrade SCRIPT`** plans the `[blocks]` rewrite after a `fenolite get block --version`,
  with each instance's version step, the new record, deprecations, build issues and, with `--out DIR`,
  circuit differences. It writes only the lock, through plan and confirm.
- **Namespaces.** `Fenolite` stays reserved for the core; a vendored item claiming it is ignored with
  `blocks.namespace-reserved`.
- **The library's CI for blocks:** record-file check, c0268 version rules, c0270 tests, no-side-effect
  import test.

## Non-goals

- No entry-point packages, no `fenolite-blocks` distribution, no `[block-packages]` lock section and no
  `FEN-6006` (dropped from the first version).
- No content of the library's blocks is specified here; the first items follow c0268 and c0272.
- No two versions of one block id in one project.
- No change of `pyproject.toml` `dependencies` or extras.

## Evidence level required

- Discovery, record files, namespaces, lock pins and upgrade plans: `INFERRED`, unit-tested with blocks
  vendored from a local release built from authored fixtures, no network (`H-G-BLOCK-PACKAGES`).

## Impact

- New: `src/fenolite/cli/blockvendored.py`, `src/fenolite/dsl/blockitem.py`, the verbs `blocks index` and
  `blocks upgrade`, `tests/data/library/demo/blocks/` (authored, CC0), tests, `docs/blocks.md` sections
  "Library blocks" and "Upgrading". Outside: the blocks jobs of `lgili/fenolite-library`'s CI.
- Changed: `cli/blocksrc.py` (source `library`), `cli/cmd_build.py` and `cli/_script.py` (record-file
  check, `get` hint), `cli/cmd_blocks.py`, `docs/cli-contract.md`, the guide page `commands.md`,
  `CHANGELOG.md`.
- Depends on: c0268 (required), c0249 (lock), c0279 phase A (`get`, `[library.items]`, `FEN-6004`).
- Size: about 4 design-days (S).
