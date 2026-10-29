## Why

c0251 makes a reusable circuit a `@block` function with ports and recorded parameters, but a block is
still only a Python function name. Nothing says who wrote it, which version a design used, what a
parameter means, which unit and range it takes, what a port is for, or where a block is used. The research
of 2026-10-29 (`docs/research/circuit-blocks.md`, sections 2 and 3.2, gaps 1, 2 and 6) names this as the
first missing layer of a block **library**: a block record, parameter metadata, the block version in the
model and pinned in the design lock, a catalog that reads records without building, generated documentation
pages and Where-Used.

Other tools keep block metadata in a workspace with revisions (Altium Reuse Blocks), a package manifest
(atopile) or JSON beside a schematic (KiCad design blocks), and only the first offers Where-Used and
reviewed updates. Fenolite keeps the record in the code that defines the block, as reviewable text, and
pins versions through c0249's lock so that an upgrade is never silent. Only concepts are taken; no
manifest schema, field list or API name of another tool is copied.

## What Changes

- **Block records.** `@block(id=, version=, summary=, category=, licence=, evidence=, sources=,
  replaces=, deprecated=)` gives a block a record. The fields follow c0259's record header: an id
  `<namespace>:<name>`, a semantic version, an SPDX licence and an evidence label. The c0251 forms `@block` and
  `@block(name=)` still work and give a block without a record: a project block.
- **Parameter metadata.** `param(default, *, doc=, unit=, min=, max=, choices=)` as the default of a
  block parameter. It records a doc text, the unit, an allowed range and a closed list of choices. `use`
  checks every value against it before the function runs.
- **Port documentation.** `b.port(..., doc="...")` adds a doc text to a port.
- **Describe without building.** `fenolite.dsl.describe(block)` returns the `BlockRecord`. It reads the
  header and parameters from the decorator. It reads the ports, local parts, local nets and required devices
  by running the block once with its defaults in a detached design. This reads no library, lock or file and
  runs no tool. The record has a canonical JSON form (`fenolite.block.v0`) with three digests: record,
  definition and interface.
- **Versions in the model and the lock.**
  - A model `Module` of a block with a record holds `block` = the record id and the new `block_version`.
  - c0249's lock gains the section `[blocks]`, which maps each instance path to `<id>@<version>`.
  - A build whose block version differs from the locked one reports `lock.block-version` (error) and
    writes nothing. An upgrade is therefore always a reviewed lock change, and `build --frozen` refuses any
    change of the section.
- **Deprecation.** Using a deprecated block warns `block.deprecated` and names its replacement. A changed
  interface (ports, or parameter names and types) needs a new id, as c0259 rules for records.
- **Catalog commands** (read-only):
  - `fenolite blocks list` and `fenolite blocks show ID` read records without building;
  - `fenolite blocks doc ID` gives a generated Markdown page, printed with `--text` or written
    with `--out DIR` through plan and confirm;
  - `fenolite blocks where ID [PATH...]` lists, from design locks, every design and instance that uses a
    block, and with which version.
- **Where-Used in `inspect`.** `fenolite inspect FILE --blocks` lists the block versions and instance
  paths of one design lock or one built `.fenolite/circuit.json`.
- **Shipped versions file.** `src/fenolite/blocks/VERSIONS.toml` records the version and digests of each
  shipped block, and a test enforces the version rules. The package `fenolite.blocks` is created empty
  here. c0272 adds the starter blocks, and c0273 adds external packages.

## Capabilities

### New Capabilities

- `block-library`: block records, their canonical form and digests, describe, version rules, generated
  pages and the sources of the catalog.

### Modified Capabilities

- `design-dsl`: ADDED "Block records in the DSL", "Block parameter metadata", "Port documentation",
  "Block identity in a design", "Block versions in the design lock", "Locked block versions in a build",
  "Deprecated blocks in a build".
- `design-model`: ADDED "Block versions in the circuit model".
- `package-layering`: MODIFIED "Allowed import edges" (the new package `blocks` imports `dsl` and `model`;
  only `cli` and the root modules import it).
- `cli-contract`: ADDED "Blocks command verbs", "Blocks list command", "Blocks show command", "Blocks doc
  command", "Blocks where command", "Blocks view of inspect".

## Dependencies

- **c0251 circuit-blocks** (required): `@block`, `BlockDef`, `use`, ports, `Module.block` and `params`.
- **c0249 design-lock** (required): the lock file, `LockSection`, `design.moved()` carrying entries,
  `--frozen` and `FEN-7004`.
- **c0259 library-data-format**: the header conventions (id pattern, version form, licence, evidence,
  `replaces`, `deprecated`) and the version discipline that this change applies to blocks.
- **c0246 quantity-ranges**: range parameters and their bounds.
- **c0248, c0254**: device ids and query texts listed under `requires`.
- Later changes of the block batch build on this one: c0270 block-tests (`fenolite blocks test`), c0271
  block-layouts (layout tied to `block_version`), c0272 starter-blocks (the first records and their pages)
  and c0273 block-packages (installed packages as a catalog source, `fenolite blocks upgrade`).

## Non-goals

- No starter blocks (c0272), no shipped tests (c0270), no layout artefact (c0271), no external package
  discovery and no upgrade command (c0273).
- No class-based records and no record file beside the code. The decorator is the record.
- No parameter solver and no automatic choice of a block from requirements.
- No change of a design that uses no block with a record. Its model, lock and outputs keep their bytes.

## Evidence level required

- Records, describe, digests, the lock section and the catalog commands: `INFERRED`, unit-tested
  (hypothesis `H-G-BLOCK-RECORDS`).
- A shipped block's own evidence label is its author's statement and is shown as such. The catalog never
  raises it.

## Impact

- New:
  - `src/fenolite/dsl/record.py` (`param`, `BlockRecord`, `describe`, canonical JSON, digests);
  - `src/fenolite/blocks/__init__.py` (empty) and `src/fenolite/blocks/VERSIONS.toml`;
  - `src/fenolite/cli/cmd_blocks.py` and `src/fenolite/cli/blocksrc.py` (catalog sources);
  - `tools/blocks/versions.py`, `tools/gen_block_docs.py` and `docs/blocks.md`;
  - `tests/data/blocks/` (authored records for tests, CC0);
  - tests under `tests/unit/dsl`, `tests/unit/cli` and `tests/unit/blocks`.
- Changed:
  - `dsl/block.py` (decorator arguments, port `doc`, parameter checks);
  - `dsl/convert.py` (`Module.block_version`);
  - `model/circuit.py` and the schemas;
  - `dsl/lock.py` (section `blocks`);
  - `cli/cmd_build.py` (lock section, codes);
  - `cli/cmd_inspect.py` (`--blocks`);
  - `cli/data/explain.toml`;
  - `cli/cmd_capabilities.py`;
  - `docs/dsl.md`, `docs/design-model.md`, `docs/cli-contract.md`;
  - the guide pages `design-script.md` and `commands.md`;
  - `CHANGELOG.md`.
- Size: about 7 design-days (M).
