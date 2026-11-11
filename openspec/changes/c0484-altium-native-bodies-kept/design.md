# Design: c0484

## D1 Records as read

A body record is written as read, except for its prefix's component index (bytes 7 and 8 of the body,
`pcbrecords.prefix`). Its outline vertices are doubles in file units in the board frame; taking them through
the model's nanometres would round some of them. A record in the board frame is right only on a footprint
that has not moved, which D3 checks.

## D2 All or nothing per footprint

The generated model of a footprint is one STEP file for all its parametric bodies. Writing some records and
the model as well would draw those bodies twice. A footprint is carried only when each body of its
generated model has its record and its twin, and is an extruded body, a cylinder or a sphere. A body that
the conversion to KiCad lost (its geometry is not proved) is in no model and stays lost.

## D3 Match by model bytes and footprint pose

A script's build gives footprints other uuids, so the key is:
- the SHA-256 of the generated model's bytes, which also proves that the bodies were not edited in KiCad;
- the footprint's place (nm) and turn (µdeg, modulo a full turn) in KiCad, and its side.

The model must also sit unmoved in its footprint (offset 0 and no turn), as the conversion to KiCad placed
it. The way back puts the footprint where the source had it while the frame carrier (c0467) holds; the
board check shows it on the maintainer's board.

shortcut: the footprint pose is compared in KiCad's frame, not in the document's units. A frame that does
not come back would shift the kept records with respect to their component; comparing the written
component's place in units with the source's would close that.
