## ADDED Requirements

### Requirement: Local import record origin
A local import SHALL use a distinct `ImportOrigin` with tool, date, source digests and `shippable = false`, and the project-only licence `see source terms`. Existing CC0 library origins MUST retain their existing validation. Imported records SHALL round trip through `parse_record` and `record_text`, with a canonical content checksum for re-import protection.

#### Scenario: A local import is a valid project record
- **WHEN** the authored archive is normalized into its three records
- **THEN** each record parses back equal, retains every source digest and is not shippable

### Requirement: Imported native definitions and volumes
Imported pins and package records SHALL retain normalized geometry and MAY name a canonical native file by basename beside the record. The project build MUST use that native definition and retain optional normalized `component_body` volumes, including height, standoff, outline, model reference and unknown-projection status. The original source path MUST NOT select an output path.

#### Scenario: Altium body retained
- **GIVEN** an authored PcbLib containing one extruded physical body
- **WHEN** its imported package is written, parsed and loaded for a project build
- **THEN** the footprint retains the body's height, outline and projection status
