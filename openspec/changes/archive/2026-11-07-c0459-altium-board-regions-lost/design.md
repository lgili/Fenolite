# Design: c0459

## Why not move the region with the board

The record holds its vertices as binary doubles after its property text, and its stack by id. Moving it
would need the record's binary layout, which no public source documents, and a stack id that the writer
gives its own stack. The region the public rows hold is the board's single layer stack region, which Altium
makes from the outline when the storage is absent: the round trip of row `-04` before c0450 held no
`BoardRegions` and poured (S-2180). Dropping the storage and saying so is the change that rests on evidence.

## Counting

`altium_storages.FRAME_BOUND` maps each frame-bound storage to its reason: `FRAME_BOUND_REASON` for
`BoardRegions`, `UNKNOWN_FRAME_REASON` for `CustomMaskShapes`. `altium_storages.Found` gains `frame_bound`,
by storage name, each with its record count (at least 1 when it holds data). The conversion to KiCad counts
each lost under `altium-storage` with its reason, beside the index-bound storages. `from_carried` keeps only the names in `CARRIED`, so a property left by an older
conversion is not written back.

## Why `CustomMaskShapes` goes too

No public row holds data in `CustomMaskShapes` (S-2181), so whether it holds geometry in the source's frame
is not known. Carrying bytes that no one has checked against a moved frame is how `BoardRegions` broke the
round trip, so the storage is counted lost instead. It costs nothing on the public rows. A document that
fills it loses its custom mask shapes in a round trip, and the report says so. Carrying it again needs a
public document that fills it and a kit run of its round trip.
