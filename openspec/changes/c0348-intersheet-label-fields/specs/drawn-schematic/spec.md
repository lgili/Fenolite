## ADDED Requirements

### Requirement: Typed fixed global-label reference field
A drawn global label MAY carry one typed optional intersheet_refs field pose. Its name and native placeholder SHALL be fixed; its pose/font/hide SHALL survive extraction and writing. Wrong kinds, duplicate/custom properties and unsupported values SHALL refuse locally. Absence SHALL preserve legacy default bytes.

#### Scenario: Native reference property round trip
- **GIVEN** one supported global-label Intersheetrefs property
- **WHEN** the drawn/native pipeline round trips it
- **THEN** its exact pose/style/hide and fixed placeholder survive with unchanged full electrical graphs

#### Scenario: Unsupported field is not omitted
- **WHEN** a duplicate, wrong-kind or noncanonical property cannot be represented
- **THEN** the operation refuses before staging rather than hiding it in opaque storage or dropping it

### Requirement: Effective reference text is contextual per instance
The viewer SHALL resolve references from the actual project settings and full sheet instances. It SHALL mirror native show/own-page/short/prefix/suffix rules and use explicit per-instance scenes where text differs. Missing or ambiguous required context SHALL refuse locally; unresolved placeholders SHALL never be displayed as effective text. Disabled/absent fields SHALL preserve legacy scenes.

#### Scenario: One child file appears on several pages
- **GIVEN** a repeated sheet and reference display enabled with own-page disabled
- **WHEN** its instances have different effective page references
- **THEN** each view has the correct explicit instance/page and reference text, without first-instance selection

#### Scenario: Project metadata alone changes
- **WHEN** reference settings change without changing the schematic bytes
- **THEN** the scene cache invalidates and native-equivalent effective reference text is recomputed
