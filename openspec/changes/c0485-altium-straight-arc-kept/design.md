# Design: c0485

## D1 Carry the import's own pair

The import keeps each arc record's centre, radius and angles in the pair `arc` (c0127,
`adapter.copper.arc_pair`), and `lower.kept_arc` already writes a record from it when its points still lie
within `ARC_TOLERANCE` of the model's. The carrier holds that pair as text, so the record comes back exact
and the check is the one a rewrite uses (`lower._arc_geometry`).

## D2 Match by ends, layer, width and net

The KiCad item's uuid changes when a script is built, so the key is the item's own data: its layer, its
width, its net's name, and its ends in the written document's frame. The middle point of the record is
compared with the midpoint of the ends, which lies within a nanometre of it for an arc whose points lie on
one line. Both orders of the ends are tried. Each record is taken once.

## D3 Tracks and straight arcs

A conversion back reads the KiCad arc as an arc whose points lie on one line; a script's build holds it as
a track (`import.arc-as-track`). Both are looked up: a matched straight arc is written with the record
instead of the c0435 track and counts no change; a matched track is written as an arc.
