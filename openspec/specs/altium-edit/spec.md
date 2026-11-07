# altium-edit Specification

## Purpose
TBD - created by archiving change c0241-altium-edit-sessions. Update Purpose after archive.
## Requirements
### Requirement: Edit session on an Altium document
`fenolite.backends.altium.edit.open(path) -> Session` SHALL open an Altium PCB document, PCB library or schematic document for typed edits, and `Session.commit(out) -> Receipt` SHALL write the edited document under the mutation protocol. The operations MUST be `delete`, `move`, `rotate`, `flip`, `set_property`, `clone(item, **changes)`, `add_component(from_doc, ref)`, `remap_layer(old, new)`, `set_rule`, `set_outline(polygon, outline, old=)` and `create` (`add_arc`, `add_fill`, `add_region`, `add_polygon`) for PCB documents, and `set_property`, `move` and `delete` for schematic documents. The items of a PCB document MUST be `Track`, `Arc`, `Via`, `Fill`, `Text`, `Region`, `Polygon` and `Component`.

#### Scenario: A move written and read back
- **GIVEN** the authored PCB document of the kit saved by the maintainer in case J1, and a session that moves the track at (10 mm, 5 mm)–(20 mm, 5 mm) on `GND` by 1 mm in Y, stating its old ends, with the gate of `move` on
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_session.py -k move` commits it
- **THEN** the written document reads back with that track at (10 mm, 6 mm)–(20 mm, 6 mm) and every other record equal to the input

#### Scenario: A free region moved with its twin
- **GIVEN** the kit's PCB document, whose filled rectangle on Mechanical 13 is a record of `Regions6` with its twin in `ShapeBasedRegions6`, and a session that moves it by 1 mm in X
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_shapes.py -k region_move` commits it
- **THEN** it is written, both records read back 1 mm to the right, and no other record changes

### Requirement: Asserted edits
Each operation MUST name its item by kind, geometry and net (or by designator for a component, by name for a polygon), MUST find exactly one item, and MUST state the old value of each field it changes. The item is the nearest record whose stated coordinates all lie within 0.002 mm (`ops.REACH`) of the record's, the distance being the largest of those differences; a second record within 2 units (`ops.TOLERANCE`) of that distance is a second match. A `width` stated on a `Track` or an `Arc` narrows the match to records of that width within 2 units. A missing item, a second match or a different old value MUST refuse the commit with `altium.edit.assertion` (exit 5) and write nothing.

#### Scenario: A move refused on a wrong old value
- **GIVEN** the authored PCB document saved by the maintainer's kit, and a session that moves the track at (10 mm, 5 mm)–(20 mm, 5 mm) on `GND` stating an old width of 0.3 mm where the document holds 0.25 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_session.py -k assertion` commits it
- **THEN** the exit code is 5, the issues hold one `altium.edit.assertion`, and nothing is written

#### Scenario: Coincident tracks of two widths deleted one at a time
- **GIVEN** the kit's PCB document with a second track on the probe's ends, layer and net, 0.5 mm wide
- **WHEN** a session deletes `Track(ends, "GND", width=0.5 mm)` and commits
- **THEN** it is written and only the 0.5 mm track is gone; without `width` the commit is refused with `altium.edit.assertion` naming two records

#### Scenario: A point rounded to the micrometre
- **GIVEN** the kit's PCB document with a track whose ends lie 0.0004 mm from (10, 7) and (20, 7) mm, and a second track 0.0015 mm further
- **WHEN** a session deletes `Track((10 mm, 7 mm), (20 mm, 7 mm), "GND")` and commits
- **THEN** the nearer track is gone and the other kept

### Requirement: Records cloned from the document
A new record MUST be cloned from a record of the same kind and layer that the document holds, with the stated changes, and MUST never be written in a shorter form beside records of the longer form. A document that holds no record to clone from MUST refuse the operation with `altium.edit.no-template`. A new arc MUST keep the template's bytes after its width, a new fill the template's bytes after its rotation, and a new region the template's property text and tail, with its twin in `ShapeBasedRegions6` cloned from the template's twin when the template has one. A new polygon MUST be cloned from a record of `Polygons6` of any layer, with a new `NAME`, `LAYER`, `NET`, `POURINDEX` above every other, a new `UNIQUEID` where the template holds one, the outline's keys and no poured primitive.

#### Scenario: No record to clone from
- **GIVEN** the authored PCB document, which holds no track on Mechanical 1, and a session that clones the track `probe` onto Mechanical 1
- **WHEN** it commits
- **THEN** the issues hold one `altium.edit.no-template` naming the kind and the layer, and nothing is written

#### Scenario: A fill created beside a fill of the document
- **GIVEN** a PCB document that holds a fill on the Top Layer, and a session that adds a fill from (2, 2) to (4, 3) mm there on `GND`, with the gate of `create` on
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_shapes.py -k fill` commits it
- **THEN** the written document holds one more fill, of the template's length, at those corners on `GND`; on the kit's document, which holds no fill, the same session is refused with `altium.edit.no-template`

### Requirement: Index upkeep
Every index the session touches (per-primitive identifiers, pad and via caches, unique-id tables, polygon indices, wide-string tables, parameter groups, model-store entries) MUST be updated in the same commit. New identifiers MUST come from a cryptographic random source and MUST be unique in the document.

#### Scenario: A deleted component leaves no index behind
- **GIVEN** the authored PCB document saved by the kit, and a session that deletes the component `R2` with the gate of `delete` on
- **WHEN** it commits
- **THEN** the unique-id table, the wide strings and the parameter groups of the written document hold no entry of `R2`, and `fenolite check out.PcbDoc --stages altium.integrity --json` reports no finding

### Requirement: Operations gated by their hypotheses
The facts that each operation relies on MUST be hypotheses of `docs/hypotheses.md` with sources or kit cases. An operation whose hypotheses are not confirmed MUST stay behind a gate that is off by default, as c0092's graduation rule requires, and MUST be refused while its gate is off, naming the gate and the unconfirmed hypotheses. `create` rests on `H-A-EDIT-CREATE` and `set_outline`, and the moves and deletions of arcs, fills, regions and polygons, on `H-A-EDIT-SHAPE`.

#### Scenario: An operation behind its gate
- **GIVEN** the gate of `flip` off, as released
- **WHEN** a session flips the component `D1` and commits
- **THEN** the commit is refused, the refusal names the gate of `flip` and `H-A-EDIT-FLIP`, and nothing is written

#### Scenario: A creation behind its gate
- **GIVEN** the gate of `create` off, as released
- **WHEN** a session adds an arc and commits
- **THEN** the commit is refused naming the gate of `create` and `H-A-EDIT-CREATE`, and nothing is written

### Requirement: Commit gates
`Session.commit` SHALL re-read the written document strictly, compare its decoded content with the input, and refuse a change outside the operations of the session (`altium.edit.unexpected-change`, exit 5), a change of the board's connectivity or of a sheet's net signature that the session does not declare (`altium.edit.connectivity`, exit 5), and any error of "Integrity check".

#### Scenario: An undeclared connectivity change
- **GIVEN** a session that moves a track onto a pad of another net without declaring a connectivity change
- **WHEN** it commits
- **THEN** the exit code is 5, the issues hold one `altium.edit.connectivity` naming both nets, and nothing is written

### Requirement: Integrity check
`fenolite check DOC --stages altium.integrity` SHALL report, without writing, the faults of an Altium document that make the native tool refuse it or fail on save, each as a finding with its stream and record. Each rule MUST cite its hypothesis; a rule whose hypothesis is not confirmed MUST report `warning`, not `error`.

#### Scenario: A gap in polygon sub-indices
- **GIVEN** an authored PCB document, saved by the kit, and a copy in which one polygon's sub-indices run 0, 1, 3
- **WHEN** `fenolite check copy.PcbDoc --stages altium.integrity --json` runs
- **THEN** the issues hold one finding naming that polygon and its stream, and the original document gives none

### Requirement: Integrity rules of indices
The stage `altium.integrity` MUST report gaps in the sub-indices of a polygon, duplicate pour indices and duplicate identifiers, each finding naming the records that share or skip the value.

#### Scenario: Two pads with one unique id
- **GIVEN** a copy of the kit's saved PCB document in which two pads share one unique id
- **WHEN** `fenolite check copy.PcbDoc --stages altium.integrity --json` runs
- **THEN** the issues hold one finding naming both pads and `UniqueIDPrimitiveInformation`, with severity `warning` while `H-A-INTEG-ID` is not confirmed

### Requirement: Integrity rules of parameters, models and layers
The stage `altium.integrity` MUST report parameter groups whose count disagrees with their records, parameter records of a component the document no longer holds, model-store entries that no body uses and bodies without an entry, and primitives whose two layer fields disagree.

#### Scenario: Two layer fields that disagree
- **GIVEN** a copy of the kit's saved PCB document in which one region's layer byte names Mechanical 13 and its `V7_LAYER` names Mechanical 15
- **WHEN** `fenolite check copy.PcbDoc --stages altium.integrity --json` runs
- **THEN** the issues hold one finding naming that region and both layers

### Requirement: Kit cases for edit sessions
`docs/evidence/altium-edit.md` SHALL hold Part J: phase A cases J1 to J22 that the maintainer runs on documents authored for Fenolite, and phase B cases J23 to J33 on the documents the session writes and on planted faults. Each case MUST state its expected outcome, and each hypothesis `H-A-EDIT-*` and `H-A-INTEG-*` MUST be named by a case.

#### Scenario: Pages name the cases
- **GIVEN** the page and `docs/hypotheses.md`
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j` runs
- **THEN** it passes: J1 to J33 in order, each with an expected outcome, and every row of both families named

### Requirement: A flip moves every layer field of a primitive
A `flip` (and every other operation that moves a primitive to another layer) MUST change a primitive's
layer byte together with every other field that names its layer: a region's or body's `V7_LAYER`, and the
long layer id of a saved long track, arc, fill, text or pad. A flipped component's designator and comment
MUST end on the overlay of the new side with the mirror flag of that side.

#### Scenario: A saved part flipped to the bottom and back
- **GIVEN** the kit board with its texts in the saved 252-byte form and its pads in the saved 194-byte form,
  each holding the long layer id of its layer
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py -k flip_to_the_bottom` flips `D1` and
  `R1` to the bottom and then back to the top
- **THEN** after the first flip both components read `BOTTOM`, their designators and comments read Bottom
  Overlay with the long id `0x01030007` and the mirror flag set, and `R1`'s pads read Bottom Layer with the
  long id `0x0100FFFF`; after the second flip every text and pad record of both equals the board's

### Requirement: A flip swaps only the mechanical pairs the board declares
A `flip` MUST move a component's primitive on a mechanical layer only when the board record declares that
layer in a pair (`MECHPAIR<i>L1`, `MECHPAIR<i>L2`), and then MUST put it on the other layer of the pair
by layer byte and long layer id. A primitive on a mechanical layer of no declared pair MUST keep its
layer.

#### Scenario: No pair declared
- **GIVEN** the kit board, which declares no mechanical pair
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py -k no_declared_pair` flips `D1`
- **THEN** `D1`'s Mechanical 15 drawings keep their layer and its overlay drawings read Bottom Overlay

#### Scenario: Pairs declared, one above Mechanical 16
- **GIVEN** the kit board with Mechanical 13 paired with 14 and 15 with 19, its drawings in the saved long forms
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py -k declared_mechanical_pairs` flips `D1` and back
- **THEN** the Mechanical 15 drawings hold the layer byte 72 and the long id `0x01020013`, the Mechanical 13
  ones Mechanical 14, and the flip back restores every layer field

### Requirement: Arcs, fills, regions and polygons
A session SHALL move and delete a free `Arc`, a `Fill` and a free `Region`, SHALL move a `Polygon`, and SHALL give a polygon a new outline. A moved region's twin in `ShapeBasedRegions6` MUST move with it. A moved polygon MUST move every vertex and arc centre of its outline and every primitive whose prefix names it. `set_outline` MUST state the old outline (its vertices, each within 0.002 mm), MUST write the new outline as line vertices with the first vertex repeated last, in the place of the old outline's keys, and MUST remove the polygon's poured primitives in both region forms and in `Tracks6` and `Arcs6`. A polygon's index and the indices of the others MUST NOT change.

#### Scenario: A polygon moved
- **GIVEN** the kit's PCB document and a session that moves the polygon `VIN` by 1 mm in X and 2 mm in Y
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_shapes.py -k polygon_move` commits it
- **THEN** the written document reads back with each vertex of `VIN` moved by that much and `GND` unchanged

#### Scenario: A polygon given a new outline
- **GIVEN** the kit's PCB document and a session that gives `VIN` the outline (2, 2), (10, 2), (10, 9), (2, 9) mm, stating its old one
- **WHEN** it commits
- **THEN** `VIN` reads back with those four vertices, its name, net, layer and pour index kept; a wrong old outline is refused with `altium.edit.assertion`

#### Scenario: An arc created, moved and deleted
- **GIVEN** the kit's PCB document, which holds an arc of a component on the Top Overlay, and a session that adds a free arc of centre (30, 20) mm, radius 2 mm, 0° to 90°, 0.2 mm wide there
- **WHEN** it commits, and a second session on the written document moves that arc by 1 mm in X and a third deletes it
- **THEN** each is written: the arc reads back free, then at centre (31, 20) mm, then gone, with every other record equal to the input

### Requirement: A flip writes Altium's frame of a bottom part
A `flip` MUST write the component's `ROTATION` as `(180 − R) mod 360`. It MUST turn each pad of the
component to `(180 − r) mod 360`, so that the pads read in the component's frame are the footprint
mirrored in Y on the bottom, as Altium places a bottom part. A flip of a body MUST set `BODYPROJECTION` to 1
on the bottom and 0 on the top, and MUST keep the values of `MODEL.3D.ROTZ` and `MODEL.2D.ROTATION`, as
Altium's own flip does (S-2123). A body flipped to the bottom with `TEXTUREROTATION` 0 MUST take Altium's
360. A flip back MUST restore every other record of the component.

#### Scenario: The frame of a flipped part
- **GIVEN** the kit board, with `D1` and `R1` on the top at rotation 0, and `R1` turned to 90 by a session
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_frame.py -k frame` flips both to the
  bottom
- **THEN** `D1` reads `ROTATION` 180 and `R1` 90. Every pad of both, taken into the component's frame and
  mirrored in Y, is at the place and the rotation it had in the top frame. A flip back gives the records
  of the source.

#### Scenario: A body follows the side
- **GIVEN** the kit board with an authored extruded body on `D1`, `BODYPROJECTION=0`, `MODEL.3D.ROTZ` 0
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_flip_frame.py -k body` flips `D1` and back
- **THEN** the body reads `BODYPROJECTION=1`, `MODEL.3D.ROTZ` and `MODEL.2D.ROTATION` 0 and
  `TEXTUREROTATION` 360 after the first flip. After the flip back, every key of the body is that of the
  source but `TEXTUREROTATION`, which stays 360.

#### Scenario: Altium keeps the flip after a save
- **GIVEN** Fenolite's flip of `D1` in `J01-resave.PcbDoc` (Part J case J9), and the same board with a
  body on `D1`
- **WHEN** the VM agent opens each in Altium Designer, saves it, reopens it and reads it
- **THEN** `D1` is on the Bottom Layer, its pads stay where Fenolite put them, its designator stays on
  Bottom Overlay, and its body projects from the bottom

