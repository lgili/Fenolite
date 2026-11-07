# Design: c0420

Every measurement below was taken on a private Altium board, converted to KiCad with this branch and
checked with `fenolite check` and KiCad 10.0.6. Its data, names and counts stay outside the repository;
the cases committed here are authored from public format facts.

## 1. Named polygons (B5)

`IsNamedPolygon('n')` is true for the pour object of that name (S-1790); the public Polygon Connect Style
records name a pour that way (S-0835). The scope reader keeps the closed grammar: `named_polygons` reads
a scope that is only such terms joined by `Or`/`||`, and stands for it with the selector `item_kind zone` plus
the set of names, compared case-folded. `governing_connection` takes the polygon's name: a named side
matches a polygon of one of its names and nothing else, so a record of another pour is passed over rather
than refusing the whole board (`connect-scope` before).

A KiCad pad holds one connection for every zone, while Altium resolves a pad per pour. The pad loop now sees
every zone of the pad's net: when the records give the pad the zone's own style everywhere, nothing
changes; when they give it one other style everywhere, the pad gets it; when the styles differ between
zones, the pad keeps its setting and the report says so (`PAD_DIFFERS`). A first version that compared
against one zone only gave own connections to many pads whose zones disagreed; the measured board then had
starved thermals that the source does not.

`tests/unit/backends/altium/test_connectstyle.py` asserted that `IsNamedPolygon('X')` refuses with
`connect-scope`. That was the gap this change closes, so the case now uses `InPolygonClass('X')`, still
outside the grammar, for the refusal, and `test_named_polygon_scopes` covers the named form.

## 2. `Not InAnyNet` (B7)

S-1680 states that `Not InAnyNet` returns the objects that are not nets or their primitives. `InAnyNet`
reads as `net *`; its negation is then exactly `NO_NET` (c0409), which the KiCad target writes as
`A.NetName == ''`. No new selector op. The Altium writer lowers `net *` back to `InAnyNet`, so `NO_NET` is written as
`Not InAnyNet` and a rule on netless pads survives a round trip.

## 3. Zone clearance (B6)

Measured first, on KiCad 10.0.6 with an authored board (`tests/kicad/fill/test_zone_clearance_oracle.py`):

| zone | custom rule on the other net | netclass | gap |
|---|---|---|---|
| 0.2 | 1.0 | 0.2 | 1.0 |
| 1.0 | 0.2 | 0.2 | 0.2 |
| 1.0 | none | 0.2 | 1.0 |
| 0.2 | none | 1.0 | 1.0 |
| 1.5 | none | 1.0 | 1.5 |

A matching custom rule decides; otherwise the larger of zone and netclass holds. The first-rule value of
c0409 put a high-voltage class value on zones that Altium clears much more tightly against most items,
and wherever no DRU rule matched a pair that value would have widened the gap. The smallest value that
governs any pair of the polygon is never wider than what Altium asks, and the DRU rules raise it where
Altium does. On the measured board every pair is covered by a DRU rule, and refilling with the widest and
with the smallest value gave identical fills on every copper zone, so the change is safe there and
correct where a pair is left to the zone.

The rules counted are those, in Altium's order, with a scope matching the polygon (the other scope may be
anything), up to and with the first whose other scope is `All`: a lower rule never governs a pair of the
polygon. Without a rule against all items the zone keeps its clearance (`NO_CLEARANCE`), as before.

c0409's requirement "Governing zone clearance" states the first-rule value. c0409 is not archived yet, so
this change adds "Smallest governing zone clearance" instead of modifying it. When both are archived, the
c0409 requirement is dropped in favour of this one.

## 4. Keep-out restrictions (N2, N3)

c0410 gave every Keep-Out-layer drawing all four restrictions, following KiCad's importer. That importer
reads a region's restrictions from a key that Altium does not write and falls back to 31
(pcb-records.md). On the measured board, the flagged Keep-Out-layer regions hold 7 (vias, tracks, copper),
and the mounting holes and a part's unplated pads lie inside them. Altium allows them there (S-1711); KiCad's
DRC reported `items_not_allowed`.

`keepout_restrictions` reads each drawing's restrictions value again from its record in the source
document, found by the drawing's locator (`Tracks6`, `Arcs6`, `Fills6`, `Regions6`). This is how
`zone_outlines` already reads a polygon. `keepouts` gives the rule area those restrictions. A drawing whose
record is not found, or whose document's SHA-256 changed, keeps all four, as c0410 measured.

A first version kept the value as a new extension-bag key, `keepout`. The model review approved a fixed set
of extension keys (c0218), and a new key would have needed that approval again, so the value is read from
the source instead. The model is unchanged.

Carving the holes out of the areas was tried and dropped. The holes are inside the value-7 regions, not
under the bands, so the restrictions alone settle it.

## 5. Net ties (N1)

`COMPONENTKIND` of the component record:

- The public `BMS.PcbDoc` (S-0188) holds 4 on its two `NETTIE` components.
- Altium's property page lists the types without numbers, in this order: Standard, Mechanical, Graphical,
  Net Tie (in BOM), Net Tie, Standard (No BOM), Jumper (S-1791). Counting from 0, 3 and 4 are the net ties
  (INFERRED, `H-A-PCBX-NETTIE`).

Import: such a component gets one group of its distinct pad numbers.

KiCad writer: writes `net_tie_pad_groups` after `attr` on a created footprint, where c0114 placed it for a
read one (KICAD-VERIFIED), instead of refusing. `FLOOR_HEADS` lists the head, and the coverage board writes
it. The KiCad DRC test bridges two pads of a converted footprint with a copper line:

- with the group, there are no new violations;
- without it, `clearance` and `solder_mask_bridge`.

KiCad reports the bridge as `clearance`, not as `shorting_items`. On the measured board, the shorting
findings were between pads joined through the footprint's copper, and they are gone with the group.

Altium writer: a footprint with groups is written as a component of `COMPONENTKIND` 4, right after
`UNIONINDEX`, where the public document holds it. Altium marks the whole component, so
`lower.net_tie_differs` counts as `net-tie` changes only the groups that say more than "every pad, one
group". The build's lens now carries a footprint's groups onto its placed instance. Reading the written
document gives the group back. The `net-tie` info of c0114 is left only for those other groups.

## 5a. Changed entries (B6)

A zone whose derived clearance differs from the one it was read with is counted under `zone` as changed
(`CLEARANCE_FROM_RULES`).

A first version also counted the Polygon Connect Style rules under `rule` as changed when every connect
style was read. c0424 (Altium rules lossless) replaces the unmapped-rule loop with a fate per rule record
and gives a Polygon Connect Style record that reads the fate changed, so that entry moved to c0424
(agreed with its session on 2026-11-05).

## 6. Hole clearance tolerance (N4)

`copper.clearance` already lowers its limit by `clearance_tolerance` (500 nm with KiCad rules,
`H-K-COPPER-EPSILON`, c0281); `copper.hole-clearance` did not, so an Altium length in mil that is no whole
number of nanometres, rounded on import, left copper a few nanometres inside the minimum. KiCad 10.0.6 tolerates
a gap 400 nm below the minimum and reports one 600 nm below (`tests/kicad/checks/test_hole_clearance_epsilon.py`),
so the check now subtracts the tolerance the caller passes. A direct call without tolerance stays strict.

## 7. Holes

KiCad holds no hole outside a footprint (c0167), so c0170 writes a board hole as a board-only
`Fenolite_Holes:NPTH_…` footprint with an empty reference. Reading those footprints back as `Board.holes`
was considered and dropped: KiCad refuses `Board.holes` on write, so a KiCad round trip of the converted
board would then fail. Every hole is instead counted `changed` under `hole`:

- `HOLE_REASON` for an unplated hole;
- `PLATED_REASON`, as before, for a plated one.

`test_kicad_overlapping_cutouts_are_merged` expected the hole as written (1, 1, 0, 0). It now expects it as
changed (1, 0, 1, 0), on purpose.

The `model.duplicate-ref` of the empty references is a warning, by c0167's rule for board-only parts. The
L1 `ref-ambiguous` is pairing: the source holds board holes and no components, so c0421 pairs them with the
NPTH footprints. The footprint shape was sent to c0421 on 2026-11-05.

## 8. TAB in a part parameter

c0363 keeps a KiCad property value with a TAB natively in the vendored footprint and never in
`Part.properties`, whose printable contract stays. c0379 made a non-KiCad TAB value a declared loss
(`property-tab`), because c0363 refused it.

An Altium import reads the board of its in-memory KiCad conversion, where each part parameter is one field
of the footprint. c0363's native path therefore applies as it does to a KiCad board. On the measured board,
the import then plans with no unexpressed item, its self-check is equivalent at levels 1 to 5, and the one
TAB value is in one vendored `.kicad_mod` and not in the script.

A parameter without that one field stays c0379's loss, never a refusal.

## 9. Level 7 residue (moved)

B8 (F.SilkS `graphic-missing` of footprints) and the footprint texts a created footprint does not write
moved to c0422. The pairing of footprint graphics, of `Mech.n` against `User.m` and of board holes moved to
c0421.

## Residue on the measured board

Single-spoke thermals where only one spoke fits, a mask bridge between pads of a fine-pitch part, and a via
pair just inside a high-voltage rule: the source's, not the import's.
