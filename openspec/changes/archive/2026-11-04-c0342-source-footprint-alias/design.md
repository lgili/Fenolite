# Design
Use emit.sheets.instances(source,include_root=True) to resolve each native symbol
UUID at its exact file/use context to its canonical reference. Read the actual
instance Footprint property, not a basename heuristic or symbol library default.
Multiple units for one ref must agree. Board-only/unmatched/empty-source cases
retain existing behavior.

For a matched nonempty alias, require the original board footprint basename to
agree with the source alias basename under the existing L3 contract. Vendor a
local copy of the exact board-derived definition under the declared alias and
include its project table row. The logical alias may be shared by explicitly different c0318 definition
lookups. Preserve each existing board-derived variant name beneath the original
source namespace, and emit footprint_definition when that lookup differs from
the logical alias. Same exact definition lookup with different normalized bytes
must refuse; normalize only library-derived identity/default Reference/Value
and UUIDs using the existing derive signature, never coordinates, poses, order
or shapes. No original per-instance edit is discarded.
The emitted Part footprint is the source alias and definition lookup is the
corresponding vendored exact geometry. Nonalias imports and edited board-only
variant behavior remain unchanged. Genuine basename mismatch must remain an
explicit failure/refusal, not a passing comparison.

Authored regressions expose a visible Footprint field with a namespace-only
alias; prove import/build L3/S/L8 equality, physical geometry/pad mapping and
ref/path/UUID preservation, empty-config local resolution and ambiguity refusal.
Use only Fenolite-authored mini fixtures in core. Public native diagnostics stay
external, including complex_hierarchy and interf_u; prove their exact source
hashes and native/default-plan behavior after implementation.

The maintainer explicitly chose early exit3/FEN-3004 for the c0326 planted
VisibleAlias:Other versus physical Mini_R inconsistency. Its negative regression
must assert a located component/Footprint error, zero plans/no target and source
byte preservation, rather than silently substituting the physical alias and
waiting for level8. No L8 comparator change is authorized.
