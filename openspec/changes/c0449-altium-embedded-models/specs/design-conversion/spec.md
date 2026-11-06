## ADDED Requirements

### Requirement: Models of a KiCad board in an Altium target
The direction from KiCad to Altium SHALL embed each STEP model that a board footprint names and the source project holds, as a model body of that footprint's component ("Embedded model bodies" of `altium-pcb-writer`), and SHALL count every `model` child of a board footprint under the kind `model`: written, changed or lost (S-2080; `H-A-BODY-MODEL-PLACE`, `H-K-MODEL-POSE`).
- A child is embedded when its path, with `${KIPRJMOD}` or `$(KIPRJMOD)` read as the source project's folder, or relative to that folder, names a file inside it whose bytes start with `ISO-10303-21;`, its scale is 1 on each axis, and `stepbox.model_box` bounds its geometry. Any other child MUST be one `model` loss with its reason: a file that is not found, a path under another variable or outside the project, a KiCad embedded file (`kicad-embed://`), a file that is no STEP text, a scale other than 1, or a STEP whose geometry the reader cannot bound. A child of a footprint that is not written MUST be lost with that reason. A hidden model MUST be written and counted changed ("Altium has no hidden model"). Without `--altium-bodies extruded` (`bodies="off"`) a child that would be embedded MUST be lost with the reason of the bodies, and `Models` stays empty.
- The pose MUST be the inverse of "Model placement of imported footprints": `MODEL.2D.X/Y` the footprint's placement of the offset (its Y negated on the bottom side), `MODEL.3D.DZ` the offset's Z, and `MODEL.3D.ROTX/Y/Z` the turns of `Rz(−θ')·R`, where `R` is the child's rotation and `θ'` the footprint's rotation on the bottom side and its negation on the top.
- The outline MUST be the rectangle of the placed model's box in the footprint frame, placed as the footprint's pads are, and `STANDOFFHEIGHT` and `OVERALLHEIGHT` its lowest and highest Z.
- `stepbox.model_box(data)` MUST give the box, in nanometres in the model's frame, of the vertex points, the points of each circular or elliptic edge where a coordinate is extreme within the edge's span, and the control points of B-spline edges of the STEP text, each scaled by its context's length unit and moved into the root frame by the item-defined transformations of the representation relationships, the component of each relationship taken from the product structure (`H-G-STEP-BOX`); `None` for a text without such geometry.

#### Scenario: A model goes to Altium and comes back
- **GIVEN** the authored board `tests/data/kicad/convert/roundrect_roundtrip.kicad_pcb` with one footprint on the top turned by 90 degrees and one on the bottom, each naming `${KIPRJMOD}/m.3dshapes/box.step` (a box written by `backends.step` in the test) with an offset, a rise of 0.5 mm and a turn about Z
- **WHEN** `uv run pytest tests/unit/convert/test_embedded_models.py -k roundtrip` converts it to Altium and the document back to KiCad
- **THEN** the document holds one `Models` record whose stream inflates to the file's bytes and two model bodies whose outlines and heights are the placed box within 3 nm; the report's row `model` has `written` 2; and the KiCad board of the way back names a file with the same bytes at each footprint with the source's offset within 3 nm and the same turns

#### Scenario: Models that cannot be embedded
- **GIVEN** footprints that name a missing file, `${KICAD9_3DMODEL_DIR}/x.step`, a `.wrl` file beside the project, a scaled model and `kicad-embed://x.step`
- **WHEN** `uv run pytest tests/unit/convert/test_embedded_models.py -k losses` converts the board to Altium
- **THEN** the row `model` has `lost` 5, each with its own reason, `Models` is empty, and the conversion succeeds

#### Scenario: Public rows keep their models
- **GIVEN** the eight public PCB documents of the corpus manifest
- **WHEN** each is converted to KiCad and back to Altium
- **THEN** every model body of the source comes back as a model body whose model inflates to the same STEP text, at the same `MODEL.2D.X/Y` within 2.54 nm (after the board's offset), on the same side, with the same rotation and rise, and with an outline box and heights within the tolerance that `docs/formats/altium/pcb-bodies.md` records for the box reader (S-2081)
