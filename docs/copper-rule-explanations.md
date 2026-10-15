# Copper rule explanations (c0097)

`ClearanceResolver.explain(a, b, zone_clearance=...)` returns subjects, an immutable tuple of
candidate rows, two backend switches and the same governing value as `resolve`. Each row carries
source, value and severity; rule rows also carry id, priority, layers and selectors. Names can
repeat; ids distinguish their rules. Selectors and subjects are immutable values, not entities.

Matching rule rows follow `rule_precedence`: priority 0 first, then descending priority (1 last),
with name and id breaking ties. The last matching rule governs. An ignored rule suppresses the
clearance judgment. Without a rule the greatest class/zone/floor value governs; equal class
values use the first class name, and a class wins a tie with zone or floor. With a rule,
`rules_over_classes` decides whether the rule replaces class/zone values, and `floor_over_rules`
decides whether the board minimum raises it. Nonpositive zone values produce no zone row.
Between the two nets of one differential pair in one class whose `diff_pair_gap` is below its
clearance, the resolver's pair candidate is a row `pair-gap:<class>` with the gap, before the class
rows; it replaces the class value as the resolver does (change c0104). The explained subjects carry
`diff_pair`, the base of their pair.

Existing kind normalization treats an arc as a track and a fill as a zone. A scoped rule matches
only its layers: equal-priority rules `R` and `R/track-via` select the latter for a track/via pair
on F.Cu when that rule is scoped there, and the former on B.Cu. The explanation uses the numeric
resolver's own candidates and helpers; it defines no additional matcher.

The values shown are those judged. A backend may already have adjusted them: the second backend
lowers each clearance rule by 5 nm before judgment. The explanation does not reconstruct the
unadjusted file value. When a banded arc near a fill is judged with the baseline clearance without
the zone, its explanation shows that actual resolver call, so resolving its inputs reproduces
the finding's clearance and source. Overshadowed candidates remain visible for ordinary calls.

Every clearance `CopperFinding` carries its explanation; the field is optional for other finding
producers. Its `relation` is intrinsic for pads of one footprint, inter_component for pads of
different footprints and routed_or_free otherwise. `group_findings(report)` sorts by relation
and source, retaining each original object exactly once and preserving order within its group.
It changes no severity, limit, source, message or exemption, and prescribes no design decision.

**Edge clearance (change c0169).** `ClearanceResolver.edge(subject)` gives the copper-to-edge clearance
of one item: the governing `edge_clearance` rule that selects it (the last of `rule_precedence` whose
selector and layers select the item; a rule is unary, so it sees the copper item alone), else the board
minimum (`min_edge_clearance`, source `floor`). An `ignore` rule silences the item. The switch
`edge_floor_over_rules` says whether the board minimum also raises a lower rule; it is false on 9.0.x and
10.0.x, where a board-wide rule governs below and above the minimum (`H-K-EDGE-RESOLVE`), and false on
Altium. `explain_edge(subject, ring)` returns an immutable `EdgeClearanceExplanation`: the item's
subject, the ring's name, the candidate rows (each matching rule with id, priority, selectors, layers,
value and severity, in precedence order with the governing one last, then the board minimum), the
switch and the governing limit, from the resolver's own candidates; resolving its inputs again gives the
finding's limit. Each `copper.edge-clearance` finding carries it, and its `relation` is `edge`, so
`group_findings` keeps edge findings apart from pair findings. The two hole findings carry no
explanation: no value applies to them. The stitching of `backends.kicad.copper` keeps its own
`edge_clearance_in_force` (a backend imports no check); for board-wide rules it equals `edge`, which
`tests/unit/checks/test_clearance.py` holds.

These diagnostic APIs are INFERRED on independently authored tests. Existing copper parity and
public corpus checks support unchanged numeric verdicts. No electrical profiles (c0098), areas,
pairs, waivers, impedance or power analysis are implemented here. Public rule references remain
S-0010, S-0038 and S-0020; see [existing format facts](formats/kicad/copper.md).
