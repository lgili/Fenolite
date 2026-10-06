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

## Signed and unknown projections (c0099)

| fact | source | label | hypothesis |
|---|---|---|---|
| Standoff can be negative; its sign and the overall height describe surface-relative extrusion bounds | S-0570 | INFERRED | H-A-IMP-BODY-Z |
| BodyProjection has type TBoardSide, whose enumeration orders Top before Bottom; interpreting serialized 0/1 by this ordering is inferred | S-0605, S-0160 | INFERRED | H-A-IMP-BODY-Z |
| A component flip changes the projection and paired mechanical layer; a body's projection can differ from its component face | S-0570 | INFERRED | H-A-IMP-BODY-Z |

The adapter keeps every component body it receives. Unproved sides, model types, reversed bounds
and malformed lengths set projection_unknown and produce located findings. Source reader bytes
and resources remain immutable; no raw-record hex JSON is duplicated into extensions.

| fact | source | label | hypothesis |
|---|---|---|---|
| Matching mounted and projection sides give z_min equal to source standoff and z_max equal to source overall height, in integer nm | S-0570, S-0605; authored import tests | INFERRED | H-A-IMP-BODY-Z |
| A nonnumeric overall or standoff length is retained as 0 with projection_unknown and bad-length/body-unknown warnings | S-0570; authored import tests | INFERRED | H-A-IMP-BODY-Z |
| Overall height below standoff is retained without a claimed interval | S-0570; authored import tests | INFERRED | H-A-IMP-BODY-Z |
| Projection outside inferred 0/1, or different from the component side, gives unknown geometry | S-0605, S-0570; authored import tests | INFERRED | H-A-IMP-BODY-Z |
| MODEL.MODELTYPE outside 0/1 gives unknown geometry; an absent key preserves the legacy extruded-record convention | S-0303; authored import tests | INFERRED | H-A-IMP-BODY-Z |

A body without a component stays unmapped. Bounded MODELID and MODEL.CHECKSUM metadata are
compatible with this contract; unbounded raw-record copies in ext are prohibited.
