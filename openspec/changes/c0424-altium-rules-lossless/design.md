# Design: Altium rules without loss

## Fates

Each rule record of an Altium PCB document gets exactly one fate in a conversion to KiCad. One table,
`convert.altium_rules.FATES`, holds it per Altium kind. Neither the reader nor the writer holds a copy.

| Altium kind | fate | how |
|---|---|---|
| Clearance, Width, RoutingVias, HoleSize, BoardOutlineClearance, MinimumAnnularRing | written | the mapping of c0042 and c0084, as today |
| RoutingVias with a preferred drill or diameter KiCad cannot take | changed | `min` and `max` are written; the model keeps `opt` |
| HoleToHoleClearance, `ALLOWSTACKEDMICROVIAS=FALSE` | written | `hole_to_hole` |
| HoleToHoleClearance, `ALLOWSTACKEDMICROVIAS=TRUE` | changed | `hole_to_hole`; KiCad holds no allowance for stacked micro vias |
| SilkToSilkClearance | written | `silk_clearance`; KiCad's rule is board-wide, so only scope `All` to `All` |
| ComponentClearance | changed | `courtyard_clearance` from `GAP`; Altium measures 3D bodies or the component boundary, with a vertical gap |
| DiffPairsRouting | changed | `diff_pair_gap` (`MINLIMIT`, `MOSTFREQGAP`, `MAXLIMIT`) and `diff_pair_uncoupled` (`MAXUNCOUPLEDLENGTH`); the per-layer widths and impedance keys are not written, and KiCad checks the gap where Altium routes to it |
| RoutingLayers | written | one `no_tracks` per copper layer of the board whose key is `FALSE`; no rule when every layer is allowed |
| SolderMaskExpansion, PasteMaskExpansion | changed or kept | the first enabled record of scope `All` becomes the pads' margins (`design-conversion`, "Mask and paste of imported pads"); the others are kept |
| ShortCircuit, `ALLOWED=FALSE`, scope `All` | written | KiCad reports items of different nets that touch on every board |
| PolygonConnect | kept | the board keeps it (c0215); its mapping onto zones belongs to change c0420 |
| every other kind, and any record of the kinds above that does not map | kept | a declared format limit: the record is kept for an Altium write |
| a disabled record of any kind | kept | Altium skips it; KiCad has no disabled rule that leaves the next rule in force |
| a malformed record (no kind, no name, no priority) | lost | |

The kinds kept by default include RoutingTopology, RoutingPriority, RoutingCorners, FanoutControl, the four
test point kinds, SupplyNets, UnRoutedNet, UnpouredPolygon, LayerPairs, Height, NetAntennae,
MinimumSolderMaskSliver, SilkToSolderMaskClearance, SilkToBoardRegionClearance, PlaneClearance,
PlaneConnect, MatchedLengths and RoomDefinition.

- **Height.** KiCad's rules have no component height constraint (`rules.md`, the constraint list).
- **Plane rules.** The conversion gives an internal plane no zone (`altium-import`, "Objects on an internal
  plane"), so nothing in KiCad could take PlaneClearance or PlaneConnect.
- **Mask sliver.** Fenolite's model and KiCad writer hold no board-setup minimum mask web.
- **NetAntennae.** KiCad's dangling-track check takes no tolerance.

Each of these is a follow-up, not a loss: the record survives in the model.

## Kept records

A record is kept when it gives no rule that `rulemap.lower` writes again in its own form. That means its
index is not among `RuleMapping.sources`, or its kind is not one of `rulemap.KIND_ORDER`, or it is a
Hole To Hole Clearance with `ALLOWSTACKEDMICROVIAS=TRUE`, whose key the lowering writes `FALSE`.
`adapter.rules.kept_texts(records, mapping, numbers)` returns them as `<kind number>|<KEY=VALUE|…>` texts,
from `RULEKIND` on, in record order. Polygon Connect Style records stay out: the board already keeps them
as `polygon_connect`. The board stores the texts as `kept_rule` pairs of its `altium` bag, beside
`polygon_connect`. That bag is already part of the model, so no schema changes.

A rule mapped from a kept record carries the pair `kept_record` in its bag. `rulemap.lower` leaves such a
rule out, with no issue: the record that is written back holds it.

## Write-back

`lower` passes the `kept_rule` pairs of a board that was read to `PcbDocSpec.kept_rules`.
`pcbdoc.rule_records` writes them after the lowered and generated records:

- **Priorities.** A kept record of a kind with lowered records takes the next priorities of that kind, in
  its original priority order. A kind with no lowered record keeps the record's own priority.
- **Names.** A name already written gets the suffix `_kept`.
- **Plane defaults.** When a kept record is a Plane Connect or Plane Clearance rule, the default plane rule
  of change c0389 is not written.
- **Order.** The order of an enabled kept record against the lowered rules of its kind is kept only up to
  this priority rule. The change says so in `docs/altium.md`.

## Report outcome

`convert.report.Outcome` gains `kept`. `ReportRow.kept` counts the items, and `written` is `source -
changed - lost - kept`. The JSON shows `kept` only when it is above zero, so existing reports keep their
bytes. `lossy` and `refused` look at `lost` only. A kept item needs no consent: it is not lost.

The conversion counts as the `rule` source every neutral rule plus every kept record that gave no neutral
rule. The per-group `unmapped-rule-group-<n>` losses of `to_kicad.altium_to_kicad` are removed: each
record now has its own fate.

## Partial limits

`altium_to_kicad` lowers each rule alone. When the lowering refuses the rule only for limits that
`kicad.rulemap.LIMITS` does not take, the rule is lowered again without them, and one `changed` item names
the limits left out. Every other refusal stays as it is: a lost rule, or `kept` when the rule came from a
kept record.

## Shadowed rules

`checks.clearance.rule_precedence` puts priority 1 last, and the last rule governs. An imported rule keeps
Altium's priority: the reader takes it from the record, and the KiCad rule name carries it through
`import --to python` (c0409, B4). So the governing rule is Altium's, and `rules.shadowed` reports an
overriding that Altium applies too. A test pins this. The code is unchanged.

## Python import

`import --to python` reads the converted KiCad project, so a kept record does not reach `design.py`. The
conversion reports its kept rules with one `convert.kept` info per kind, as `convert.changed` does for
changed items, and the import forwards that info. So the record is named, not silently gone, and the
import does not refuse (a kept rule is not `unexpressed`). Carrying kept records through `design.py` needs a public DSL name, and is a follow-up.

## Alternatives

- **A model field for kept rules.** Rejected: the board's `altium` bag already carries Altium-only records
  (`polygon_connect`), and a new field would change the model schema for one backend.
- **Severity `ignore` for a disabled rule.** Rejected, as in c0043: in KiCad the ignored rule still governs.
