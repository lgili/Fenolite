## ADDED Requirements

### Requirement: Layer stacks of any even count
The PCB document writer SHALL write the copper layers of the model's stack-up, for any even count from 2 to 32 with at most 16 signal layers and 16 plane layers, in the model's order, each as a signal or a plane layer, with the dielectrics between them (thickness, material name, permittivity).
- The layer map MUST assign each copper layer of the model to one Altium layer, and two model layers MUST NOT share one. The map MUST be recorded in `docs/formats/altium/pcb-copper.md`.
- A design without a stack-up MUST get the stack that the writer gave it before this change.
- A stack-up the rules above exclude MUST give `altium.not-lowered` with `where` `stackup` and the default stack; no partial stack is written.

#### Scenario: Six layers read back
- **GIVEN** the authored design `board6` with the copper layers `F.Cu, In1.Cu, In2.Cu, In3.Cu, In4.Cu, B.Cu`, of which `In2.Cu` is a plane
- **WHEN** it is written and the PCB document is read back
- **THEN** the board has six copper layers in that order, `In2.Cu` is a plane, and the dielectric thicknesses equal the design's within 2 nm

#### Scenario: Odd count refused
- **GIVEN** a design whose stack-up has five copper layers
- **WHEN** it is built for Altium
- **THEN** `altium.not-lowered` has `where` `stackup`, and the document holds the default stack

### Requirement: Blind and buried via records
A via whose span is two copper layers of the written stack SHALL be written with its start and end layer, and the board record SHALL hold one drill pair per distinct span.
- A through via MUST be written as before this change.
- A micro via MUST give `altium.via-unsupported` (warning) and MUST NOT be written.

#### Scenario: Three spans
- **GIVEN** `board6` with a through via, a via from `F.Cu` to `In1.Cu` and a via from `In1.Cu` to `In2.Cu`
- **WHEN** the document is written and read back
- **THEN** the three vias have those spans, and the board record holds three drill pairs

### Requirement: Board text records
Board texts SHALL be written as stroke text records with their string, layer, position, height, stroke width, rotation, mirror and justification.
- The string MUST be written in every form that `altium-pcb-reader` ("Text records and wide strings") needs to return it unchanged, non-ASCII characters included.
- A text of another kind (TrueType, barcode) MUST give `altium.not-lowered` with `where` `text/<id>` and the reason `value-unsupported`.

#### Scenario: Accented text
- **GIVEN** a board text `Tensão 5 V` on `F.SilkS`
- **WHEN** the document is written and read back
- **THEN** the text record returns that string, on the top overlay, at the same place within 2 nm

### Requirement: Board graphics and keep-out records
Board graphics on non-copper layers SHALL be written as track, arc and region records without a net; keep-outs SHALL be written as records with the keep-out flag and the restriction set of the model.
- A restriction that the record cannot carry MUST give `altium.not-lowered` with `where` `keepout/<id>` naming the restriction; the keep-out is written with the others.
- The board outline MUST stay as written before this change.

#### Scenario: Keep-out with two restrictions
- **GIVEN** a keep-out that forbids tracks and vias in a rectangle on all copper layers
- **WHEN** the document is written and read back
- **THEN** one keep-out region with those two restrictions is read

### Requirement: Non-plated holes and slots
A non-plated round hole of the board SHALL be written as a free pad record with a hole and no copper, and a slot with the slot fields of the pad record.
- A hole of another shape MUST give `altium.not-lowered` with `where` `hole/<id>`.

#### Scenario: Mounting hole
- **GIVEN** a non-plated hole of 3.2 mm
- **WHEN** the document is written and read back
- **THEN** a free pad with a 3.2 mm hole, plating off and no copper is read

### Requirement: Component body records written
Each `ComponentBody` of a footprint SHALL be written as a component body record with its outline, standoff height and overall height on the layers the layer map gives bodies. No model file is embedded.

#### Scenario: Body height
- **GIVEN** a footprint with a rectangular body of height 2.5 mm
- **WHEN** the document is written and read back
- **THEN** the footprint has one body with that outline and height, within 2 nm

### Requirement: Unpoured polygons are a contract
Every zone SHALL be written as a polygon record in the unpoured state with its net, layer, outline, priority, thermal settings and island removal, and the writer MUST NOT write poured copper for it.
- The build MUST report `altium.zones-unpoured` (info) once, with the count, and the documentation MUST say that the board is repoured in Altium.

#### Scenario: Two polygons
- **GIVEN** `board6` with a `GND` zone on `F.Cu` and one on `B.Cu`
- **WHEN** it is built for Altium
- **THEN** the document holds two unpoured polygons, no region of poured copper, and one `altium.zones-unpoured` with the count 2

### Requirement: Written items are accounted
The writer SHALL return, per kind of model item (footprint, pad, track, arc, via, zone, text, graphic, keep-out, hole, body, rule), the number of items written and the number not lowered, and every item of the board MUST be in exactly one of the two.

#### Scenario: Nothing is lost silently
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py -k accounted` builds `board6` and every example script
- **THEN** for each kind, written plus not lowered equals the number of items in the model, and each not-lowered item has an issue
