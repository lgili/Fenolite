# Design: c0449

## Context

- Altium → KiCad (c0223, c0423): `models3d.body_models` gives each embedded model's bytes and pose;
  `convert.models.place_models` writes `<lib>.3dshapes/<footprint>_<sha12>.step` and a `ModelPlacement`
  (footprint frame, Y down, turns counter-clockwise) that KiCad shows at the source's pose
  (`H-K-MODEL-POSE`). The board footprint holds the same `model` child (c0409).
- KiCad → Altium: `read_board` keeps a footprint's `model` children as opaque slots; nothing projects them.
  `pcbdoc` writes `Models` and `ModelsNoEmbed` with `Header` 0 and an empty `Data`; `body_problem` refuses a
  body of kind `model`.

Measured on the seven public rows of the local checkout (S-2080, 453 bodies that name a model, 201
records); row 05 is read again for the proof (task 4.1):

| fact | count |
|---|---|
| `Models/Header` is the record count as a 32-bit integer; `ModelsNoEmbed` holds a 4-byte `Header` and an empty `Data` | 7 of 7 |
| A record is a 32-bit length and `EMBED=TRUE\|MODELSOURCE=Undefined\|ID=\|ROTX=\|ROTY=\|ROTZ=\|DZ=\|CHECKSUM=\|NAME=` with a NUL, no leading bar | 201 of 201 |
| Each stream inflates with zlib; the two header bytes are `78 9C` (level 6) | 201 of 201 |
| A record serves 1 to 75 bodies; its `ROTX`, `ROTY`, `NAME` and `DZ` (integer file units) equal its body's | 453 of 453 |
| Its `ROTZ` equals the body's | 243 of 453 |
| Its `CHECKSUM` equals the body's `MODEL.CHECKSUM` | 312 of 453 |
| A model body holds 34 keys: the extruded form's first 32, then `MODEL.MODELTYPE=1`, `MODEL.MODELSOURCE=Undefined`; 243 add `MODEL.SNAPCOUNT` before `MODEL.MODELTYPE` | 201 + 243 of 453 |
| `MODEL.EMBED=TRUE`, `MODEL.2D.ROTATION=0.000`, `ARCRESOLUTION=0.5mil` | 453 of 453 |
| `BODYCOLOR3D=8421504` | 374 of 453 |
| The outline has 4 vertices; they are the corners of a box aligned with the board's axes | 453; 443 of 453 |
| CRC-32 or Adler-32 of the inflated or the deflated bytes, or a byte sum, equals `CHECKSUM` | 0 of 201 |

## Decisions

### 1. Which model children are embedded

A `model` child of a board footprint is embedded when its path, with `${KIPRJMOD}` (or `$(KIPRJMOD)`) read as
the source project's folder, or relative to that folder, names a file there whose bytes start with
`ISO-10303-21;`, its scale is 1 on every axis, and its STEP holds geometry the box reader can bound. Each
other child is a `model` loss with one of the reasons of `convert.models` (`MISSING`, `VARIABLE`,
`KICAD_EMBEDDED`, `NOT_STEP`, `SCALED`, `NO_GEOMETRY`). A hidden model is written: Altium has no hidden
body (a `model` change). A KiCad embedded file (`kicad-embed://`) is compressed by KiCad with zstd, which
the core does not decompress without a dependency: it is a loss, and the c0423 direction keeps writing
`.3dshapes` files.

Absolute paths outside the project are not read: a conversion reads what the project holds, so the result
does not depend on the machine.

### 2. Pose: the inverse of c0423

c0423 places a model at `R_K = Rz(θ')·R_A` with `θ' = θ` on the bottom and `−θ` on the top, and offset
`(x, ±y, z)` of the model's position in the footprint frame. The inverse:

- `MODEL.2D.X/Y` = the footprint's placement applied to `(x, y)` on the top and `(x, −y)` on the bottom;
- `MODEL.3D.DZ` = `z`;
- `MODEL.3D.ROTX/Y/Z` = the turns of `Rz(−θ')·R_K` (`convert.models.turns`); with no turn about X or Y,
  exactly `γ + θ` on the top and `γ − θ` on the bottom. Each is written in [0, 360) with three decimals.

A round trip therefore gives KiCad the same placement again, within the record's unit (2.54 nm).

### 3. Outline and heights: the box of the placed model

Saved documents hold the box of the placed model as the outline and the heights (`H-A-BODY-MODEL-PLACE`:
465 of 472 within 0.5 mm). The writer does the same: `stepbox.model_box(data)` gives the model's box in its
own frame; its eight corners turned by `R_K` and moved by the offset give, in the footprint frame, the four
outline corners (the box's xy rectangle) and the heights `STANDOFFHEIGHT` (z min, may be negative) and
`OVERALLHEIGHT` (z max). The corners are placed as the footprint's pads are, so a part turned by an angle
that is no multiple of 90° keeps a turned rectangle.

The box reader is Fenolite's own, written from the STEP text's structure (ISO 10303-21 entity instances),
not from any parser's code. It bounds the model's edges, which bound every face of a closed solid except a
surface that bulges between them (a sphere or a torus): the vertex points, the extremes, within the edge's
span, of a circular or elliptic edge, and the control points of a B-spline edge (a B-spline lies in the hull of its
control points). Points are taken in the frame of their shape representation and moved into the root frame
through each `REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION`'s `ITEM_DEFINED_TRANSFORMATION`, with the
length unit of each representation's context (`SI_UNIT` with a prefix, or a `CONVERSION_BASED_UNIT` with a
`LENGTH_MEASURE_WITH_UNIT`). The rules of the relationship put `transform_item_1` in `rep_1`'s context
(S-2082), so `rep_1` is placed in `rep_2`; exporters write the pair in either order, so the component is the
representation whose product is the `related_product_definition` of the usage that the relationship's
`CONTEXT_DEPENDENT_SHAPE_REPRESENTATION` names. On the corpus (S-2081) the placed box matches the stored
outline and heights within 0.01 mm for 455 of 472 bodies, within 0.5 mm for 5 more.

### 4. Records

- `Models/Data`: one record per distinct model (by SHA-256), in the order of first use; `ID` a GUID in
  braces from the SHA-256 of `fenolite.altium.model:` and the model's SHA-256, so a build is repeatable;
  `EMBED=TRUE`, `MODELSOURCE=Undefined`, `ROTX`, `ROTY`, `ROTZ` and `DZ` of the first body that names it
  (`DZ` in integer file units), `CHECKSUM=0` (the stand-in of c0121), `NAME` the file's name.
  `Models/Header` is the count; `Models/<n>` is `zlib.compress(data, 6)`.
- A model body: the 34-key form, `MODELID` the record's `ID`, `MODEL.CHECKSUM=0`, `MODEL.EMBED=TRUE`,
  `MODEL.NAME` the file's name, `BODYCOLOR3D=8421504`, `MODEL.MODELTYPE=1`, `MODEL.MODELSOURCE=Undefined`;
  the layer and `BODYPROJECTION` by the footprint's side as an extruded body's; the outline and heights of
  decision 3. Both body storages hold it, after the footprint's extruded bodies.
- A document without a model body keeps `Models` empty: every document written before is unchanged.

### 5. Name

`MODEL.NAME` is the KiCad file's name. After a round trip it is the c0423 name
(`<footprint>_<sha12>.step`), not the source's: the name is no geometry, and keeping the source's would need
a carrier in KiCad.

## Risks

- The box reader overestimates a model with B-spline edges (the hull) and underestimates a sphere that no
  edge bounds; the corpus run states how often the box differs from the saved one by more than 0.5 mm.
- Altium's acceptance of `CHECKSUM=0` and of Fenolite's GUIDs is not proved: open a round trip in Altium
  (altium-rounds-2) before claiming more than `INFERRED`.
