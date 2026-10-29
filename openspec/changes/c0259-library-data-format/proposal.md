## Why

The shipped catalog is Python: 49 symbols and 100 footprints written as tuples and dimension tables with
an `if/elif` dispatch in `src/fenolite/catalog/__init__.py` and `_symbol_expansion.py`. A record cannot be
reviewed, versioned, deprecated or licensed on its own, nothing says which version of a footprint a design
was built with, and adding a part means editing code. c0248 adds TOML device records, and c0254 adds TOML
family records, but symbols and footprints stay code, and no record has a version or a licence.

Research section 4.1 of `docs/research/component-library.md` proposes one data format for the whole
library, after LibrePCB and Horizon EDA (concepts only): **pins**, **package**, **device** and **part**
records as TOML files, each with a stable id, a semantic version, a licence, its sources, its evidence and
its reviews; an interface change makes a new id and deprecates the old one. The later library changes
(c0260 to c0267) all read and write this format, and c0266 ships it in a separate data repository.

The maintainer decided on 2026-10-29 that data from a source whose licence is CC0-1.0, such as the
LibrePCB official libraries, may seed the data, openly and with its origin recorded. The living catalog
requirement forbids copying from any other CAD library, so it is changed here.

## What Changes

- **Four record kinds, one header.** `fenolite.pins.v0` (a pin table, with an optional explicit symbol
  drawing), `fenolite.package.v0` (dimensions, or explicit lands and graphics, giving a footprint),
  `fenolite.device.v1` (c0248's `v0` with the header and orderable parts) and `fenolite.part.v0` (an
  orderable variant kept in its own file). Every record carries `id`, `version`, `summary`, `licence`,
  `evidence`, `sources`, and may carry `reviewed_by`, `origin`, `replaces` and `deprecated`.
- **Stable ids.** `id` is the canonical name `<namespace>:<name>`. `record_uid(kind, id)` is a UUIDv5 of
  `(kind, id)` in Fenolite's namespace, so regenerating a record keeps it. Model ids stay derived from the
  lib id as today, so no built file changes.
- **Versions and interfaces.** `version` is `MAJOR.MINOR.PATCH`. PATCH: text, sources, evidence or
  reviews changed and the definition did not; MINOR: the definition changed and its interface (pin
  numbers, names and types; pad numbers; functions and their pins and pads) did not. MAJOR stays `1` for
  the life of an id: an interface change is a new id with `replaces`, and the old record gets
  `deprecated`. `catalog/data/VERSIONS.toml` records each shipped id's version, digest, interface digest
  and output digest; a test enforces the rules and refuses the reuse of a removed id.
- **Parts and inheritance.** A device holds `[[part]]` tables (or `fenolite.part.v0` files point to it).
  A part inherits everything from its device and may set only orderable facts: `mpn`, `manufacturer`,
  `packing`, `lifecycle`, `grade`, `datasheet`, `properties`, and ratings that narrow the device's.
  `extends` chains parts. A part's id is `<device id>@<mpn>`, and `design.part(device="X@MPN")` places it.
- **Licence and origin.** Shipped records are `CC0-1.0` (the maintainer's decision of 2026-10-29); a record taken from a CC0 source
  carries `origin` (library, version or commit, the original element's UUID), `licence = "CC0-1.0"` and
  stays `UNVERIFIED` until a review of its current digest (c0262) is recorded.
- **The catalog moves to data, byte for byte.** `src/fenolite/catalog/data/{pins,packages,devices,parts}/`
  holds one file per record; the Python tables and geometry functions are deleted. `get_symbol`,
  `get_footprint`, `list_entries`, `ENTRIES`, `default_pad_map` and the CLI keep their names; every
  definition's canonical JSON and every build output of the catalog examples stay byte-identical, proved
  by a golden digest file written before the move.
- **Project records.** The project folder `devices/` of c0248 is read recursively and may hold all four
  kinds; project records override shipped ones per id.
- **Codes.** `library.deprecated` (warning), `library.review-stale` (info), `library.generator-missing`
  (error).

## Non-goals

- No generator: package and pins records without explicit geometry are accepted by the parser and refused
  at use with `library.generator-missing` until c0260 (footprints) and c0261 (symbols) land.
- No `fenolite library check`, review command or visual diff (c0262); this change only defines the
  `reviewed_by` entry those write.
- No family grammar (c0254 owns `fenolite.family.v0`, c0263 extends it); families join the same tree.
- No data repository, fetch or pack precedence (c0266). No import of user files (c0264).
- No seeding from LibrePCB here: the converter is c0266's. No STEP bodies (c0260).

## Evidence level required

- Parsing, ids, digests, versions and inheritance: `INFERRED`, unit-tested (`H-G-LIBRARY-RECORDS`).
- The move: every shipped definition equal to its golden canonical JSON digest, and the KiCad builds of the
  catalog examples byte-identical (`H-K-CATALOG-DATA`, KiCad job in CI).
- Each record keeps its own label; nothing here raises one.

## Impact

- New: `src/fenolite/catalog/records.py`, `catalog/data/` (about 150 TOML files and `VERSIONS.toml`),
  `tools/catalog/to_data.py` (deleted again in the last phase), `tests/data/catalog/golden.json`,
  `docs/library-records.md`, tests under `tests/unit/catalog/`.
- Changed: `catalog/__init__.py` (data-backed), `catalog/devices.py` (c0248; reads `v1`), `cli/cmd_catalog.py`
  (additive keys `uid`, `version`, `licence`), `cli/_script.py` (recursive `devices/`), `lens/build.py`
  (codes), `docs/devices.md`, the guide page `parts.md`, `CHANGELOG.md`.
- Removed: `catalog/_symbol_expansion.py` and the geometry tables of `catalog/__init__.py`.
- Depends on: c0248 (device records, project folder). Uses c0246's `Range` for package dimensions when it
  is merged. c0254 and c0263 put families in the same tree. c0260 to c0267 build on it.
- Size: about 7 design-days (M).
