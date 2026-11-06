# Design: c0450

## Why a uuid marks a fill

A KiCad rectangle has no field that could say "this was a fill", but every item has a uuid, which KiCad
keeps on a save and on an edit of the item. A copy gets a new uuid, so a copied fill is written as a
region, which is safe. `boarditems` already tags script items with a version-8 uuid whose first 48 bits spell
`fenitm` (RFC 9562, S-0110). A fill uses the same scheme with its own 48 bits, `altfil`. Its last 74 bits
are a hash of the graphic's id, so the tag survives KiCad's sort and needs no registry.

The tag is set by the conversion, not by the import: the import knows nothing of KiCad.

## The fill record

The census of the 70 fills of the eight public rows (S-2091) finds 2 of 46 bytes (row `-01`) and 68 of
50, the form:
- the prefix (13 bytes);
- `x1`, `y1`, `x2`, `y2` (32-bit);
- the rotation as a double at 29;
- five zero bytes;
- the long layer id at 42;
- the restriction byte at 46, 0 without the keep-out flag;
- three zero bytes.

Every byte that is not one of those fields is zero in all 68.

The writer writes that form, with the corners of the rectangle about its centre and the rotation of its
first edge. A four-corner polygon is a fill only when its sides are perpendicular and equal in opposite
pairs, within 4 binary units (about 10 nm).

## Board properties

KiCad writes a board property as a root `(property "name" "value")` after `setup`, sorted by name, and keeps
any string value on a save, a 200 KB one included (S-2092). The values are compressed with `zlib` (standard
library). On row `-01` the `EmbeddedFonts6` storage gives a property of 698 048 characters, and the KiCad
board is 2.3 MB; KiCad 10.0.6 saves it back with the four properties unchanged (task 2.1).

The writer of a created board writes `Board.ext["kicad"]` root slots named `property` after `setup`. The
reader keeps unknown root children in those slots, so the conversion to Altium finds them again.

## Index-bound storages

A `PrimitiveGuids` record and a violation record name primitives by their index in their storage. The round
trip writes primitives in another order and count, so a copied record would name the wrong primitive. Altium
gives a primitive without a GUID a new one, and the next DRC run makes new violation records.

## Keep-out strokes of copper

A keep-out track or arc of a copper layer (second flag byte 2) is a rule area of that layer in the model:
the band its width covers (c0407). The census of the eight public rows (S-2093) finds eight: arcs of
components, two on Top in row `-04` and three on Top and three on Bottom in row `-08`, all in the 60-byte
form with the restriction byte 31 at 56; the other bytes after 47 are zero. No row holds a keep-out track;
its 49-byte form is the long track form of `pcb-records.md` (S-0580), with the byte at 45.

The marker of c0442 gains an optional `flag<r>/` segment after `Altium.KeepOut/`. The import knows the
stroke and its byte and records them in the area's bag (`stroke`: kind, points in the area's frame, width,
byte). The adapter imports no writer module, so it does not build the marker. The conversion clears every
bag, so it reads the strokes from the source design first, as it does the fill ids, builds each marker
(`keepout_lines.marker`) and names an area with it only when the area is still that ring of the stroke's
band within the c0442 tolerance (a footprint's area is turned into its pad frame). KiCad keeps a rule
area's name.

The writer checks the area again (`keepout_lines.intact`): one layer, the restrictions of r and no more, the
band as its outline. An area that passes is written as its stroke, on its own layer, with the flag, the
long layer id and r. A footprint's stroke is an item of the component, as KiCad holds it, without a layer
flip.

Writing the circles of rows `-04` and `-08` showed that the second ring of a c0442 circle looked for its
partner under the wrong name, so it stayed a keep-out region. The pairing now takes the first ring from the
second; c0442's tests had counted that leftover region as the board's own rule area.
