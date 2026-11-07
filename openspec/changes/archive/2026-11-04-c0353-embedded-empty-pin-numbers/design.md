# Design

Native reader canonical pin texts distinguish empty from literal tilde. Existing symembed converts
empty pin names and properties for modern targets but overlooks numbers, especially when an empty
number also prevents matching its empty name. Reconcile raw pin slots against canonical pins by
unit/body-style and stable pin order, checking cardinality and source geometry/identity before any
empty-marker rewrite. Rewrite only a raw tilde whose checked canonical number is empty; preserve a
modern literal tilde. Resolve pad mapping from the checked canonical number. Do not use blanket text
replacement or guess an ambiguous match. Keep old-target/default bytes when no correction is needed.

A literal pin number consisting of a tilde cannot retain its meaning on the old target; refuse
located before emission even with allow-lossy unless an explicit pin-pad mapping rewrites it to a
representable number. Do not hide a pin, intersect pin sets, waive a mismatch or add canonical fields.

Independent original Fenolite controls cover both source formats and both targets, empty/literal
numbers, unrelated numbered pins, unit/body-style/cardinality negatives and mapped identity. Native
original/target tools export complete pin universes and named partitions. Public3 full-owner census
is repeated on9 and10 with exact manifest input hashes. Actual imported portable libraries already
pass separately; do not alter that pipeline or claim the direct-embedding failure was its failure.

Coordinator review — 2026-11-03: parent approved c0353 and S-1291 before code, narrow measured
blank-number boundary, authored empty versus literal-tilde controls first, all four source/target
combinations and complete identities/names with no filter, no new fields and no silent fallback.

## Unresolved source inheritance addendum (review approved before code)

The combined source-context negative revealed a caller ordering violation: source import passes
an unresolved derived SymbolDef (empty own pin list) to embed_symbol, while _flatten correctly
emits the parent's body. Exact binding then sees raw parent pins versus empty unresolved model pins
before the existing contextual-inheritance refusal can run. Normal resolver callers already pass
sym.resolve_extends(chain)[0]. Use that same existing canonical resolver in the source-import caller
before embedding, retaining the child raw slots/properties and the original parent chain. Do not
alter cardinality/unit/style/geometry/identity checks or weaken the contextual rejection.

Author ordinary single-sheet inheritance controls on targets9/10 that prove exact parent-derived
pins/units and child property overrides; keep the original contextual-inheritance negative unchanged.
Run all existing contextual, embedded-pin and embedded-symbol negatives after the focused repair.
No native grammar fact, model field, default, tolerance or output-scope change is introduced.
