# Altium PCB document: poured copper (`.PcbDoc`)

This page states, in Fenolite's own words, what the pour engine `fenolite.backends.altium.pour` (change
c0215) relies on to compute the copper of a polygon pour and to write it as regions. The polygon record
itself is in `pcb-copper.md`, "Polygon pour"; the region record in `pcb-records.md`, "Regions and
keep-outs", and `pcb-read.md`, "Regions".

- Sources: Altium's documentation, read for facts only (S-0196, S-0287, S-0460, S-0462, S-0558, S-0771,
  S-0833, S-0834), and the eight public PCB documents and the public rule file of the corpus, read with
  Fenolite's own readers (S-0835; the documents of S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199,
  S-0200 and the rule file of S-0297). Nothing of them is in the repository, and nothing is copied: the
  rows state the rules their records follow. Nothing was decompiled, and no third-party code was read.
- A row about what the saved files hold is `CORPUS-VERIFIED`; a row about what Altium does with it is
  `INFERRED` under an `H-A-POUR-*` hypothesis until the kit group K6 settles it (`docs/altium-kit.md`).
- The engine uses an input only when it has a row of "Pour inputs" (`pour.INPUTS`; a unit test compares
  the two). `tests/unit/test_format_facts.py` checks the tables.

## Pour inputs

| fact | source | label | hypothesis |
|---|---|---|---|
| I1. The polygon record gives the outline, the layer, the net, `POURINDEX`, `HATCHSTYLE`, `REMOVEDEAD`, `REMOVEISLANDSBYAREA` with `AREATHRESHOLD`, `REMOVENECKS` with `NECKWIDTHTHRESHOLD`, `ARCRESOLUTION`, `POUROVER` with `POUROVERSTYLE`, `OPTIMALVOIDROTATION` and `SHELVED`. A solid pour (`HATCHSTYLE=Solid`) is built from regions, one per contiguous area; a hatched one from tracks and arcs; a shelved polygon takes part in no check and no connectivity | S-0196, S-0833, S-0834, S-0835 | INFERRED | H-A-POUR-REGION |
| I2. The clearance from the pour to an object of another net is the value of the Clearance rules: the first enabled rule, by priority (1 is the highest), whose two scopes match the polygon and the object in either order, and in that rule the matrix cell of the polygon's kind (`Poly`) and the object's kind when the record holds one, else its generic value. The void of a sharp ring (a rectangular pad, a fill, a region) keeps square corners: the saved pours of the public documents show square voids around rectangular pads, a superset of the round ones. Beside straight tracks the saved pours lie 3.7 to 6.0 µm beyond the clearance (census of 2026-10-26), a margin no source states | S-0558, S-0462, S-0833, S-0744, S-0835 | INFERRED | H-A-POUR-CLEARANCE |
| I3. A Clearance rule for a polygon alone names it with the query `InPolygon` (or `InPoly`); one public Clearance record of the eight documents holds `InPolygon` in a scope | S-0833, S-0835 | INFERRED | H-A-POUR-SCOPE |
| I4. A void lies at the exact value of its rule. Altium's own rule check passes copper up to 3.5 file units inside a clearance (c0152), which is a tolerance of the check and no part of a pour | S-0616 | INFERRED | H-A-POUR-CLEARANCE |
| I5. Polygon Connect Style gives the connection of a pad or a via of the polygon's net: Relief Connect, Direct Connect or No Connect; a relief has an air gap width, a conductor width and 2 or 4 conductors at 90° or 45°; the Simple form holds one setting for pads and vias, the Advanced form one each for through-hole pads, SMD pads and vias; an Auto mode, a minimum distance between conductors and an object's own Thermal Relief setting exist and are not read by Fenolite | S-0287, S-0833, S-0834, S-0835 | INFERRED | H-A-POUR-CONNECT |
| I6. A relief is a void of the pad's or via's copper grown by the air gap width, crossed by its conductors: bars of the conductor width from the pad's centre, at 0° (90° angle) or 45° (45° angle) and then every 90° for four conductors, turned with the pad's rotation, reaching across the gap into the pour; a conductor that would cross the clearance of another net's object is left out | S-0287, S-0833 | INFERRED | H-A-POUR-RELIEF |
| I7. Direct Connect joins the pad's copper to the pour with no void; No Connect keeps the air-gap void and no conductor | S-0287, S-0833 | INFERRED | H-A-POUR-RELIEF |
| I8. Objects of the polygon's own net are covered by the pour or avoided by `POUROVERSTYLE`: Don't Pour Over Same Net Objects pours in free space only, Pour Over All Same Net Objects covers same-net tracks, arcs, fills, regions and polygons, Pour Over Same Net Polygons Only covers same-net polygons and avoids every other object. Every saved polygon pairs `POUROVER=TRUE` with `POUROVERSTYLE=1` (64 of 82) or `POUROVER=FALSE` with `POUROVERSTYLE=2` (18 of 82); no saved polygon holds 0. Fenolite reads 0 as Don't Pour Over, 1 as All Same Net Objects and 2 as Same Net Polygons Only | S-0833, S-0835 | INFERRED | H-A-POUR-OVER |
| I9. Polygons on one layer are poured in rising `POURINDEX`; a polygon of another net poured later keeps the clearance from the copper of an earlier one; of overlapping polygons the one of higher order pours over the shared area; layers do not interact | S-0196, S-0833 | INFERRED | H-A-POUR-ORDER |
| I10. Necks are the copper that an opening by a disc of diameter `NECKWIDTHTHRESHOLD` removes, taken piece by piece: a piece at a convex corner sharper than 89.5° goes with its convex hull near that corner, so the tip is cut by the chord between the ends of the opening's arc (2·r·cos(α/2) for a corner of α, r half the width); the sliver the opening takes off a corner of 89.5° or more comes back, so that corner stays sharp; every other piece is a neck and is removed. The page says that the removal rounds outer corners to half the width; the saved pours of the public documents hold no convex corner below 75° and only 16 between 75° and 89.9° among 2853 at 75° or more, and their acute tips are cut by such a chord. With `REMOVENECKS=FALSE` nothing is removed | S-0833, S-0835 | INFERRED | H-A-POUR-NECK |
| I11. The steps run in this order: the area within the outline and the board; the voids of other nets, keep-outs and earlier pours; the relief voids and the same-net avoidance; the neck removal; the conductors and direct joins; the pieces; the islands; the dead copper | S-0833 | INFERRED | H-A-POUR-STEPS |
| I12. With `REMOVEISLANDSBYAREA=TRUE`, a piece whose area is below `AREATHRESHOLD` is removed whatever it connects. `AREATHRESHOLD` is in square file units (0.0001 mil squared): the saved values are 250000000000.000000 (63 polygons; 2500 mil²), 232500465000.930304 (9; 1.5 mm²) and 15500031000.062008 (10; 0.1 mm²) | S-0833, S-0835 | INFERRED | H-A-POUR-ISLAND |
| I13. With `REMOVEDEAD=TRUE`, a piece that touches no object of the polygon's net (a pad through a conductor or a direct join, a via, a same-net track, arc or region that it covers) is removed; a polygon that encloses no pad of its net keeps its outline and no copper; a polygon without a net pours nothing | S-0833, S-0834 | INFERRED | H-A-POUR-DEAD |
| I14. A curve (an arc, a round pad, a track end, a via, a rounded corner) is drawn with straight edges within `ARCRESOLUTION` of the true curve while the advanced pour is off; Fenolite keeps each void outside the true curve and each copper corner inside it, so no copper comes nearer than its clearance. The saved values are 0.5mil (63 polygons), 0.0394mil (9), 0.5118mil (9) and 0.3937mil (1) | S-0833, S-0771, S-0835 | INFERRED | H-A-POUR-ARC |
| I15. Optimal Void Rotation arranges the edges of the voids to widen necks; a polygon with `OPTIMALVOIDROTATION=FALSE` is poured without it. Every saved polygon that holds the key holds `TRUE` (77 of 82; 5 lack the key) | S-0833, S-0835 | INFERRED | H-A-POUR-VOIDROT |
| I16. A keep-out region with the copper restriction (`KEEPOUTRESTRICTIONS` bit `0x04`; second flag byte 2), on the polygon's layer or on the Keep-Out layer, is a void at the clearance of the governing rule. The import makes a filled graphic of a keep-out region, so the engine reads it from its record | S-0833, S-0835 | INFERRED | H-A-POUR-KEEPOUT |
| I17. The pour lies within the board shape (the outline less the board cut-outs the document holds), inset by the governing Board Outline Clearance when the document holds one | S-0460 | INFERRED | H-A-POUR-EDGE |
| I18. A pad or a via is its copper on the polygon's layer as the copper check shapes it for an Altium reading (`checks.copper`, "Copper items and their shapes"); a via without a pad shape on a layer (c0132) is its hole there. The copper that the import keeps as graphics (the tracks and arcs of components, fills, free copper regions) is shaped from its record, with the net of its prefix; a region is its outline | S-0835 | INFERRED | H-A-POUR-VIAPAD |
| I19. A hole without copper keeps the clearance of the `Hole` row of the Clearance matrix | S-0462, S-0558 | INFERRED | H-A-RULE-CLEARANCE-CELLS |
| I20. Copper text, polygon cut-outs (regions of `KIND=1`), a pad whose copper the import does not shape, and an object's own connect style are inputs the engine does not shape: a polygon that one of them reaches is not poured | S-0833, S-0834 | INFERRED | H-A-POUR-REGION |
| I21. The kit's repour runs with `PCB.Polygon.AdvancedPour` off, so curves are straight edges | S-0834 | INFERRED | H-A-POUR-ENGINE |

## Polygon Connect Style records

| fact | source | label | hypothesis |
|---|---|---|---|
| A Polygon Connect Style record of `Rules6` has the kind number 20, `RULEKIND=PolygonConnect`, `NETSCOPE=AnyNet`, `LAYERKIND=SameLayer` and the common rule keys, then either the five keys `CONNECTSTYLE`, `RELIEFCONDUCTORWIDTH`, `RELIEFENTRIES`, `POLYGONRELIEFANGLE` and `AIRGAPWIDTH` (14 records) or the same five keys three times, prefixed `THPAD.`, `SMDPAD.` and `VIA.`, in that order (4 records). The rule file of S-0297 holds one record of the first form | S-0835 | CORPUS-VERIFIED | H-A-POUR-CONNECT |
| `CONNECTSTYLE` is `Relief` (7 values) or `Direct` (19); `RELIEFENTRIES` is `4` (26); `POLYGONRELIEFANGLE` is `90 Angle` (25) or `45 Angle` (1); the widths are lengths in mil. No public record holds a No Connect style, so its value is not known | S-0835 | CORPUS-VERIFIED | H-A-POUR-CONNECT |
| The scopes of the 18 records: `All` and `All`; `InNet`, `InNetClass` or `HasFootprint` in the first scope with `All` in the second; `All` with `IsVia` or `InNet` in the second; a polygon query (`IsNamedPolygon`) or a layer query in the first. A binary rule applies when the two objects match its two scopes in either order | S-0835, S-0558 | INFERRED | H-A-POUR-CONNECT |
| `IsNamedPolygon('name')` is true for the polygon pour object of that name, not for the primitives of its copper; `InNamedPolygon` is the query for those primitives | S-1790 | INFERRED | H-A-POUR-CONNECT |

A Polygon Connect Style scope of named polygons (`IsNamedPolygon('n')`, or such terms joined by `Or` or `||`,
one pair of parentheses round the whole allowed) governs the pours of those names, compared without case, and no
other pour (change c0420, B5; `connectstyle.named_polygons`). Any other polygon query stays a `connect-scope`
refusal. In a conversion to KiCad each zone takes the record that governs it by its own name; a pad whose
governing records give it another style than its zones do gets its own `zone_connection` when they give it one
style for every zone of its net, and keeps its setting with a `pad` change when they give it different styles,
since a KiCad pad holds one connection for every zone.

## Saved poured regions

| fact | source | label | hypothesis |
|---|---|---|---|
| The 82 polygons of type `Polygon` of the eight documents hold 229 poured regions in `Regions6` (regions whose prefix names a polygon index), with 2682 holes, and each has its twin at the same position of `ShapeBasedRegions6` with the same prefix, the same property text and the same rings, whose vertices the twin holds as whole units within one unit of the doubles of the plain form | S-0835 | CORPUS-VERIFIED | H-A-POUR-REGION |
| The property text of a poured region holds, in this order, `V7_LAYER` (the polygon's layer), `NAME` (one space), `KIND=0`, `SUBPOLYINDEX` (the number of the piece in its polygon), `UNIONINDEX=0`, `ARCRESOLUTION` (the polygon's value), `ISSHAPEBASED=FALSE` and `CAVITYHEIGHT=0mil`: the keys of a free region | S-0835 | CORPUS-VERIFIED | H-A-POUR-REGION |
| The prefix of a poured region holds the flags `0C 00`, no net (`0xFFFF`), the index of its polygon as the record's position in `Polygons6` (not its `POURINDEX`, which differs from the position in 80 of the 82 polygons), and no component | S-0835 | CORPUS-VERIFIED | H-A-POUR-REGION |
| The outer ring of a poured region runs clockwise in the file's frame (229 of 229) and each hole anticlockwise (2682 of 2682); no ring repeats its first vertex in the plain form; the holes follow the outline in both forms as plain vertex lists | S-0835 | CORPUS-VERIFIED | H-A-POUR-REGION |
| The pieces of a polygon carry `SUBPOLYINDEX` 0 to n − 1 in stream order in 69 of 81 polygons (4 hold another order of those numbers, 8 numbers with gaps); poured regions stand among the other regions of `Regions6` in no fixed order, and the vertices of 6 of the 8 documents are not all whole units | S-0835 | CORPUS-VERIFIED | H-A-POUR-REGION |
| No other storage of the eight documents names a region by its position: the read primitives refer to polygons and components, never to regions | S-0835 | INFERRED | H-A-POUR-REGION |

## Outline arcs

Change c0463, S-2221: the twelve polygons of the public rows whose outline holds an arc vertex, read with
Fenolite's own reader on 2026-11-06, and their saved regions.

| fact | source | label | hypothesis |
|---|---|---|---|
| 12 polygons of type `Polygon` hold an arc vertex: 2 of row -02, 4 of row -07 and 6 of row -08. Their 194 arc vertices hold `KIND<k>=1` with `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `R<k>`, `SA<k>` and `EA<k>`; each sweeps a quarter turn (122) or an eighth of a turn (72) counter-clockwise from `SA` to `EA` | S-2221 | CORPUS-VERIFIED | H-A-POUR-ARC |
| The arc of vertex k joins vertex k to vertex k + 1: the ends computed from its centre, radius and angles lie within 6.7 µm of the two vertices, the start angle's end at vertex k for 72 arcs and at vertex k + 1 for 122, so a ring walks an arc either way | S-2221 | CORPUS-VERIFIED | H-A-POUR-ARC |
| The saved regions follow 2 arcs of each polygon of row -02 (radius 39.4 and 41.9 mil, `ARCRESOLUTION=0.5mil`) with 10 vertices each, within one unit of the arc: its two ends and 8 between them at 5.625° + k·11.25° from the start angle, 32 steps per turn. The largest step within 0.5 mil is 18.3° there. No other outline arc of the 12 polygons bounds saved copper: the regions lie inside them | S-2221 | CORPUS-VERIFIED | H-A-POUR-ARC |

## Outlines that are not simple

Change c0463, S-2222: the two polygons of the public rows whose outline the pour refused as `outline`
before the change, and their saved regions.

| fact | source | label | hypothesis |
|---|---|---|---|
| Two polygons repeat a vertex: in row -02 (`NETD1_1_L01_P000`, 10 vertices) and row -07 (`POURINDEX=17`, 8 vertices) the vertex before the closing one stands twice in a row, and the last vertex repeats the first | S-2222 | CORPUS-VERIFIED | H-A-POUR-REGION |
| Altium's saved pour of each is one region whose outer ring follows the outline without the repeat (19 and 30 vertices, no hole), pulled in by clearances and rounded corners | S-2222 | CORPUS-VERIFIED | H-A-POUR-REGION |
| No polygon of the eight rows has an outline that touches itself at a vertex or crosses itself, so the rows do not show how Altium fills either | S-2222 | CORPUS-VERIFIED | H-A-POUR-REGION |

## Records of Altium's repour

Change c0463, tasks 3.1 and 4.1. Two runs of Altium Designer 26 give the pour that Altium makes, with no
saved pour to trust: step K6.12 of the kit repours the sample `pour-hatched` (S-2223), and the step
`repour` repours the eight public rows of the pour census as published (S-2224).
`tools/kit_pour_c0463.py prepare` writes the folder of the run outside the repository, and `record` reads
the boards Altium saved into `tests/data/altium/kit/pour-hatched.json` and `tests/data/altium/kit/repour.json`
(`backends.altium.pourrecord`, schema `fenolite.altium-kit-pour-record.v0`). Per polygon a record holds:

- its `LAYER`, `HATCHSTYLE`, `GRIDSIZE`, `TRACKWIDTH`, `POURINDEX` and `SHELVED` as saved;
- its regions: their count, holes, vertices, area in nm² and the SHA-256 of their rings (each ring from its
  least vertex, counter-clockwise), which a test given the saved board checks;
- the tracks and arcs that name it: their counts, the exact directions of the tracks (`dx:dy`) and widths.

The record of the sample also lists every poured track and arc in file units, from which the hatch is built
(task 3.2). The record of a row holds no coordinate: no stretch of a row's geometry enters the repository,
and no board that Altium saved does. Each record names the tool, the date, the SHA-256 of each source and
saved board, and the dialogs and message counts the run typed.

The writer writes a zone whose `altium` pairs hold `hatch_style`, `grid_size` and `track_width` (nm) as a
hatched polygon: `HATCHSTYLE`, `GRIDSIZE` and `TRACKWIDTH` (`docboard.polygon_fields`). A zone read with
`hatch_style` alone keeps the solid pour's keys: the import does not keep the grid or the track width yet.

## Fenolite's choices

- **Regions.** A computed pour is written after every other region of `Regions6`, so the positions of the
  graphics, keep-outs and cut-outs do not change: polygon by polygon in record order, each polygon's pieces
  by their lowest point and then their leftmost point, `SUBPOLYINDEX` 0 to n − 1, `ARCRESOLUTION` the
  polygon's value. Vertices are whole units; the outer ring runs clockwise and each hole anticlockwise in
  the file's frame; the twin of each region stands at the same position of `ShapeBasedRegions6`.
- **Polygons.** With the pour mode `computed` the polygon record gets `OPTIMALVOIDROTATION=FALSE`
  (I15); every other key is the key of `pcb-copper.md`, "Fenolite's choices".
- **A scope that is not read, on the way back** (change c0457). Since change c0434 a Clearance record
  whose scope the pour does not read comes back from KiCad as read, so the pour of the way back refuses
  the polygons it could govern (`rule-scope`, then `depends-on-refused`), as the pour of the source does.
  Public row -04 refuses its 9 polygons both ways (S-2160). Neither ignoring the record (what lote-27 did
  by losing it) nor pouring with the larger of its gap and the governing gap matches Altium: 8 of the 9
  saved pours of -04 differ from either by 3.5 to 7.4 times the M1 allowance, and 4 polygons of -07 by up
  to 10.9 times (S-2160). So the refusal stays.
- **Outline arcs** (change c0463). The import gives a polygon with an arc vertex the ring of its record
  (`adapter.arcring.record_outline`, `altium.import.zone-arc`), and the pour pours it: each arc becomes the fewest
  equal chords whose sagitta is at most the polygon's `ARCRESOLUTION` d, their ends on the arc and the two
  vertices at the arc's ends. Altium places more vertices on the arcs of row -02 (S-2221); the two rings
  differ by less than d, which M1 and M2 allow. The polygon record is not changed: the regions are chords.
  An arc without radius, or whose ends lie more than 10 µm from its two vertices, refuses `outline-arc`.
- **Outlines that are not simple** (change c0463). A run of a repeated vertex is kept once, as Altium's
  saved pours of rows -02 and -07 show (S-2222). A ring that touches itself at a vertex is poured as the
  boolean backend's normal form gives it, one piece per loop; no source shows Altium's fill of such a ring
  (S-2222), so this rests on `H-A-POUR-REGION`. A ring that crosses itself still refuses `outline`.
- **Exact non-pours** (change c0463). `shelved` and `plane-layer` are Altium's own outcome, not refusals:
  Altium shows a shelved polygon with no copper (I1), and an internal plane is no polygon pour. They pour no
  copper, a census counts them under `exact`, and no later polygon of the layer is held back by them
  (`pour.EXACT`). Every value of `POUROVERSTYLE`, `ARCRESOLUTION`, `AREATHRESHOLD` and
  `NECKWIDTHTHRESHOLD` that I8, I10, I12 and I14 record reads; `threshold` and `pour-over` remain for a
  value no source defines.
- **Polygon Connect Style.** The records of change c0215, Decision 11: the Advanced form, one rule per
  net scoped `InNet` and one `All` rule.
