## Context

KiCad stores board geometry as integer nanometres with v4 UUIDs on most objects; the other target stores 1/10000 mil integers (2.54 nm) with eight-letter unique ids on components and none on many primitives; KiCad rejects unknown tokens on load, so extension data cannot live inside KiCad files. A neutral model therefore needs: exact integer units, an id scheme that survives import/export, a place for what the model does not understand (`ext`), a record of where each object came from (`provenance`), and a rule for which artefact is the source of truth. Existing single-tool toolkits show the cost of skipping this step.

## Goals / Non-Goals

**Goals:**
- One-page normative spec that backends implement against.
- `core` and `model` packages, stdlib-only, immutable dataclasses, property-tested.
- Canonical JSON so that diffs are readable and re-serialisation is idempotent.

**Non-Goals:**
- Completeness. Objects not needed by the first board round-trip are not modelled yet.
- Performance work (indexes are plain dicts; spatial index lives in `geometry`, `c0005`).

## Decisions

1. **Entity header.** Every model object is a `@dataclass(frozen=True, slots=True)` with `id: str`, `native_ids: dict[str, str]`, `provenance: Provenance | None`, `ext: dict[str, ExtBag]`. `ExtBag` = `{min_version: str | None, payload: tuple[tuple[str, str], ...]}` where `payload` holds opaque text fragments (S-expression subtrees or key/value pairs) verbatim. Alternatives: mutable objects with change tracking (rejected: transactions are post-1.0; immutability plus `--dry-run/--confirm` is enough); a generic `dict` model (rejected: no typing, no schema).
2. **Units.** Lengths are `int` nanometres (`Nm = int` type alias); angles are `int` microdegrees (`Udeg`). `core/units.py` provides `parse_length("0.25mm") -> 250000`, `format_length(nm, unit)`, `mil_to_nm`, `nm_to_mil`, and the exact conversion to/from the 1/10000 mil unit (`u`): `u_to_nm(u) = round_half_even(u * 127 / 50)` and `nm_to_u(nm) = round_half_even(nm * 50 / 127)`, both computed with integers only (`divmod`), symmetric for negative values, with the midpoint cases tabulated in `docs/formats/units.md`. Python `int` is unbounded, so no overflow limit exists in the model; backends clamp to their own ranges and report `capability` issues. ADR-0001 records the rejected alternative "1/50 nm base unit" (exact both ways but multiplies every stored integer by 50 and breaks readability and parity with KiCad).
3. **Ids.** `id = f"{prefix}_{uuid}"` with prefixes `cmp, pin, net, cls, fp, pad, trk, arc, via, zon, kpo, txt, gfx, hol, out, lay, stk, rul, mfn`. Imported objects with a native id: `uuid5(FENOLITE_NS, f"{backend}:{native_id}")`. Imported objects without native id: `uuid5(FENOLITE_NS, f"{backend}:{doc_native_id}:{section}:{content_hash}")` where `content_hash` is SHA-256 of the object's normalised content (geometry in nm, layer, net, kind); the file hash never enters an id. Created objects: `uuid4` drawn from an injectable `random.Random(seed)`. `ref` (e.g. `R1`) and `path` (hierarchical, e.g. `power/ldo/C1`) are attributes and secondary keys, never the primary key. Documented consequence: ids of native-id-less objects are stable under edits of *other* objects, not under edits of themselves; diffs match those objects by content.
4. **Provenance.** `Provenance(backend, file, file_sha256, locator, evidence)`; `locator` is an opaque backend string (e.g. `sexpr:/kicad_pcb/footprint[12]`). `file_sha256` lives only here.
5. **Evidence.** `core/evidence.py` defines `Level` (`ALTIUM_VERIFIED_KIT`, `ALTIUM_VERIFIED_AUTHOR_REPORT`, `KICAD_VERIFIED`, `ORACLE_VERIFIED`, `CORPUS_VERIFIED`, `INFERRED`, `UNKNOWN`, `UNVERIFIED`) with a total order for the "lowest level wins" combination (`min_level(a, b)`), an `Evidence(level, oracle, hypotheses)` record, and the string forms used in the CLI envelope (e.g. `ORACLE-VERIFIED(kicad-import)`). The rule "author-report never promotes an operation to verified in the release matrix" is documented here and enforced by the matrix generator later (v0.2a).
6. **Errors and issues.** `FormatError(file, locator, offset, message)`, `ConsistencyError`, and `Issue(code, severity, message, where, hint, retryable)` shared with the CLI. Issue codes are dotted lowercase (`model.duplicate-ref`).
7. **Coordinates.** `Point(x: Nm, y: Nm)` and `Size(w: Nm, h: Nm)` live in `fenolite.core.coords`, because both `model` and `geometry` (change c0005) need them and the layering allows each of them to import only `core`.
8. **I/O.** `core/io.py`: `atomic_write(path, data: bytes, *, backup=True) -> WriteReceipt(path, sha256, backup_path)` (temp file in the same directory, `os.replace`), `sha256_of(path)`, `read_bytes`. No file is ever modified in place.
9. **Model layers for this change (v0.1 subset).** `circuit`: `Component(ref, value, dnp, lib_symbol_ref, lib_footprint_ref, properties, path, pins)`, `Pin(number, name, etype)`, `Net(name, netclass_id)`, `NetClass`, `Interface(name, kind, members)`, `Module(path, children)`. `board`: `Board(outline, layers, stackup, footprints, tracks, arcs, vias, zones, keepouts, texts, graphics, holes)`, `Layer(name, kind, ordinal)`, `Stackup/StackLayer(material, thickness_nm)`, `FootprintInstance(component_id, position, rotation_udeg, side, locked, pads)`, `Pad(number, shape, size, drill, layers, net_id, padstack)` with a minimal `Padstack` (per-layer shape overrides, optional), `Track/Arc/Via/Zone(fills)/Keepout/Text/Graphic/Hole/Outline`. `rules`: `Rule(id, name, kind, selector_a, selector_b, layers, min, opt, max, severity, priority)`, `RuleSet`, kinds `clearance, track_width, via_diameter, via_drill, hole_size, edge_clearance`; selector algebra `all | net(glob) | netclass | ref(glob) | layer | item_kind | and | or | not`. `manufacturing`: `Manifest(artefacts[{path, sha256, tool, tool_version, revision, variant, evidence, state}])`, `PnpRow`. `findings`: `Issue` list on `Design`. `design.py`: `Design(meta, circuit, board, rules, manufacturing, findings)` with lazily built read-only indexes `by_id`, `by_ref`, `by_net`, `by_layer`.
10. **Slots (specified here, implemented by backends).** Every typed node a backend reads is represented as an ordered list of children, each either `Modeled(field)` or `Opaque(subtree, min_version)`; the writer walks the original order, re-emits modelled children in place and opaque children verbatim; new children are inserted at a documented canonical position per node type. This is what makes `RT1` (model → file → model identical) achievable without byte-identity with the tool's own formatter.
11. **Layout authority.** For a design authored in Fenolite and exported to a tool project, the tool project file is the source of truth for layout; `.fenolite/` is a regenerable, git-ignored cache; `native/` holds immutable copies (by SHA-256) only of imported third-party files; sidecar `placements.toml` (v0.2b) is the only extra committed layout source. Pre-1.0 caches are regenerable, not migratable.
12. **Canonical JSON.** `model/canonical.py`: UTF-8, LF, two-space indent, key order = dataclass field order, collections sorted by `(kind, path or ref or name, id)`, defaults omitted, integers only (no floats anywhere), `ext` emitted verbatim with sorted keys, one file per layer under `.fenolite/` (`circuit.json`, `board.json`, `rules.json`, `manufacturing.json`, `findings.json`) plus `meta.json` with `schema_version = "0"` and `fenolite_version`. `dumps(load(dumps(x))) == dumps(x)` is a property test.
13. **Schemas.** `tools/gen_schemas.py` (from `c0002`) emits `schemas/fenolite.model.v0/<layer>.json`; `tests/unit/test_schema_drift.py` covers them; schema ids are `fenolite.<layer>.v0` until 1.0.
14. **Tests.** `hypothesis` strategies for lengths, angles, ids and small designs; boundary tables for the unit conversion; id stability tests (edit other object → id unchanged; edit self → id changes; reorder → unchanged).

## Risks / Trade-offs

- [Model becomes KiCad-shaped because KiCad is the first backend] → the spec is reviewed again when the second backend's reader lands (week 8 clean-room track); until then every field must be justified by a public spec of either tool.
- [Integer microdegrees cannot represent some rotations exactly] → hypothesis `H-G-ANGLE` in `docs/hypotheses.md`; non-representable values go to `ext` as original text.
- [Canonical sorting by `ref` changes when refs are renamed] → `id` tie-break keeps order deterministic; diffs remain readable.
- [Frozen dataclasses make bulk edits verbose] → `dataclasses.replace` helpers in `model/design.py`; acceptable pre-1.0.

## Migration Plan

- No persisted data exists yet; `.fenolite/` caches are regenerable by definition.

## Open Questions

- Should `Pad` carry `padstack` in v0.1 or only from the KiCad backend change once the `pad` grammar is inventoried? Default: optional field now, populated later.

## Evidence level required before merge

- Mechanical tests green; `docs/evidence/sources.md` rows for both units with URLs; `docs/hypotheses.md` rows `H-K-UNIT`, `H-A-UNIT`, `H-G-ANGLE` at level `INFERRED`.

## Implementation notes

- `canonical.loads` validates with a type-directed decoder driven by the same dataclass annotations the JSON Schemas are generated from, so the package does not need the schema files at run time; the first violation is reported as `FormatError` with its JSON pointer.
- Fields whose order is semantic (stack-up layers, board layers, polygon points) are marked `ordered` in the field metadata and keep their order; other collections of entities are sorted canonically.
