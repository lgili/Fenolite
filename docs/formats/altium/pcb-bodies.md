# Component bodies of Altium PCB files

This page states, in Fenolite's own words, what `fenolite.backends.altium.read.bodies` (change c0043) reads
from the component-body records of a PCB document (the `Data` streams of the storages `ComponentBodies6` and
`ShapeBasedComponentBodies6`) and of a library footprint (primitives of type 12). The PCB reader of c0041
keeps these bytes untyped (`pcb-read.md`); this module decodes them and parses no other record.

- Sources: KiCad's binary parser and importer, read for facts only and never transcribed (S-0160, S-0161);
  Altium's documentation of the 3D body object (S-0303); and the public files of the PCB reader's corpus
  (S-0170 to S-0176, S-0188, S-0199, S-0200), fetched into the corpus cache and never committed. Rows
  measured on those files say "files kept outside the repository"; only counts and value forms are recorded.
- A key is typed only when its row has a source. Every key of a record stays in `BodyRecord.properties`.
- `encode(read_bodies(data)) == data`: every record keeps its bytes (`tests/corpus/test_altium_import.py
  -k bodies_identity`).

## Record

| fact | source | label | hypothesis |
|---|---|---|---|
| A component body is a primitive of type 12 with one subrecord, framed as every primitive is: the type byte, a 32-bit length and that many bytes | S-0002, S-0160 | CORPUS-VERIFIED (11 rows; 2026-10-05, c0041) | H-A-RD-PCB-FRAME |
| The subrecord starts with the common prefix of 13 bytes (layer at 0, component index at 7, `0xFFFF` for none), as a region does | S-0160, files kept outside the repository (446 bodies of seven documents: every component index names a component) | INFERRED | H-A-IMP-BODY |
| After the prefix come five bytes, zero in every body read; a 16-bit count at offset 14 is read as a region's hole count | S-0160, files kept outside the repository | INFERRED | H-A-IMP-BODY |
| At offset 18 a 32-bit length and a property text of that length, ending in a NUL | S-0160 | INFERRED | H-A-IMP-BODY |
| After the property text come a 32-bit vertex count and the outline: in `ComponentBodies6` and in a library, that many vertices of two doubles (16 bytes); in `ShapeBasedComponentBodies6`, one more vertex than the count, each of 37 bytes as a shape-based region's. With this framing every body of the files read ends exactly at its subrecord's end | S-0160, files kept outside the repository (446 and 446 bodies of seven documents, one of a library) | INFERRED | H-A-IMP-BODY |
| Both storages of a document hold the same number of bodies | files kept outside the repository (seven documents: 23 to 247 bodies each), S-0160 | INFERRED | H-A-IMP-BODY |

## Typed keys

| fact | source | label | hypothesis |
|---|---|---|---|
| `STANDOFFHEIGHT` is the standoff height, the distance from the board surface to the underside of the body, as mil text | S-0160, S-0303 | INFERRED | H-A-IMP-BODY |
| `OVERALLHEIGHT` is the overall height, the distance from the board surface to the top of the body, as mil text; it is at least the standoff height in every body read | S-0160, S-0303, files kept outside the repository (446 bodies) | INFERRED | H-A-IMP-BODY |
| `BODYPROJECTION` is an integer that names the board side the body projects from; 0 and 1 occur | S-0160, S-0303 | INFERRED | H-A-IMP-BODY |
| `IDENTIFIER` is the body's identifier as decimal character codes joined by commas, as a polygon's name; it may be empty | S-0160, S-0303, files kept outside the repository (373 of 446 hold codes, 73 are empty) | INFERRED | H-A-IMP-BODY |
| `MODEL.NAME` is the file name of the body's 3D model; it is empty for an extruded body | S-0160, S-0161, S-0303 | INFERRED | H-A-IMP-BODY |
| `MODELID` is the id of the model, a GUID in braces that names an entry of the `Models` storage | S-0160, S-0161 | INFERRED | H-A-IMP-BODY |
| `MODEL.EMBED` is `TRUE` when the model's data is embedded in the file | S-0160, S-0303 | INFERRED | H-A-IMP-BODY |
| In the files read, a body with `MODEL.MODELTYPE=1` names a model and is embedded (391), and a body with `MODEL.MODELTYPE=0` names none and holds the keys `MODEL.EXTRUDED.MINZ` and `MODEL.EXTRUDED.MAXZ` (55). The reader leaves the key in properties; the adapter reads it to screen supported model types and takes the kind from the model name | files kept outside the repository, S-0303 | INFERRED | H-A-IMP-BODY |

Keys that are not typed stay in `properties`: `V7_LAYER`, `NAME`, `KIND`, `SUBPOLYINDEX`, `UNIONINDEX`,
`ARCRESOLUTION`, `ISSHAPEBASED`, `CAVITYHEIGHT`, `BODYCOLOR3D`, `BODYOPACITY3D`, `BODYOVERRIDECOLOR`, the
`MODEL.2D.*`, `MODEL.3D.*`, `MODEL.CHECKSUM`, `MODEL.SNAPCOUNT`, `MODEL.MODELSOURCE` and `TEXTURE*` keys.
`V7_LAYER` may name a mechanical layer above 16, which the layer byte cannot hold; the adapter uses the byte.

## Mapping to the model

| fact | source | label | hypothesis |
|---|---|---|---|
| A body with a component index becomes a `ComponentBody` of that component's footprint: `kind` `model` when `MODEL.NAME` is not empty and `extruded` otherwise; `height` the overall height; `standoff` the standoff height; `outline` the vertices in the footprint frame; `layer` the neutral name of the layer byte; `name` the identifier | S-0303, S-0161 | INFERRED | H-A-IMP-BODY |
| Cylinder and sphere bodies are not told apart: they import as `extruded` with their heights. Model data of the `Models` storage is not imported | S-0303 | INFERRED | H-A-IMP-BODY |

## Written form of an extruded body

This section is what `pcbrecords.body_record` and `pcbdoc.write_pcbdoc` write for a component body (change
c0121). It was written before the writer: the writer sets one binary field per row marked `Field` and one
key per row marked `(key n)`, in that order, and nothing else; `tests/unit/backends/altium/test_pcb_bodies.py
-k facts` compares `pcbrecords.BODY_KEYS` with the key rows in both directions.

**How far the evidence goes.** The rows were measured with Fenolite's own readers on the eight public PCB
documents and the four public PCB libraries of the corpus manifest (1748 body records in each of the two
storages), and `tests/corpus/test_altium_bodies.py` holds them: what a row says of every record is asserted
on every record, and a count is pinned. Of the 1748 records, 1272 are extruded bodies (`MODEL.MODELTYPE=0`)
and 476 name a 3D model (`MODEL.MODELTYPE=1`). The 1272 extruded records come from five documents of three
repositories, and **1265 of the 1272 come from one repository** (2 and 5 from the two others). The label
`CORPUS-VERIFIED` is earned by its rule (three repositories) and is thin. The rows say what Altium saved in
those files. They do not say what Altium accepts: **nothing that Fenolite writes from this section was
opened in Altium**, and no row says anything about Altium taking the two stand-in values below. That is
`H-A-PCBX-BODY-OPEN`, an author report that is pending, and it is why bodies are written only on request
(`--altium-bodies extruded`; the default is `off`).

- Sources: the public files of the corpus that hold extruded bodies (S-0172, S-0187, S-0188, S-0199, S-0200),
  fetched into the corpus cache and never committed; the framing rows of "Record" above (S-0160) as they
  stand; Altium's documentation of the 3D body object and of extruded bodies (S-0303, S-0570) for what the
  heights, the side and the layer mean; and the format page of a third-party writer (S-0571; GPL, read for
  facts, no code read) for the report of a short form.
- A value rule is one of three: a **constant** (the one value of every record read), a **value of the
  model** (with the link that every record read holds), or a **choice** of Fenolite among values that
  saved records hold. A row whose value no source supports is marked **stand-in**.

### Binary fields

| fact | source | label | hypothesis |
|---|---|---|---|
| Field: the record is the type byte 12 and one subrecord (a 32-bit length and that many bytes); the subrecord ends exactly after the outline, with no hole list and no byte after it (1748 of 1748 records in each storage) | S-0160, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| Field: offset 0 is the layer byte: 69 (764 records), 72 (488), 70 (15), 57 (5), which is `56 + n` for Mechanical `n` up to 16; every body whose `V7_LAYER` names a layer above 16 lies on the byte 72 (488). Written: the byte of a mechanical layer 1 to 16 (57 to 72), by the layer rule under "What is written of a model body" | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| Field: offsets 1 and 2 are the bytes 12 and 0; offsets 3 to 6 are `FF` (no net, no polygon); offsets 9 to 12 are `FF`; offsets 13 to 17 are zero (1748 of 1748). Written: these constants | S-0160, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| Field: offset 7 is the component index as 16 bits: every extruded body of a document names a component of `Components6` (1272 of 1272); `0xFFFF` occurs in 4 bodies that name a model, of one document, and in the one body of a library. Written: the index of the body's component, and `0xFFFF` in a library | S-0160, S-0172, S-0187, S-0188, S-0199, S-0200, S-0171 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| Field: offset 18 is the 32-bit length of the property text with its NUL, then the text: the keys below joined as `KEY=VALUE` by vertical bars, without a leading bar, in 7-bit ASCII | S-0160, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| Field: after the text, a 32-bit vertex count and the outline. In `ComponentBodies6` and in a library each vertex is two doubles; every coordinate of every vertex is a whole number of units (1748 of 1748), absolute in the document, and the first vertex is not repeated at the end (1271 of the 1272 extruded; the one exception is the body with arcs). Both windings occur (633 counter-clockwise, 639 clockwise). Written: the model's outline, placed, each point rounded to a whole unit, equal neighbours and a repeated last point dropped, in the order of the model | S-0160, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| Field: the twin in `ShapeBasedComponentBodies6` at the same stream index holds the same 18 bytes, the same property text byte for byte and the same component (1748 of 1748); its vertices are 37 bytes each (a round flag, two 32-bit coordinates, a centre, a radius and two angles), none round, with the same integer coordinates as the plain ones and one more vertex that repeats the first (1271 of the 1272 extruded; the body with `ISSHAPEBASED=TRUE` holds round vertices there). Each storage's `Header` is the 32-bit record count (8 of 8 documents). Written: both records, with zero for the centre, the radius and the angles | S-0160, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| Field: no other storage holds an entry for an extruded body: no `MODELID` of an extruded body is an entry of `Models` (0 of 1272; every body that names a model has one, 476 of 476), `ModelsNoEmbed` and `Textures` are empty in the eight documents, and `UniqueIDPrimitiveInformation` lists pads only (3784 records). Written: nothing in those storages for a body | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |

### Keys, in the order they are written

The order below is the order of 1267 of the 1272 records; the five others hold the same keys in the same
order and one optional key more (see "What is not written").

| fact | source | label | hypothesis |
|---|---|---|---|
| `V7_LAYER` (key 1): `MECHANICAL<n>`; it agrees with the layer byte for `n` up to 16 (784 records) and names a higher layer on the byte 72 (488: `MECHANICAL23`). Written: the text of the written byte, so `n` is 1 to 16 | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `NAME` (key 2): one space in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `KIND` (key 3): `0` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `SUBPOLYINDEX` (key 4): `-1` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `UNIONINDEX` (key 5): `0` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `ARCRESOLUTION` (key 6): `0.5mil` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `ISSHAPEBASED` (key 7): `FALSE` in 1271 records and `TRUE` in the one body with arcs. Written: `FALSE` (an outline of the model holds no arc) | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `CAVITYHEIGHT` (key 8): `0mil` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `STANDOFFHEIGHT` (key 9): mil text with at most four decimals and no trailing zero: `0mil` in 1268 records, a positive value in 4, never negative in an extruded body. It is the distance from the board surface to the underside of the body. Written: `ComponentBody.standoff`, a value of the model | S-0303, S-0570, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `OVERALLHEIGHT` (key 10): mil text of the same form; 20 values, each above the standoff (1272 of 1272). It is the distance from the board surface to the top of the body. Written: `ComponentBody.height`, a value of the model | S-0303, S-0570, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `BODYPROJECTION` (key 11): `0` on a component whose layer is `TOP` (767 of 767) and `1` on a component whose layer is `BOTTOM` (505 of 505); the bodies that name a model and have a component hold the same (291 and 181). Written: 0 or 1 by the side of the body's footprint, a value of the model; 0 in a library | S-0303, S-0570, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `ARCRESOLUTION` (key 12): the key a second time, `0.5mil` again in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `BODYCOLOR3D` (key 13): a decimal integer; seven values occur, `12632256` in 836 records. Written: `12632256`, a choice of Fenolite among the values that saved records hold; the model holds no colour | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `BODYOPACITY3D` (key 14): `1.000` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `IDENTIFIER` (key 15): empty (1270 records) or decimal character codes joined by commas (2 records; 373 of the 391 model bodies of the seven smaller documents). Written: the codes of `ComponentBody.name`, a value of the model, empty without a name | S-0160, S-0303, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `TEXTURE` (key 16): empty in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `TEXTURECENTERX` (key 17): `0mil` in 1225 records; else within 0.0004 mil of 0. Written: `0mil` | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `TEXTURECENTERY` (key 18): `0mil` in 1227 records; else within 0.0004 mil of 0. Written: `0mil` | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `TEXTURESIZEX` (key 19): `0mil` in 1265 records; else `0.0001mil`. Written: `0mil` | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `TEXTURESIZEY` (key 20): `0mil` in 1265 records; else `0.0001mil`. Written: `0mil` | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `TEXTUREROTATION` (key 21): a real in the form ` 0.00000000000000E+0000` (a leading space, one digit, 14 decimals, a four-digit exponent); the values 0, 45, 90, 180, 270 and 360 occur; it equals the rotation of the body's component in 796 of the 1272 records, so no rule is known. Written: the form with the value 0, which 115 records hold: a choice of Fenolite among the values that saved records hold | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODELID` (key 22): **stand-in**. Saved: a GUID in braces, upper-case; 77 values for the 1272 bodies; none is an entry of `Models`. No source says how the value is made or whether Altium needs a particular one. Written: a GUID in braces derived from the body's id by a hash (`pcbrecords.body_model_id`), so that a build is repeatable. Whether Altium takes it is not known | S-0172, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-PCBX-BODY-OPEN |
| `MODEL.CHECKSUM` (key 23): **stand-in**. Saved: an unsigned 32-bit decimal, one value per `MODELID` (77), never 0; it is not a function of the outline and the heights: of the 53 distinct shapes (the box of the outline and the two heights) 24 hold more than one checksum, and 17 checksums are held by more than one shape. No source gives a rule. Written: `0`, a value that no saved record holds. Whether Altium takes it is not known; S-0571 reports that a checksum of 0 is tolerated in a record of the `Models` storage, which is another record | S-0172, S-0187, S-0188, S-0199, S-0200, S-0571 | INFERRED | H-A-PCBX-BODY-OPEN |
| `MODEL.EMBED` (key 24): `FALSE` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.NAME` (key 25): empty in every record (a body that names a model holds a file name here). Written: empty | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.2D.X` (key 26): mil text; with `MODEL.2D.ROTATION=0.000` exactly the X of the centre of the bounding box of the outline, a half unit rounded towards zero (1266 of 1266). Written: that centre of the written vertices | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-2D |
| `MODEL.2D.Y` (key 27): the Y of the same centre, by the same rule (1266 of 1266; 675 bodies hold a half unit in one coordinate or both, 698 values, each rounded towards zero). Written: that centre | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-2D |
| `MODEL.2D.ROTATION` (key 28): `0.000` in 1266 records and `360.000` in 6, whose `MODEL.2D.X/Y` are not the centre of the box. Written: `0.000` | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.3D.ROTX` (key 29): `0.000` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.3D.ROTY` (key 30): `0.000` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.3D.ROTZ` (key 31): `0.000` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.3D.DZ` (key 32): `0mil` in every record. Written: the constant | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.MODELTYPE` (key 33): `0` in every extruded record (`1` in a body that names a model). Written: `0` | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.EXTRUDED.MINZ` (key 34): equal to `STANDOFFHEIGHT`, text for text (1272 of 1272). Written: the standoff again | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| `MODEL.EXTRUDED.MAXZ` (key 35): equal to `OVERALLHEIGHT`, text for text (1272 of 1272). Written: the height again | S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |

### What is written of a model body

| fact | source | label | hypothesis |
|---|---|---|---|
| Layer rule. A body whose `ComponentBody.layer` names a mechanical layer 1 to 16 (`F.Fab`, `B.Fab`, `F.CrtYd` and `B.CrtYd` of the writer's layer map, ids 69 to 72, or the import's name `Mech.<n>`, id `56 + n`) is written on that layer. Any other layer, and no layer, gives Mechanical 13 (69) for a body of a top footprint and Mechanical 14 (70) for a body of a bottom one: a choice of Fenolite, the pair that 777 of the 1272 saved bodies follow (762 top bodies on 69 and 15 bottom bodies on 70; 2 bottom bodies lie on 69, 5 top bodies on 57 and 488 bottom bodies on 72). A layer above 16 is never written by name: the byte cannot hold it | S-0570, S-0172, S-0187, S-0188, S-0199, S-0200 | CORPUS-VERIFIED (1272 records of five documents, 1265 of one repository; 2026-10-07, c0121) | H-A-PCBX-BODY-FORM |
| Short form. A third-party writer reports that the extruded bodies it writes hold no model key and end at `TEXTUREROTATION` (the first 21 keys of the table). No saved record of the corpus has that form (0 of 1748), and the page does not say that such a body was opened in Altium Designer. `body_record(..., form="short")` builds it for step X8 of the author report only; no command writes it | S-0571 | INFERRED | H-A-PCBX-BODY-SHORT |
| Library. The form of a body in a library footprint is the document's with the component index `0xFFFF`, plain vertices in the library's frame and `BODYPROJECTION=0`, as one primitive of type 12 in the footprint's stream. **No extruded body of a saved library was read**: the four public libraries hold one body, in one footprint beside 2 pads and 21 tracks, and it names a model (34 keys, the first 21 in the document's order, `0xFFFF`, whole units, `BODYPROJECTION=0`); it is the last primitive of the stream, the stream's `Header` counts it, and the footprint's `UniqueIDPrimitiveInformation` lists the two pads and not the body. Written: the body after the footprint's other primitives, counted in the header, without a unique-id entry. The written form is the document's by analogy | S-0170, S-0171, S-0172, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-PCBX-BODY-LIB |

### What is not written

- **A body that names a 3D model** (`MODEL.MODELTYPE=1`; 476 of the 1748 records, 391 of the 446 of the
  seven smaller documents). Its `MODELID` names a record and a numbered stream of the `Models` storage
  with the model's data (476 of 476), and the design model holds a model's name and no data. Such a body is
  reported with `altium.not-lowered` and never written.
- **The optional keys** `MODEL.SNAPCOUNT` (2 records, `0`) and `BODYOVERRIDECOLOR` (3 records, `TRUE`).
- **An arc in an outline** (`ISSHAPEBASED=TRUE`, one record), a hole in a body, a texture, a cylinder and a
  sphere: no record of the last two was told apart, and the model holds none of them.
- **A negative standoff.** No extruded record holds one (93 of the bodies that name a model do); a body
  whose height is not above its standoff has no record.
- **A body that the model does not hold.** No outline is derived from a courtyard or from any graphic, and
  no height is assumed.

KiCad's importer (`kicad-cli` 10.0.6, run as a subprocess) shows nothing for an extruded body; the oracle
test of change c0121 holds that for the written sample and that every other kind is undisturbed
(`H-A-PCBX-BODY-KICAD`). The proposal also counted, on the seven smaller public documents, that the
footprints with a model in KiCad's board are exactly the components with a body that names a model; that
count was not repeated for this page and no row rests on it.
## Signed and unknown projections (c0099)

| fact | source | label | hypothesis |
|---|---|---|---|
| Standoff can be negative; its sign and the overall height describe surface-relative extrusion bounds | S-0708 | INFERRED | H-A-IMP-BODY-Z |
| BodyProjection has type TBoardSide, whose enumeration orders Top before Bottom; interpreting serialized 0/1 by this ordering is inferred | S-0709, S-0160 | INFERRED | H-A-IMP-BODY-Z |
| A component flip changes the projection and paired mechanical layer; a body's projection can differ from its component face | S-0708 | INFERRED | H-A-IMP-BODY-Z |

The adapter keeps every component body it receives. Unproved sides, model types, reversed bounds
and malformed lengths set projection_unknown and produce located findings. Source reader bytes
and resources remain immutable; no raw-record hex JSON is duplicated into extensions.

| fact | source | label | hypothesis |
|---|---|---|---|
| Matching mounted and projection sides give z_min equal to source standoff and z_max equal to source overall height, in integer nm | S-0708, S-0709; authored import tests | INFERRED | H-A-IMP-BODY-Z |
| A nonnumeric overall or standoff length is retained as 0 with projection_unknown and bad-length/body-unknown warnings | S-0708; authored import tests | INFERRED | H-A-IMP-BODY-Z |
| Overall height below standoff is retained without a claimed interval | S-0708; authored import tests | INFERRED | H-A-IMP-BODY-Z |
| Projection outside inferred 0/1, or different from the component side, gives unknown geometry | S-0709, S-0708; authored import tests | INFERRED | H-A-IMP-BODY-Z |
| MODEL.MODELTYPE outside 0/1 gives unknown geometry; an absent key preserves the legacy extruded-record convention | S-0303; authored import tests | INFERRED | H-A-IMP-BODY-Z |

A body without a component stays unmapped. Bounded MODELID and MODEL.CHECKSUM metadata are
compatible with this contract; unbounded raw-record copies in ext are prohibited.
