# Design: Fenolite standard component catalog

## Shape

Add `src/fenolite/catalog/` as a data-only, standard-library package. It returns immutable `SymbolDef` and `FootprintDef` objects from Fenolite-authored definitions; it imports only `core` and `model`, never a CAD backend, user files, environment, or network. A manifest maps every public ID to a category, summary, evidence label and source IDs. The initial pack covers generic resistor, capacitor, polarized capacitor and inductor symbols, with 0402/0603/0805/1206 reusable chip lands shared by two-terminal passives. This establishes the catalog and rendering path; additional device families arrive as independently sourced follow-up packs.

`SymbolDef` gains optional ordered body graphics in a neutral value object with integer coordinates. The KiCad symbol reader and writer round-trip line, rectangle, circle and polygon primitives. The DSL `Symbol` builder may declare these primitives in symbol-local nanometres. Existing symbols without graphics retain their current generated rectangle behavior.

The public `fenolite.catalog` API exposes `list_entries(kind=None, query=None)`, `get_symbol(lib_id)`, `get_footprint(lib_id)`, and immutable entry metadata. IDs live under `Fenolite:` and remain stable. The first catalog is deliberately generic: schematic pin numbers/names are part of the symbol definition; package selection remains explicit on `Part.footprint` where one symbol could use multiple packages.

`fenolite.cli` adds `fenolite catalog list` and `fenolite catalog show ID`, returning the standard JSON envelope and the source/evidence metadata without invoking a backend. The KiCad target of `fenolite build` merges catalog definitions with project-authored definitions, where project definitions win on an exact ID match, then uses the existing authored-library writers and project vendoring. The resulting KiCad project contains the actual definitions it uses and needs no global library table or network for those entries.

Physical source facts are recorded in `docs/catalog/README.md` and `docs/catalog/sources.md`, with public source IDs in `docs/evidence/sources.md`; no employer or private-project facts enter the repository. Geometry authored by Fenolite but not prescribed by a source is `INFERRED`, not promoted by writer round-trip.

## Files

- Create `src/fenolite/catalog/__init__.py` and tests under `tests/unit/catalog/`.
- Extend `SymbolDef`, `dsl.Symbol`, the canonical library schema and KiCad symbol reader/writer for reusable body graphics; update package-layering and design-model specifications.
- Extend `src/fenolite/cli/` command registration and `src/fenolite/cli/cmd_build.py` to list/show and resolve built-ins.
- Add normative requirements in `openspec/specs/fenolite-component-catalog/spec.md` and this change's delta.
- Add public-source/provenance documentation in `docs/catalog/`, register sources, update `docs/roadmap.md`, `docs/cli-contract.md`, and `CHANGELOG.md`.

## Evidence and safety

- Registry identity, metadata, search and deterministic ordering: Fenolite-authored unit tests (`INFERRED`).
- Symbol and footprint writer/readback, and build without external libraries: Fenolite-authored round-trip/build tests (`INFERRED`).
- Package dimensions/pitches and symbol pin identities: public manufacturer datasheets or standards, cited per entry; evidence level cannot exceed the source's support.
- No `kicad-cli` is used as a data source. No official CAD-library file is committed.

## Budget

8 design-days for the catalog API, build integration and first useful generic pack; coverage then grows in separately reviewable catalog-data changes.
