## Context

- **Source.** `docs/research/circuit-blocks.md` (2026-10-29): section 2 ("Still missing for a library",
  items 1, 2 and 6), section 3.2 ("The block record and the catalog") and row c0268 of the table in
  section 4. That page compares atopile packages, tscircuit subcircuits, JITX circuits, KiCad design blocks,
  Altium Reuse Blocks, SKiDL and others. Only concepts are taken. No manifest schema, field list, API name,
  block content or value table of another tool is copied.
- **What the batch defines before this change.**
  - c0251: `@block` and `@block(name=)` return a `BlockDef`. `design.use(block, name, **params)` makes a
    `Block` (a `Module`), and `b.port(name, kind, *, direction, optional)` declares ports. The model
    `Module` gains `block` (the block name) and `params` (`BlockParam(name, type, text)`). The recordable
    types are `bool`, `int`, `str`, `Length`, `Quantity`, the c0246 range and `None`.
  - c0249: the lock `<script stem>.lock` (`fenolite.lock.v0`), generic sections registered through
    `LockSection(name, resolve)`, `design.moved()` carrying entries, `build --frozen` with `FEN-7004`, and
    `result.lock.changes`.
  - c0259: the record header (`id`, `version`, `summary`, `licence`, `evidence`, optional `category`,
    `sources`, `replaces`, `deprecated`). Versions are `MAJOR.MINOR.PATCH` with MAJOR fixed at `1`, and an
    interface change needs a new id.
  - c0266: a lock section that pins what served a build, with the rule "only what is used is pinned".
- **What exists on `dev` (0.6.0).** `fenolite catalog` lists catalog symbols and footprints.
  `fenolite inspect FILE` has the views `--summary` and `--streams`. There is no notion of a block, a block
  version or a block catalog.

## Goals / Non-Goals

**Goals**

- A block carries its identity, version, licence, evidence and sources, its parameters with meaning,
  unit and limits, and its ports with docs, all in the code that defines it.
- A tool or an agent can list and read blocks without building a design.
- A design records which version of each block made each instance. A different version is never taken
  silently: the lock holds the version, and a change is a reviewed lock change.
- Documentation pages are generated from records, so they cannot drift from the code.
- A user can see where a block, and which version of it, is used.

**Non-Goals**

- See the proposal. Also: no remote registry, no search service, and no upgrade command (c0273).

## Decisions

### 1. The decorator is the record

```python
# Today (c0251)
@block
def voltage_divider(b, *, vout=volt("3.3"), current=ua(100)): ...


# Proposed
from fenolite.dsl import Rail, block, ma, param, ua, volt


@block(
    id="Fenolite:voltage_divider",
    version="1.0.0",
    summary="Resistive divider with a worst-case output range",
    category="analog",
    licence="Apache-2.0",
    evidence="INFERRED",
    sources=("S-0901",),
)
def voltage_divider(
    b,
    *,
    vout=param(volt("3.3").pct(5), doc="target output range"),
    vin=param(volt("12").pct(10), doc="input range"),
    current=param(ua(100), doc="bias current at nominal input", min=ua(1), max=ma(10)),
    series=param("E96", choices=("E24", "E96"), doc="resistor series"),
):
    hi = b.port("HI", Rail, direction="in", doc="input")
    out = b.port("OUT", Rail, direction="out", doc="divided output")
    lo = b.port("LO", Rail, direction="in", doc="reference, usually ground")
    ...
```

The divider body is c0272's. This sketch only shows the decorator and `param`. `S-0901` stands for a
source that c0272 registers.

- **Keywords**, all keyword-only:
  - `id` (`<namespace>:<name>`, each part `[A-Za-z0-9_.+-]+`, c0259's pattern);
  - `version` (`MAJOR.MINOR.PATCH`, decimal, no leading zeros);
  - `summary` (one line, at most 120 characters, no newline);
  - `category` (one of the closed set of decision 7, default `other`);
  - `licence` (an SPDX expression; default `Apache-2.0` for the namespace `Fenolite`, required otherwise);
  - `evidence` (a label of `AGENTS.md`; default `INFERRED`);
  - `sources` (a tuple of texts; for the namespace `Fenolite` each MUST be an `S-` id of
    `docs/evidence/sources.md`, checked by a test, not at import);
  - `replaces` (an id);
  - `deprecated` (`{"by": id, "since": version, "reason": text}`).
- `id` and `version` go together: giving one without the other raises `DslError` at decoration. `name=`
  of c0251 and `id=` cannot both be given.
- A block **without** `id` is a project block, as in c0251. It has no record header, no version and no
  lock entry. `describe` still gives its parameters and ports.
- The namespace `Fenolite` is reserved for blocks under `src/fenolite/blocks/`. A block defined elsewhere
  with that namespace raises `DslError` at decoration, judged by the defining module's `__name__`.
- **Alternatives considered.**
  - A TOML or JSON manifest beside the code (the atopile and KiCad forms). Rejected: two sources of
    truth that drift, and the ports would still be in the code.
  - Ports declared in the decorator, so that a record needs no run of the function. Rejected: ports are
    written twice, and their kind and direction already live in `b.port`. Decision 4 runs the function
    once with defaults instead.

### 2. Parameter metadata

```python
param(default=REQUIRED, *, doc="", unit=None, min=None, max=None, choices=None)
```

- `param(...)` is used only as a default in a block signature. `@block` unwraps it. The signature default
  becomes `param.default`, and `REQUIRED` makes the parameter required, as a missing default does in c0251.
- **Checks at decoration** (`DslError` naming the block and the parameter):
  - `default` is recordable (c0251) or `REQUIRED`;
  - `unit`, when given, is a `Quantity` unit name (`volt`, `amp`, `ohm`, ...) or `length`, and equals
    the unit of the default when there is one;
  - `min` and `max` are of the default's type and unit (a `Quantity`, `Length` or `int`), with
    `min <= max`;
  - a `choices` tuple holds at least two distinct recordable values of one type;
  - the default lies within `[min, max]` (for a c0246 range, both ends) and is one of `choices`;
  - `doc` is at most 200 characters, with no newline.
- **Checks at `use`** (before the function runs, as c0251's binding):
  - a `Quantity` or range of another unit raises `DslError` naming the parameter, the unit given and the
    unit expected;
  - a value outside `[min, max]` (for a range, an end outside), or not in `choices`, raises `DslError`
    naming the parameter, the value and the allowed range or choices.
- **The unit** is the unit name of `fenolite.dsl.quantity.UNITS`, or `length` for a `Length`, which is
  shown in millimetres in pages. It is the canonical name, not a symbol, so the record never depends on a
  display choice. A parameter without a default and without `unit` accepts any recordable value, and its
  record shows `type = "any"`.
- **Not in the model.** The metadata stays in the record. The model keeps c0251's `BlockParam(name,
  type, text)` only, so the model bytes of a design do not change when a doc text changes.
- **Alternative considered:** `typing.Annotated[Quantity, Unit("V"), Range(...)]`. Rejected: it needs a
  type-hint evaluator, and the default value already carries the type.

### 3. Port documentation

`b.port(name, kind=Net, *, direction="inout", optional=False, doc="")`. `doc` follows the rule of
parameter docs. It is kept on the port handle for `describe` and pages, and is not written to the model.

### 4. Describe: the record without a build

`fenolite.dsl.describe(block_def) -> BlockRecord` is pure.

- The header and parameters come from the decorator.
- For the ports, local parts, local nets and requirements, `describe` makes a detached `Design("describe")`,
  calls `use(block_def, "x", **defaults)` once and reads the instance. Defaults are the signature
  defaults. A block with a required parameter cannot be elaborated without a value, so its record lists
  the parameters and leaves `ports`, `parts`, `nets` and `requires` as `null`, with the reason
  `"required parameter <name>"`.
- **No side effects.** No library, catalog row, lock or file is read, no tool is run, and the design is
  never converted to a model. c0254 query parts stay unresolved. An exception of the block function is
  caught and given back as the record's `elaboration` = `{"error": "<class>: <message>"}`. `blocks show`
  then exits 3 with `FEN-3004`.
- **Fields from the elaboration**, each sorted by code point:
  - `ports`: name, kind, direction, optional, members and doc;
  - `parts`: local part names, for nested blocks prefixed with their local path (`inner/R`);
  - `nets`: local net names;
  - `blocks`: each nested block instance's local name and its id or block name;
  - `requires`: `devices` (device ids named by `b.part(device=...)`), `lib_ids` (lib ids of parts
    without a device) and `queries` (c0254's canonical query texts).
- **Ports depend on defaults.** A block that declares ports conditionally on a parameter shows the
  ports of its defaults. Pages say so in one sentence. Describing with other values is a later option (open
  question 2).

### 5. Canonical record and digests

`record_json(record)` writes `fenolite.block.v0` with `canonical.dumps` (sorted keys, no float, LF).

```json
{"blocks": [], "category": "analog", "deprecated": null,
 "digests": {"definition": "sha256:…", "interface": "sha256:…", "record": "sha256:…"},
 "elaboration": null, "evidence": "INFERRED", "id": "Fenolite:voltage_divider", "licence": "Apache-2.0",
 "nets": [],
 "params": [{"choices": null, "default": "100uA", "doc": "bias current at nominal input",
   "max": "10mA", "min": "1uA", "name": "current", "type": "quantity", "unit": "amp"}],
 "parts": ["bot", "top"],
 "ports": [{"direction": "in", "doc": "input", "kind": "rail", "members": ["hv"], "name": "HI",
   "optional": false}],
 "replaces": null, "requires": {"devices": [], "lib_ids": [], "queries": ["resistor(…)"]},
 "schema": "fenolite.block.v0", "sources": ["S-0901"], "summary": "…", "version": "1.0.0"}
```

The JSON above shows the shape. A `default`, `min` or `max` text is c0251's canonical text of the value.

- **interface digest**: SHA-256 of the canonical JSON of the ports (name, kind, direction, optional,
  members) and of the parameters (name, type, unit, required or not).
- **definition digest**: the interface plus parameter defaults, ranges and choices, parts, nets, nested
  blocks and `requires`.
- **record digest**: the whole record without `digests`, so docs, summary, sources and evidence count.
- The digests are computed by the core and never typed by an author.

### 6. Version rules (shipped blocks)

`src/fenolite/blocks/VERSIONS.toml` holds one table per shipped id: `version`, `record`, `definition`,
`interface`, and `removed = true` for a removed id. `tools/blocks/versions.py --update` rewrites it, and
`tests/unit/blocks/test_versions.py` checks the rules against the committed file:

| what changed | required |
|---|---|
| record digest only (docs, summary, sources, evidence) | PATCH or more |
| definition digest, interface unchanged | MINOR or more |
| interface digest | a new id; the old block gains `deprecated`, the new one `replaces` |
| an id marked `removed` reused | refused |

- MAJOR stays `1` for the life of an id (c0259).
- Behaviour that the record cannot see (a formula inside the function) is the author's duty. c0270's
  golden JSON per block makes such a change visible in review.

### 7. Categories

The closed set is `analog`, `power`, `protection`, `interface`, `indicator`, `timing`, `connector` and
`other`. It is small on purpose, and a change of the set is a spec change. A project block may use any of
them, and the default is `other`.

### 8. Identity in the design and the model

- For a block with a record, the c0251 **block name** is its id (`Fenolite:voltage_divider`). The rule
  "two different functions with one block name in one design" (c0251) therefore applies to ids. Two
  versions of one id cannot be loaded in one process, because a module is imported once.
- The model `Module` of such an instance holds `block = "<id>"` and the new
  `block_version = "<version>"`. The field is omitted when empty, so a project block and a plain module
  write the same bytes as with c0251.
- The KiCad sheet name of c0251 becomes `sense_a (Fenolite:voltage_divider)`. Its file name does not
  change.

### 9. The `[blocks]` lock section

```toml
schema = "fenolite.lock.v0"
design = "sensor"

[refs]
"sense_a/bot" = "R2"
"sense_a/top" = "R1"
"sense_b/bot" = "R4"
"sense_b/top" = "R3"

[blocks]
"sense_a" = "Fenolite:voltage_divider@1.0.0"
"sense_b" = "Fenolite:voltage_divider@1.0.0"
```

- Registered through c0249's `LockSection("blocks", resolve)`. It is written after the sections defined
  before it, keys sorted by code point.
- **Who gets an entry.** Each instance of a block with a record, at any depth, keyed by its instance
  path. Project blocks get none. A design with no block record gets no section, and no lock is created
  for it by this change. c0249's "when a lock exists at all" gains the case "a block instance with a record".
- **Resolution in a build**, per instance path:

  | lock entry | block used | result |
  |---|---|---|
  | none | `id@v` | entry planned; `result.lock.changes` reason `block-locked`; no issue |
  | `id@v` | `id@v` | nothing |
  | `id@v` | `id@w`, `w ≠ v` | `lock.block-version` (error); nothing is written |
  | `id@v` | `other@w` | entry replaced; reason `block-replaced`; `lock.block-replaced` (info) |
  | `id@v` | the path is no block instance with a record | entry dropped; reason `block-released`; `lock.block-released` (info) |

- **Never silent.** A version change is never applied by a build. The installed code cannot build the old
  version, so the build stops and asks for a review. The error names the path, the locked and the used
  version. Its hint is "review `fenolite blocks show <id>`, then change the entry in `<lock>`". c0273
  replaces the hint with `fenolite blocks upgrade <script>`. Editing the entry by hand, or deleting it, is
  a reviewed lock diff.
- `design.moved()` carries entries of moved instance paths (c0249, decision 6). Under `--frozen`, any
  change of the section is a lock change, and the build exits 7 with `FEN-7004`.
- **Alternative considered:** taking the newer version and warning. Rejected: the research asks that a
  newer block version is never taken silently, and a warning in a long build log is silent in practice.

### 10. Deprecated blocks

A build that uses a block whose record has `deprecated` succeeds and reports `block.deprecated` (warning)
once per id, naming the id and `deprecated.by`. A block with `replaces = X` requires that block `X`, when
loaded in the same catalog, names it in `deprecated.by`. The catalog checks it (`blocks show`, the version
test), not the build.

### 11. Catalog sources

`fenolite.cli.blocksrc.find_blocks(*, files=()) -> tuple[CatalogEntry, ...]` gives
`(record, source, where)`:

1. **`builtin`**: the module `fenolite.blocks` and its sub-modules, imported. Each module lists its blocks
   in `__all__`. `tests/unit/blocks/test_import_side_effects.py` asserts that importing them creates no
   design, opens no file and imports no third-party module.
2. **`file`**: each `--from FILE.py` given on the command line, imported by path under a private module
   name. Every top-level `BlockDef` it defines is listed. Importing runs that module's code. The command
   text and `docs/blocks.md` say so, and recommend keeping block modules apart from design scripts.

The package `fenolite.blocks` is created empty here. It may import only `fenolite.dsl`, `fenolite.model`
and `core`, and only `cli` and the root modules import it (`package-layering`, "Allowed import edges").

c0273 adds a third source, `library`, read from the record files of blocks vendored from `fenolite-library` (c0279), without import. Two entries with one id
give `blocks.duplicate-id` (error) naming both sources. `list` still lists both, and `show` exits 3.

### 12. Commands

`fenolite blocks <verb>`. The verbs are `list`, `show`, `doc` and `where`. c0270 adds `test`, c0271 adds
`capture`, and c0273 adds `upgrade`. `capabilities` lists each verb as `blocks <verb>`. All four verbs here
are read-only (`mutates=False`) except `doc --out`.

```
fenolite blocks list [--from FILE.py]... [--category C] --json
fenolite blocks show ID [--from FILE.py]... --json
fenolite blocks doc ID [--from FILE.py]... (--text | --out DIR [--dry-run | --confirm])
fenolite blocks where ID [PATH]... --json
fenolite inspect FILE --blocks --json
```

- **list** `result.blocks`: one row per entry, sorted by id then by source. A row has `id`, `version`,
  `summary`, `category`, `licence`, `evidence`, `source`, `deprecated` (bool) and `digest` (the record
  digest). Project blocks of `--from` files without an id are listed under their block name with
  `version: null`.
- **show** `result.block`: the full `fenolite.block.v0` record plus `source` and `where` (a module name,
  never an absolute path). An unknown id exits 2 with `FEN-2001`, and the hint lists up to five closest ids.
- **doc**: the page of decision 13. `--text` prints it. `--out DIR` plans one file `<namespace>/<name>.md`
  under `DIR` (kind `block-doc`) and writes it under `--confirm`.
- **where**: reads every `*.lock` file below each `PATH` (default `.`), parsed as c0249's lock, and
  lists `result.uses`. Each use has `lock` (path relative to the working directory), `design`, `instance`
  and `version`, sorted. It imports nothing and runs no script. A lock that does not parse is reported as an
  issue `blocks.lock-unreadable` (warning) and skipped.
- **inspect --blocks** on a lock file or a `circuit.json` gives `result.blocks`: per id and version,
  the instance paths. For a `circuit.json` it also gives each instance's recorded parameters. It is a third
  view beside `--summary` and `--streams`, and giving two views exits 2.

### 13. Generated pages

`fenolite.dsl.record.page(record) -> str` is pure. It writes Markdown with LF:

```markdown
# Fenolite:voltage_divider 1.0.0

Resistive divider with a worst-case output range

| category | licence | evidence |
|---|---|---|
| analog | Apache-2.0 | INFERRED |

## Parameters

| name | type | unit | default | allowed | doc |
|---|---|---|---|---|---|
| current | quantity | amp | 100uA | 1uA to 10mA | bias current at nominal input |

## Ports

| name | kind | direction | optional | doc |
|---|---|---|---|---|
| HI | rail | in | no | input |

## Requires

## Sources
```

The JSON and page above show shapes only.

- Sources are listed as given. For `Fenolite:` blocks, `tools/gen_block_docs.py` adds each source's title
  from `docs/evidence/sources.md`. The core never reads that file.
- `tools/gen_block_docs.py` writes `docs/blocks/<name>.md` for every shipped block and an index
  `docs/blocks/index.md`. With `--check` it fails on a difference, and `tests/consistency` runs it. c0272
  adds the first pages.

### 14. Codes

| code | severity / exit | when |
|---|---|---|
| `lock.block-version` | error, exit 5 | a locked instance uses another version of its block |
| `lock.block-replaced` | info | a locked instance path now uses another block id |
| `lock.block-released` | info | a locked instance path is no block instance any more |
| `block.deprecated` | warning | a deprecated block is used |
| `blocks.duplicate-id` | error | two catalog sources hold one id (`blocks` commands) |
| `blocks.lock-unreadable` | warning | `blocks where` skipped a lock it cannot parse |
| `FEN-7004` | exit 7 | existing (c0249): the `[blocks]` section would change under `--frozen` |
| `FEN-3004` | exit 3 | existing: a block cannot be elaborated for `show` or `doc` |
| `FEN-2001` | exit 2 | existing: unknown block id |

New `DslError` cases, each at the offending call: bad `id`, `version` or header keyword; `id` without
`version`; the namespace `Fenolite` outside `fenolite.blocks`; bad `param` metadata; a value of another
unit, outside its range or not a choice. No new `FEN-` code.

## Risks / Trade-offs

- **Describe runs the block.** A block with a heavy or failing body slows or breaks `show`. Blocks are
  small by design. The error is reported, not raised, and `list` needs no elaboration.
- **`--from` imports code.** A design script given by mistake is executed. The documentation warns about
  it, and the command never writes anything during listing. c0273's `library` source needs no import.
- **Version discipline for behaviour.** The digests see the record, not formulas inside the function.
  This is mitigated by c0270's golden JSON and by review. The version test catches every visible change.
- **Hard stop on version mismatch.** Updating Fenolite updates the shipped blocks, so a project that
  pinned 1.0.0 stops building until the lock is reviewed. This is intended. The error message makes the
  fix one command (c0273), and `--frozen` CI already expects it.

## Open Questions

1. **Should project blocks need an id?** Recommended: no. A project block lives in the project's git
   history, and its version is the commit. An id is optional, and a project block with an id is pinned like
   a shipped one.
2. **Describe with other parameter values** (`blocks show ID --set vout=1.8V±5%`)? Recommended: later.
   Parsing texts into values needs the c0246 parser in the CLI, and defaults cover the catalog.
3. **Should a PATCH difference also stop a build?** Recommended: yes, for 0.7. Every difference is a lock
   review, which is one command. Revisit if it proves noisy.
4. **Licence of shipped blocks.** Recommended: Apache-2.0 like the code (research question 2). Items of
   `fenolite-library` keep their own licences (c0279).

## Relation to the other changes of this batch

- **c0251:** `@block` gains keywords, and `b.port` gains `doc`. The block name of a recorded block is its
  id. Nothing else changes.
- **c0249:** a new lock section through `LockSection`, and one more case for "a lock exists".
- **c0259:** the same header vocabulary and version discipline, applied to code records. A block is not a
  c0259 record kind and has no TOML form.
- **c0266:** the same "pin only what is used" rule. c0279's `[library.items]` pins vendored items; this pins block instances.
- **c0269 block-schematic:** independent. It reads ports, not records.
- **c0270 block-tests:** adds `blocks test` and the usage and golden conventions.
- **c0271 block-layouts:** ties a layout to `block` and `block_version` from the model.
- **c0272 starter-blocks:** the first records, sources, pages and `VERSIONS.toml` rows.
- **c0273 block-packages:** the `library` source for blocks vendored from `fenolite-library` (c0279), their record files (from
  `describe`) and `fenolite blocks upgrade`.
