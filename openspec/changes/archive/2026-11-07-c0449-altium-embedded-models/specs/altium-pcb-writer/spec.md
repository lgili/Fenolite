## ADDED Requirements

### Requirement: Embedded model bodies
`pcbdoc.write_pcbdoc` SHALL write each `PlacedBody` of `PcbDocSpec.bodies` that carries a model (`PlacedBody.model`, change c0449) as a body record that names an embedded model, and SHALL write the models it names into the `Models` storage (`pcb-bodies.md`, "Written form of a model body"; S-0816, S-2080; `H-A-BODY-MODEL-PLACE`).
- `Models/Data` MUST hold one record per distinct model data, in the order of first use: a 32-bit length and the property text `EMBED=TRUE|MODELSOURCE=Undefined|ID=<id>|ROTX=<x>|ROTY=<y>|ROTZ=<z>|DZ=<dz>|CHECKSUM=0|NAME=<name>` ending in a NUL, with the turns and the rise of the first body that names it (`DZ` as integer file units). `ID` MUST be `pcbrecords.model_id(data)`: a GUID in braces upper-case from the SHA-256 of `fenolite.altium.model:` and the hex SHA-256 of the data. `Models/Header` MUST be the record count as a 32-bit integer, and `Models/<n>` MUST be record `n`'s data deflated by `zlib` at level 6.
- The body record MUST hold the 34 keys of a saved model body, in order: the first 21 keys of an extruded body, `MODELID` (the record's `ID`), `MODEL.CHECKSUM=0`, `MODEL.EMBED=TRUE`, `MODEL.NAME`, `MODEL.2D.X`, `MODEL.2D.Y`, `MODEL.2D.ROTATION=0.000`, `MODEL.3D.ROTX`, `MODEL.3D.ROTY`, `MODEL.3D.ROTZ`, `MODEL.3D.DZ`, `MODEL.MODELTYPE=1` and `MODEL.MODELSOURCE=Undefined`; `BODYCOLOR3D=8421504`; the turns as degrees in [0, 360) with three decimals; `STANDOFFHEIGHT` MAY be negative. Both body storages MUST hold it, as an extruded body's twin.
- A spec without a model body MUST write `Models` with `Header` 0 and an empty `Data`, as before.
- A model whose data is empty, a name that the record cannot hold (empty, or a character other than a letter, a digit, a space or one of `_.()+-`), or an overall height not above the standoff MUST raise `ValueError` naming the body.

#### Scenario: One model named by two bodies
- **GIVEN** a spec with two components whose bodies carry the same STEP data, the second turned by 90 degrees, and a third body that carries other data
- **WHEN** `uv run pytest tests/unit/backends/altium/test_model_bodies.py -k records` writes and reads the document
- **THEN** `Models/Data` holds two records, `Models/Header` is 2, `Models/0` inflates to the first data, the three body records hold `MODEL.MODELTYPE=1` and the `MODELID` of their record, the first record holds the first body's `ROTZ`, and `ComponentBodies6` and `ShapeBasedComponentBodies6` hold three records each

#### Scenario: No model, no entry
- **WHEN** a spec without a model body is written
- **THEN** `Models/Header` is 0, `Models/Data` is empty (`test_model_bodies.py -k records`), and the document's bytes equal those written before change c0449 (`uv run python tools/gen_altium_graduation.py --check`)

## MODIFIED Requirements

### Requirement: Component bodies are reported
The writer SHALL write a component body record for each `ComponentBody` of a footprint of the board that is extruded, has an outline and a height above its standoff, when bodies are asked for (`altium-build`, "Component bodies in an Altium build"), and each other `ComponentBody` SHALL give one `altium.not-lowered` with `where` `body/<id>` that names its height and its reason. A model file is embedded only for a model that the caller gives with its data ("Embedded model bodies", change c0449), and no body is written that the model does not hold.
- `pcbdoc.body_problem(body)` MUST return why a body has no record, or `None`: the kind `model` ("a body that names a 3D model needs the model's data, which the model does not hold"); an outline of fewer than three distinct points ("the body has no outline"); a standoff below the board surface, which no saved extruded body holds; and a height that is not above the standoff in the units of the record. The function reads `kind`, `outline`, `height` and `standoff` of the body as the model holds them and no other field. A body whose footprint is no component of the written document has the reason "its footprint is not written", and a body whose placed outline keeps fewer than three vertices in whole units has no outline: `pcbdoc.place_body` and the lowering decide these two.
- Without the request (`bodies="off"`, which `fenolite build` gives only with `--altium-bodies off` since change c0155) every body MUST be reported, with the reason "component bodies are not written without --altium-bodies extruded" and the body's height, and no record is written: the document is the document of change c0085.
- A written body MUST be one record of "Extruded component body records": the component is the body's footprint; the outline is the body's outline placed by the position and rotation that the document gives the footprint's component, without a mirror (the outline of a footprint instance is held as seen from the top, as its pads are); `STANDOFFHEIGHT` and `OVERALLHEIGHT` are `standoff` and `height`; `bottom` is the footprint's side; the identifier is `name`; `MODELID` is `body_model_id(body.id)`.
- The layer MUST be the Altium id of `ComponentBody.layer` when the layer map gives it a mechanical layer 1 to 16, and otherwise Mechanical 13 for a body of a top footprint and Mechanical 14 for a body of a bottom one.
- A footprint without a body MUST get no record and no issue: no outline is derived from a courtyard or from any other graphic, and no height is assumed.
- Each body MUST be counted once, as written or as not lowered ("Written items are accounted").

#### Scenario: Body height
- **GIVEN** a board footprint with a body of height 2.5 mm
- **WHEN** the design is built for Altium with `--altium-bodies off` (without the option the body is written since change c0155)
- **THEN** `result.pcb.not_lowered` holds `body` with the count 1, and one `altium.not-lowered` with `where` `body/<id>` names 2.5 mm and the option

#### Scenario: Body written
- **GIVEN** the same footprint, placed on the bottom side and turned by 90 degrees, with a rectangle outline
- **WHEN** the design is built with `--altium-bodies extruded` and the document is imported
- **THEN** `result.pcb.written` holds `body` with the count 1 and no issue names the body, both body storages hold one record with `BODYPROJECTION=1` on Mechanical 14 and the index of the footprint's component, and the imported footprint holds one extruded body with the height 2.5 mm and the outline of the model within 2 nm

#### Scenario: Bodies that have no record
- **GIVEN** a footprint with a body of kind `model`, a body without outline and a body whose height equals its standoff, and a second footprint without a body
- **WHEN** the design is built with `--altium-bodies extruded`
- **THEN** `result.pcb.not_lowered.body` is 3, each of the three has one `altium.not-lowered` with its own reason, the second footprint has no issue, and both body storages are empty
