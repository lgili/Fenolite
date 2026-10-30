# Block records and the block catalog

A block (`docs/dsl.md`, "Blocks") becomes a library item when it carries a **record**: an id, a version, a
licence, evidence and sources, its parameters with meaning, unit and limits, and its ports with docs (change
c0268). The decorator is the record: there is no manifest beside the code. This page describes how a
record is read, how its versions are kept, and the commands that list, show, document and find blocks.

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
silently. It stops with `lock.block-version` until the lock entry is changed after a review.

## Catalog

`fenolite blocks` reads two sources (`docs/cli-contract.md`, "blocks"):

- `builtin`: the package `fenolite.blocks` and its modules, imported; each module lists its blocks in
  `__all__`. Importing them creates no design, opens no file and imports no third-party module. The
  namespace `Fenolite` is reserved for them; each is `Apache-2.0` and names `S-` sources of
  `docs/evidence/sources.md`. No block is shipped yet.
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
