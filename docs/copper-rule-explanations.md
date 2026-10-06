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

These diagnostic APIs are INFERRED on independently authored tests. Existing copper parity and
public corpus checks support unchanged numeric verdicts. No electrical profiles (c0098), areas,
pairs, waivers, impedance or power analysis are implemented here. Public rule references remain
S-0010, S-0038 and S-0020; see [existing format facts](formats/kicad/copper.md).
