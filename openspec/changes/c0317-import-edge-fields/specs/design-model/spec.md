## ADDED Requirements

### Requirement: Optional outline stroke width
`Outline.stroke_width` SHALL be an optional nonnegative integer nanometre value, default `None`, for generated root outline strokes. Canonical JSON MUST omit the default and retain an explicit zero. Existing outlines without the field MUST retain their bytes.

#### Scenario: Default and explicit zero
- **WHEN** outlines with an omitted width and with zero width are serialized and read back
- **THEN** the former omits `stroke_width` and the latter preserves zero
