## MODIFIED Requirements

### Requirement: Edit session on an Altium document
`fenolite.backends.altium.edit.open(path, *, gates=None, project=None) -> Session` SHALL open an Altium PCB document, PCB library or schematic document for typed edits, and `Session.commit(out) -> Receipt` SHALL write the edited document under the mutation protocol. The operations MUST be `delete`, `move`, `rotate`, `flip`, `set_property`, `clone(item, **changes)`, `add_component(from_doc, ref)`, `link(component, project=, part=)`, `remap_layer(old, new)`, `set_rule`, `set_outline(polygon, outline, old=)` and `create` (`add_arc`, `add_fill`, `add_region`, `add_polygon`) for PCB documents, and `set_property`, `move`, `delete`, `add_part`, `annotate` and `create` (`add_wire`, `add_net_label`, `add_power_port`) for schematic documents (change c0499). The items of a PCB document MUST be `Track`, `Arc`, `Via`, `Fill`, `Text`, `Region`, `Polygon` and `Component`. `project` names the `.PrjPcb` whose sheets a schematic session checks designators against.

#### Scenario: A move written and read back
- **GIVEN** the authored PCB document of the kit saved by the maintainer in case J1, and a session that moves the track at (10 mm, 5 mm)–(20 mm, 5 mm) on `GND` by 1 mm in Y, stating its old ends, with the gate of `move` on
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_session.py -k move` commits it
- **THEN** the written document reads back with that track at (10 mm, 6 mm)–(20 mm, 6 mm) and every other record equal to the input

#### Scenario: A free region moved with its twin
- **GIVEN** the kit's PCB document, whose filled rectangle on Mechanical 13 is a record of `Regions6` with its twin in `ShapeBasedRegions6`, and a session that moves it by 1 mm in X
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_shapes.py -k region_move` commits it
- **THEN** it is written, both records read back 1 mm to the right, and no other record changes

## ADDED Requirements

### Requirement: A part copied into a schematic sheet
`SchematicSession.add_part(from_doc, designator, *, new_designator=None, at=None)` SHALL append the part `designator` of the binary sheet `from_doc` to the sheet: its component record and every record it owns, at any depth, binary pins included, in their order. Each `OWNERINDEX` MUST name the new index of its owner, the header's `WEIGHT` MUST be the new record count, every record that holds `UNIQUEID` MUST get a new one unique in the sheet, and the designator MUST be `new_designator`, or the source's with its number replaced by `?`. `at` MUST move the part by whole 10-mil units, as `move` does. A sheet that already holds `new_designator` MUST refuse with `altium.edit.assertion`.

#### Scenario: A part copied and placed
- **GIVEN** the kit's sheet and a session that copies `R1` as `R9` 500 mil to its right, with the gates of `add_part` and `create` open
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_schematic_add.py -k add_part` commits it with `declare_connectivity()`
- **THEN** the written sheet reads back with `R9`, its parameters and pins 500 mil right of `R1`'s, every `OWNERINDEX` of its records naming `R9`'s component record, and no `UNIQUEID` held twice

#### Scenario: A designator held twice
- **WHEN** the test copies `R1` as `R2`, which the sheet holds
- **THEN** the commit is refused with `altium.edit.assertion` naming `R2`, and nothing is written

### Requirement: Annotation of a schematic part
`SchematicSession.annotate(part, designator, *, old)` SHALL set the text of the part's designator record, stating its old text. It MUST refuse with `altium.edit.assertion` when another part of the sheet, or of any sheet of the project given to `open(project=)`, holds `designator`, or when the part lies on a repeated sheet. The net-signature guard MUST accept the rename of the annotated part without `declare_connectivity()`.

#### Scenario: A copied part annotated
- **GIVEN** a session that copies `R1` without a new designator, which gives `R?`, and annotates it `R9`, stating `R?`
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_schematic_add.py -k annotate` commits it
- **THEN** the written sheet holds `R9` and no `R?`

#### Scenario: A designator held on another sheet of the project
- **GIVEN** a two-sheet authored project whose second sheet holds `R5`, and a session opened on the first sheet with `project=`
- **WHEN** it annotates a part `R5`
- **THEN** the commit is refused with `altium.edit.assertion` naming the second sheet

### Requirement: Wires, net labels and power ports added to a sheet
`SchematicSession` SHALL add a wire (`add_wire(points)`, two or more points), a net label (`add_net_label(text, at, *, orientation=0)`) and a power port (`add_power_port(text, at, *, orientation=0, style=None)`), each point in nanometres and a whole number of 10-mil units. A new record MUST be cloned from a record of the same kind in the sheet (a power port first from one of the same text), else written in the form of `backends.altium.schdoc`, changing only its location keys, text, orientation, style and a new `UNIQUEID`. A wire end that lies inside another wire's segment MUST get a junction record. These operations rest on the gate `create` and the row `H-A-EDIT-SCH-ADD`; a session that changes the net signature with them MUST declare it.

#### Scenario: A part wired to a power net
- **GIVEN** the kit's sheet, a copied part `R9`, a wire from its pin 1 to a point 200 mil left, and a power port `GND` at that point
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_schematic_add.py -k power_port` commits it with `declare_connectivity()`
- **THEN** Fenolite's read of the written sheet puts `R9` pin 1 on the net `GND`, and the new power port has the style of the sheet's other `GND` port

#### Scenario: A net label on a wire's middle
- **GIVEN** a new wire whose end lies on the middle of an existing wire, and a net label `SENSE` on the new wire
- **WHEN** the test commits it with `declare_connectivity()`
- **THEN** the sheet holds one more junction at that end, and both wires and the label form one net named `SENSE`

#### Scenario: An undeclared wire
- **WHEN** the test adds the same wire without `declare_connectivity()`
- **THEN** the commit is refused with `altium.edit.connectivity`, and nothing is written

### Requirement: A PCB component linked to its schematic part
`Session.link(component, *, project, part, sheet=None)` SHALL set the component's `SOURCEUNIQUEID` to the unique-id path of the one part `part` of the project (on `sheet` when given), and its `SOURCEHIERARCHICALPATH`, `SOURCEDESIGNATOR`, `SOURCELIBREFERENCE`, `SOURCECOMPONENTLIBRARY` and `CHANNELOFFSET` from that part. When `Classes6` holds the component class of the part's sheet, the designator MUST be added to its members. The link MUST be refused with `altium.edit.assertion` when no part or two parts match, or when the part's footprint model or comment differs from the component's, naming both values. The operation rests on the gate `link` and the row `H-A-EDIT-LINK`.

#### Scenario: A copied component linked
- **GIVEN** the kit project, a sheet session that copies `R1` as `R9`, and a PCB session that adds the component `R1` of the kit board as `R9` and links it to the part `R9`
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_link.py -k linked` commits both and reads the project with `fenolite import`'s reader
- **THEN** the footprint `R9` links to the component `R9` by its unique-id path, and the import reports no `altium.import.pcb-net-conflict` and no unlinked footprint

#### Scenario: A footprint the part does not name
- **WHEN** the test links `R9` to a part whose footprint model is another pattern
- **THEN** the commit is refused with `altium.edit.assertion` naming both patterns, and nothing is written

### Requirement: Bodies and regions of another key set added with their component
`add_component` SHALL compare a body or region record of the source with the document's records of its kind and layer by its 18-byte head and its vertex size, not by its length, so that a body whose property text holds another key set is copied as it is. A body that names a model the document's `Models` storage lacks MUST be copied with that model's entry and stream; a model the document already holds MUST be shared.

#### Scenario: An older body copied
- **GIVEN** an authored source board whose component holds an extruded body with a smaller key set than the bodies of the target board
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_ops.py -k older_body` adds that component
- **THEN** it is written with its body byte for byte but the component index and position, and `fenolite check out.PcbDoc --stages altium.integrity` reports no new finding

#### Scenario: A model body copied with its model
- **GIVEN** an authored source board whose component holds a body that names an embedded model, and a target that holds no model
- **WHEN** the test adds that component
- **THEN** the written document holds one more `Models` entry with that model's id and stream, and no `altium.integrity` model finding

### Requirement: A part added to a project survives Compile and Update PCB
Kit case J34 of `docs/evidence/altium-edit.md` SHALL add one part to the kit project through public operations only: `add_part`, `annotate`, `add_wire`, `add_net_label` and `add_power_port` on the sheet, and `add_component` and `link` on the board. The person running it in Altium Designer MUST find that Compile reports no message the source project lacks, Design » Update PCB proposes no change, the new body shows in 3D, and a save and reopen keeps them. The gates `add_part`, `annotate`, `create` (schematic) and `link` MUST stay off until J34 passes.

#### Scenario: The case is written
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j` runs
- **THEN** it passes with J1 to J34 in order, and J34 names `H-A-EDIT-SCH-ADD` and `H-A-EDIT-LINK`

#### Scenario: The gates are off
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_schematic_add.py -k gates` commits each new operation with the released gates
- **THEN** each is refused with `altium.edit.gate` naming its row, and nothing is written
