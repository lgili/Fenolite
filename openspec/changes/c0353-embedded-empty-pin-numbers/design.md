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
