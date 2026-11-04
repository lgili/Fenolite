## Decision — 2026-11-02

Use Design.board(..., technical_layers: Sequence[str] | None = None). The option
is a complete selection of standard non-copper rows, rather than an accumulating
list of omissions. None preserves the historical full table and default model
bytes. Reject strings, duplicate names, copper/User.n names and unknown names.
Require Edge.Cuts because board() always declares an outline. Normalize accepted
names to the existing standard row order. User.n declarations remain independent.

Store the selection only on the non-dataclass DSL Design object. Conversion
places selected known technical rows in existing Board.layers before its User.n
rows. The build recognizes those explicit known rows and filters its existing
created table accordingly, always retaining copper and declared User.n rows.
Edge.Cuts makes an explicit selection distinguishable from the historical
user-only/empty DSL table without a new persisted marker or schema field.
No model, dataclass, canonical format or schema definition changes are allowed.

A fresh build writes exactly the selected rows with their existing standard
number/type/display defaults. All modeled item references, including footprint
fields/pads/graphics and images, remain subject to the undeclared-layer refusal.
Do not erase or reassign an item to make a shorter table valid. The strict
native layer-table/equivalence assertions remain unchanged.

The importer computes the supported canonical technical selection from the
source. It emits technical_layers only when that selection differs from the
created table and contains Edge.Cuts. Omitted supported rows stop being losses
only after this selection has a concrete representation. Unknown/extra names,
missing required outline layer, unsupported User.n gaps and unrelated losses
remain ledger findings and refuse strict import. Existing mixed-width tests
retain their width refusal while proving the supported shorter table separately.

Default scripts, default model bytes and every existing build-byte table entry
remain unchanged. The new written guide page is separate from full reserved
pages, and generators are run rather than hand-editing generated reference data.
Use the actual cached kit only in scratch, snapshot its bytes before/after,
import and explicitly build without lossy/acceptance flags, then report strict
verification outcomes separately. A removed layer-table refusal is not a claim
that every fidelity level or native application accepts the project.

## Ownership

Work only in the isolated c0324 checkout. The authoritative model freeze keeps
Board.layers and all model/schema definitions byte-identical. Root owns whole
local gates, exact-head CI and publication. Keep c0320 bus resolution and other
workers' native/schema work untouched.
