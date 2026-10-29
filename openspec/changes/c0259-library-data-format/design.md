## Context

- **Source.** `docs/research/component-library.md`, sections 2 (how LibrePCB, Horizon EDA, KiCad and
  Altium 365 organise their libraries), 3 (where Fenolite is) and 4.1 ("Five records, data files, stable
  ids"). Concepts only: ids that are never reused, an interface that never changes in place, semantic
  versions, part inheritance for orderable variants, a stable-id cache keyed by kind and name. No schema,
  file, element name or constant of those tools is taken.
- **What exists on `dev` (0.6.0).**
  - `src/fenolite/catalog/__init__.py` (1 796 lines) and `_symbol_expansion.py` (435 lines) build 49
    `SymbolDef` and 100 `FootprintDef` from `_SymbolSpec` tuples, `_FOOTPRINT_SPECS` and per-family
    dimension tables in µm (`_QFN_LANDS_UM`, `_DIP_BODIES_UM`, …), dispatched by `_symbol_graph(name)` and
    `_footprint(name)`. Every entry is `INFERRED` and cites `S-` ids.
  - Model ids are already stable: `derived_id("sym", "fenolite.catalog", "Fenolite:<name>")`,
    `derived_id("fpd", …)`, pads `derived_id("pad", "fenolite.catalog", "<name>:<pad key>")`, graphics
    `"<name>:<layer>"` or `"<name>:<tag>"` (`cathode`, `actuator`, …). A UUIDv5 of a text key
    (`fenolite.core.ids`).
  - `default_pad_map` joins `ANODE_FIRST_SYMBOLS` with `CATHODE_FIRST_LANDS` (c0144, c0147).
  - `tools/catalog/render_symbols.py` and `render_footprints.py` draw review sheets from `get_*`.
- **What this batch adds before this change.** c0248: `fenolite.device.v0`, `catalog/devices.py`,
  `parse_device`, `device_text`, `device_digest`, project devices in `devices/*.toml`, precedence and
  provenance. c0249: the design lock. c0254: `fenolite.family.v0`, `CATALOG_VERSION` and
  `catalog/families/VERSIONS.toml`. c0246: exact `Range`.
- **Licensing** (research section 1; maintainer decision of 2026-10-29). Ship only data authored for
  Fenolite from public facts, or data whose licence is CC0-1.0, with its origin recorded. CC-BY-SA
  libraries (KiCad, Horizon EDA), libraries with other terms (SnapMagic, Ultra Librarian, SamacSys,
  EasyEDA) and manufacturer CAD files stay out of shipped data; they are only imported locally (c0264).

## Goals / Non-Goals

**Goals**

- Every library record is a reviewable TOML file with a stable id, a version, a licence, sources,
  evidence and reviews.
- An interface never changes under an id. A changed definition always changes its version.
- Orderable variants (packing, grade) are written once on top of their device.
- The shipped catalog becomes data with no output change: same definitions, same bytes.
- The same parser reads shipped records, project records and (c0266) pack records.

**Non-Goals**

- See the proposal. In addition: no change of a catalog entry's geometry or metadata (the move is
  mechanical), no new catalog entry, no change to how KiCad or Altium libraries are read.

## Decisions

### 1. Four record kinds and a common header

| kind | schema | gives | file in the tree |
|---|---|---|---|
| pins | `fenolite.pins.v0` | a pin table; with `[symbol]`, a `SymbolDef` | `pins/<name>.toml` |
| package | `fenolite.package.v0` | dimensions; with `generator = "explicit"`, a `FootprintDef` | `packages/<name>.toml` |
| device | `fenolite.device.v1` | c0248's `DeviceDef`, plus parts | `devices/<name>.toml` |
| part | `fenolite.part.v0` | orderable variants of a device kept apart | `parts/<name>.toml` |

Families (c0254 `fenolite.family.v0`, c0263) live in `families/` of the same tree and take the same
header when c0263 lands. The research also names a separate symbol record; here the drawing is the
optional `[symbol]` table of a pins record, so that a symbol never draws pins it does not define.

**Common header** (every kind):

| key | required | meaning |
|---|---|---|
| `schema` | yes | the kind and format version |
| `id` | yes | canonical name `<namespace>:<name>`, each part `[A-Za-z0-9_.+-]+` (c0248's rule). For pins and packages it is the lib id of the symbol or footprint they give |
| `version` | yes | `MAJOR.MINOR.PATCH`, decimal, no leading zeros (decision 3) |
| `summary` | yes | one printable line |
| `category` | no | catalog category (today's `CatalogEntry.category`) |
| `licence` | yes | an SPDX expression (decision 5) |
| `evidence` | yes | one label of the evidence vocabulary |
| `sources` | yes for `Fenolite:` and pack records | a list of source ids, or a table key → list of source ids (c0254's per-attribute form) |
| `origin` | no | where a record taken from a CC0 library came from (decision 5) |
| `reviewed_by` | no | list of reviews (decision 6) |
| `replaces` | no | the id this record succeeds after an interface change (decision 4) |
| `deprecated` | no | `{ by = "<id>", since = "<version>", reason = "<text>" }` |

Any other top-level key gives `FEN-3004` naming the file and the key; a higher schema version gives
`FEN-3002`. TOML is read with `tomllib` and `parse_float=Decimal`; no float is created.

**Lengths and angles.** Text with a unit, parsed exactly by `fenolite.core.quantities` (c0248):
`"1.27mm"`, `"500um"`, `"25mil"`, `"90deg"`. A length that is not a whole number of nm, or an angle that is
not a whole number of µdeg, gives `FEN-3004`. Points are two-element arrays (`at = ["-0.8mm", "0mm"]`).
Dimensions that are tolerances (`body.length = "4.80mm..5.00mm"`) read as c0246 ranges when c0246 is
merged; until then the parser keeps their exact text and bounds as integers.

### 2. Stable ids

- `record_uid(kind, id) -> str` is `str(uuid.uuid5(FENOLITE_NS, f"fenolite.library:{kind}:{id}"))`.
  It is computed, never stored: the file holds only `id`, so a record cannot claim another record's uid.
  `catalog show`, `catalog list`, the build result and the design lock (c0254, c0266) show it.
- **Model ids stay as they are.** A pins record gives `SymbolDef.id = derived_id("sym",
  "fenolite.catalog", id)`; a package gives `derived_id("fpd", …)`; its pads `derived_id("pad",
  "fenolite.catalog", "<name>:<key>")` where `key` defaults to the pad number; its graphics
  `"<name>:<key>"` where `key` defaults to the layer. The migration writes `key` only where today's code
  uses another text (a second pad of one number, `cathode`, `actuator`, `pin1`). This is what makes the
  move byte-identical: ids depend on names and keys, never on file order.
- **The same id in two files of one tree** gives `FEN-3004` naming both. Across trees, precedence decides
  (c0248 for project over shipped; c0266 adds packs).
- *Alternative considered:* random UUIDs stored in the file (as LibrePCB does). Rejected: a regenerated
  record would need the stable-id cache that LibrePCB keeps; deriving from `(kind, id)` gives the same
  stability with no cache, and the canonical name is already unique.

### 3. Versions

- **PATCH** when the record's digest changed and its definition did not: summary, sources, evidence,
  reviews, deprecation, part metadata.
- **MINOR** when the definition changed (a land size, a courtyard, a drawing, a new part, a rating) and its
  interface did not.
- **MAJOR** stays `1` for the life of an id. A change that would need it is an interface change, which is
  a new id (decision 4).
- **Digests.** `record_digest(record)`: SHA-256 of the canonical JSON of the parsed record without
  `reviewed_by` (so recording a review does not change what was reviewed). `output_digest(record)`: SHA-256
  of the canonical JSON of the definition it gives (`SymbolDef`, `FootprintDef`, `DeviceDef` and parts).
  `interface_digest(record)`: SHA-256 of its interface (decision 4).
- **`catalog/data/VERSIONS.toml`** holds, per shipped id: `kind`, `version`, `digest`, `output`,
  `interface`, and `removed = true` for an id that was deleted. `tests/unit/catalog/test_versions.py`
  fails when a digest changed and the version did not grow by the rule above, when an interface changed
  under an id, when an id marked `removed` comes back, or when a record is missing from the file. A tool
  mode `tools/catalog/versions.py --update` rewrites the file after a reviewed change.
- **`CATALOG_VERSION`.** c0254 defines it for families. Here it covers every shipped record: it MUST change
  whenever any entry of `VERSIONS.toml` changes. If c0254 is not merged yet, this change adds the constant
  and c0254 then only adds families to the same file (task 0.1 records which).

### 4. Interfaces, new ids and deprecation

| kind | interface |
|---|---|
| pins | the set of `(number, name, type)` of its pins and its units |
| package | the set of pad numbers (unnumbered holes excluded) and `kind` (smd or through-hole) |
| device | `symbol`, `footprint`, and each function with its symbol pins and pads |
| part | its device id and `mpn` |

- An interface change makes a **new record** with a new `id` (the author chooses the name; a suffix is a
  convention, not a rule) and `replaces = "<old id>"`. The old record stays, gains
  `deprecated = { by = "<new id>", since = "<old version + PATCH>", reason = "…" }`, and is not removed
  before one published `CATALOG_VERSION` has carried the deprecation.
- A build that uses a deprecated record gives `library.deprecated` (warning, once per record, naming the
  replacement); the design still builds.
- `replaces` must name a record that exists and is deprecated `by` this id, else `FEN-3004`.
- *Alternative considered:* a revision number in the id (`…#2`). Rejected: lib ids reach KiCad library
  tables and file names, where such characters are awkward, and a name chosen by the author reads better.

### 5. Licence, sources and origin

- `licence` is an SPDX expression. **Shipped records** (`Fenolite:`) MUST be `Apache-2.0` (the licence of
  the package that ships them today) or `CC0-1.0`. **Pack records** (c0266) MUST be `CC0-1.0`. **Project
  records** may hold any text; c0264 writes `LicenseRef-see-source-terms` for imports.
- `sources` hold ids registered in `docs/evidence/sources.md` for shipped records, and ids of the pack's own
  `sources.toml` for pack records (c0266). An unregistered id gives `FEN-3004`.
- **Records from a CC0 library** (maintainer decision 2026-10-29) carry
  `origin = { library = "<name>", version = "<release or 40-hex commit>", element = "<the element's UUID in that library>", licence = "CC0-1.0" }`.
  The record's own `licence` MUST then be `CC0-1.0`, and its `evidence` MUST be `UNVERIFIED` unless
  `reviewed_by` holds a review of the current digest (decision 6). Both are checked when the record is read
  (`FEN-3004`). The source library is also registered in `docs/evidence/sources.md` with its licence.
  Data from a CC-BY-SA library or any other CAD library MUST NOT be shipped (the living requirement is
  changed to say exactly this, see the spec delta).
- *Why `UNVERIFIED`.* A CC0 library's contributors may themselves have taken geometry from a source whose
  licence or accuracy is unknown. The record is usable, shown as unconfirmed, and c0262's checks plus a
  human review are what raise it.

### 6. Reviews

```toml
[[reviewed_by]]
who = "maintainer-handle"          # a person, never an e-mail address
date = "2026-10-29"
version = "1.0.0"
digest = "3b1f…"                   # record_digest at review time
evidence = "CORPUS-VERIFIED"       # the label the reviewer asserted
sheet = "reviews/Fenolite/Chip_0603/1.0.0.svg"   # optional, relative to the tree
```

- A review whose `digest` differs from the current `record_digest` is **stale**: `library.review-stale`
  (info) when the record is used, and it no longer supports a label above `UNVERIFIED` for an `origin`
  record. c0262 owns the command that writes a review and the rule by which a review raises a label; this
  change only defines and checks the entry.

### 7. Pins records and the explicit symbol drawing

```toml
# src/fenolite/catalog/data/pins/Resistor.toml   (as the migration writes it)
schema = "fenolite.pins.v0"
id = "Fenolite:Resistor"
version = "1.0.0"
summary = "Generic two-terminal resistor"
category = "Passive"
licence = "Apache-2.0"
evidence = "INFERRED"
sources = ["S-0314", "S-0343"]

[[pin]]
number = "1"
name = "~"
type = "passive"

[[pin]]
number = "2"
name = "~"
type = "passive"

[symbol]
reference = "R"
pin_names_hidden = true
pins = [
  { number = "1", at = ["0mm", "3.81mm"], rotation = "270deg", length = "1.27mm" },
  { number = "2", at = ["0mm", "-3.81mm"], rotation = "90deg", length = "1.27mm" },
]

[[symbol.graphic]]
kind = "rect"
points = [["-1.016mm", "-2.54mm"], ["1.016mm", "2.54mm"]]
width = "0.254mm"
```

- `[[pin]]`: `number`, `name`, `type` (the `PinType` names), and optional `shape`, `hidden`, `unit`,
  `group` (used by c0261's layout rule), `alternates`. Numbers are unique.
- `[symbol]`: `reference`, `value` (default the name part of `id`), `pin_names_hidden`,
  `pin_numbers_hidden`, `pin_name_offset`, `units`, `pins` (one placement per pin number, every pin
  placed once) and `[[symbol.graphic]]` (`kind`, `points`, `width`, `filled`, the fields of
  `SymbolGraphic`). The `SymbolDef` gets `properties = {Reference, Value, Description = summary}` as today.
- `polarity = "anode-first"` on a pins record replaces the tuple `ANODE_FIRST_SYMBOLS`, which stays public
  and is computed from the records.
- A pins record without `[symbol]` is valid data; asking for its symbol gives `library.generator-missing`
  until c0261 provides the generator.

### 8. Package records

```toml
# src/fenolite/catalog/data/packages/Chip_0603.toml   (as the migration writes it)
schema = "fenolite.package.v0"
id = "Fenolite:Chip_0603"
version = "1.0.0"
summary = "Chip 0603 two-terminal land"
category = "Chip passive"
licence = "Apache-2.0"
evidence = "INFERRED"
sources = ["S-0314"]
generator = "explicit"
kind = "smd"
body = { length = "1.6mm", width = "0.8mm" }

[[pad]]
number = "1"
shape = "rect"
size = ["0.9mm", "1mm"]
at = ["-0.8mm", "0mm"]
layers = ["F.Cu", "F.Paste", "F.Mask"]

[[pad]]
number = "2"
shape = "rect"
size = ["0.9mm", "1mm"]
at = ["0.8mm", "0mm"]
layers = ["F.Cu", "F.Paste", "F.Mask"]

[[graphic]]
kind = "rect"
layer = "F.Fab"
points = [["-0.8mm", "-0.4mm"], ["0.8mm", "0.4mm"]]
width = "0.1mm"

[[graphic]]
kind = "rect"
layer = "F.CrtYd"
points = [["-1.75mm", "-1.0mm"], ["1.75mm", "1.0mm"]]
width = "0.05mm"
```

(Illustrative numbers; the migration writes what today's code computes.)

- `generator`: `"explicit"` (pads and graphics written out) or a family name of c0260 (`"chip"`,
  `"gullwing"`, `"nolead"`, …). A family package without its generator gives `library.generator-missing`
  at use. The dimension keys (`pins`, `pitch`, `body`, `span`, `lead`, `[land]`) are those of research 4.2
  and are only stored and range-checked here; c0260 defines what they produce.
- `[[pad]]` keys mirror `fenolite.model.board.Pad`: `number`, `key`, `shape`, `size`, `at`, `kind`,
  `rotation`, `drill`, `layers`, `corner_ratio`, `mask_margin`, `paste_margin`, and the padstack and slot
  forms the catalog uses. `[[graphic]]` mirrors `Graphic`: `key`, `kind`, `layer`, `points`, `width`,
  `filled`. An unknown key gives `FEN-3004`.
- `pad1 = "cathode"` replaces the tuple `CATHODE_FIRST_LANDS`, which stays public, computed from the
  records. `default_pad_map` keeps its result.
- The footprint description is `summary + "; land pattern remains INFERRED and requires part-specific
  review"` when `evidence` is `INFERRED`, exactly the text of today (living "Source and evidence labels").

### 9. Devices and parts

`fenolite.device.v1` is c0248's `v0` plus the common header (`version`, `licence`, `category`,
`reviewed_by`, `origin`, `replaces`, `deprecated`) and `[[part]]`. `symbol` names a pins record's id (or any
lib id), `footprint` a package record's id (or any lib id), as in `v0`. `v0` files are still read: they
have version `0.0.0` and licence unset, which is refused for `Fenolite:` records and shown as `unknown` for
project records; `fenolite fmt`-style rewriting is not added (open question 3).

```toml
schema = "fenolite.device.v1"
id = "Example:BUCK_6V_2A"
version = "1.1.0"
summary = "6 V 2 A step-down regulator (illustrative, authored for Fenolite)"
licence = "CC0-1.0"
evidence = "UNVERIFIED"
sources = ["S-9xxx"]
manufacturer = "Example Semi"
mpn = "EXB6202"
symbol = "Example:Buck_6pin"
footprint = "Fenolite:SOT23_6_TI_DBV0006A"
# … c0248's pins, ratings …

[[part]]
mpn = "EXB6202DR"
packing = "reel 2500"
lifecycle = "active"

[[part]]
mpn = "EXB6202QDRQ1"
extends = "EXB6202DR"
grade = "automotive"
ratings = { temperature = { min = "-40degC", max = "125degC" } }
```

- **Part keys** (inline or in `fenolite.part.v0`, which adds the header and `device = "<id>"`): `mpn`
  (required, unique within the device), `extends` (another part's `mpn` of the same device), `manufacturer`,
  `packing`, `lifecycle` (`active`, `nrnd`, `last-time-buy`, `obsolete`, `unknown`), `grade`, `datasheet`,
  `properties`, `ratings`, `summary`.
- **Inheritance.** The effective part is the device, then each ancestor of the `extends` chain from the
  root, then the part; a later level replaces a key, and `properties` merge by key. A cycle or an
  unknown `extends` gives `FEN-3004`.
- **No interface in a part.** `symbol`, `footprint`, `pins`, `ground`, `unused_pads`, `ends`, `ref_prefix`
  in a part give `FEN-3004` with the hint "a different interface is a different device".
- **Narrowing only.** A part rating must lie within the device's rating of the same key (a part may state a
  narrower temperature, never a wider one); a wider one gives `FEN-3004`.
- **Placing a part.** `design.part(device="Example:BUCK_6V_2A@EXB6202DR")` uses the device and writes the
  part's `MPN`, `Manufacturer`, `Datasheet` and properties. The plain device id keeps c0248's behaviour.
  The part's uid is `record_uid("part", "<device id>@<mpn>")`. `@` cannot occur in an id part, so this
  never collides; c0254 uses the same separator for family values.

### 10. Trees and loading

- `fenolite.catalog.records`:
  - `parse_record(text, *, file) -> Record` (pure; `Record` is a frozen union of `PinsRecord`,
    `PackageRecord`, `DeviceRecord`, `PartRecord`);
  - `record_text(record) -> str`: canonical TOML (fixed key order per kind, arrays of tables in id or
    number order, LF, one final newline). `parse_record(record_text(r)) == r`;
  - `record_uid`, `record_digest`, `output_digest`, `interface_digest`;
  - `load_tree(root) -> LibraryTree(records, issues)`: every `*.toml` below `root` in POSIX path order,
    the kind taken from `schema`; part files joined to their devices;
  - `shipped_tree()`: the package data under `catalog/data/`, read once (cached) through
    `importlib.resources`.
- `fenolite.catalog` keeps `CatalogEntry`, `ENTRIES`, `list_entries`, `get_symbol`, `get_footprint`,
  `default_pad_map`, `ANODE_FIRST_SYMBOLS`, `CATHODE_FIRST_LANDS`, `CATHODE_FIRST_PAD_MAP`. `ENTRIES` is
  computed lazily from `shipped_tree()` through a module `__getattr__`. `CatalogEntry` gains `version`,
  `licence` and `uid` (with defaults, so positional construction keeps working).
- **Project records.** c0248's runner reads `devices/*.toml`; it now reads `devices/` recursively with
  `load_tree`, and any kind is allowed there. A project pins or package record whose id is a catalog lib
  id overrides it for that build, labelled `authored`, as an authored symbol does today.
- **Layering.** `catalog` → `model`, `core` only, as today. No new edge.

### 11. The move, byte for byte

1. **Golden first.** Before any data file exists, `tools/catalog/golden.py` writes
   `tests/data/catalog/golden.json`: per lib id, `output_digest` of today's definition, and the SHA-256 of
   each file `fenolite build` writes for `examples/catalog*` with `--seed 1 --timestamp …`. It is reviewed
   and committed on its own.
2. **Write the data.** `tools/catalog/to_data.py` calls today's `get_symbol` / `get_footprint` and writes one
   pins or package record per entry with `record_text`, lengths in mm with the fewest digits that are
   exact, keys only where the default key differs, `version = "1.0.0"`, `licence = "Apache-2.0"`.
3. **Switch.** `get_symbol` and `get_footprint` read the records. `tests/unit/catalog/test_golden.py`
   compares every definition with `golden.json`; the KiCad job rebuilds the examples and compares bytes.
4. **Delete.** The geometry functions, tables and `_symbol_expansion.py` are removed; `to_data.py` is
   removed (git history keeps it). `golden.json` stays as the guard of later refactors and is updated only
   together with a version bump in `VERSIONS.toml`.

The render tools and the catalog browser use `get_*` and need no change; their outputs are compared too.

### 12. Codes

| code | severity / exit | when |
|---|---|---|
| `library.deprecated` | warning | a build uses a deprecated record; names the replacement |
| `library.review-stale` | info | a used record's newest review is of another digest |
| `library.generator-missing` | error | a pins or package record without explicit geometry is used and its generator is not available |
| `FEN-3004` | exit 3 | malformed record, unknown key, duplicate id, bad licence, origin rules, inheritance errors |
| `FEN-3002` | exit 3 | a newer record schema |

The `library.*` prefix is shared with c0223 (`library.drift`, …) and c0262 (rule codes). c0262 must not
reuse these three names.

## Risks / Trade-offs

- **150 small files instead of two modules.** More files to review, but each diff is one record, which is
  the point. Load time is kept by reading the tree once per process (a test budgets it under 150 ms on CI).
- **Explicit geometry is verbose.** It is the honest form of what the code computes today. c0260 replaces
  it by family generators where the generator reproduces the bytes, or with a MINOR version bump and a
  reviewed visual diff (c0262).
- **Licence of the shipped records.** Writing `Apache-2.0` keeps today's terms; moving them to CC0 needs the
  maintainer's decision as copyright holder (open question 1).
- **`v0` device files.** Reading them as `0.0.0` avoids breaking c0248 projects; shipped devices are
  rewritten as `v1` in this change.

## Open questions

1. *Licence of the shipped catalog records: keep `Apache-2.0` or dedicate them to CC0?* Recommended: CC0-1.0,
   so records move freely between the core and the `fenolite-devices` pack (c0266); until decided the
   migration writes `Apache-2.0`.
2. *May a project record use the `Fenolite:` namespace?* Recommended: yes, as an override, as c0248 decided
   for devices.
3. *Should `fenolite fmt` rewrite `v0` device files as `v1`?* Recommended: yes, in a follow-up; not needed
   for this change.
4. *Should the review `who` be checked against a list (CODEOWNERS)?* Recommended: in the data repository
   only (c0266); the core cannot know reviewers.

## Relation to the batch

- **c0248**: the device record becomes `v1`; precedence and project folder are reused, made recursive.
- **c0249 / c0254**: picks record `record_uid` and `record_digest`; `CATALOG_VERSION` covers all records.
- **c0260**: implements `generator = "<family>"` for packages, adds bodies and STEP.
- **c0261**: implements symbols for pins records without `[symbol]`, multi-unit and derived symbols.
- **c0262**: `fenolite library check` and reviews; writes `reviewed_by` and raises labels.
- **c0263**: family grammars take the common header.
- **c0264**: imports write project records with `licence = "LicenseRef-see-source-terms"` and provenance.
- **c0265**: proposals write pins and package records with `UNVERIFIED`.
- **c0266**: pack records (`CC0-1.0`, pack sources), precedence with packs, the LibrePCB seed converter that
  writes `origin`.
- **c0267**: supplier lookups never write records.
