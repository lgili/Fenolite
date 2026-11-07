## ADDED Requirements
### Requirement: Explicitly preserve custom footprint property presentation
Board import SHALL preserve representable custom property poses using typed
field requests for properties declared by that part. Unsupported source poses
SHALL refuse before staging rather than silently lowering presentation.

#### Scenario: A rotated footprint has a hidden custom property
- **WHEN** a source footprint has a custom property whose board angle differs from its body angle
- **THEN** import and fresh build retain its complete typed field pose and value
- **AND** strict geometry and rendering comparisons remain active

#### Scenario: A property pose is not representable by the public API
- **WHEN** a custom property has unsupported size, layer or an inexact board-frame anchor
- **THEN** import refuses with a located error before planning writes

#### Scenario: Unknown field name
- **WHEN** a script requests placement of a field that is neither conventional nor a declared user property
- **THEN** the DSL rejects that request


## Proposed native mirror-ownership scenario

An otherwise exactly representable native custom-property field whose mirror differs from its owner side MAY be retained through the existing native library field representation without adding a public mirror API. Its name/value/geometry/style/visibility and relative mirror SHALL remain exact. The ordinary printable Part property declaration SHALL remain subject to existing conflict checks. Unknown/malformed names, effects or dimensions and other unsupported poses SHALL still refuse before a plan. This proposal remains unimplemented until authored RED and transform evidence are reviewed.
