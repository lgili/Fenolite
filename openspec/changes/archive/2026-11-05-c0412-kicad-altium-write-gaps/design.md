# Design: c0412 KiCad to Altium write gaps

## Copper shapes (B12)

What the records need is already in `docs/formats/altium`:

- The common prefix (layer, two flag bytes, net index at 3, polygon index at 5, component index at 7) is
  the first 13 bytes of the geometry subrecord of every primitive, a region included (`pcb-read.md`,
  "Fields"; the net row is `ORACLE-VERIFIED(kicad-cli)`).
- The region framing, its property text and its two storages are in `pcb-read.md` ("Regions") and
  `pcb-records.md` ("Regions and keep-outs"). `KIND=0` is a copper or drawn shape.
- The import already takes a free copper region with the net of its prefix (`pcb-pour.md` I18), and the
  computed pour shapes such regions from the document's own records. So the written copper joins the
  pour of its net and clears the pours of other nets without pour code.

`pcbrecords.region_record` gains `net=`. `lower._items` keeps copper graphics on signal layers. A plane
holds no primitive (`_Copper.signal_layer`). It maps the graphic's net through the same `net_names` as
the tracks; a net that no record holds leaves the shape out as a `net` loss. `pcbdoc.free_records`
writes them with the copper layer id from `_Copper.layers`, so the build path (`options` given, empty
`layer_ids`) works as well as the conversion path.

**Fill record.** The brief allowed a fill for an axis-aligned rectangle. The fields at 13 to 37 of a fill
are documented (`pcb-read.md`, FillRecord rows), but a saved fill is 46 or 50 bytes long, and no row says
what bytes 37 to 45 hold. Writing a 37-byte fill would be a guess about bytes Altium may read, so every
copper shape is a region: a rectangle is a region of four vertices. This is the one point of B12 that
the documentation decides.

## Rule scopes (B14)

The writer's guard stays: a scope is written only when `parse_scope` reads it back as the selector. The
writer builds the query bottom-up:

| selector | query |
|---|---|
| `net v` | `InNet('v')` |
| `netclass v` | `InNetClass('v')` |
| `ref v` | `InComponent('v')` |
| `item_kind track`, `via`, `pad` | `IsTrack`, `IsVia`, `IsPad` |
| `item_kind zone` | `InPolygon` |
| `and(a, b, …)` | `a And b And …` |
| `or(a, b, …)` | `a Or b Or …` |
| `not(a)` | `Not a` |

An operand that is itself an `and`, `or` or `not` is put in parentheses, because the reader holds one
kind of operator per level. Sources: `InComponent`, `IsPad`, `IsTrack`, `IsVia`, `And`, `Or`, `Not` are in
the reader's grammar (`rule-file.md`, "Closed scope grammar", S-0296, S-1531). `InPolygon` comes from
S-1702: the note under `IsPolygon` on Altium's Object Type Checks page says a clearance rule for a pour
must use the `InPolygon` attribute check, because clearance applies to the primitives in the pour. KiCad's
`A.Type == 'Zone'` (`item_kind zone`) matches a zone's filled copper in a clearance, so the two name the
same copper. The reader maps `InPolygon` and `InPoly` back to `item_kind zone`. That changes one import
count: a scope with `InPolygon` alone was unmapped (`rule-file.md`, "Unmapped forms"), and now maps.

Kinds take the forms as before (`RuleRow.scopes`); the forms `ref`, `item`, `or` and `not` are added to
every exact row. The rule name stays derived from the scope: leaf names are joined by `_and_`, `_or_`
and `not_`, then sanitised to the characters the name already allows.

The single-sided rule for pads without a net is a selector of these leaves:
`or(and(or(ref …), item_kind pad), and(ref …, item_kind pad, not(or(net …))))`, the pads of parts with no
net or a part's pads minus its nets. Written in the forms above, it is covered by the general rule. A
`no_net` leaf (`InNet('No Net')` or another query) is not written: no source read documents the query
for an object without a net.

`InPolygon`, not `IsPolygon`, is the query for `item_kind zone`: the note under `IsPolygon` (S-1702) says
a clearance rule for a pour must use `InPolygon`, because the clearance applies to the primitives the pour
holds.

## Rule values (B14)

`lower` writes a rule only when the record holds it exactly, and the spec says so ("A minimum alone is
not a Width rule"). `pcb-copper.md` records that a Width record holds `MINLIMIT`, `PREFEREDWIDTH` and
`MAXLIMIT`, a Routing Via Style record its seven keys (diameter and hole, each minimum, preferred and
maximum), and a Hole Size record `MINLIMIT` and `MAXLIMIT`, and that no record read leaves a limit out
(`H-A-RULE-KINDS`). No source states a value that means "no bound". So each combination is decided by
whether the rule gives every limit of its record:

| rule (scoped `all` or by a selector) | record | decision |
|---|---|---|
| `track_width` min, opt, max | Width | written |
| `track_width` min only; min and max | Width | loss: no preferred width, no maximum; a chosen one would be a bound or a routing width the rule does not hold |
| `via_diameter` min, opt, max with `via_drill` min, opt, max of the same selector | Routing Via Style | written |
| `via_diameter` without such a `via_drill` | Routing Via Style | loss: the record holds the hole limits too |
| `via_diameter` min only | Routing Via Style | loss: no preferred or maximum diameter |
| `hole_size` min and max | Hole Size | written |
| `hole_size` min only | Hole Size | loss: no maximum |

The reason sentence of each loss names the missing limit or the missing partner rule and says why
(`rulemap._lengths`). A rule scoped `all` takes the same path as a scoped one: the scope plays no part in
the decision. This change writes no value it cannot read back, so `lift(lower(r))` equals `r` for every
written rule.

## Mechanical user layers (B13)

`lower._document` builds `layer_ids` from `KICAD_MECHANICAL`. A new step reads each `User.<k>` layer of
`board.layers` whose `kicad` bag holds `user_name` matching `Mech.<n>` or `Mechanical <n>` (1 ≤ n ≤ 16)
and maps that layer to `56 + n`. The first form is the name Fenolite's Altium import gives a mechanical
layer (`lower.MECHANICAL_LAYERS`); the second is the name the board record gives it
(`pcbrecords`, layer names). The named map replaces the fixed position of that layer. Another layer that
the fixed map puts on the same mechanical layer (`F.Fab` on Mechanical 13, for example) keeps its place,
so both are drawn there. The named layers come last in the map, so the board record names their
mechanical layer after the named user layer (`User.11`), as it names every other layer after the last
KiCad layer that lands on it (`lower.kicad_mechanical`). A user layer above `User.8` without such a name
is a `graphic` loss (`altium.not-lowered`), as before.

## Imported designs in an Altium build (B15)

Two routes were possible: honour the override, or refuse with a better hint. The Altium build already
resolves KiCad footprints through the same resolver and authored definitions as the KiCad build
(`lens.altium.resolve_footprints`). The definition the import pins is a KiCad footprint in the
project's own library. Honouring it costs one model rewrite before the Altium lens runs:
`lib_footprint_ref := footprint_definition_ref`. A refusal would leave every imported design unbuildable
for Altium, with a workaround (rewrite the script) that loses the geometry pin. So the override is
honoured.

The written footprint name is the definition's name. The native identity cannot be kept when two
instances share a native name with two geometries, because one PcbLib storage holds one footprint per
name. Each part whose written footprint differs from its native link gets an `altium.footprint-definition`
info (`where` the part's path). A part without the override is untouched, so every existing Altium build
keeps its bytes.
