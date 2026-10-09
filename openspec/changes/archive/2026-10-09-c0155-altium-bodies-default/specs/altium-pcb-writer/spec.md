## MODIFIED Requirements

### Requirement: Component bodies are reported
The writer SHALL write a component body record for each `ComponentBody` of a footprint of the board that is extruded, has an outline and a height above its standoff, when bodies are asked for (`altium-build`, "Component bodies in an Altium build"), and each other `ComponentBody` SHALL give one `altium.not-lowered` with `where` `body/<id>` that names its height and its reason. No model file is embedded, and no body is written that the model does not hold.
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
