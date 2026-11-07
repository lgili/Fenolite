## Evidence and current boundary

The exact L10 KiCad 9 job reports 41 failed, 1503 passed, 972 skipped and one
xfail in 1117 s. Its 41 corpus failures match the local context-correct replay:
36 VME owner contexts plus one orphan and four older standalone formats.
The historical `9c44f7a2`, `695dee0f` and `ce3b9992` observations remain immutable.

Read-only source investigation uses registered S-0058 inputs, verified hashes,
Fenolite's existing parser and native CLI S-0020 across a process boundary.
Actual local KiCad 9.0.2 loads/exports the complete VME owner: 36 reachable
sheets, 6811 pins and 1800 groups. Three native IDs differ across 2, 11 and 5
sheet snapshots. For each ID, logical pins, pin geometry and body geometry have
one signature. Removing only the property nodes that vary makes the entire
remaining native AST identical, including unknown non-property slots.

The changing property nodes are Description/Val; Description/Tolerance/
Tolerance_1; and Description/Part Number. Tolerance's full node differs even
where its projected value is equal. Sheet UUIDs and full input
digests bind these local snapshots. The projected definition IDs include their
source sheet UUID; those context IDs are not the conflicting serialized fields.
This is evidence of legitimate local
metadata, not evidence that any metadata may be discarded or that every native
semantic contract has already been proved. The native load/export is 9.0.2;
the actual CI failure is separately bound to its exact head/job.

## Accepted decision, 2026-11-02

The maintainer's delegated review accepted this boundary on 2026-11-02 after
reviewing witness/design commit `29a984544acc6f3be29506c9c49d5e47ecc68f83`.
Scope full metadata variants to the existing drawn-sheet key and
native library ID. Keep the ordinary global path for definitions that are
identical. For a conflicting group, require identical complete non-property
AST, identical Reference/Value/Footprint core-default nodes, and an explicit
hash-bound context for every occurrence. Different logical pins, geometry,
flags or core defaults remain refused in this first phase. Do not infer safety
from a data-specific allowlist of descriptive property names.

Retain every complete property node, including values, effects, order and opaque
content. No common definition is manufactured by dropping properties, choosing
a winning snapshot, sorting a raw cache or normalizing differences away.
Same-file duplicate definitions and incompatible bindings for one reference/unit
remain ambiguous errors. The existing Value-conflict negative remains closed.

## Accepted data flow

1. `SourceSymbols` retains per-file/native-ID definitions and content digests in
   importer/backend maps. These are not model or S dataclass fields. The common
   pin/body projection validates compatibility; it is never substituted for the
   full source definition.
2. Import writes deterministic, full native assets plus a small closed context
   index beside the drawn source. Proposed index key: existing drawn-sheet key
   plus native library ID; value: relative asset path, full AST digest and source
   input digest. A context index is required for every occurrence of a variant
   group, including its first occurrence. Missing/unknown/stale bindings refuse.
   The concrete closed layout below is the implementation contract.
3. Build reads and binds that index/assets as inputs before lowering. A backend
   context-symbol map selects the full definition for the current sheet. Extend
   the backend embed-cache identity with context/digest so identical native IDs
   cannot reuse another sheet's property snapshot. The existing per-sheet
   `lib_symbols` collection emits the original native ID and its full metadata.
4. Circuit values, references, footprints, fitted/exclusion state and source
   instance properties retain their existing paths. No optional model field,
   S field or ext namespace is added. Ordinary builds have no context index and
   must keep their existing byte pins.
5. Import/build/sync and confirmation replay bind every index, asset and original
   input. A changed digest refuses confirmation with existing FEN-4002. Plans
   and receipts show all writes; direct commands gain no approval bypass.

An implementation must prove the full emitted property AST per sheet, not only
connectivity or the model's projected property values. Wrong-context selection
must fail even when pins and geometry happen to match.
Unknown or repeated property nodes cannot disappear through a projected
dictionary; preserve their full native order/content or refuse explicitly.
This first contextual phase refuses inherited definitions: the existing
ordinary flattening path merges parent/child property dictionaries and cannot
prove complete repeated/opaque property preservation. Ordinary identical
inherited libraries retain their existing behavior; no metadata exception is
enabled by flattening two distinct contextual sources into one node.

The standalone library reader projects legacy `(power)` as `(power global)`
for target 10; the embedded schematic reader retains the literal source node.
Assets therefore restore through the existing schematic reader. Only validation
against a resolved library definition may compare these two documented global
forms by their meaning (S-0043/S-0049, `libraries.md`); local power, duplicates
and every other non-property difference remain closed. Source-to-source
compatibility stays exact and emitted AST comparison still includes the
original power node. No cache or authored node is rewritten for this check.

## Concrete context-index contract

The required sibling file is `symbol-contexts.toml`, schema
`fenolite.symbol-contexts.v0`. Import emits
`design.load_schematic("schematic.toml", symbol_contexts="symbol-contexts.toml")`.
The additive keyword records a required input in DSL state only, like the
existing drawing path; it changes no model/S field or CLI envelope. Nested
drawings require the index in the same folder. Removing the required index
fails before staging, rather than silently using the global definition.

The root has exactly `schema: str`, `drawing: str`, `target: int`, and
`symbol: list[table]`. `schema` is the literal above; `drawing` is the actual
sibling drawn-source basename; `target` is 9 or 10, never a boolean. The list
is nonempty, sorted by `(sheet, native_id)` using case-sensitive Unicode order.
Duplicate pairs, unknown/missing keys and incorrect primitive types refuse.
Every occurrence of a variant group, including the first, requires one row.
No row for an unknown sheet or unused native ID is accepted.
Once any variant exists, the index covers every used native definition of the
drawing, including identical groups. This complete coverage makes deletion of
an entire group detectable from the drawing/part bindings without adding a
model marker. A project with no variants still has no index or extra assets.

Every `[[symbol]]` has exactly these string fields, emitted in this order:

| Key | Meaning and validation |
|---|---|
| `sheet` | Existing drawn-sheet key, exactly matching the drawing |
| `native_id` | Original case-sensitive `library:name`, with one colon and nonempty printable halves |
| `asset` | `lib/.symbol-contexts/<asset_sha256>.kicad_sym`, relative to the index |
| `asset_sha256` | SHA-256 of the complete UTF-8 native-library file bytes |
| `definition_sha256` | SHA-256 of the qualified embedded native symbol AST serialized by `sexpr.dumps(style="compact")`, UTF-8, no added newline |
| `input` | Original schematic's canonical relative POSIX path inside the imported source tree |
| `input_sha256` | SHA-256 of that original input's exact bytes, retained as provenance |
| `binding_sha256` | SHA-256 of the binding object defined below |

All hashes are exactly 64 lowercase hexadecimal characters. The binding object
is `{"schema": schema, "drawing": drawing, "target": target, **row_without_binding_sha256}`,
serialized as UTF-8 JSON with `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=False`, and no newline. It binds the selection and source digest;
it is an integrity check, not an authenticity signature or a reason to trust
arbitrary authoring edits. Review binds the actual index and all asset bytes.

Paths use canonical relative POSIX spelling: no absolute/drive paths, colon,
backslash, controls, empty segments, `.` or `..`. The drawing is one basename;
the asset must have the exact generated prefix and digest filename. Reject
symlinked index/assets or symlinked ancestors and any resolution outside their
allowed project folder. The original `input` is a provenance path: later builds
do not read an arbitrary upstream file or require the original CAD to remain
available. The import plan binds every actual original input; build/sync bind
the script, drawing, required index and every asset they consume.
Confirmation also checks the recorded context paths for symlink/escape changes
before reading their digests. This read-only replay validation does not execute
the producer, parse the drawing again or change the CLI envelope/plan schema.
Import checks the same paths under its selected output folder before staging.
This first native phase requires KiCad schematic output: `--schematic skip`
and an Altium target refuse when the DSL requires a context index.

Each asset contains exactly one full native definition. Restore its original
qualified ID before computing `definition_sha256`; preserve every complete
property node, order, effects and opaque content. Validate all rows, including
the first, and every digest before lowering. Require exact equality with all
used drawing sheet/native-ID pairs, not merely the IDs still present in a
possibly incomplete index. Missing, duplicate, unknown,
wrong-context, stale or traversal/symlink data refuses. Index rows may be sorted
for determinism; native AST/property order must never be sorted or normalized.

The ordinary project library retains its native nickname. Safe interior spaces
are accepted in a nickname without replacing the native namespace; path
separators, traversal, controls, reserved names and trailing ambiguous spelling
remain refused. Context assets use digest filenames, never raw native IDs.
This closes the independently observed VME nickname-path refusal without
changing project/symbol names or widening the semantic metadata boundary.

## Authored CC0 witnesses

The scratch packet contains two files split from Fenolite's own repeated-child
fixture. Native IDs and annotations remain intact. Both the control and a local
Description variant retain 8 pins / 5 groups on actual 9.0.2; the existing global
vendor guard refuses the variant. A Value-default variant is retained as a
protected semantic negative for this bounded phase. Further negatives change
one pin number, one pin position and the `in_bom` flag. They still refuse under
the current guard. No third-party CAD fixture or copied parser is committed.

These are investigation witnesses, not implemented passing import/build tests.
Before support is enabled, commit authored CC0 fixtures with declarations and
prove source-to-written property nodes, native component semantics, all nine
fidelity levels, stale-input refusal and native 9/10 behavior.

## Naming investigation is independent

All six investigated owners retain equal full partitions. Their 143 raw name
differences comprise 25 slash-escape spellings, 117 parent-bus name candidates
missing from the resolver's election, and one local/hierarchical election case
whose exact native tie rule is still under investigation. Four-signal authored
vector/group/overbar controls reproduce the parent-bus mismatch with 40 pins
and equal full own/native partitions for each controlled input. Ordinary scalar
local/hierarchical/global controls agree with the existing election, so they do
not justify changing the generic depth rule to fit the remaining Royal case.
Keep every raw difference and warning; no name
normalization or guessed priority rule belongs to this metadata-only change.

## Review and validation limits

## Native replay compatibility decision, 2026-11-02

Literal VME replay on clean `217387a4` reaches source extraction/resolution,
then reports an internal KeyError in the strict partition adapter: two of 6811
pin paths have a duplicated `fpga` frame. A read-only observer finds exactly
one failed relative-module calculation, with child frame equal to parent
frame. `_relative` handles descendants but returns None for equality; the
reference fallback serializes the nonempty absolute frame as relative.

The bounded correction encodes equal parent/child module frames as the empty
relative module at the reference construction site. An owned nested-page
witness places two parts of one code module on parent/child pages; extraction
must retain `m/R1` and `m/R2`, never `m/m/R2`. All pins stay in the strict
comparison. Do not repair the report by suffix matching, aliasing unknown pin
paths or changing the model/S fields, name resolver or reader floor. No
ancestor-frame inference or general module relocation is needed for this case.

## Remaining gates

The entry evidence and design review are complete. The closed index contract
is recorded before implementation; decoder support and its negative tests are
still pending. Tasks for
source support, native 9/10, the full gate and exact-head CI stay open. The five
old-format failures remain separately visible; this change cannot close c0276
task 7.2 by itself. No native Altium acceptance is available or claimed.
