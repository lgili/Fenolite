# Design

The DSL `Symbol(library, name, *, reference, value="", footprint="", description="")` owns an ordered set of pins added with `pin(number, name, *, etype, at, length, rotation=0, shape="line")`. Lengths use DSL exact units. `Design.add(symbol)` attaches symbols by `library:name`, rejecting duplicate IDs. `to_model` remains the design model conversion boundary; authored definitions are carried separately from the model so canonical design JSON is not expanded with library data.

The build receives authored symbol definitions as an explicit argument. They override no external data: if an authored ID conflicts with a resolvable library row, fail with a clear duplicate-source finding. Otherwise, use the definition to resolve circuit pins and references. The KiCad build writes a standalone `.kicad_sym` library and a project `sym-lib-table` row for its nickname. The library writer serializes only the authored subset of the existing `SymbolDef` model; unsupported constructs are absent from this DSL and cannot be silently dropped.

The custom symbol writer follows documented KiCad symbol-library syntax, cites the existing public source row in `docs/evidence/sources.md`, and labels generated output `INFERRED` until verified by KiCad oracle coverage.
