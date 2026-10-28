## MODIFIED Requirements

### Requirement: Changes of the Altium direction
In the report of the direction from KiCad to Altium, a polygon whose fill is not carried from the source (kind `zone-fill`) and a schematic generated from the circuit (kind `schematic`) SHALL be counted under `changed`, not `lost`, each under its reason. The reason of `zone-fill` MUST be "a polygon is written unpoured; Altium fills it on a repour" with the pour mode `outline`, and "the pour is computed by Fenolite from the written document (experimental)" for a polygon poured with `computed`; a polygon refused with `computed` keeps the first reason.

#### Scenario: Unpoured polygon is a change
- **GIVEN** the routed two-layer KiCad sample, whose board holds a filled zone
- **WHEN** it is converted to Altium with `--altium-pour outline`
- **THEN** the row `zone-fill` has `changed` above 0 and `lost` 0 with the reason of an unpoured polygon, and the row `schematic` has `changed` 1 and `lost` 0

#### Scenario: Computed polygon is a change
- **WHEN** the same sample is converted with `--altium-pour computed`
- **THEN** the row `zone-fill` has `changed` above 0 and `lost` 0 with the reason of a computed pour
