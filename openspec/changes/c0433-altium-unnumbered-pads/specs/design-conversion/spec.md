## MODIFIED Requirements

### Requirement: Conversion report
A `ConversionReport` SHALL hold one row per kind of `fenolite.convert.report.KINDS` that the source holds or the write touches, in table order, each with `kind`, `source`, `written`, `changed`, `lost` and `reasons`. `reasons` MUST count every changed or lost item under its own reason, sorted by count and then by reason; a first reason standing for all MUST NOT be used.

#### Scenario: Reasons are counted apart
- **GIVEN** a KiCad board with one custom pad and two connector pads
- **WHEN** it is converted to Altium with `allow_lossy=True`
- **THEN** the row `pad` has `lost` 1 and `changed` 2, each under its own reason: the custom shape with count 1 and the connector pads with count 2
