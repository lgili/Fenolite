# Contextual native symbols

An imported KiCad hierarchy can hold different local property snapshots under
the same native symbol ID. Fenolite retains every full snapshot. When any
snapshot varies, import writes `symbol-contexts.toml` beside `schematic.toml`,
digest-named native symbol assets, and this required DSL input:

```python
design.load_schematic("schematic.toml", symbol_contexts="symbol-contexts.toml")
```

The index and its assets are authoring inputs. They add no model/S field or CLI
envelope. The DSL only records the path; build validates it before lowering.
Each sheet emits its original native ID and all property nodes, effects, order
and opaque content. The common library resolves logical parts; it cannot stand
in for a missing local snapshot. An ordinary import with identical definitions
writes no index and keeps its existing bytes.

This phase admits property differences with identical complete non-property
AST and identical full Reference/Value/Footprint default nodes. Pin, body, flag,
unknown non-property and protected-default differences still refuse. Same-file
duplicates refuse. Contextual inherited definitions refuse before the ordinary
flattening path can merge their properties. Safe interior spaces in library
namespaces remain native; unsafe/reserved filenames refuse.

## Closed v0 index

The filename is exactly `symbol-contexts.toml`, in the drawing's folder. Its
root has exactly four keys:

| Key | Type and meaning |
|---|---|
| `schema` | String, exactly `fenolite.symbol-contexts.v0` |
| `drawing` | String, the sibling drawn-source basename |
| `target` | Integer 9 or 10, the native asset format; a boolean is invalid |
| `symbol` | Nonempty array of tables, written with `[[symbol]]` |

Each row has exactly these string keys, emitted in this order:

| Key | Meaning |
|---|---|
| `sheet` | Existing drawn-sheet key |
| `native_id` | Original case-sensitive `library:name`, with nonempty printable halves and one colon |
| `asset` | `lib/.symbol-contexts/<asset_sha256>.kicad_sym`, relative to the index |
| `asset_sha256` | SHA-256 of the full native-library file bytes |
| `definition_sha256` | SHA-256 of the complete qualified native AST in compact s-expression form, UTF-8 without an added newline |
| `input` | Original schematic's canonical relative POSIX path inside the imported tree |
| `input_sha256` | SHA-256 of the original schematic's exact bytes |
| `binding_sha256` | SHA-256 of the selection object below |

Every digest is 64 lowercase hexadecimal characters. The binding object is
`{"schema": schema, "drawing": drawing, "target": target, **row_without_binding_sha256}`,
encoded as UTF-8 JSON with `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=False`, without a newline. This detects an inconsistent selection;
it is not an authenticity signature. Intentional authoring edits need a fresh
review, including updated hashes.

Rows are unique and sorted by `(sheet, native_id)` using case-sensitive Unicode
order. Once a variant exists, every used native definition has a row, including
identical groups and the first occurrence. An omitted whole group cannot fall
back to the common library. Unknown or unused bindings refuse. Each asset holds
exactly one complete symbol under its bare name; its original qualified ID is
restored before checking the AST digest. Native AST/property order is preserved,
never sorted to make definitions appear equal.

Paths use canonical relative POSIX spelling. Absolute/drive paths, backslashes,
colons, controls, empty segments, `.` and `..` refuse. Index/assets and their
ancestors inside the allowed folder cannot be symlinks or escape that folder.
The `input` path/digest records provenance; later builds do not read an arbitrary
upstream CAD file or require the original import folder to exist.

## Build, sync and review

Import binds every original input and lists all asset/index writes in the plan.
Build and sync bind the script, factories, drawing, required index and every
asset. Confirmation writes the reviewed bytes without running the producer
again. Changed inputs or newly symlinked context paths require a fresh plan
under `FEN-4002`; malformed fresh inputs refuse with `FEN-3004`.

Sync may retain drawing and field-pose edits. It refuses edited native cache
definitions that would otherwise be discarded: edit and review the source
context assets instead. This first phase requires KiCad schematic output;
`--schematic skip` and an Altium target refuse for a contextual project.

The ordinary library reader projects legacy `(power)` as global. The context
loader uses the embedded schematic reader to preserve its literal AST. Only
comparison against that resolved library projection recognizes the documented
equivalence to `(power global)`; local power and every other difference remain
closed, and the actual written-cache check includes the original node.

The format facts and source references are in
[contextual-symbols](formats/kicad/contextual-symbols.md). Local native 9.0.2
proof is supplemental. Required 9.0.9/10.0.6 CI and complete combined-head gates
remain separate; this feature does not resolve naming differences or the
schematic reader floor.
