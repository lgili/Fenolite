# ADR-0001: Neutral model — small now, frozen after the second backend

## Status
Accepted (2026-09-30)

## Context
Every backend, check and export in Fenolite reads and writes one in-memory model. Toolkits built
around a single EDA tool end up shaped like that tool, and a second backend then does not fit.
The two target tool families use different units (integer nanometres in one; integer units of
1/10 000 mil, i.e. 2.54 nm, in the other), different identifier schemes (UUIDs on most objects in
one; eight-letter ids on components and none on many primitives in the other), and one of them
rejects unknown tokens on load, so extension data cannot be stored inside its files.

## Decision
1. The model is **small** at first (circuit, board, rules, manufacturing, findings for v0.1;
   schematic presentation arrives with the schematic backend) and grows per change, driven by real
   files. It becomes additive-only at the end of v0.3 and is frozen with migrators at 1.0.
2. Every entity carries the header `{id, native_ids, provenance, ext}`.
3. **Units:** lengths are `int` nanometres; angles are `int` microdegrees; no floats anywhere in the
   model. Conversion to the 1/10 000 mil unit is integer-only with round-half-even; it is lossy by
   at most 0.5 nm one way and 1.27 nm the other, so importers keep the original coordinates of
   untouched objects in `ext` (`coords_raw`) and prefer them when writing back.
4. **Ids:** `<prefix>_<uuid>`; `uuid5` of `backend:native_id` for imported objects with a native id;
   `uuid5` of `backend:document id:section:content hash` for imported objects without one; seeded
   `uuid4` for created objects. A file hash never enters an id. `ref` and hierarchical `path` are
   attributes, not keys.
5. **Extensions:** `ext[backend]` keeps what the model does not understand, verbatim, with the
   minimum format version it needs, so writers never emit something the target cannot load.
6. **Slots:** backends represent each typed node as an ordered list of modelled and opaque
   children and re-emit opaque children verbatim in place.
7. **Authority:** for a design authored in Fenolite, the exported tool project is the source of
   truth for layout; `.fenolite/` is a regenerable cache; imported third-party files are kept
   immutable by hash.
8. **Canonical JSON:** one file per layer, sorted, defaults omitted, integers only, so that
   re-serialising is idempotent and Git diffs show exactly what changed.

## Alternatives
- **A complete "universal EDA IR" first** (semantic, physical, presentation, manufacturing,
  analysis, query engine, transactions, undo): years of work before any user value; the model
  would be designed without the second backend in view anyway.
- **A generic dictionary model**: no typing, no schema, no editor support; rejected.
- **1/50 nm base unit** (exact for both targets): multiplies every stored integer by 50, hurts
  readability of files and diffs and breaks direct parity with nanometres; rejected in favour of
  nanometres plus `coords_raw` for untouched imported objects.
- **Floats with tolerances**: non-deterministic round-trips; rejected.

## Consequences
- Backends need an adapter from their records to the model and back; the adapter is where the
  target's quirks live.
- Some object kinds (schematic graphics, 3D bodies, full padstacks, variants) are missing until the
  change that needs them.
- Everything serialisable is typed, schema-generated and diffable.

## Evidence
- Unit definitions: S-0001, S-0002 in `docs/evidence/sources.md`; hypotheses `H-K-UNIT`,
  `H-A-UNIT`, `H-G-ANGLE` in `docs/hypotheses.md`; `docs/formats/units.md`.
- Normative text: `openspec/specs/design-model/spec.md`.
