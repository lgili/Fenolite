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

The properties are written and read with `backends.kicad.boardcarrier` (change c0434): the conversion to
KiCad gives the storages and the rule records of `Fenolite.Altium.Rules6` to one `with_carried` call, and
the conversion to Altium reads them with `carried`. The bytes a storage property carries are the length of
`Header` (32-bit), `Header` and `Data`; `boardcarrier` packs them as base64 of zlib (level 9).

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

## Mechanical layers above 16 (task 4.4)

A layer byte names Mechanical 1 to 16 only (57 to 72). A track, an arc or a fill on Mechanical 17 to 32
holds the byte of Mechanical 16 and the layer's long id (`pcb-records.md`, "Long forms"; S-1654), and Altium
shows it on the layer of the long id (S-1588). The import named such an item by its byte, `Mech.16`, so the
round trip wrote it back on Mechanical 16: 4 074 tracks, 116 arcs and 5 fills of row `-08`, 56 tracks of
`-04` and 60 of `-07`.

The adapter now gives such a record the long id as its layer before it maps the primitives, and names it
`Mech.<n>`, with the Altium name of the `LAYERV7_<i>` entry whose `LAYERID` is that id. KiCad needs no
carrier: the conversion gives every `Mech.<n>` a user row of that user name (up to 45 rows). On the way back
`lower.named_mechanical` reads `Mech.<n>` up to 32 and gives n above 16 its long id
(`pcbrecords.mechanical_id`). The writer takes a long id as a layer: the prefix holds the byte 72, a track or
an arc is written in the long form (the union tail of c0460 with index 0), a fill holds the long id at 42,
and `pcbdoc.record_layer` reads the long id back, so the board record enables the layer where it is used
(`LAYERV7_<i>MECHENABLED`, the `V9` and `_V8` lists, the layer sets). `Board6.Settings` carries
`LAYERV7_<i>LAYERID`, `NAME` and `MECHENABLED` beside the keys of Mechanical 1 to 16, and a slot of 17 to 32
takes the source's name and flag as c0464's slots do. Texts and regions on these layers are not moved: the
text form the writer writes holds no long id.

## Texts on Mechanical 17 to 32 (task 4.5)

A text record names Mechanical 17 to 32 the way a track does: the byte of Mechanical 16 and the layer's long
id, at 226 of a first subrecord of 232 or 252 bytes (`pcb-records.md`, "Text"; 266 texts of the public rows,
241 of them on `-08`). The form the writer writes ends at 137, and of bytes 137 to 251 only some are constant
over the corpus: floats at 173 to 223 and eight bytes at 244 to 251 vary from text to text. The writer
therefore writes no long form from constants. The import reads 226 only on a text with the byte 72 and a
first subrecord of at least 230 bytes, gives such a text `Mech.<n>`, and keeps its bytes from 137 on in its
bag (`text_tail`). A conversion to KiCad carries them by KiCad uuid in `Fenolite.Altium.TextTails`, as
`strokefonts` carries fonts. The writer writes a text on a long id that holds them as its 137 bytes, then
those bytes with the long id at 226; a text on a long id without them (an authored one, or one whose uuid
KiCad changed) keeps the 137-byte form on Mechanical 16, and every other text keeps the 137-byte form, so no
other record changes.

## Width 0 on mechanical layers (task 4.6)

Altium stores tracks and arcs of width 0 on mechanical layers: rows `-01` (68 tracks and 1 arc on
Mechanical 1) and `-03` (4 and 4), all of components (S-2286). The import and a build keep width 0, but
`pcbdoc.graphic_problem` refused every drawn shape without a positive width, so flow A of `-01` lost them.
The writer now accepts width 0 for a line or an arc on a layer that the document names as Mechanical 1
to 32 (`Mech.<n>` of a board that was read, a KiCad user layer of `lower.named_mechanical`;
`pcbrecords.mechanical_number`), free or of a component, and writes it with width 0. Copper, the layers of
the fixed KiCad map (`F.Fab` and the others: their pins keep the refusal), every other layer, drawn rectangles, circles and polygons, and negative widths keep the refusal: the corpus shows width
0 nowhere else.
