# Narrow typed value and ephemeral display context

## Native measurements before implementation

The actual9.0.9 and10.0.6 CLIs exported sixteen original authored SVG cases from
a tiny root/child schematic, extended to three repeated child instances for the
short-format controls. Every process exits0 and originals retain their hashes.
No vendor implementation, grammar, parser or third-party fixture is used.

The two tools agree: project show=false draws no reference text; show=true draws
root2/child1. Own-page=true draws1,2 on both, including otherwise unique labels.
Prefix/suffix[P and ] draw[P2]/[P1], and even[P] for the empty reference list.
A repeated child on page2 sees1,3,4; short format is1..4 (first/last, even with the
removed-own-page gap). With own-page enabled all instances see1..4. The same
physical child file therefore has distinct effective text in separate instances.
Project show=true also draws the field when the original property's effects
contain hide=yes. Stored hide must survive, but it cannot independently override
this measured project display rule. An unsupported-context viewer must never draw
the literal placeholder or silently select one repeated instance.

## Representation and strict parsing

Append DrawnLabel.intersheet_refs: DrawnField | None = None, default-omitted in
canonical JSON and TOML. Only kind=global and name=Intersheetrefs are valid. The
property text is fixed to sch.INTERSHEET[1], not another public arbitrary text
value. Preserve exact position/rotation/justification/hide/font styles. Reuse the
existing private typed field-pose carrier through NetLabel; do not add a second
native IR model field or expand opaque capture. The native writer writes the
fixed placeholder property for either supported target when the typed pose is
present. When absent, retain the existing target-specific default bytes exactly.

Extract only one exact matching property. Reject duplicates, wrong names/text,
local/hierarchical properties or unsupported poses/effects with located existing
format errors. Existing hidden default placeholder behavior remains byte-compatible
when no typed change is needed. No visible custom field is silently ignored.
Other backends must retain their existing localized refusal; do not invent an
Altium interpretation for this KiCad-specific field.

## Viewer context, instances and callers

Use a private ephemeral context value in the view layer, outside the canonical
model: effective show/own-page/short/prefix/suffix, current page/instance, and the
complete global-label page membership. Resolve it from the actual project JSON
and sheet-use/page metadata using existing parsed source hierarchy types. Verify
file paths, cycles, required pages and unique owning project; retain duplicate
physical uses as separate instances while deduplicating repeated labels on one
page. Preserve native page formatting, including tested ordering and short/empty
behavior. Add further authored page-order controls before implementing unmeasured
numeric/text/duplicate cases; refuse unsupported ambiguity rather than guess.

build_kicad_schematic_scene gains an optional private keyword-only context. Its
old no-context call remains byte-identical for sheets without this property or
with references known to be disabled. A visible reference requiring unavailable
project/instance context refuses with a located existing error, never a literal
placeholder or inferred active page. Once context exists, use the exact native
property pose/font and project-driven visibility policy to draw resolved text.

Project presentation/view callers must consume explicit per-instance scenes when
effective reference text differs; one scene per physical path cannot represent
that case. Keep the legacy scene keys and bytes when references are disabled.
For enabled hierarchies, append deterministic logical instance path identifiers
(not random/native UUID identities) and expose the instance/page in the viewer's
document selection. Cache identities include all project settings, hierarchy
inputs and selected instance; a changed project alone must invalidate references.
Do not silently pick the first active instance for a direct child-file request.
A direct file with no unambiguous owning project/instance must fail with an
existing located context error and an actionable explanation.

## Complete pipeline and compatibility

Update model validation/codec/docs/schema inventory, schematic TOML, native
extract/lower/write, viewer contexts/callers/cache and tested agent teaching.
Source project metadata remains in the existing reviewed project-template carrier,
not a new persisted settings field. Generated native properties retain the
placeholder so KiCad resolves them; Fenolite resolves the field only in its view.

Proofs compare complete electrical pins/partitions/names, all source flag/property
bytes and native SVG effective text on9/10. Controls include malformed/duplicate
properties, wrong kind, unknown context, multiple owners, repeated instances,
project-only settings changes, stored hide and all five settings. Defaults must
retain canonical/TOML/native and legacy scene bytes. Public source-derived replay
is limited to the three affected inputs and their complete declared owner inputs.
Root owns combined fast, final model0 inventory/75 plans and exact-head native CI.
No archive before all required gates, no reader-floor/tolerance/baseline changes.

## Coordinator decision — 2026-11-02

The coordinator approves this design before runtime implementation. A hidden
property cannot be discarded merely because it is hidden: native project
show=true overrides that flag, and target9 omission or target10 default posing
may differ. Preserve its typed pose unless exact target/context equivalence is
proved. Measure no-project default visibility and page-order/text/dedup controls
before the context algorithm. Typed default constructors retain their legacy
bytes. Send the typed checkpoint before final model0 inventory/freeze.

## Raw API and discovery clarification approved before context runtime

The coordinator confirms that the bytes-only scene API's None context explicitly
means standalone/no-project, matching the measured native disabled default.
Path/project-aware callers must resolve known context; failed ownership or
instance lookup cannot become a None fallback. Discovery is restricted to an
explicit project or adjacent project files within the known directory, never
ancestor search or disk traversal. A repeated child requires an actual explicit
instance document ID; default selection cannot silently choose the first.

## Explicit missing-pose regression control

A project-template investigation enables project reference display on the full
authored drawing. That drawing has no authored label field poses: target9 keeps
that absence, while target10's existing writer supplies its legacy hidden
property. Therefore the target9 active viewer refusal is intentional input
validation, not permission to synthesize a pose. Add independent authored9/10
controls for exact explicit field text and coordinates, missing-field refusal
when display is active, and unchanged disabled behavior. No runtime, original
helper, default writer, or native guard changes are requested. The coordinator
authorized these focused regression controls after reviewing the actual
FEN-3004 locator VCC; this is distinct from a power-symbol guard.

## CI pose correspondence diagnostic

Native9 CI reported x20.0908 minus13.5712 instead of5mm in the authored typed-field translation proof. Before changing a writer or test, capture complete authored inputs, native graphs/pins and each SVG with basename/text/pose on both9.0.9 and10.0.6. Flat output-dictionary/XML enumeration is not a field identity; if order is the cause, compare only stable same-sheet/same-effective-field keys and explicitly distinguish moved root fields from unchanged child fields. Duplicate or missing correspondence must fail, exact5mm/7mm assertions remain, and all native graph/pin assertions stay. No tolerance increase, placement normalization or result waiver is authorized.
