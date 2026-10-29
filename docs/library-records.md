# Library records

Fenolite's library is data: every symbol, footprint, device and orderable part is a TOML **record** with a
stable id, a version, a licence, its evidence and its sources (change c0259). The shipped catalog lives under
`src/fenolite/catalog/data/` (`pins/`, `packages/`, `devices/`); a project keeps its own records in
`devices/` beside the design script, in any sub-folder. `fenolite.catalog.records` reads, writes and checks
them; `fenolite.catalog.get_symbol`, `get_footprint`, `list_entries` and `ENTRIES` read the shipped tree.

## Kinds

| kind | schema | gives | folder |
|---|---|---|---|
| pins | `fenolite.pins.v0` | a pin table; with `[symbol]`, a symbol | `pins/` |
| package | `fenolite.package.v0` | dimensions; with `generator = "explicit"`, a footprint | `packages/` |
| device | `fenolite.device.v1` | a device (`docs/devices.md`) and its orderable parts | `devices/` |
| part | `fenolite.part.v0` | one orderable variant of a device, in its own file | `parts/` |

The folders are a convention: the kind comes from `schema`. Change c0248's `fenolite.device.v0` files are
still read, with version `0.0.0` and no licence; a shipped device is always `v1`.

## The header

Every record starts with the same keys:

| key | required | meaning |
|---|---|---|
| `schema` | yes | the kind and its format version; a higher version gives `FEN-3002` |
| `id` | yes | `<namespace>:<name>`, each part `[A-Za-z0-9_.+-]+`; for pins and packages, the lib id they give; for a part file, `<device id>@<mpn>` |
| `version` | yes | `MAJOR.MINOR.PATCH`, no leading zeros |
| `summary` | yes | one printable line |
| `category` | no | the catalog category |
| `licence` | yes | an SPDX expression |
| `evidence` | yes | one label of the evidence vocabulary |
| `sources` | for `Fenolite:` | source ids of `docs/evidence/sources.md`, a list or a table attribute → list |
| `origin` | no | where a record taken from a CC0-1.0 library came from |
| `replaces` | no | the id this record succeeds after an interface change |
| `deprecated` | no | `{ by = "<id>", since = "<version>", reason = "<text>" }` |
| `reviewed_by` | no | the reviews, as `[[reviewed_by]]` tables |

Any other key, a missing key or a wrong type gives `FEN-3004`, naming the file and the key. TOML is read
with no float: lengths and angles are text with a unit, `"1.27mm"`, `"500um"`, `"25mil"`, `"90deg"`, parsed
exactly to integer nanometres and microdegrees (`"0.0000001mm"` is refused).

## Ids

`record_uid(kind, id)` is a UUIDv5 of `fenolite.library:<kind>:<id>` in Fenolite's namespace. It is computed,
never stored, so a regenerated record keeps it. The definitions keep the model ids of the catalog before the
move: `derived_id("sym" | "fpd", "fenolite.catalog", id)`, and pads and graphics keyed by `<name>:<key>`,
where `key` is the pad number or the graphic's layer unless the record names another. Two records of one
kind and id in one tree give `FEN-3004` naming both files.

## Versions and interfaces

- **PATCH**: the record changed and its definition did not (summary, sources, evidence, deprecation, part
  metadata).
- **MINOR**: the definition changed (a land, a courtyard, a drawing, a part, a rating) and its interface did
  not.
- **MAJOR** stays `1` for the life of an id.

The interface is: for pins, the pins' numbers, names, types and units; for a package, its pad numbers and
kind; for a device, its symbol, footprint and functions with their pins and pads; for a part, its device and
MPN. An interface never changes under an id: the successor is a new record with `replaces`, the old one gains
`deprecated`, and a build that uses it reports `library.deprecated` (warning) naming the successor.

`src/fenolite/catalog/data/VERSIONS.toml` records each shipped id's kind, version and three digests:
`record_digest` (the canonical JSON of the record without its reviews), `output_digest` (the definition it
gives) and `interface_digest`. `tests/unit/catalog/test_versions.py` fails when a record changed without the
version the rules ask for, when an interface changed under an id, or when a removed id comes back;
`uv run python tools/catalog/versions.py --update` rewrites the file after a reviewed change and raises the
catalog version (`fenolite.catalog.CATALOG_VERSION`).

## Licences and origin

Shipped records are `Apache-2.0` or `CC0-1.0`. A record taken from a library whose licence is CC0-1.0 holds
`origin = { library, version, element, licence = "CC0-1.0" }`, is itself `CC0-1.0`, and stays `UNVERIFIED`
until a review of its current digest is recorded: the origin is not evidence. Data from a CC-BY-SA library
or any other CAD library is never shipped.

## Reviews

```toml
[[reviewed_by]]
who = "maintainer-handle"
date = "2026-10-29"
version = "1.0.0"
digest = "…"            # record_digest of the record as it is after the review
evidence = "CORPUS-VERIFIED"
```

`who` names a person, never an e-mail address. A review whose digest is not the record's current digest is
stale: a build that uses the record reports `library.review-stale` (info).

## Pins records

```toml
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
name = "A"
type = "passive"

[[pin]]
number = "2"
name = "B"
type = "passive"

[symbol]
reference = "R"
pin_names_hidden = true
pins = [
  { number = "1", at = ["-5.08mm", "0mm"], length = "2.54mm" },
  { number = "2", at = ["5.08mm", "0mm"], rotation = "180deg", length = "2.54mm" },
]

[[symbol.graphic]]
kind = "line"
points = [["-2.54mm", "0mm"], ["-1.905mm", "1.05mm"]]
```

`[[pin]]` takes `number`, `name`, `type`, and optionally `shape`, `hidden`, `unit`, `group`, `alternates`.
`[symbol]` places every pin exactly once and lists its graphics; the symbol's properties are `Reference`,
`Value` (default the name part of the id) and `Description` (the summary). `polarity = "anode-first"` marks
the two-pin symbols with pin 1 at the anode. A pins record without `[symbol]` is valid data; a build that uses
it reports `library.generator-missing` (error) until a symbol generator exists.

## Package records

`generator = "explicit"` lists the lands: `[[pad]]` (`number`, `key`, `shape`, `size`, `at`, `kind`,
`rotation`, `drill`, `layers`, `corner_ratio`, `mask_margin`, `padstack`) and `[[graphic]]` (`key`, `kind`,
`layer`, `points`, `width`, `filled`). The dimension keys `pins`, `pitch`, `body`, `span`, `lead` and `land`
are stored (a range is `"4.80mm..5.00mm"`); a family generator (`generator = "gullwing"`, …) gives
`library.generator-missing` at use until its change lands. `pad1 = "cathode"` marks the lands that keep pad 1
at the cathode. An `INFERRED` footprint's description ends with "; land pattern remains INFERRED and requires
part-specific review".

## Devices and parts

A `fenolite.device.v1` record is the device of `docs/devices.md` with the header and `[[part]]` tables:

```toml
[[part]]
mpn = "EXB6202DR"
packing = "reel 3000"
lifecycle = "active"
```

A part takes `mpn` (unique within the device), `extends`, `summary`, `manufacturer`, `packing`, `lifecycle`
(`active`, `nrnd`, `last-time-buy`, `obsolete`, `unknown`), `grade`, `datasheet`, `properties` and `ratings`.
It inherits the device, then each ancestor of its `extends` chain, then its own keys; properties merge by key.
A part never holds `symbol`, `footprint`, `pins`, `ground`, `unused_pads`, `ends` or `ref_prefix` (a different
interface is a different device), and its ratings only narrow the device's. A `fenolite.part.v0` file keeps
one part apart, with the header and `device = "<id>"`.

`design.part("U1", device="Example:BUCK_6V_2A@EXB6202DR")` places the device as that part: the component gets
the part's `MPN`, `Manufacturer`, `Datasheet` and properties. An unknown MPN raises `DslError` listing the
device's parts.

## Trees and precedence

`load_tree(root)` reads every `*.toml` below a folder in POSIX path order and joins part files to their
devices; `shipped_tree()` reads the shipped catalog once per process. The records of `devices/` beside a
script override shipped ones per id: a project package with a catalog lib id replaces that footprint for the
build, and the build reports its origin as `authored`. The files of `devices/` are inputs of `build`
(`result.device_files`).

## The move from Python

`tests/data/catalog/golden.json` was written from the Python catalog before the move
(`tools/catalog/golden.py`): the canonical JSON digest of every definition, the two review sheets and the
built files of `examples/catalog`. The records give the same bytes; the file changes only together with a
version change in `VERSIONS.toml`.
