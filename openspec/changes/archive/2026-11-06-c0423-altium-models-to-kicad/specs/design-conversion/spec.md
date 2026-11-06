## MODIFIED Requirements

### Requirement: Model placement of imported footprints
`FootprintDef.placements` SHALL hold, for a footprint read from another format, each 3D model's path, offset, rotation and scale, and the KiCad footprint writer SHALL write one `model` child per placement.
- An embedded Altium model MUST be extracted beside the derived library and placed so that KiCad's model pose (`H-K-MODEL-POSE`) equals the source's (`H-A-BODY-MODEL-PLACE`), for any turn about X, Y and Z and on either side.
- The board's footprints MUST hold the same placements, and every model file that the library or the board names MUST be written.

#### Scenario: A rotated body
- **GIVEN** an imported top-side footprint whose body names an embedded model turned by 90° about Z and raised by 0.5 mm
- **WHEN** `uv run pytest tests/unit/convert/test_model_placement.py` converts it to KiCad
- **THEN** the library footprint names the extracted `.step` with `(offset (xyz 0 0 0.5))` and `(rotate (xyz 0 0 -90))`, and the file holds the model's bytes

#### Scenario: A model on the bottom turned about X and Y
- **GIVEN** the same footprint on the bottom side, its model turned about X, Y and Z
- **WHEN** it is converted
- **THEN** the model is written, the report lists it under `model` as changed, and KiCad's pose of the written offset and rotation equals the source's within 1 nm and 1 µdeg

## ADDED Requirements

### Requirement: Generated models of imported bodies
A conversion to KiCad SHALL write each imported component body as a STEP model file of Fenolite's own writer, beside the derived library, unless its embedded model carries it, and count it under `body` as changed.
- An extruded body MUST become the prism over its outline from standoff to overall height; a cylinder (`MODEL.MODELTYPE` 2) with a square outline and no turn about X or Y a faceted cylinder; a sphere (3) whose outline side equals its height span a faceted sphere; any other of these the prism over its outline.
- A body of unknown geometry MUST be a `body` loss with its reason; `body` and `model` losses MUST give `convert.lossy` warnings.

#### Scenario: Every body type
- **GIVEN** the authored PCB document of `tests/_altium_models.py` with extruded, cylinder, sphere and embedded-model bodies, its models turned about X, Y and Z on the top and the bottom
- **WHEN** `uv run pytest tests/unit/convert/test_body_models.py -q` converts it to KiCad
- **THEN** the report holds no `body` and no `model` loss, every footprint names its model files, and each generated file is the STEP solid of its body

#### Scenario: KiCad shows the source pose
- **GIVEN** the same conversion
- **WHEN** `uv run pytest tests/kicad/convert/test_altium_model_pose.py -q` exports each component with `kicad-cli pcb export stl` on 9.0.9 and 10.0.6
- **THEN** every model vertex lies within 2 µm of where the source's pose puts it, and every generated body's vertices lie on its shape
