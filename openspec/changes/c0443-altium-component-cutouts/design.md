# Design: c0443

## Model form

A footprint's `Edge.Cuts` polygon is what KiCad itself holds for a cut-out that belongs to a part. KiCad
joins it into the board outline when it checks the board. The model therefore needs no new field. The
reader places the region's ring in the footprint's pad frame, as it places every graphic of a component.
The writer places it back with the instance (`ComponentGraphic`: no mirror, no layer flip), as it writes
every other graphic it keeps for the instance.

## The ring a KiCad outline repeats

`convert --to altium` takes the board's cut-outs from KiCad's edges (`edge_outline`), which include the
footprints' edge items. Without a check, a footprint's cut-out would be written twice: once with the
component and once free. `_cutouts` compares each cut-out of one ring and no arc with the placed rings of
the footprints' cut-outs. It leaves out a ring with the same vertices within 10 nm, which is the rounding
a placement gives.
