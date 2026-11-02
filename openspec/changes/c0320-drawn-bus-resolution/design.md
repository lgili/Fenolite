## Context

The clean entry source is a4d11e589fa90d971f07af00de6f030c6f7e72b0, selected with
the source-import owner. His read-only diagnostic reports full own/native pin
coverage: 313 pins for public corpus row 10-13 and 2,033 for 10-17. Native 9.0.2
partitions match each PCB. Own/native differing groups are 61/29 and 176/82;
drawn.bus-member-unknown counts are 30 and 374. These are reported entry facts,
not yet a proof run on this branch. Raw source S text and geometry remain intact.

## Decisions

Decided 2026-11-01 under standing maintainer authorisation: first reproduce the
specific resolver defect and compare small original bus controls with the actual
installed native CLI. Do not infer a general rule from one fetched board or hide
differences through canonicalisation, label rewriting, loss acceptance or skips.

Decided 2026-11-01: preserve the KiCad extraction/connection-name API and raw
drawn model. No field addition is planned. Generic/Altium literal naming and
existing bus-entry-without-label diagnostics remain covered by negative controls.
If the actual defect requires a backend-specific interpretation, keep it at that
existing boundary rather than changing unrelated model semantics.

Decided 2026-11-01: use existing registered KiCad manual/format facts where they
apply. New measured facts must name the actual native version and an authored
control; reserved S-1280 through S-1299 are unused at entry. No source parser,
grammar, third-party CAD fixture or native output is committed. A pending final
model0 freeze preempts this independent packet without merging its experiments.

## Proof boundaries

Only focused worker tests and actual subprocess measurements are in scope.
Root owns combined/full gates, publication and exact-head CI. A 9.0.2 result is
not a 9.0.9/10.0.6 proof. Existing evidence levels remain unchanged unless a
specific actual control justifies its own scoped statement.

## Reproduced entry classification — Decided 2026-11-02

The immutable model1 cutoff09544d4f is now ready independently. Resume this
field-free repair on its existing isolated source. A read-only inventory finds
all17 bus labels in public13 at a bus-entry endpoint, with no wire or component
pin at the anchor. The resolver counts both ends as wire-layer contacts and
therefore reads those bus labels as scalar labels. Public17's58 bus labels do
not have that contact, so do not attribute all of its differences to this defect.

First author vector/group/alias hierarchy controls which move the bus label to
the bus side of an entry or to a bus junction. Compare the actual native pin
partition before changing production code. A bus-only contact must not invent
a wire contact; actual wires/pins retain their priority and an unlabeled member
must remain unconnected. Preserve ordinary/Altium literal names and all raw S
labels/geometry. Do not add a model field or alter the backend connection-name API.

## Remaining bus definitions — Decided 2026-11-02

The contact repair improves public13 differing groups from61/29 to15/7 and
leaves public17 at176/82, with unchanged complete pin coverage. Two exposed
hierarchical definitions contain an overbar member; the old flat-brace matcher
cannot expand them. Other remaining public13 edges join qualified groups with
different prefixes on one physical bus. Author overbar, renamed vector/group,
member-order and disconnected-bus controls before selecting the join rule.

Any relative member identity must be scoped to a connected bus. Preserve the
qualified scalar labels and their names; do not canonicalise unrelated nets,
change Altium/generic literals, add model fields or waive native disagreements.
Native9.0.2 measurements decide the exact index/member correspondence; no claim
for unexecuted pinned versions follows. Record remaining public differences.

## Remaining scalar label scopes — Decided 2026-11-02

The scoped bus identities bring public13 to the exact313-pin native partition.
Public17 retains16 native-only groups: inspection finds local scalar labels
whose exact text is also a hierarchical label on their sheet. The resolver uses
separate local/hierarchical nodes, leaving those pins split. This is a concrete
candidate beyond bus-definition matching, not evidence for general name merging.

First measure local/hierarchical/global label combinations on authored sheets,
with unequal-name and other-instance controls. If native9.0.2 confirms an alias,
enable only the measured same-sheet scalar-label aliases at the KiCad boundary.
Keep generic/Altium defaults, raw source and unmatched-port errors unchanged.
No broad global-name rewrite or evidence promotion is authorised by this result.

## Offset vectors — Decided 2026-11-02

An additional discriminating control refutes the initial numeric-index
interpretation: native9.0.2 pairs `D[0..3]` and `Q[2..5]` by ascending index
position, also when the written Q range is reversed. The first equal-base
controls did not distinguish those rules. Correct only the top-level vector
identity to that measured position and rerun existing controls/public rows.
Keep the literal nested-group distinction and disconnected-bus negatives.
