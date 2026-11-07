## MODIFIED Requirements

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

## ADDED Requirements

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
