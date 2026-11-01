# Block records and the block catalog

A block (`docs/dsl.md`, "Blocks") becomes a library item when it carries a **record**: an id, a version, a
licence, evidence and sources, its parameters with meaning, unit and limits, and its ports with docs (change
c0268). The decorator defines the record; a published library item stores its static copy beside the code
(c0273). This page describes records, discovery, pinned library packages and reviewed upgrades.

## Records

`@block(id="Acme:divider", version="1.0.0", summary=..., licence=..., ...)` gives a block its record, and
`param(...)` and `b.port(..., doc=...)` its parameter and port metadata (`docs/dsl.md`, "Block records,
parameter metadata and versions"). The header follows the vocabulary of library records
(`docs/library-records.md`): an id `<namespace>:<name>`, a version `MAJOR.MINOR.PATCH` whose MAJOR stays
`1`, an SPDX licence, an evidence label, sources, `replaces` and `deprecated`. A block's evidence label is
its author's statement; the catalog shows it and never raises it.

`fenolite.dsl.describe(block)` returns the `BlockRecord`. The header and the parameters come from the
decorator. The ports, local parts (`inner/R` for a nested block's), local nets, nested blocks and
requirements (device ids, lib ids of parts without a device, part query texts) come from using the block
once with its defaults in a detached design. `describe` reads no file, library or lock, runs no tool and
never converts the design to a model. The ports shown are those of the default parameters: a block that
declares ports conditionally shows the ports of its defaults. A block with a required parameter lists its
parameters, and `ports`, `parts`, `nets`, `blocks` and `requires` are `null` with `elaboration.reason`
naming the parameter; a block whose function raises gives `elaboration.error` instead of raising.

`fenolite.dsl.record.record_json(record)` writes the record as canonical JSON of schema
`fenolite.block.v0` (keys sorted, lists by name, values as the canonical texts of block parameters, no
float, LF). Its `digests` are SHA-256 digests computed by Fenolite, never typed by an author:

| digest | covers |
|---|---|
| `interface` | the ports (name, kind, direction, optional, members) and the parameter names, types, units and whether each is required |
| `definition` | the interface plus parameter defaults, limits and choices, parts, nets, nested blocks and requires |
| `record` | the whole record but its digests: docs, summary, sources and evidence count too |

## Version rules

`src/fenolite/blocks/VERSIONS.toml` holds one table per shipped block id: `version`, `record`, `definition`
and `interface`, or `removed = true` for a removed id. `uv run python tools/blocks/versions.py --update`
rewrites it after a reviewed change, and `tests/unit/blocks/test_versions.py` checks the rules:

| what changed | required |
|---|---|
| the record digest only (docs, summary, sources, evidence) | a PATCH step or more |
| the definition digest, the interface unchanged | a MINOR step or more |
| the interface digest | a new id; the old block gains `deprecated`, the new one `replaces` |
| an id marked `removed` used again | refused |

A record with `replaces = X` is accepted only when block `X`, if it is in the same catalog, names the record
in `deprecated.by`; `fenolite blocks show` and the version test report the mismatch. Behaviour that the
record cannot see (a formula inside the function) is the author's duty and the reviewer's.

A design pins the version of every instance in its lock (`[blocks]`): a build never takes another version
silently. It stops with `lock.block-version` until `fenolite blocks upgrade SCRIPT` reviews and updates
the instance versions.

## Catalog

`fenolite blocks` reads three sources (`docs/cli-contract.md`, "blocks"):

- `builtin`: the package `fenolite.blocks` and its modules, imported; each module lists its blocks in
  `__all__`. Importing them creates no design, opens no file and imports no third-party module. The
  namespace `Fenolite` is reserved for them; each is `Apache-2.0` and names `S-` sources of
  `docs/evidence/sources.md`. These starter blocks use only devices in the shipped catalog.
- `library`: static `block.json` files in `fenolite_library/blocks/<Namespace>/<name>/` beside the script.
  `list`, `show` and `doc` read these files without importing any vendored package. `--script FILE`
  chooses the project; the default is `design.py` in the current directory when it exists.
- `file`: each `--from FILE.py` of the command line, imported by path under a private module name, with
  every block that the file defines. **Importing a file runs its code**: keep block modules apart from
  design scripts, and never pass a file you have not read.

```
fenolite blocks list --from blocks/power.py --json
fenolite blocks show Acme:divider --from blocks/power.py --json
fenolite blocks doc Acme:divider --from blocks/power.py --out docs --dry-run --json
fenolite blocks where Acme:divider . --json
fenolite inspect build/.fenolite/circuit.json --blocks --json
```

`where` and `inspect --blocks` are Where-Used: `where` reads every design lock below the given folders and
lists each instance of the block with its version; `inspect --blocks` lists the block versions and instances
of one lock or one built `circuit.json`, with each instance's recorded parameters.

## Generated pages

`fenolite.dsl.record.page(record)` writes a Markdown page with LF line ends and no date: the id and version
as title, the summary, a table of category, licence and evidence, the parameters (name, type, unit,
default, allowed, doc; lengths in millimetres), the ports (name, kind, direction, optional, doc), the
requirements and the sources. `uv run python tools/gen_block_docs.py` writes `docs/blocks/<name>.md` for
every shipped block, with each source's link from `docs/evidence/sources.md`, and `docs/blocks/index.md`;
with `--check` it fails on any difference, and `tests/consistency/test_block_docs.py` runs it.

## Library blocks

| tier | namespace | delivery | execution |
|---|---|---|---|
| core starter blocks | `Fenolite` | released with Fenolite, Apache-2.0, stdlib only | imported from `fenolite.blocks` |
| library blocks | `FenoliteBlocks` for authored items; source namespace for converted items | a licensed `fenolite-library` item, independently versioned | the script explicitly imports its vendored package |
| project blocks | the project's namespace | modules in the project | the script imports them; `--from` imports them explicitly |

`get block ID` reviews the item's licence, code files and item pin. A block item has `executes: true`;
`get` still never executes its payload. Its directory contains `item.json`, `PROVENANCE.json`, `LICENSE`,
`NOTICE`, a regular Python package exporting one `BlockDef` in `__all__`, and `block.json`. Usage,
test, golden and layout files travel with the item. Derived library material remains in the external
`fenolite-library` repository, with its licence and provenance.

The authored test item is `Demo:led`, a synthetic two-terminal resistor block, not a validated circuit.
For a local release folder, the sequence is:

```
fenolite get block Demo:led --from release --dry-run --json
fenolite get block Demo:led --from release --confirm --plan <plan_id> --json
fenolite blocks list --script design.py --json
```

`blocks test --script design.py` selects the same vendored catalog and explicitly executes its tests.
Usage builds copy the vendored namespace into a private folder; tests keep its project import context.
Golden plans bind the namespace's dependency bytes and leave source lock files untouched.

The script imports `from fenolite_library.blocks.Demo.led import led`. The directories above `led/`
have no `__init__.py`: they are script-local namespace packages. Each script run temporarily sets aside
other `fenolite_library` modules and restores them afterwards, including namespace modules with no file.

### Writing the record file

```
fenolite blocks index ITEM_DIR --dry-run --json
fenolite blocks index ITEM_DIR --confirm --plan <plan_id> --json
fenolite blocks index ITEM_DIR --check --json
```

Indexing explicitly imports the package and describes its exported block. `--out FILE` overrides the
default `ITEM_DIR/block.json`. The canonical `fenolite.block-item.v0` file holds `id`, `version`,
`namespace`, `fenolite` (the author's compatibility statement), and its complete `fenolite.block.v0`
record and digests. The id, version and namespace must agree with the record and `item.json`.
Zero or multiple block exports, malformed records or disagreeing identities give `FEN-3004`.

Use `--check` in library CI: it writes nothing and exits 5 with `blocks.index-stale` on a difference.
A build compares each used vendored definition with the static record and reports the same code as a
warning for a local edit; it continues using the code. Corrupt or missing static records give
`blocks.item-broken`. A vendored `Fenolite:` item gives `blocks.namespace-reserved`, never a core override.
Catalog metadata does not reconstruct parameter values from display text, including rounded ranges.

Library CI also checks version rules, declared dependencies and sources, usage builds, golden tests,
and clean imports. Those jobs and the first published authored item are separate external-repository
work; the local fixture and tests establish the core protocol.

### Lock pins and missing items

`[blocks]` stores each used instance's literal `<id>@<version>`. The separate
`[library.items."block/<id>"]` stores the item version, release, index digest, tree digest, licence and
vendored path; only `get` changes it. A build keeps it unchanged. Core and project blocks have no item pin.
A missing pinned folder fails before script execution with existing `FEN-6004`; restore it using
`fenolite get --locked SCRIPT --dry-run`. An unpinned missing block import remains `FEN-3004` and adds
the exact `fenolite get block <Namespace>:<name> --dry-run` hint.

## Upgrading

First review and get the new item version. Then review its effect on existing instance pins:

```
fenolite blocks upgrade design.py --dry-run --json
fenolite blocks upgrade design.py --out B --block Demo:led --dry-run --json
fenolite blocks upgrade design.py --confirm --plan <plan_id> --json
```

`result.upgrades` is sorted by instance path. Each row contains `path`, `id`, `before`, `after`, the
`step` (`patch`, `minor`, `major` or `downgrade`), the new record, deprecation metadata and build issues
that name the instance. `--block ID` is repeatable and selects which versions change. A major step
is refused with `blocks.upgrade-major` unless `--allow-major` is explicit. `--frozen` is not accepted.
An id replacement keeps c0268's normal build behaviour; this command changes versions under one id.

`--out B` compares with a confirmed `B/.fenolite/circuit.json`. Each row gains `circuit`: added,
removed or changed parts, by hierarchical path, with before/after value, device, symbol and footprint.
The field is unavailable (`null`) when validation cannot produce a new circuit. A missing baseline
is an input error. Device selection and build checks run as in `build`; an error plans no write.

The only planned target is the design lock. Existing refs, picks, pins and library item pins retain
their values; code, vendored files and the previous build stay untouched. The script runs once during
review. Confirmation with the plan id replays the reviewed lock bytes without running it again and
refuses changed source, record, lock or baseline inputs. Normal `build` records first-time instances;
an upgrade with no changed locked versions writes nothing.

## Starter conventions

The five core starter bodies import DSL/core/stdlib only. Their shipped `tests/test_*.py`
files are deliberate package data and executable plain zero-argument functions on
`fenolite.testing`; they import no pytest or third-party runtime package. The `blocks.tests`
layering exception applies only to those tests. Usage, golden, layout and illustrative
project-device assets are listed in `fenolite/blocks/MANIFEST.toml`.

For shipped starters the catalog requests `describe(..., partial=True)`: port and layout
metadata declared before missing electrical inputs remains visible with an explicit
`elaboration` reason. A required parameter remains required with no default. Direct
`describe` keeps the default incomplete view until inputs are supplied. Required primitive
annotations, such as `protection: str`, are recorded and checked before the body runs.
