# Design: c0489

## D1 Mechanical layer kinds only from a public source

`import.md` records that Altium has no fixed fabrication or courtyard layer (S-0002, `INFERRED`), and the
import names Mechanical n `Mech.<n>`. A layer is read as a courtyard or assembly layer only by a key that
states its kind, and only when that key has a row in `docs/formats/altium/pcb-records.md` with a public
source and an evidence label. A layer name such as `Top Courtyard` is not used: names are free text.

Task 1.1 looks for that key in public sources. If none is found, the row stays `UNKNOWN`, steps 1 and 2 of
the order are off, and every footprint takes step 3.

## D2 The shape

Step 3 takes, in the footprint frame:

- the outline of each `ComponentBody` of the footprint whose geometry is known (a body with unknown geometry,
  c0099, is left out and the derived courtyard is `exact=False` anyway);
- the copper of each pad, as `frame._footprint_pads` gives it today.

It returns the convex hull of all those points (`frame.convex_hull`), grown by the margin with integer
arithmetic, as one closed polygon on `F.CrtYd` (top) or `B.CrtYd` (bottom). A convex hull overstates a
concave part. That is the safe side for a legality check.

Steps 1 and 2 take the closed outline of the layer's footprint drawings; step 2 grows it by the margin.

## D3 The mark

The graphic gets `provenance.evidence = Evidence(Level.INFERRED, hypotheses=("H-A-IMP-COURTYARD",))` and
the pair `("derived", "courtyard")` in its `altium` bag. Its id comes from the footprint id with the suffix
`#courtyard`, so it is stable across reads. A footprint that already has a courtyard graphic gets nothing.

## D4 Not written back

- The Altium writer (`lower`) skips a footprint graphic with the pair `derived=courtyard`. The skip is not
  a loss: the conversion report gives it no row.
- A conversion to KiCad writes the derived courtyard as an `fp_poly` on `F.CrtYd`/`B.CrtYd`, so KiCad's
  placement and DRC see it. It also carries, in the board property `Fenolite.Altium.DerivedCourtyards`, each
  one's footprint (by reference and position), layer and points.
- The way back finds each carried courtyard by content (footprint reference, layer and points within 1 nm
  in the written document's frame), not by uuid, as c0485 finds its arcs. A match is skipped. A courtyard
  that a person edited in KiCad no longer matches and is written as a source drawing.

## D5 Extents

`frame.placed_extents` gives a footprint with a derived courtyard the ring of that courtyard, `source`
`derived` and `exact=False`. Placement code that treats `courtyard` as a real courtyard treats `derived` the
same, except that `place.keepout-no-courtyard` and the "(approximate extent)" note still apply.

## Hypotheses registered by this change

| id | backend | statement | level |
|---|---|---|---|
| `H-A-IMP-COURTYARD` | altium | For an imported footprint with no courtyard, the convex hull of its known component bodies and its pad copper, grown by `DERIVED_COURTYARD_MARGIN`, encloses the part, so a placement check on it is on the safe side | INFERRED |

The row goes to `docs/hypotheses.md`, and the id to the adapter's `evidence.HYPOTHESES`, when task 1 lands.
